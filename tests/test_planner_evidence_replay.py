"""Replay-envelope fixtures, not semantic model qualification."""
import runpy
from copy import deepcopy
from pathlib import Path

import pytest

envelope = runpy.run_path(str(Path(__file__).parents[1] / "scripts/replay_planner_evidence.py"))["envelope"]
output_budget = runpy.run_path(str(Path(__file__).parents[1] / "scripts/replay_planner_evidence.py"))["output_budget"]


def test_retained_replay_preserves_evidence_status_and_bounds_action():
    receipt = {"evidence": [{"ref": "event:a:claim", "category": "undetermined", "value": "Unsupported account"}],
               "settings": {"rules": {"autonomous": False}, "boundaries": {"max_operations": 1}}}
    before = deepcopy(receipt)
    result = envelope(receipt)
    assert result["evidence"] == receipt["evidence"]
    assert result["allowed_actions"] == ["stop"]
    assert result["available_analysis"] == []
    assert result["retained_seconds"] is None
    assert result["choices"] == []
    assert receipt == before


@pytest.mark.parametrize("budget", [2200, 256, 4096, True, "2200", 4097, 0])
def test_replay_preserves_valid_retained_budget_and_rejects_unbounded_values(budget):
    receipt = {"settings": {"boundaries": {"max_output_tokens": budget}}}
    if type(budget) is int and 256 <= budget <= 4096:
        assert output_budget(receipt) == budget
    else:
        with pytest.raises(ValueError):
            output_budget(receipt)
