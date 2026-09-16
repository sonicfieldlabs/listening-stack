import json
import runpy
from pathlib import Path

import pytest


TOOLS = runpy.run_path(str(Path(__file__).parents[1] / "scripts/preflight_editorial_cases.py"))


def selected(tmp_path, ids=("record-a",), case="amsterdam"):
    path = tmp_path / f"{case}.json"
    path.write_text(json.dumps({"case_id": case, "accounts": [{"account_id": i} for i in ids]}))
    return path


def fake_export(**kwargs):
    assert kwargs["dry_run"] and kwargs["prepare_decision"]
    assert not kwargs["include_media"] and kwargs["audience"] == "editorial"
    return {"published": False, "preview_only": True, "bundle": {
        "accounts": [{"account_id": i} for i in kwargs["identifiers"]],
        "disclosure": {"approval_proposal": {"state": "unapproved"}}, "assets": []}}


def test_unapproved_preview_has_exact_selection_and_no_media(tmp_path):
    report = TOOLS["preflight"](tmp_path / "workspace", [selected(tmp_path)], tmp_path / "out", fake_export)
    assert report["status"] == "prepared-unapproved"
    assert report["cases"][0]["record_ids"] == ["record-a"]
    assert (tmp_path / "out/case-01-decision-proposal.json").is_file()


@pytest.mark.parametrize("ids", [(), ("a", "a"), (None,), ("",)])
def test_invalid_selection_refuses_before_output(tmp_path, ids):
    with pytest.raises(ValueError):
        TOOLS["preflight"](tmp_path / "workspace", [selected(tmp_path, ids)], tmp_path / "out", fake_export)
    assert not (tmp_path / "out").exists()


def test_existing_output_is_preserved(tmp_path):
    with pytest.raises(ValueError, match="Fresh"):
        TOOLS["preflight"](tmp_path / "workspace", [], tmp_path, fake_export)


def test_live_workspace_output_is_refused(tmp_path):
    with pytest.raises(ValueError, match="outside"):
        TOOLS["preflight"](tmp_path, [], tmp_path / "out", fake_export)


def test_case_failure_is_reported_without_hiding_next_case(tmp_path):
    def export(**kwargs):
        if kwargs["case_id"] == "amsterdam":
            raise ValueError("missing owner receipt")
        return fake_export(**kwargs)
    report = TOOLS["preflight"](tmp_path / "workspace", [selected(tmp_path), selected(tmp_path, case="answer")], tmp_path / "out", export)
    assert report["status"] == "incomplete"
    assert [c["status"] for c in report["cases"]] == ["failed", "prepared-unapproved"]


def test_exporter_cannot_silently_drop_selected_account(tmp_path):
    def export(**kwargs):
        preview = fake_export(**kwargs)
        preview["bundle"]["accounts"] = []
        return preview
    report = TOOLS["preflight"](tmp_path / "workspace", [selected(tmp_path)], tmp_path / "out", export)
    assert report["cases"][0]["status"] == "failed"
    assert not (tmp_path / "out/case-01-preview.json").exists()
