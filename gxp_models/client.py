"""Native, tool-free transports; explicit issuer-bound credentials, no retries."""
import json
import os
from pathlib import Path
import time
import urllib.request
import urllib.error
from main_experiment.support import save

MAX_TOKENS=32768
PROFILES={
 'gemini':{'id':'gemini','model':'gemini-3.1-pro-preview','provider':'Google official Gemini API','kind':'gemini','key_env':'GOOGLE_GENERATIVE_AI_API_KEY','endpoint':'https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-pro-preview:generateContent','upstream_identity_independently_verified':False,'identity_scope':'Official provider model-version assertion; not fixed weights'},
 'deepseek':{'id':'deepseek','model':'deepseek-flash','provider':'DeepSeek official API','kind':'chat','key_env':'DEEPSEEK_API_KEY','endpoint':'https://api.deepseek.com/chat/completions','upstream_identity_independently_verified':False,'identity_scope':'Official provider alias; not fixed weights'},
 'gateway_sol':{'id':'gateway_sol','model':'gpt-6.1-sol','provider':'Third-party xyz.llmapigateway.org gateway; claimed Sol, not authenticated OpenAI','kind':'responses','key_env':'GATEWAY_API_KEY','endpoint':'https://xyz.llmapigateway.org/v1/responses','upstream_identity_independently_verified':False,'identity_scope':'Gateway response model claim only; may not establish upstream model identity'}
}


def body_for(profile,prompt,system):
    if profile['kind']=='gemini':return {'systemInstruction':{'parts':[{'text':system}]},'contents':[{'role':'user','parts':[{'text':prompt}]}],'generationConfig':{'maxOutputTokens':MAX_TOKENS}}
    if profile['kind']=='chat':return {'model':profile['model'],'max_tokens':MAX_TOKENS,'messages':[{'role':'system','content':system},{'role':'user','content':prompt}],'stream':False}
    return {'model':profile['model'],'instructions':system,'input':prompt,'max_output_tokens':MAX_TOKENS,'store':False,'tools':[],'truncation':'disabled'}


def parse(profile,raw):
    if profile['kind']=='gemini':
        candidates=raw.get('candidates',[])
        if len(candidates)!=1:raise ValueError('Expected exactly one Gemini candidate')
        c=candidates[0];reason=c.get('finishReason');model=raw.get('modelVersion');usage=raw.get('usageMetadata',{})
        parts=c.get('content',{}).get('parts',[])
        if any('functionCall' in p for p in parts):raise ValueError('Unexpected Gemini tool call')
        text='\n'.join(p['text'] for p in parts if p.get('text') and not p.get('thought'))
        normal=reason=='STOP' and not raw.get('promptFeedback',{}).get('blockReason')
    elif profile['kind']=='chat':
        choices=raw.get('choices',[])
        if len(choices)!=1:raise ValueError('Expected exactly one chat choice')
        c=choices[0];reason=c.get('finish_reason');model=raw.get('model');usage=raw.get('usage',{});message=c.get('message',{})
        if message.get('tool_calls'):raise ValueError('Unexpected chat tool calls')
        text=message.get('content') or '';normal=reason=='stop'
    else:
        reason=raw.get('status');model=raw.get('model');usage=raw.get('usage',{});output=raw.get('output',[])
        if any(x.get('type') not in ('reasoning','message') for x in output):raise ValueError('Unexpected Responses tool output')
        text='\n'.join(p['text'] for x in output if x.get('type')=='message' for p in x.get('content',[]) if p.get('type')=='output_text')
        normal=reason=='completed' and not raw.get('error') and not raw.get('incomplete_details')
    return {'model':model,'stop_reason':reason,'usage':usage,'normal':bool(normal and text.strip()),'text':text.strip()}


def request(profile,prompt,directory,system,expected_response_model=None):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=False);body=body_for(profile,prompt,system);save(directory/'request.private.json',body)
    headers={'content-type':'application/json'}
    if profile['kind']=='gemini':headers['x-goog-api-key']=os.environ[profile['key_env']]
    else:headers['Authorization']='Bearer '+os.environ[profile['key_env']]
    started=time.time()
    try:
        req=urllib.request.Request(profile['endpoint'],data=json.dumps(body,ensure_ascii=False).encode(),headers=headers)
        # No redirects: never forward a credential to an unapproved recipient.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self,*args,**kwargs):return None
        with urllib.request.build_opener(NoRedirect()).open(req,timeout=300) as response:raw=json.load(response)
    except Exception as exc:
        failure={'type':type(exc).__name__,'status':getattr(exc,'code',None),'seconds':time.time()-started}
        if isinstance(exc,urllib.error.HTTPError):
            data=exc.read();(directory/'error-response.private.bin').write_bytes(data)
            try:
                error=json.loads(data).get('error',{});failure.update(error_code=error.get('code'),error_type=error.get('type'))
            except Exception:pass
        save(directory/'provider-failure.json',failure);raise
    save(directory/'response.private.json',raw)
    try:parsed=parse(profile,raw)
    except Exception as exc:
        save(directory/'completion-failure.json',{'type':type(exc).__name__});raise
    save(directory/'usage.json',{'provider':profile['provider'],'requested_model':profile['model'],'model':parsed['model'],'stop_reason':parsed['stop_reason'],'usage':parsed['usage'],'seconds':time.time()-started})
    if not parsed['normal'] or not parsed['model'] or expected_response_model and parsed['model']!=expected_response_model:
        save(directory/'completion-failure.json',{'normal':parsed['normal'],'observed_model':parsed['model'],'expected_model':expected_response_model,'stop_reason':parsed['stop_reason']});raise ValueError('Unqualified completion or model identity drift; no automatic retry')
    return parsed['text']


def tokens(profile,usage):
    if profile['kind']=='gemini':return {'input':usage.get('promptTokenCount',0),'output':usage.get('candidatesTokenCount',0)+usage.get('thoughtsTokenCount',0),'cached_input':usage.get('cachedContentTokenCount',0),'thinking_output':usage.get('thoughtsTokenCount',0)}
    if profile['kind']=='chat':return {'input':usage.get('prompt_tokens',0),'output':usage.get('completion_tokens',0),'cached_input':usage.get('prompt_cache_hit_tokens',0),'thinking_output':usage.get('completion_tokens_details',{}).get('reasoning_tokens')}
    return {'input':usage.get('input_tokens',0),'output':usage.get('output_tokens',0),'cached_input':usage.get('input_tokens_details',{}).get('cached_tokens',0),'thinking_output':usage.get('output_tokens_details',{}).get('reasoning_tokens')}
