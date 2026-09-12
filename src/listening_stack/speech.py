"""Admit a provisioned, evaluated local speech bundle without altering P1 deployments."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess

PINS = {
    'asr': ('mlx-community/Qwen3-ASR-0.6B-4bit', '313d850181767edf09f00a9c289becca70e58cd0'),
    'aligner': ('mlx-community/Qwen3-ForcedAligner-0.6B-4bit', '2f652af86ae0c73fe189b9429225c908ce4bf020'),
}


HASHES = {'asr': '70c7e67e588062adce4f10796e47ad42ead51c6671eda61a0987eae38ca95ddf', 'aligner': '630bcfbaccf2635940bbe94ad5475fd60ee4f47259b62d36deff806d60bcf24c'}

def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''): digest.update(block)
    return digest.hexdigest()


def prepare(root: Path, oida: Path, receipt: Path):
    root, oida, receipt = root.resolve(), oida.resolve(), receipt.resolve()
    worker = oida/'oida/specialists/speech_worker.py'
    python = root/'.venv/bin/python'
    checkpoint = root/'asr/model.safetensors'
    license = root/'license-review.json'
    lock = root/'requirements.lock'
    pins = json.loads((root/'upstream.json').read_text())
    if pins != {key:list(value) for key,value in PINS.items()}:
        raise ValueError('Speech release pins differ from reviewed artifacts')
    if any(sha(root/kind/'model.safetensors') != digest for kind,digest in HASHES.items()):
        raise ValueError('Model weights differ from pinned upstream hashes')
    report = json.loads(receipt.read_text())
    if (report.get('status') != 'passed' or report.get('task') != 'transcribe'
        or report.get('worker_sha256') != sha(worker) or report.get('checkpoint_sha256') != sha(checkpoint)
        or report.get('max_input_seconds') != 60 or not report.get('rows')
        or any(not row.get('passed') for row in report['rows'])):
        raise ValueError('Speech evaluation is incomplete or belongs to different artifacts')
    required = {'human-0','human-1','human-2','code-switch','long-60','silence','silence-ungated','tone','rain','spanish-ungated'}
    if not required.issubset({r['name'] for r in report['rows']}):
        raise ValueError('Required speech acceptance cases missing')
    review = json.loads(license.read_text())
    if review.get('status') != 'reviewed' or not review.get('sources'):
        raise ValueError('Missing component license review')
    site = Path(subprocess.check_output([str(python),'-c','import site; print(site.getsitepackages()[0])'],text=True).strip())
    paths = [worker, oida/'oida/specialists/speech_validation.py', receipt, license, lock, root/'upstream.json', python.resolve()]
    paths += list(root.glob('license-source-*.txt'))
    for kind in PINS:
        paths += [p for p in (root/kind).rglob('*') if p.is_file() and not p.name.startswith('.')]
    for name in ['mlx_audio','mlx','silero_vad','transformers','tokenizers']:
        paths += [p for p in (site/name).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    files = {str(p):sha(p) for p in paths}
    components = [dict(id=PINS[kind][0], revision=PINS[kind][1], sha256=sha(root/kind/'model.safetensors')) for kind in PINS]
    # Detector code and weights are included in the verified file inventory.
    manifest = dict(contract='earworm/model-deployment/v1', id='qwen3-asr-06b-'+sha(checkpoint)[:12], owner='oida',adapter='qwen3-asr-06b',capabilities=['transcribe'],components=components,runtime_revision=sha(worker),license_review=sha(license),validation_receipt=sha(receipt),enabled=True,provisioned=True,max_input_seconds=60,max_output_seconds=0,measured_peak_memory_mib=report['peak_memory_mib'])
    entry = dict(task='transcribe',manifest=manifest,files=files,python=str(python),repository=str(root),checkpoint=str(checkpoint),receipt=str(receipt),license=str(license),environment_lock=str(lock))
    target = root/'deployments.json';temporary=target.with_suffix('.tmp')
    temporary.write_text(json.dumps(dict(deployments=[entry]),indent=2)+'\n');temporary.chmod(0o600);temporary.replace(target)
    return target


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--oida',type=Path,required=True)
    parser.add_argument('--receipt',type=Path,required=True)
    args=parser.parse_args();print(prepare(args.root,args.oida,args.receipt))
