"""Issuer-bound native transports. No fallback, redirects or automatic retries."""
import json
import os
from pathlib import Path
import time
import urllib.request
import urllib.error
from gxp_models.client import PROFILES as GXP_PROFILES, body_for as other_body, parse as other_parse, tokens as other_tokens
from main_experiment.support import save

MAX_TOKENS = 32768
PROFILES = {
    'claude': {'id':'claude','model':'claude-sonnet-5-5','provider':'Anthropic official API','kind':'anthropic','key_env':'ANTHROPIC_API_KEY','endpoint':'https://api.anthropic.com/v1/messages','identity_scope':'Official provider assertion; hosted weights not independently fixed'},
    **GXP_PROFILES,
    'gpt_oss_20b': {'id':'gpt_oss_20b','model':'openai/gpt-oss-20b','provider':'DeepInfra hosted open-weight model','kind':'chat','key_env':'DEEPINFRA_API_KEY','endpoint':'https://api.deepinfra.com/v1/openai/chat/completions','identity_scope':'DeepInfra response assertion; not local execution or authenticated official OpenAI API'},
}

def body_for(profile, prompt, system):
    if profile['kind']=='anthropic':
        return {'model':profile['model'],'max_tokens':MAX_TOKENS,'system':system,'messages':[{'role':'user','content':prompt}]}
    return other_body(profile,prompt,system)

def parse(profile, raw):
    if profile['kind']!='anthropic':return other_parse(profile,raw)
    content=raw.get('content',[])
    if any(x.get('type') not in ('text','thinking','redacted_thinking') for x in content):raise ValueError('Unexpected Anthropic content/tool block')
    text='\n'.join(x['text'] for x in content if x.get('type')=='text')
    return {'model':raw.get('model'),'usage':raw.get('usage',{}),'stop_reason':raw.get('stop_reason'),'text':text.strip(),'normal':raw.get('stop_reason')=='end_turn' and bool(text.strip())}

def tokens(profile, usage):
    if profile['kind']=='anthropic':
        # Anthropic input_tokens excludes both cache-read and cache-created input.
        return {'input':usage.get('input_tokens',0)+usage.get('cache_read_input_tokens',0)+usage.get('cache_creation_input_tokens',0),'output':usage.get('output_tokens',0),'cached_input':usage.get('cache_read_input_tokens',0),'cache_created_input':usage.get('cache_creation_input_tokens',0)}
    value=other_tokens(profile,usage)
    if profile['kind']=='chat' and 'prompt_cache_hit_tokens' not in usage:
        value['cached_input']=usage.get('prompt_tokens_details',{}).get('cached_tokens',0)
    return value

def request(profile,prompt,directory,system,expected_model=None):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=False)
    body=body_for(profile,prompt,system);save(directory/'request.private.json',body)
    key=os.environ[profile['key_env']];headers={'content-type':'application/json'}
    if profile['kind']=='anthropic':headers.update({'x-api-key':key,'anthropic-version':'2023-06-01'})
    elif profile['kind']=='gemini':headers['x-goog-api-key']=key
    else:headers['Authorization']='Bearer '+key
    started=time.time()
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs):return None
    try:
        req=urllib.request.Request(profile['endpoint'],data=json.dumps(body,ensure_ascii=False).encode(),headers=headers)
        with urllib.request.build_opener(NoRedirect()).open(req,timeout=300) as response:raw=json.load(response)
    except Exception as exc:
        failure={'error_type':type(exc).__name__,'http_status':getattr(exc,'code',None),'seconds':time.time()-started}
        if isinstance(exc,urllib.error.HTTPError):(directory/'error-response.private.bin').write_bytes(exc.read())
        save(directory/'provider-failure.json',failure);raise
    save(directory/'response.private.json',raw)
    try:parsed=parse(profile,raw)
    except Exception as exc:
        save(directory/'completion-failure.json',{'error_type':type(exc).__name__});raise
    save(directory/'usage.json',{'model':parsed['model'],'requested_model':profile['model'],'stop_reason':parsed['stop_reason'],'usage':parsed['usage'],'seconds':time.time()-started})
    if not parsed['normal'] or not parsed['model'] or expected_model and parsed['model']!=expected_model:
        save(directory/'completion-failure.json',{'normal':parsed['normal'],'observed_model':parsed['model'],'expected_model':expected_model,'stop_reason':parsed['stop_reason']})
        raise ValueError('Incomplete completion or model identity drift; no automatic retry')
    return parsed['text']
