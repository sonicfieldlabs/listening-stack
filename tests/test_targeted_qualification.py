from copy import deepcopy
import hashlib
import json
from pathlib import Path
import runpy

import pytest


def validator():
    return runpy.run_path(str(Path(__file__).parents[1] / "scripts/qualify_targeted_relisten.py"))["validate_sidecar"]


def fixture():
    event = {"id": "e", "segment": {"id": "s", "data_ref": {"sha256": "a" * 64}}}
    sidecar = {"base_event_id": "e", "conversation_id": "qualification-conversation",
        "turn_id": "cold-thinking", "segment_ref": "s", "segment_hash": "a" * 64,
        "model": "/model", "observation": "fixture", "source_binding": {
            "status": "verified", "observed_sha256": "a" * 64},
        "pass_provenance": [{"model": "/model", "effective_input": {"status": "known"},
                             "weights": {"status": "known"}}]}
    sidecar["sha256"] = hashlib.sha256(json.dumps(sidecar, sort_keys=True,
        separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    return event, sidecar


def test_targeted_evidence_validation_preserves_inputs():
    event, sidecar = fixture()
    before = deepcopy((event, sidecar))
    validator()(sidecar, event, "cold-thinking", Path("/model"))
    assert (event, sidecar) == before


@pytest.mark.parametrize("field,value", [
    ("base_event_id", "other"), ("turn_id", "other"), ("model", "/other"),
    ("segment_hash", "b" * 64), ("pass_provenance", []),
    ("source_binding", {"status": "unverified_original"}), ("sha256", "0" * 64),
    ("reasoning_trace", "must not be retained"),
])
def test_targeted_evidence_mismatch_refuses(field, value):
    event, sidecar = fixture()
    sidecar[field] = value
    with pytest.raises(ValueError):
        validator()(sidecar, event, "cold-thinking", Path("/model"))
