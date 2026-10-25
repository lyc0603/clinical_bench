"""Nonclinical readiness only: no study inputs, model outcomes or P21 calls."""
import argparse
import json
import os
from pathlib import Path
import subprocess

from main_experiment.backend import capture
from main_experiment.core import code_manifest,private_path
from main_experiment.support import digest,load_env,manifest,save
from .deepinfra_backend import MODELS,COMPLETION,DeepInfraSession,settings

HERE=Path(__file__).resolve().parent

def tools():
    return {p.name:digest(p) for p in sorted(HERE.iterdir()) if p.suffix in ('.py','.md')}

def transport(out,image):
    out.mkdir(parents=True,exist_ok=False)
    records=[]
    for model in MODELS:
        c=settings(model)
        c.update(enabled_providers=['deepinfra'],permission={'*':'allow','webfetch':'deny','websearch':'deny','task':'deny'})
        p=subprocess.run(['docker','run','--rm','--network','none',
            '-e','PROBE_MODEL='+model['model'],'-e','PROBE_CONFIG='+json.dumps(c),
            '-v',str(HERE/'deepinfra_transport.py')+':/workspace/probe.py:ro',
            image,'python','/workspace/probe.py'],capture_output=True,text=True,timeout=120)
        if p.returncode:
            save(out/(model['id']+'.json'),{'exit_code':p.returncode,'stderr':p.stderr})
            raise RuntimeError('Offline transport process failure')
        d=json.loads(p.stdout);save(out/(model['id']+'.json'),d)
        requests=d['requests']
        qualified=d['exit_code']==0 and len(requests)==1
        if qualified:
            r=requests[0]
            qualified=(r['path']=='/v1/openai/chat/completions' and r['model']==model['model'].split('/',1)[1]
                and r['temperature']==1 and r['reasoning_effort']=='medium'
                and r['max_tokens']==16384 and r['stream'] is True and r['tool_count']>0)
        records.append({'model':model['id'],'qualified':qualified,'requests':requests})
    save(out/'qualification.json',{'qualified':all(r['qualified'] for r in records),
        'scope':'offline mock only; dummy credentials; network none','tools':tools(),'records':records})
    if not all(r['qualified'] for r in records):
        raise RuntimeError('Offline request parameters did not match declared settings')

def smoke(out,image,transport_root,ripgrep):
    receipt=json.loads((transport_root/'qualification.json').read_text())
    if not receipt['qualified'] or receipt['tools']!=tools():
        raise ValueError('Current passing offline transport evidence required')
    if not os.environ.get('DEEPINFRA_API_KEY'):
        raise ValueError('Missing DEEPINFRA_API_KEY')
    out.mkdir(parents=True,exist_ok=False)
    original_code=code_manifest();original_tools=tools()
    runtime={'image':capture(['docker','image','inspect','--format','{{.Id}}',image]),
        'opencode':capture(['docker','run','--rm','--network','none',image,'opencode','--version'])}
    records=[]
    for model in MODELS:
        directory=out/model['id'];directory.mkdir()
        empty=directory/'empty-inputs';empty.mkdir()
        c={'inputs':str(empty.resolve()),'cpus':4,'memory':'8g','phase_seconds':300,
           'tool_ripgrep':str(ripgrep.resolve()),'tool_ripgrep_sha256':digest(ripgrep)}
        a=DeepInfraSession(c,model,directory,runtime['image'])
        record={'model':model,'qualified':False,'clinical_inputs_transmitted':False}
        try:
            a.start();sid=None;phases={}
            prompts=[
                'This is a nonclinical connection test. Use bash to write ONLY cedar-12345 to smoke-marker.txt. Then use glob to find smoke-marker.txt in the current directory, and use grep to find cedar in that file. Do not inspect any other files or environment variables. Then reply READY.',
                'Continue this same test session. Use the read tool to read smoke-marker.txt. Do not inspect any other files or environment variables. Then reply READY2.'
            ]
            for name,text in zip(('initial','continuation'),prompts):
                phase=directory/name;phase.mkdir();(phase/'prompt.txt').write_text(text)
                sid,h=a.phase(text,phase,sid)
                agent=json.loads((phase/'agent.json').read_text())
                if not agent.get('tool_calls') or agent.get('tool_failures'):
                    raise RuntimeError('Readiness requires successful tool execution in both turns')
                names={p.get('tool') for m in h['messages'] for p in m.get('parts',[])
                       if p.get('type')=='tool' and p.get('state',{}).get('status')=='completed'}
                if name=='initial' and not {'bash','glob','grep'}<=names:
                    raise RuntimeError('Readiness must exercise bash, glob and grep')
                if name=='continuation' and 'read' not in names:
                    raise RuntimeError('Readiness must exercise read tool')
                if (a.workspace/'smoke-marker.txt').read_text().strip()!='cedar-12345':
                    raise RuntimeError('Tool output did not reproduce the requested marker')
                usage=agent['completion'].get('export_usage',[])
                if not usage or any(not isinstance(x.get('tokens'),dict) or x.get('cost') is None for x in usage):
                    raise RuntimeError('Missing native usage telemetry')
                phases[name]={'normal_completion':agent['completion']['normal'],
                    'finish':agent['completion']['normalized_finish'],
                    'tool_calls':agent['tool_calls'],'tool_failures':agent['tool_failures'],
                    'cost_estimate_usd':sum(x['cost'] for x in usage),
                    'agent_sha256':digest(phase/'agent.json')}
            record.update(qualified=True,same_session_continuation=True,phases=phases,
                marker_verified=True,settings=settings(model))
        except Exception as exc:
            record.update(error_type=type(exc).__name__,reason=str(exc))
        finally:
            a.stop()
            save(directory/'qualification.json',record)
        records.append(record)
    unchanged=original_code==code_manifest() and original_tools==tools()
    save(out/'qualification.json',{'scope':'nonclinical readiness; no main or clinical experiment started',
        'qualified':unchanged and all(r['qualified'] for r in records),
        'clinical_inputs_transmitted':False,'main_study_started':False,
        'tools':original_tools,'main_code':original_code,'runtime':runtime,
        'transport_receipt_sha256':digest(transport_root/'qualification.json'),
        'tool_support':{'ripgrep_sha256':digest(ripgrep)},
        'completion_policy':COMPLETION,'records':records,'evidence':manifest(out),
        'limitations':'Short readiness probes only; long context and clinical task completion untested. Smoke-only 300-second turn timeout does not set an experiment time cap. Telemetry estimates are not invoices.'})
    if not unchanged or not all(r['qualified'] for r in records):
        raise SystemExit('DeepInfra readiness failed; original attempts retained; no clinical generation.')
    print('Both DeepInfra models passed nonclinical tool use, continuation and completion checks.')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('transport','smoke'))
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--env-file',type=Path,required=True)
    p.add_argument('--transport',type=Path)
    p.add_argument('--ripgrep',type=Path)
    p.add_argument('--image',default='adam-experiment:main')
    p.add_argument('--execute',action='store_true')
    a=p.parse_args();load_env(a.env_file)
    out=private_path(a.out)
    if a.action=='transport':
        transport(out,a.image)
        print('Both offline DeepInfra transport captures passed.')
    else:
        if not a.execute or not a.transport or not a.ripgrep:
            p.error('smoke requires --execute, --transport and --ripgrep')
        smoke(out,a.image,a.transport,a.ripgrep)

if __name__=='__main__':
    main()
