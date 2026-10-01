from pathlib import Path
import runpy

import pytest

score = runpy.run_path(str(Path(__file__).parents[1] / "scripts/evaluate_local_planner.py"))["score"]
boundaries = runpy.run_path(str(Path(__file__).parents[1] / "scripts/evaluate_local_planner.py"))["proposal_boundary_issues"]


def fixture():
    case = {"id": "budget", "evidence": [{"ref": "event:a:anchor"}],
            "expected": "stop", "allowed_actions": ["stop"]}
    decision = {"summary": "Budget exhausted", "findings": [],
                "next_move": {"action": "stop", "reason": "No budget", "evidence_refs": ["event:a:anchor"]}}
    return case, decision


def test_valid_stop():
    assert score(*fixture())


@pytest.mark.parametrize("damage", ["unknown_ref", "forbidden", "missing_ref", "schema"])
def test_invalid_decision(damage):
    case, decision = fixture()
    if damage == "unknown_ref":
        decision["next_move"]["evidence_refs"] = ["invented"]
    elif damage == "forbidden":
        decision["next_move"]["action"] = "relisten"
    elif damage == "missing_ref":
        decision["next_move"]["evidence_refs"] = []
    else:
        decision["next_move"]["action"] = "shell"
    if damage in {"missing_ref", "schema"}:
        with pytest.raises(ValueError):
            score(case, decision)
    else:
        assert not score(case, decision)


def test_requested_specialist_and_interval_both_required():
    case, decision = fixture()
    case.update(id="holdout-span", expected="relisten", allowed_actions=["relisten"])
    decision["next_move"].update(action="relisten", analysis_tasks=["transcribe"], segment={"start_seconds": 4, "seconds": 3})
    assert score(case, decision)
    decision["next_move"]["analysis_tasks"] = None
    assert not score(case, decision)


def test_conflict_requires_two_distinct_refs():
    case, decision = fixture()
    case.update(id="conflict", expected="relisten", allowed_actions=["relisten"], evidence=[{"ref": "a"}, {"ref": "b"}])
    decision["next_move"].update(action="relisten", evidence_refs=["a"])
    decision["findings"] = [{"kind": "divergence", "text": "Accounts differ", "evidence_refs": ["a", "a"]}]
    assert not score(case, decision)
    decision["findings"][0]["evidence_refs"] = ["a", "b"]
    assert score(case, decision)


def test_historical_score_does_not_imply_host_boundary_acceptance():
    case, decision = fixture()
    decision["findings"] = [{"kind": "divergence", "text": "One cited account", "evidence_refs": ["event:a:anchor"]}]
    assert score(case, decision)
    assert boundaries(case, decision) == ["comparison_requires_distinct_refs"]


def test_unoffered_adaptive_operations_are_flagged():
    case, decision = fixture()
    case.update(expected="relisten", allowed_actions=["relisten"])
    decision["next_move"].update(action="relisten", analysis_tasks=["tag_events"], segment={"start_seconds": 0, "seconds": 60})
    assert score(case, decision)
    assert boundaries(case, decision) == ["unoffered_analysis", "unbounded_or_excess_interval"]
    case.update(available_analysis=["tag_events"], retained_seconds=60)
    assert boundaries(case, decision) == []
