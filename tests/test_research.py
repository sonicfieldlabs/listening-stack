import json
from pathlib import Path
import pytest
from listening_stack import research


def test_admission_rejects_changed_worker_and_missing_cases(tmp_path,monkeypatch):
    root=tmp_path/'research';root.mkdir();germ=tmp_path/'germ';worker=germ/'server/research/worker.py';worker.parent.mkdir(parents=True);worker.write_text('worker')
    (root/'upstream.json').write_text(json.dumps({'revision':research.RAVE_PIN,'license':'cc-by-nc-4.0'}))
    model=root/'guitar_iil_b2048_r48000_z16.ts';model.write_bytes(b'checkpoint');monkeypatch.setattr(research,'RAVE_SHA',research.sha(model))
    report=tmp_path/'evaluation.json';report.write_text(json.dumps({'worker_sha256':'old'}))
    with pytest.raises(ValueError,match='Worker differs'):research.prepare(root,germ,report)
    report.write_text(json.dumps({'worker_sha256':research.sha(worker),'rows':[]}))
    with pytest.raises(ValueError,match='incomplete'):research.prepare(root,germ,report)
    assert not (root/'deployments.json').exists()
