"""Provision an already-downloaded CLAP bundle after local evaluation."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

REVISION='ada0c23a36c4e8582805bb38fec3905903f18b41'

def digest(path):
    with open(path,'rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def identity(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def prepare(root,akousmata,evaluation):
    root=Path(root).resolve();model=root/'model';worker=Path(akousmata).resolve()/'akousmata_app/acoustic/worker.py'
    receipt=Path(evaluation).resolve();report=json.loads(receipt.read_text());upstream=json.loads((root/'upstream.json').read_text())
    if upstream['sha']!=REVISION:raise ValueError('Unexpected CLAP revision')
    expected=next(row['lfs']['sha256'] for row in upstream['siblings'] if row['rfilename']=='pytorch_model.bin')
    if digest(model/'pytorch_model.bin')!=expected:raise ValueError('Weights do not match the pinned upstream artifact')
    if report['status']!='passed' or report['worker_sha256']!=digest(worker) or report['model_sha256']!=expected or report['max_tested_seconds']<10:
        raise ValueError('Current worker and weights need passing local evaluation')
    python=root/'.venv/bin/python';lock=root/'requirements.lock'
    if not lock.exists():raise ValueError('Freeze the isolated environment before admission')
    artifacts={str(p):digest(p) for p in [worker,python.resolve(),receipt,lock,*[p for p in model.iterdir() if p.is_file()]]}
    # Pin the actual Transformers CLAP implementation as well as its version.
    code=Path(subprocess.check_output([str(python),'-c','import importlib.util;print(importlib.util.find_spec("transformers").submodule_search_locations[0])'],text=True).strip())
    for p in (code/'models/clap').glob('*.py'):artifacts[str(p)]=digest(p)
    preprocessing=identity({Path(k).name:v for k,v in artifacts.items() if k.endswith('.json') and Path(k).parent==model}|{'worker':digest(worker),'environment':digest(lock)})
    space=dict(model='laion/larger_clap_general',revision=REVISION,preprocessing_sha256=preprocessing,dimensions=512,pooling='CLAP projected L2-normalized; max segment cosine for sound queries',metric='cosine')
    manifest=dict(contract='earworm/model-deployment/v1',id='clap-'+REVISION[:10]+'-'+preprocessing[:10],owner='akousmata',adapter='clap-local',capabilities=['embed_audio','embed_text'],
        components=[dict(id='laion/larger_clap_general',revision=REVISION,sha256=expected)],runtime_revision=digest(worker),license_review=digest(model/'README.md'),validation_receipt=digest(receipt),enabled=True,provisioned=True,max_input_seconds=10,max_output_seconds=0,measured_peak_memory_mib=report['peak_memory_mib'])
    value=dict(manifest=manifest,space=space,artifacts=artifacts,model=str(model),worker=str(worker),python=str(python),receipt=str(receipt),lock=str(lock))
    target=root/'deployment.json';temp=target.with_suffix('.tmp');temp.write_text(json.dumps(value,indent=2));temp.chmod(0o600);temp.replace(target)
    return target

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',required=True);parser.add_argument('--akousmata',required=True);parser.add_argument('--evaluation',required=True);args=parser.parse_args()
    print(prepare(args.root,args.akousmata,args.evaluation))
