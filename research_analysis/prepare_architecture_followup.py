"""Freeze a new attempt from verified input-only source; never copy model outputs."""
import argparse
import json
from pathlib import Path
import shutil
from main_experiment.support import load_env,save,manifest
from main_experiment.core import fingerprint
from ai431_full.client import PROFILES as AI_PROFILES
from ai431_full.run import prepare as prepare_ai
from gxp_models.client import PROFILES as GXP_PROFILES
from gxp_fresh.run import payload
from gxp_full.plan import make_plan


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--architecture',choices=['gxp','ai431'],required=True);p.add_argument('--root',type=Path,required=True);p.add_argument('--source',type=Path,required=True);p.add_argument('--readiness',type=Path,required=True);p.add_argument('--qualification',type=Path,required=True);p.add_argument('--env-file',type=Path,required=True)
    a=p.parse_args();load_env(a.env_file)
    original=json.loads((a.source/'freeze.json').read_text());receipt=json.loads(a.readiness.read_text());profile=receipt['profile']
    if fingerprint(original['payload'])!=original['sha256'] or manifest(a.source/'inputs')!=original['payload']['inputs']:raise ValueError('Source freeze/input drift')
    profiles=AI_PROFILES if a.architecture=='ai431' else GXP_PROFILES
    if profile['id'] not in ('gemini','openai_official','gpt_oss_20b','llama_scout') or profiles[profile['id']]!=profile or not receipt['qualified']:raise ValueError('Exact approved provider readiness required; no gateway')
    if a.architecture=='ai431':prepare_ai(a.root,a.source,a.readiness,a.qualification);return
    a.root.mkdir(parents=True,exist_ok=False);shutil.copytree(a.source/'inputs',a.root/'inputs')
    shutil.copy2(a.source/'source-schemas.json',a.root/'source-schemas.json')
    base=json.loads((a.source/'base-config.private.json').read_text());base['inputs']=str(a.root/'inputs');save(a.root/'base-config.private.json',base)
    shutil.copy2(a.qualification,a.root/'qualification.json');shutil.copy2(a.readiness,a.root/'provider-readiness.json')
    save(a.root/'provider-profile.json',{**profile,'response_model':receipt['response_model']})
    save(a.root/'dag.json',make_plan(json.loads((a.root/'inputs/specifications.json').read_text())))
    save(a.root/'source-provenance.json',{'source_freeze_sha256':original['sha256'],'identical_input_manifest':manifest(a.root/'inputs')==original['payload']['inputs'],'uses_prior_programs_or_results':False})
    frozen=payload(a.root);save(a.root/'freeze.json',{'payload':frozen,'sha256':fingerprint(frozen)})
    print('Frozen new zero-reuse',a.architecture,'attempt',profile['id'])

if __name__=='__main__':main()
