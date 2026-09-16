"""Admit evaluated offline RAVE and Basic Pitch instruments, preserving other models."""
import hashlib,json,subprocess
from pathlib import Path

RAVE_PIN='c25a03d625840c40cd3a48779ed72f2a1947d7b4'
RAVE_SHA='02458214e23890d6818504319a5b9903eabfe87a524491f6524f453e7f3dbcf0'

def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def prepare(root:Path,germ:Path,evaluation:Path):
    root,germ,evaluation=root.resolve(),germ.resolve(),evaluation.resolve()
    upstream=json.loads((root/'upstream.json').read_text())
    if upstream.get('revision')!=RAVE_PIN or upstream.get('license')!='cc-by-nc-4.0':raise ValueError('Unreviewed RAVE artifact')
    rave=root/'guitar_iil_b2048_r48000_z16.ts'
    if sha(rave)!=RAVE_SHA:raise ValueError('RAVE checkpoint hash mismatch')
    worker=germ/'server/research/worker.py';report=json.loads(evaluation.read_text())
    if report.get('worker_sha256')!=sha(worker):raise ValueError('Worker differs from evaluation')
    expected={(tool,case) for tool in ['rave-guitar','basic-pitch'] for case in ['tone','silence','maximum']}
    if {(r['tool'],r['case']) for r in report['rows']}!=expected or len(report['rows'])!=6 or not all(r['passed'] and 0<r['seconds']<180 for r in report['rows']):raise ValueError('Research evaluation is incomplete')
    if not report.get('files') or any(sha(p)!=d for p,d in report['files'].items()):raise ValueError('Evaluation evidence changed')
    review=json.loads((root/'license-review.json').read_text())
    if review.get('status')!='reviewed' or review.get('rave_profile')!='noncommercial_research':raise ValueError('Research component review missing')
    python=root/'.venv/bin/python'
    site=Path(subprocess.check_output([str(python),'-c','import site;print(site.getsitepackages()[0])'],text=True).strip())
    version=subprocess.check_output([str(python),'-c','from importlib.metadata import version;print(version("basic-pitch"))'],text=True).strip()
    if version!='0.4.0':raise ValueError('Unreviewed Basic Pitch package')
    common=[worker,germ/'server/providers/research_provider.py',germ/'server/research/deployment.py',root/'requirements.lock',root/'upstream.json',root/'README.md',root/'license-review.json',evaluation,python.resolve()]
    common.append(germ/'server/deployment_validation.py')
    packages=['torch','numpy','librosa','soundfile.py','onnxruntime','basic_pitch','pretty_midi','resampy','mir_eval']
    for package in packages:
        path=site/package
        common += [path] if path.is_file() else [p for p in path.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    files={str(p):sha(p) for p in common};tools={}
    for tool,model,profile,license,revision in [('rave-guitar',rave,'noncommercial_research','CC-BY-NC-4.0',RAVE_PIN),('basic-pitch',site/'basic_pitch/saved_models/icassp_2022/nmp.onnx','general','Apache-2.0','basic-pitch-0.4.0:'+sha(site/'basic_pitch/saved_models/icassp_2022/nmp.onnx'))]:
        tools[tool]=dict(status='admitted',tool=tool,python=str(python),model_path=str(model),profile=profile,license=license,revision=revision,files={**files,str(model):sha(model)},evaluation_sha256=sha(evaluation),limits=dict(max_seconds=30,max_job_seconds=180,concurrency=1,offline=True),measurements=[r for r in report['rows'] if r['tool']==tool])
    target=root/'deployments.json';tmp=target.with_suffix('.tmp');tmp.write_text(json.dumps(dict(contract='centaur.research-deployment/v1',tools=tools),indent=2));tmp.chmod(0o600);tmp.replace(target);return target

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('root','germ','evaluation'):parser.add_argument('--'+key,type=Path,required=True)
    args=parser.parse_args();print(prepare(args.root,args.germ,args.evaluation))
