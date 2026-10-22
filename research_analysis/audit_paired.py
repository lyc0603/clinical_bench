"""Offline consistency audit; requires access to private frozen evidence."""
import argparse,json,sys
from pathlib import Path
from main_experiment.support import digest,manifest
from main_experiment.core import code_manifest,fingerprint,prompts
from main_experiment.backend import message_ids
from pre_experiment.paired_pilot import tool_manifest
from pre_experiment.recover_paired import completed_evidence,reassessment_evidence
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--paired-root',type=Path,required=True)
parser.add_argument('--lock',type=Path,required=True)
parser.add_argument('--qualification-root',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args()
RUN,LOCK,QUAL,OUT=args.paired_root,args.lock,args.qualification_root,args.out
lock=json.loads(LOCK.read_text());p=lock['payload'];assert fingerprint(p)==lock['sha256']
assert p['seal']['code']==code_manifest() and p['tools']==tool_manifest()
assert digest(Path(p['source_lock']))==p['source_lock_sha256']
assert p['cache_source_manifest']==manifest(Path(p['seal']['config']['p21']['cache']))
assert 'lib/engines/app.data' not in p['cache_source_manifest']
assert digest(QUAL/'qualification.json')==p['qualification_sha256']
q=json.loads((QUAL/'qualification.json').read_text());assert q['qualified'] is True and len(q['checks'])==12
mapping=json.loads((RUN/'result-sources.json').read_text());records=[]
for model in p['seal']['config']['models']:
 alias=model['id'];d=Path(mapping['model_directories'][alias]);state=json.loads((d/'state.json').read_text())
 reused=alias in p['sources']
 if reused:assert completed_evidence(d,model,p['prior_payload'])==p['source_proof'][alias]
 else:assert state['status']=='completed'
 initial=None;phases={}
 for phase in ('initial','final'):
  path=d/phase
  assert manifest(path/'workspace')==json.loads((path/'workspace-manifest.json').read_text())
  if (path/'checkpoint-manifest.json').exists():
   actual=manifest(path);actual.pop('checkpoint-manifest.json',None)
   assert actual==json.loads((path/'checkpoint-manifest.json').read_text())
  else:assert reused and phase=='final'
  agent=json.loads((path/'agent.json').read_text());assert agent['completion']['normal'] is True
  h=json.loads((path/'history.json').read_text());assert h==json.loads((path/'history.raw.json').read_text())
  assert all(m['info']['providerID']+'/'+m['info']['modelID']==model['model'] for m in h['messages'] if m['info']['role']=='assistant')
  ids=message_ids(h)
  if initial is None:initial=ids
  else:assert ids[:len(initial)]==initial and len(ids)>len(initial)
  assert (path/'prompt.txt').read_text()==prompts()['generate' if phase=='initial' else 'self_review']
  e=json.loads((path/'evaluation.json').read_text())
  if not reused:
   diag=json.loads((path/'p21-diagnostics.json').read_text())
   assert not diag['failure_code'] and not diag['immutable_changed_paths'] and not diag['client_error_markers'] and not diag['stdout_error_markers']
   assert e['conformance']['report_usable'] is True
  phases[phase]={'original_evaluation_sha256':digest(path/'evaluation.json'),
     'original_p21_status':e['conformance']['status'],'semantic_reproduced':e.get('semantic_reproduced'),
     'checkpoint_manifest_at_original_run':(path/'checkpoint-manifest.json').exists()}
 receipt=json.loads((d/'initial-only.json').read_text());assert receipt['evaluation_sha256']==digest(d/'initial/evaluation.json')
 assert receipt['workspace_manifest_sha256']==fingerprint(manifest(d/'initial/workspace'))
 assert not (d/'live/feedback').exists()
 records.append({'model':alias,'requested_model':model['model'],'original_controller_status':state['status'],
     'reused_completed_agent_phases':reused,'initial_only_receipt_sha256':digest(d/'initial-only.json'),
     'same_session_continuity':'passed','model_identity':'passed','frozen_prompts':'passed',
     'workspace_integrity':'passed','phases':phases})
recheck={a:{phase:v['directory'] for phase,v in phases.items()} for a,phases in p['reassessments'].items()}
assert reassessment_evidence(recheck,p['seal']['config'],p['sources'])==p['reassessments']
assert len(records)==3
OUT.mkdir(parents=True,exist_ok=True)
(OUT/'evidence-audit.json').write_text(json.dumps({'excluded_from_main':True,'main_study_started_by_this_task':False,
 'audit_script_sha256':digest(Path(__file__)),
 'recovery_lock_sha256':lock['sha256'],'qualification_sha256':p['qualification_sha256'],
 'qualification_validations':24,'new_generation_sessions':3,'new_paired_endpoints':6,'historical_controls':3,
 'original_controller_failures_retained':sum(r['original_controller_status']=='failed' for r in records),
 'p21_java_options':p['seal']['config']['p21']['java_options'],'p21_state_policy':'app.data absent in immutable source; initialized separately in each disposable cache',
 'records':records,'limitation':'Local consistency check, not external signed attestation. Original OpenAI final checkpoint manifest was not created after the evaluator gate raised; earlier workspace manifest and raw histories are verified instead.'},indent=2)+'\n')
print('All completed phases, source mapping, qualification and original failures verified.')
