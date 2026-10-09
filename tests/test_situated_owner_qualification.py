from pathlib import Path
import hashlib
import runpy

import pytest
from oida.owner_journal import canonical

validate = runpy.run_path(str(Path(__file__).parents[1] / "scripts/qualify_situated_owner.py"))["validate_decision"]


def fixture():
    record = {"akousma_id": "fixture", "summary": "Oída"}
    deployment = {"revision": "a" * 40, "worker_sha256": "b" * 64, "evaluation_sha256": "c" * 64}
    decision = {"status": "complete", "basis": "LLM decision", "provider_id": "local_ecology",
                "model_id": "model", "action": "stop", "blockers": [], "evidence": [{"ref": "fixture"}],
                "deployment": dict(deployment), "record_sha256": hashlib.sha256(canonical(record).encode()).hexdigest()}
    return decision, record, "model", deployment


def test_exact_learned_decision_is_accepted():
    validate(*fixture())


@pytest.mark.parametrize("field,value", [("status", "failed"), ("basis", "deterministic; no LLM used"),
    ("provider_id", "external"), ("model_id", "substitute"), ("action", "generate"),
    ("blockers", ["refused"]), ("evidence", []), ("deployment", {"revision": "wrong"}),
    ("record_sha256", "d" * 64)])
def test_mismatched_receipts_cannot_pass(field, value):
    args = fixture()
    args[0][field] = value
    with pytest.raises(RuntimeError):
        validate(*args)
