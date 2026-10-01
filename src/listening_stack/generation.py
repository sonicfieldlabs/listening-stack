"""Admit an evaluated, pinned ACE-Step deployment without replacing Stable Audio."""
from pathlib import Path
import hashlib
import json
import subprocess

PIN='19671f406d603126926c1b7e2adc169acbcade22'
RUNTIME='ca1e85fe9430179831e6bc6be790c332190a3866'


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def prepare(root:Path,germ:Path,evaluation:Path):
    root,germ,evaluation=root.resolve(),germ.resolve(),evaluation.resolve()
    upstream=json.loads((root/'upstream.json').read_text())
    if upstream['revision']!=PIN or upstream['runtime_commit']!=RUNTIME:raise ValueError('Unreviewed ACE-Step revision')
    if subprocess.check_output(['git','rev-parse','HEAD'],cwd=root/'upstream',text=True).strip()!=RUNTIME:raise ValueError('Runtime checkout changed')
    worker=germ/'server/ace/worker.py';report=json.loads(evaluation.read_text());rows=report['rows']
    if report['worker_sha256']!=sha(worker):raise ValueError('Worker differs from evaluation')
    if len(rows)!=4 or {r['case'] for r in rows}!={'text','maximum','cover','repaint'} or not all(r['passed'] and r['wall_seconds']<300 for r in rows):raise ValueError('Required generation evaluations did not pass')
    for entry in upstream['files']:
        if entry.get('lfs') and sha(root/'checkpoints'/entry['rfilename'])!=entry['lfs']['sha256']:raise ValueError('Checkpoint hash mismatch')
    review=json.loads((root/'license-review.json').read_text())
    if review.get('status')!='reviewed':raise ValueError('Component review missing')
    python=root/'.venv/bin/python'
    site=Path(subprocess.check_output([str(python),'-c','import site;print(site.getsitepackages()[0])'],text=True).strip())
    files=[worker,germ/'server/providers/ace_step_provider.py',germ/'server/ace/deployment.py',root/'requirements.lock',root/'upstream.json',root/'license-review.json',evaluation,python.resolve()]
    files.append(germ/'server/deployment_validation.py')
    files += [p for p in (root/'checkpoints').rglob('*') if p.is_file() and '.cache' not in p.parts and '__pycache__' not in p.parts]
    for package in ['acestep','mlx','mlx_lm','torch','transformers','diffusers','tokenizers','torchaudio']:
        files += [p for p in (site/package).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    value=dict(status='admitted',model='acestep-v15-turbo',revision=PIN,runtime_commit=RUNTIME,python=str(python),checkpoints=str(root/'checkpoints'),evaluation_sha256=sha(evaluation),limits=dict(max_duration=30,max_job_seconds=300,concurrency=1,planner=False),measurements=rows,files={str(p):sha(p) for p in files})
    target=root/'deployment.json';tmp=target.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2));tmp.chmod(0o600);tmp.replace(target)
    return target


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('root','germ','evaluation'):parser.add_argument('--'+key,type=Path,required=True)
    args=parser.parse_args();print(prepare(args.root,args.germ,args.evaluation))
