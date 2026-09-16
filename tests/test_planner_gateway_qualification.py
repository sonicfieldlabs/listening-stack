from pathlib import Path
import runpy

import pytest

check = runpy.run_path(str(Path(__file__).parents[1] / "scripts/qualify_planner_gateway.py"))["admitted_evaluation"]
cases = runpy.run_path(str(Path(__file__).parents[1] / "scripts/evaluate_local_planner.py"))["CASES"]


def fixture():
    return {"status": "passed", "worker_sha256": "a" * 64,
            "rows": [{"case": c, "passed": True, "historical_task_passed": True,
                      "proposal_boundary_issues": []} for c in sorted(cases)]}


def test_complete_strict_evaluation_is_required():
    check(fixture(), "a" * 64)


@pytest.mark.parametrize("damage", ["worker", "status", "missing", "unknown", "old_scorer", "boundary", "task"])
def test_incomplete_or_legacy_evidence_cannot_admit(damage):
    value = fixture()
    if damage == "worker":
        value["worker_sha256"] = "b" * 64
    elif damage == "status":
        value["status"] = "running"
    elif damage == "missing":
        value["rows"].pop()
    elif damage == "unknown":
        value["rows"][0]["case"] = "invented"
    elif damage == "old_scorer":
        value["rows"][0].pop("proposal_boundary_issues")
    elif damage == "boundary":
        value["rows"][0]["proposal_boundary_issues"] = ["unoffered_analysis"]
    else:
        value["rows"][0]["historical_task_passed"] = False
    with pytest.raises(ValueError):
        check(value, "a" * 64)
