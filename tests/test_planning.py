import json
from pathlib import Path
import pytest
from listening_stack.planning import prepare, sha


def test_planning_requires_evaluation_for_exact_worker(tmp_path):
    worker=tmp_path/'oida/oida/reasoning/local/worker.py'
    worker.parent.mkdir(parents=True);worker.write_text('new worker')
    receipt=tmp_path/'evaluation.json';receipt.write_text(json.dumps({'worker_sha256':'0'*64}))
    with pytest.raises(ValueError,match='another worker'):
        prepare(tmp_path,tmp_path/'oida',receipt)


def test_planning_rejects_unreviewed_checkpoint(tmp_path):
    worker=tmp_path/'oida/oida/reasoning/local/worker.py'
    worker.parent.mkdir(parents=True);worker.write_text('worker')
    receipt=tmp_path/'evaluation.json';receipt.write_text(json.dumps({'worker_sha256':sha(worker),'rows':[]}))
    (tmp_path/'upstream.json').write_text(json.dumps([{'id':'qwen','revision':'unreviewed'}]))
    with pytest.raises(ValueError,match='Unreviewed'):
        prepare(tmp_path,tmp_path/'oida',receipt)
