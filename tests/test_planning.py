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


def _rows(family, failing=()):
    from listening_stack.planning import FAMILIES
    return [dict(model='qwen', family=family, case=c, passed=c not in failing, seconds=1)
            for c in sorted(FAMILIES[family]['required'])]


def test_task_families_are_admitted_separately():
    from listening_stack.planning import admit_families
    planning = [{k: v for k, v in r.items() if k != 'family'} for r in _rows('planning')]
    result = admit_families(planning + _rows('routing') + _rows('inquiry'))
    assert all(v['admitted'] for v in result.values())
    # A failed injection case refuses its family, and only that family.
    result = admit_families(planning + _rows('routing', {'holdout-router-injection'}) + _rows('inquiry'))
    assert result['planning']['admitted'] and result['inquiry']['admitted']
    assert not result['routing']['admitted'] and result['routing']['passed'] == 8
    # A family that was not evaluated is not admitted.
    assert admit_families(planning)['inquiry'] == dict(passed=0, total=0, admitted=False)
