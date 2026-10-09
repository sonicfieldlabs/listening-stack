"""Qualification-validator fixtures, never evidence of real owner execution."""
import hashlib
import json
import runpy
from copy import deepcopy
from pathlib import Path

import pytest

validate = runpy.run_path(str(Path(__file__).parents[1] / "scripts/qualify_central_connected.py"))["validate_situated_stop"]
validate_record = runpy.run_path(str(Path(__file__).parents[1] / "scripts/qualify_central_connected.py"))["validate_situated_record"]
planning_options = runpy.run_path(str(Path(__file__).parents[1] / "scripts/qualify_central_connected.py"))["planning_options"]
validate_snapshot = runpy.run_path(str(Path(__file__).parents[1] / "scripts/qualify_central_connected.py"))["validate_owner_snapshot"]


def test_per_run_options_explicitly_select_learned_provider_and_record_only_context():
    assert planning_options({"model_id": "qualified-local"}) == {
        "provider_id": "local_ecology", "model_id": "qualified-local",
        "reasoning_context": "record", "reasoning_sound": True}
    assert planning_options(None)["provider_id"] == "local_structured"


def test_owner_record_digest_uses_its_own_unicode_recipe():
    record = {"title": "Oída · écoute"}
    expected = hashlib.sha256(json.dumps(record, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    chain = {"decisions": [{"record_sha256": expected}]}
    assert validate_record(chain, record)["status"] == "passed"
    other = hashlib.sha256(json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    assert other != expected
    chain["decisions"][0]["record_sha256"] = other
    with pytest.raises(RuntimeError):
        validate_record(chain, record)


def fixture():
    return {"results": {"reasoning_chain": {
        "contract": "listening-swarm/reasoning-chain/v1", "status": "complete", "moves": [],
        "record_id": "fixture",
        "decisions": [{"id": "decision-1", "status": "complete", "action": "stop",
                       "provider_id": "local_structured", "basis": "deterministic; no LLM used",
                       "record_id": "fixture", "decision": {"next_move": {"evidence_refs": ["event:fixture:anchor"]}},
                       "record_sha256": "a" * 64}],
        "decision_receipts": [{"decision_id": "decision-1", "initiator_class": "deterministic_policy",
                               "is_authorizing": False}],
    }}}


def test_situated_validator_preserves_retained_chain():
    run = fixture()
    before = deepcopy(run)
    assert validate(run) == run["results"]["reasoning_chain"]
    assert run == before


def learned_fixture():
    run = fixture()
    planner = {"model_id": "local-candidate", "deployment": {
        "revision": "revision-1", "worker_sha256": "b" * 64, "evaluation_sha256": "c" * 64}}
    chain = run["results"]["reasoning_chain"]
    chain["decisions"][0].update(provider_id="local_ecology", basis="LLM decision",
                                 model_id=planner["model_id"], deployment=deepcopy(planner["deployment"]), blockers=[])
    chain["decisions"][0]["decision"]["next_move"]["evidence_refs"] = ["event:fixture:caption"]
    chain["decision_receipts"][0]["initiator_class"] = "model_proposed_admitted"
    return run, planner


def test_learned_stop_accepts_non_anchor_evidence_without_changing_receipt():
    run, planner = learned_fixture()
    before = deepcopy(run)
    assert validate(run, planner) == run["results"]["reasoning_chain"]
    assert run == before
    with pytest.raises(RuntimeError):
        validate(run)


@pytest.mark.parametrize("damage", [None, "join", "move_ref", "finding_ref"])
def test_owner_snapshot_requires_retained_context_and_exact_join(damage):
    run, _ = learned_fixture()
    chain = run["results"]["reasoning_chain"]
    saved = deepcopy(chain["decisions"][0])
    saved["evidence"] = [{"ref": "event:fixture:caption"}]
    if damage == "join":
        saved["record_id"] = "another-account"
    elif damage == "move_ref":
        saved["evidence"] = [{"ref": "unoffered"}]
    elif damage == "finding_ref":
        finding = [{"evidence_refs": ["unoffered"]}]
        saved["decision"]["findings"] = deepcopy(finding)
        chain["decisions"][0]["decision"]["findings"] = finding
    before = deepcopy(saved)
    if damage:
        with pytest.raises(RuntimeError):
            validate_snapshot(chain, saved)
    else:
        assert validate_snapshot(chain, saved) == {"status": "passed", "evidence_items": 1}
    assert saved == before


@pytest.mark.parametrize("damage", ["model_id", "deployment", "basis", "provider_id", "blockers", "evidence", "initiator"])
def test_learned_stop_requires_exact_identity_and_attribution(damage):
    run, planner = learned_fixture()
    chain = run["results"]["reasoning_chain"]
    decision = chain["decisions"][0]
    if damage == "evidence":
        decision["decision"]["next_move"]["evidence_refs"] = []
    elif damage == "initiator":
        chain["decision_receipts"][0]["initiator_class"] = "deterministic_policy"
    elif damage == "blockers":
        decision[damage] = ["blocked"]
    else:
        decision[damage] = "wrong"
    with pytest.raises(RuntimeError):
        validate(run, planner)


@pytest.mark.parametrize("damage", ["skipped", "no_decision", "extra_move", "wrong_provider",
                                   "missing_evidence", "missing_digest", "wrong_join", "authority"])
def test_situated_validator_refuses_missing_or_wrong_evidence(damage):
    run = fixture()
    chain = run["results"]["reasoning_chain"]
    if damage == "skipped":
        chain["status"] = "skipped"
    elif damage == "no_decision":
        chain["decisions"] = []
    elif damage == "extra_move":
        chain["moves"] = [{"action": "generate"}]
    elif damage == "wrong_provider":
        chain["decisions"][0]["provider_id"] = "external"
    elif damage == "missing_evidence":
        chain["decisions"][0]["decision"]["next_move"]["evidence_refs"] = []
    elif damage == "missing_digest":
        chain["decisions"][0].pop("record_sha256")
    elif damage == "wrong_join":
        chain["decision_receipts"][0]["decision_id"] = "other"
    else:
        chain["decision_receipts"][0]["is_authorizing"] = True
    with pytest.raises(RuntimeError):
        validate(run)
