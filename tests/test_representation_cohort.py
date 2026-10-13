"""The installed inscription cohort, with no model or acoustic event implied."""
from pathlib import Path
import hashlib
import json
import struct

import pytest


def test_installed_diagnostic_names_software_support_without_activation(tmp_path, monkeypatch):
    from listening_stack.representations import installed_capabilities
    monkeypatch.chdir(tmp_path)
    report = installed_capabilities()
    assert report["state"] == "installed_software"
    assert report["owners"] == {"sonicfield-oida":"0.13.1", "akousma":"0.10.0", "akousmata":"0.9.0", "akouo-contract":"0.12.0"}
    assert set(report["execution"]["conventions"]) == {"text", "data", "morse", "notation", "glyphs", "code", "midi"}
    assert report["execution"]["output_forms"] == ["text"]
    assert report["execution"]["output_kinds"] == ["account", "work"]
    assert report["execution"]["audio_required"] is False
    assert report["execution"]["adoption_default"] == "none"
    assert report["provider_availability"] == "not_probed"
    assert report["model_execution"] == report["owner_activation"] == "not_requested"
    assert set(p["id"] for p in report["lifecycle"]["presets"]) == {"minimal","research","phantom-acoustics","covenant","swarm"}
    assert all(p["adoption"] == "not_adopted" for p in report["lifecycle"]["presets"])
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("form,material", [
    ("text", b"hum\r\n     hum\r\n"), ("data", b'{"pulse":[1,null,3]}'),
    ("morse", b".... .."), ("notation", b"rest | C4\n"),
    ("glyphs", "∴\n∴".encode()), ("code", b"tick();\n"),
    ("midi", b"MThd" + struct.pack(">IHHH", 6, 0, 1, 480) + b"MTrk" + struct.pack(">I", 4) + b"\x00\xff\x2f\x00"),
])
def test_each_installed_convention_keeps_its_exact_original(form, material):
    from oida.representation_inputs import representation
    from akousma.representations import representation_errors
    rep = representation(material, form=form, terms_ref="fixture:local-use")
    assert representation_errors(rep) == []
    assert rep["artifact"]["sha256"] == hashlib.sha256(material).hexdigest()
    assert rep["artifact"]["byte_count"] == len(material)
    assert rep["form"] == form and rep["origin"]["domain"] == "non_acoustic"


def test_owner_test_wheels_and_lock_name_the_same_bytes():
    import tomllib
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "vendor/owner-test-wheels.json").read_text())
    lock = tomllib.loads((root / "uv.lock").read_text())
    assert manifest["compatibility_basis"] == "listening-md-core/v1"
    for row in manifest["wheels"]:
        digest = hashlib.sha256((root / "vendor" / row["file"]).read_bytes()).hexdigest()
        assert digest == row["sha256"]
        package = next(p for p in lock["package"] if p["name"] == row["distribution"])
        assert package["version"] == row["version"]
        assert package["source"] == {"path": "vendor/" + row["file"]}
        assert package["wheels"][0]["hash"] == "sha256:" + digest
