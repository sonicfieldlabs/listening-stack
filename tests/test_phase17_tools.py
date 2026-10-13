import hashlib
import json
from pathlib import Path
import runpy
from types import SimpleNamespace
import sys

import pytest


def tool(name):
    return runpy.run_path(str(Path(__file__).parents[1] / "scripts" / name))


def test_http_receipt_walk_preserves_nested_passes_without_duplicate_descent():
    walk = tool("qualify_oida_http.py")["pass_receipts"]
    first = {"actual_audio_model": {"model_id": "fixture-a"}}
    second = {"actual_audio_model": {"model_id": "fixture-b"}}
    event = {"engine": {"pass_provenance": [first]},
             "events": [{"report": {"pass_provenance": [second]}}]}
    assert list(walk(event)) == [first, second]
    assert list(walk({"unrelated": [None, "text", 1]})) == []


@pytest.mark.parametrize("family", ["instruct", "thinking"])
def test_http_cases_preserve_alias_and_canonical_identity(family):
    cases = tool("qualify_oida_http.py")["listening_cases"](
        family, Path("/offline/MOSS-Audio-4B-" + family.capitalize()), "events")
    assert len(cases) == 2
    assert cases[0]["requested"]["model_id"] == family
    assert cases[0]["actual"] == cases[1]["actual"] == cases[1]["requested"]
    assert cases[0]["actual"]["model_id"] == "OpenMOSS-Team/MOSS-Audio-4B-" + family.capitalize()
    assert len({case["operation_id"] for case in cases}) == 2
    assert all(case["pass"] == "events" for case in cases)


@pytest.mark.parametrize("family,checkpoint", [
    ("instruct", "MOSS-Audio-4B-Thinking"), ("thinking", "MOSS-Audio-4B-Instruct")])
def test_http_cases_refuse_mismatched_checkpoint(family, checkpoint):
    with pytest.raises(ValueError, match="does not match"):
        tool("qualify_oida_http.py")["listening_cases"](family, Path("/offline") / checkpoint, "caption")


@pytest.mark.parametrize("flag,value", [("--listen-model", "thinking"), ("--listen-pass", "events")])
def test_http_model_selection_without_listening_refuses_before_output(tmp_path, monkeypatch, flag, value):
    argv = ["qualification"]
    for name in ("manifest", "variant", "instruct", "thinking", "output", "libraries"):
        argv.extend(["--" + name, str(tmp_path / name)])
    monkeypatch.setattr(sys, "argv", [*argv, flag, value])
    with pytest.raises(SystemExit) as result:
        tool("qualify_oida_http.py")["main"]()
    assert result.value.code == 2
    assert not (tmp_path / "output").exists()


def test_moss_preparation_preserves_existing_destination(tmp_path):
    prepare = tool("prepare_moss_qualification.py")["prepare"]
    output = tmp_path / "existing"
    output.mkdir()
    with pytest.raises(ValueError, match="Fresh destination"):
        prepare(tmp_path / "missing.json", tmp_path / "upstream", tmp_path / "owner", output)
    assert list(output.iterdir()) == []


def test_moss_environment_excludes_credentials_and_ambient_configuration(tmp_path, monkeypatch):
    environment = tool("run_moss_qualification.py")["selected_environment"]
    monkeypatch.setenv("OPENAI_API_KEY", "fixture-not-a-key")
    monkeypatch.setenv("OIDA_MOSS_BACKUP_MODEL", "ambient-fallback")
    monkeypatch.setenv("PYTHONPATH", "/ambient/python")
    monkeypatch.setenv("LISTENINGSTACK_RESOURCE_DIR", "/ambient/private-lock")
    selected = environment(tmp_path, "/selected/ffmpeg/lib")
    assert "OPENAI_API_KEY" not in selected
    assert "PYTHONPATH" not in selected
    assert "LISTENINGSTACK_RESOURCE_DIR" not in selected
    assert selected["OIDA_MOSS_BACKUP_MODEL"] == ""
    assert selected["HF_HUB_OFFLINE"] == "1"
    assert selected["OIDA_DATA_DIR"] == str(tmp_path / "state")


@pytest.mark.parametrize("flag,value", [("--timeout", "nan"), ("--seconds", "nan"), ("--tokens", "257")])
def test_moss_runner_rejects_unbounded_inputs_before_reading_sources(tmp_path, monkeypatch, flag, value):
    main = tool("run_moss_qualification.py")["main"]
    monkeypatch.setattr(sys, "argv", ["runner", "--variant", str(tmp_path), "--instruct", str(tmp_path),
                                     "--thinking", str(tmp_path), "--output", str(tmp_path / "out"),
                                     "--libraries", "/fixture", flag, value])
    with pytest.raises(SystemExit) as result:
        main()
    assert result.value.code == 2
    assert not (tmp_path / "out").exists()
