import json
from pathlib import Path
import pytest
from listening_stack import generation


def test_generation_rejects_unreviewed_artifacts(tmp_path):
    (tmp_path/'upstream.json').write_text(json.dumps({'revision':'unreviewed','runtime_commit':'x'}))
    with pytest.raises(ValueError,match='Unreviewed'):
        generation.prepare(tmp_path,tmp_path,tmp_path/'receipt.json')


def test_generation_needs_all_runtime_cases_and_exact_worker(tmp_path,monkeypatch):
    (tmp_path/'upstream.json').write_text(json.dumps({'revision':generation.PIN,'runtime_commit':generation.RUNTIME}))
    monkeypatch.setattr(generation.subprocess,'check_output',lambda *a,**k:generation.RUNTIME)
    worker=tmp_path/'server/ace/worker.py';worker.parent.mkdir(parents=True);worker.write_text('worker')
    receipt=tmp_path/'receipt.json';receipt.write_text(json.dumps({'worker_sha256':'old','rows':[]}))
    with pytest.raises(ValueError,match='Worker differs'):
        generation.prepare(tmp_path,tmp_path,receipt)
    receipt.write_text(json.dumps({'worker_sha256':generation.sha(worker),'rows':[]}))
    with pytest.raises(ValueError,match='evaluations did not pass'):
        generation.prepare(tmp_path,tmp_path,receipt)
