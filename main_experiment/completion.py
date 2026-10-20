"""Completion is current-turn session evidence, not the last stdout string."""
import json
import math
from pathlib import Path

from main_experiment.support import digest

POLICY=Path(__file__).with_name('completion-policy.json')


def policy():
    return json.loads(POLICY.read_text())


def normalize(reason):
    return reason.strip().lower().replace('_','-') if isinstance(reason,str) else None


def assess(history, before_ids, session, provider, execution):
    """Fail closed on unrecognized schemas/reasons, but tolerate omitted stdout finish."""
    result={'normal':False,'provider':provider,'policy_sha256':digest(POLICY),
            'event_finish_reasons':execution.get('finish_reasons',[]),
            'source':'exported_current_turn'}
    def reject(reason):
        result['reason']=reason
        return result
    if execution.get('exit_code')!=0 or execution.get('timed_out') or execution.get('provider_errors'):
        return reject('process_or_provider_failure')
    allowed=policy()['normal_reasons'].get(provider)
    if not allowed:
        return reject('unqualified_provider')
    if execution.get('session_ids')!=[session]:
        return reject('session_mismatch')
    root_id=(history.get('info') or {}).get('id')
    if root_id is not None and root_id!=session:
        return reject('export_session_mismatch')
    messages=history.get('messages',[])
    ids=[m.get('info',{}).get('id') for m in messages]
    if not ids or not all(ids) or len(set(ids))!=len(ids):
        return reject('invalid_export_message_ids')
    if ids[:len(before_ids)]!=list(before_ids) or len(ids)<=len(before_ids):
        return reject('no_new_turn_or_history_changed')
    new=messages[len(before_ids):]
    if any(m.get('info',{}).get('sessionID',session)!=session for m in new):
        return reject('message_session_mismatch')
    if any(m.get('info',{}).get('error') for m in new):
        return reject('exported_message_error')
    users=[m for m in new if m.get('info',{}).get('role')=='user']
    if not users or new[-1].get('info',{}).get('role')!='assistant':
        return reject('missing_current_user_or_final_assistant')
    final=new[-1];info=final['info']
    result.update(final_message_id=info['id'],user_message_id=users[-1]['info']['id'])
    if info.get('parentID')!=users[-1]['info']['id']:
        return reject('final_assistant_not_bound_to_current_user')
    completed=(info.get('time') or {}).get('completed')
    if not isinstance(completed,(int,float)) or isinstance(completed,bool) or not math.isfinite(completed) or completed<=0:
        return reject('assistant_not_completed')
    for message in new:
        for part in message.get('parts',[]):
            if part.get('type')=='tool' and (part.get('state') or {}).get('status') not in ('completed','error'):
                return reject('pending_or_unrecognized_tool_state')
    finish_parts=[p for p in final.get('parts',[]) if p.get('type')=='step-finish']
    finishes=[p.get('reason') for p in finish_parts]
    exported=[]
    if info.get('finish') is not None:
        exported.append(info['finish'])
    if finishes:
        exported.append(finishes[-1])
    result['export_finish_reasons']=exported
    if not exported or any(normalize(r) not in allowed for r in exported):
        return reject('unrecognized_or_non_normal_export_finish')
    # Earlier tool-calls steps are not final-turn completion. Check only stdout
    # parts bound to this assistant, or an unbound last part conservatively.
    steps=execution.get('steps',[])
    final_part_id=finish_parts[-1].get('id') if finish_parts else None
    if final_part_id:
        export_part_ids={p.get('id') for p in finish_parts}
        if any(p.get('messageID')==info['id'] and p.get('id') and
               p['id'] not in export_part_ids for p in steps):
            return reject('export_event_part_mismatch')
        relevant=[p for p in steps if p.get('id')==final_part_id]
    else:
        relevant=[p for p in steps if p.get('messageID')==info['id']]
    if not final_part_id and not relevant and steps and not steps[-1].get('messageID'):
        relevant=[steps[-1]]
    final_event=relevant[-1].get('reason') if relevant else None
    result['final_event_reason']=final_event
    if relevant and normalize(final_event) not in allowed:
        return reject('conflicting_or_unknown_final_event')
    result.update(normal=True,reason='completed_current_turn',completed_unix_ms=completed,
                  stdout_finish_missing=not bool(relevant),
                  normalized_finish=normalize(exported[-1]),
                  export_usage=[{'message_id':m['info']['id'],'tokens':m['info'].get('tokens'),
                                 'cost':m['info'].get('cost')} for m in new
                                if m.get('info',{}).get('role')=='assistant'])
    return result


def validate_smoke_evidence(evidence,model):
    provider=model['model'].split('/',1)[0]
    if set(evidence)!= {'initial','final'}:
        raise ValueError('Both smoke phases require completion evidence: '+model['id'])
    for item in evidence.values():
        if (item.get('normal') is not True or item.get('provider')!=provider or
                item.get('policy_sha256')!=digest(POLICY) or
                item.get('normalized_finish') not in policy()['normal_reasons'][provider] or
                not item.get('final_message_id') or not item.get('user_message_id')):
            raise ValueError('Unqualified smoke completion evidence: '+model['id'])


def smoke_evidence(directory,model):
    evidence={phase:json.loads((directory/phase/'agent.json').read_text())['completion']
              for phase in ('initial','final')}
    validate_smoke_evidence(evidence,model)
    return evidence
