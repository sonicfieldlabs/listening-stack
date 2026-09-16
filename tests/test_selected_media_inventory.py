import json
import runpy
from pathlib import Path

inspect = runpy.run_path(str(Path(__file__).parents[1] / "scripts/qualify_selected_media.py"))["inspect"]


def test_byte_presence_does_not_turn_into_permission(tmp_path):
    audio = tmp_path / "sound.wav"
    audio.write_bytes(b"fixture, not audio")
    bundle = tmp_path / "bundle.json"
    bundle.write_text(json.dumps({"case_id": "technical-fixture", "assets": [
        {"account_id": "a", "asset_id": "one", "content_hash": "selected", "grant": {"state": "unpublished"}},
        {"account_id": "b", "asset_id": "two", "content_hash": "missing"}]}))
    report = inspect([bundle], (tmp_path,), lambda digest: audio if digest == "selected" else None)
    available, missing = report["cases"][0]["assets"]
    assert available["status"] == "digest-verified-available"
    assert available["grant_state_in_bundle"] == "unpublished"
    assert available["relative_path"] == "sound.wav"
    assert missing["status"] == "not-found-in-selected-roots"
    assert "media_included" not in available
    assert "authorization" in report["scope"]
