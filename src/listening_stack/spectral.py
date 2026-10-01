"""Validate a separately provisioned optional spectral environment; never run at startup.

Provision Python 3.12 with numpy==1.26.4, scipy==1.14.1, nsgt==0.19,
kymatio==0.3.0. NSGT needs NumPy installed before --no-build-isolation.
This command writes an opt-in admission file; it does not enable a daemon.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(python, worker, destination):
    python, worker, destination = Path(python).absolute(), Path(worker).resolve(), Path(destination).absolute()
    probe = '''
import importlib.util, importlib.metadata as md, json, pathlib, sys
import numpy as np
expected = {'numpy':'1.26.4', 'scipy':'1.14.1', 'nsgt':'0.19', 'kymatio':'0.3.0'}
assert all(md.version(k) == v for k,v in expected.items()), 'Unqualified package versions'
import hashlib
# NSGT 0.19 clips an integer array against floating infinity, rejected by NumPy.
# Replacing that unbounded upper clip with integer maximum is equivalent.
path=pathlib.Path(md.distribution('nsgt').locate_file('nsgt/nsgfwin_sl.py'))
source=path.read_text()
old='np.clip(M, min_win, np.inf, out=M)'
new='np.maximum(M, min_win, out=M) # Oida qualified integer-bound compatibility'
if old in source:
 assert hashlib.sha256(path.read_bytes()).hexdigest() == '67d7d692622f4cd60cfd16fa7309d6a72100986f7384cd28e6152b8311be5c80', 'Unknown upstream NSGT source'
 path.write_text(source.replace(old,new))
assert new in path.read_text(), 'Missing qualified NSGT compatibility fix'
assert hashlib.sha256(path.read_bytes()).hexdigest() == '96fadddc8ffeb09723fd0a7fbfafe646028a879af4934eb54b8e4a062bf04766', 'Qualified NSGT source changed'
spec=importlib.util.spec_from_file_location('worker',sys.argv[1]); module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
rows=[]
for task in ('nsgt','kymatio'):
 for n in (4096,16384):
  for rate in (48000,96000,192000):
   for value in ('silence','tone'):
    x=np.zeros((n,2)) if value=='silence' else np.column_stack([np.sin(2*np.pi*1000*np.arange(n)/rate),np.cos(2*np.pi*3000*np.arange(n)/rate)])
    y,meta=module.compute(task,x,rate)
    assert y.shape[0]==2 and np.isfinite(y).all()
    assert (np.max(np.abs(y)) == 0) if value=='silence' else (np.max(np.abs(y)) > 0)
    rows.append(dict(task=task, samples=n, rate=rate, fixture=value, output_bytes=y.nbytes))
files=[]
for name in expected:
 dist=md.distribution(name)
 files.extend(str(dist.locate_file(f).resolve()) for f in dist.files if (str(f).endswith(('.py','.so','.dylib','METADATA')) or 'LICENSE' in str(f).upper() or 'COPYING' in str(f).upper()) and dist.locate_file(f).is_file())
print(json.dumps(dict(rows=rows,files=sorted(set(files)))))
'''
    with tempfile.TemporaryDirectory(prefix='spectral-validation-') as root:
        script = Path(root)/'probe.py'
        script.write_text(probe)
        completed = subprocess.run([str(python), '-I', str(script), str(worker)], capture_output=True,
                                   text=True, check=True, timeout=60)
    result = json.loads(completed.stdout)
    value = dict(contract='oida/spectral-workers/v1', enabled=True, python=str(python),
                 python_sha256=sha(python.resolve()), worker_sha256=sha(worker),
                 files={path: sha(path) for path in result['files']},
                 receipt=dict(status='passed', tasks=['nsgt','kymatio'], fixtures=result['rows'],
                              nsgt_patch='0.19 integer min-window maximum replaces clip against float infinity; exact source hash guarded',
                              scope='Synthetic numeric integration; no physical or domain accuracy claim'))
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2)+'\n')
    temporary.chmod(0o600)
    temporary.replace(destination)
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python', required=True, type=Path)
    parser.add_argument('--worker', required=True, type=Path)
    parser.add_argument('--destination', required=True, type=Path)
    args = parser.parse_args()
    print(prepare(args.python, args.worker, args.destination))
