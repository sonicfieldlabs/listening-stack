import hashlib
import json
from pathlib import Path
import runpy
import subprocess
from types import SimpleNamespace
from unittest.mock import patch
import zipfile

import pytest

from listening_stack.candidate import CONTRACT, CORE, FULL, install, selected_environment, verify


def wheel(root, name, version, extra=None):
    path = root / (name.replace("-", "_") + "-" + version + "-py3-none-any.whl")
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(name + ".dist-info/METADATA", f"Name: {name}\nVersion: {version}\n")
        if extra:
            archive.writestr(*extra)
    return dict(file=path.name, distribution=name, version=version, sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def fixture(root, full=False):
    manifest = root / "manifest.json"
    manifest.write_text(json.dumps(dict(contract=CONTRACT, published=False,
        compatibility_profile="listening-stack-full/v1" if full else "listening-stack-core/v1",
        wheels=[wheel(root, name, version) for name, version in (FULL if full else CORE).items()])))
    return manifest


@pytest.mark.parametrize("full", [False, True])
def test_profiles_admit_public_components_without_an_application(tmp_path, full):
    assert len(verify(fixture(tmp_path, full))["wheels"]) == (6 if full else 5)


@pytest.mark.parametrize("mutation", ["checksum", "path", "duplicate", "published", "profile", "version", "missing", "application"])
def test_invalid_selection_has_no_install_effect(tmp_path, mutation):
    manifest = fixture(tmp_path)
    value = json.loads(manifest.read_text())
    if mutation == "checksum":
        (tmp_path / value["wheels"][0]["file"]).write_bytes(b"tampered")
    elif mutation == "path": value["wheels"][0]["file"] = "../outside.whl"
    elif mutation == "duplicate": value["wheels"].append(value["wheels"][0])
    elif mutation == "published": value["published"] = True
    elif mutation == "profile": value["compatibility_profile"] = "unreviewed/v1"
    elif mutation == "version": value["wheels"][0] = wheel(tmp_path, "sonicfield-oida", "0.10.0")
    elif mutation == "missing": value["wheels"].pop()
    else: value["wheels"].append(wheel(tmp_path, "sonicfield-private-fixture", "1.0"))
    manifest.write_text(json.dumps(value))
    with patch("listening_stack.candidate.subprocess.run") as run:
        with pytest.raises(ValueError): install(manifest, tmp_path / "install")
        run.assert_not_called()
    assert not (tmp_path / "install").exists()


def test_optional_germ_is_only_admitted_in_full_profile(tmp_path):
    manifest = fixture(tmp_path, True)
    value = json.loads(manifest.read_text())
    value["compatibility_profile"] = "listening-stack-core/v1"
    manifest.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="exact declared"): verify(manifest)


def test_archive_member_traversal_is_rejected_before_install(tmp_path):
    manifest = fixture(tmp_path)
    value = json.loads(manifest.read_text())
    value["wheels"][0] = wheel(tmp_path, "sonicfield-oida", CORE["sonicfield-oida"], ("../outside", "unsafe"))
    manifest.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="Unsafe"): verify(manifest)


def test_source_inventory_and_wheel_symlinks_are_bound(tmp_path):
    manifest = fixture(tmp_path)
    inventory = tmp_path / "source-inventory.json"
    inventory.write_text("{}")
    value = json.loads(manifest.read_text())
    value["source_inventory_sha256"] = hashlib.sha256(inventory.read_bytes()).hexdigest()
    manifest.write_text(json.dumps(value))
    verify(manifest)
    inventory.write_text('{"changed":true}')
    with pytest.raises(ValueError, match="inventory changed"): verify(manifest)
    inventory.write_text("{}")
    path = tmp_path / value["wheels"][0]["file"]
    target = tmp_path / "original.whl"
    path.rename(target)
    path.symlink_to(target)
    with pytest.raises(ValueError, match="checksum"): verify(manifest)


def test_existing_root_and_source_checkout_are_preserved(tmp_path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    manifest = fixture(bundle)
    existing = tmp_path / "existing"
    existing.mkdir()
    sentinel = existing / "keep.txt"
    sentinel.write_text("preserve")
    with pytest.raises(ValueError, match="existing environments"): install(manifest, existing)
    checkout = tmp_path / "checkout"
    (checkout / ".git").mkdir(parents=True)
    with pytest.raises(ValueError, match="source checkouts"): install(manifest, checkout / "install")
    assert sentinel.read_text() == "preserve"
    assert not (checkout / "install").exists()


def test_selected_environment_excludes_ambient_credentials_and_stores(tmp_path, monkeypatch):
    for key in ("OPENAI_API_KEY", "HF_TOKEN", "PYTHONPATH", "AKOUSMATA_PATH", "OIDA_DATA_DIR", "GERM_DATA_DIR"):
        monkeypatch.setenv(key, "/ambient/fixture")
    env = selected_environment(tmp_path, include_germ=True)
    assert not {"OPENAI_API_KEY", "HF_TOKEN", "PYTHONPATH"} & env.keys()
    for key in ("AKOUSMATA_PATH", "OIDA_DATA_DIR", "GERM_OUTPUT_DIR"):
        assert Path(env[key]).is_relative_to(tmp_path)
    assert not any(key.startswith("GERM_") for key in selected_environment(tmp_path))


def test_existing_interpreter_is_resolved_before_home_is_isolated(tmp_path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    manifest = fixture(bundle)
    root = tmp_path / "runtime"
    responses = [SimpleNamespace(stdout="/selected/python\n"), *[SimpleNamespace(returncode=0) for _ in range(4)]]
    with patch("listening_stack.candidate.subprocess.run", side_effect=responses) as run, patch("listening_stack.candidate.doctor", return_value={"fixture": True}):
        assert install(manifest, root) == {"fixture": True}
    calls = run.call_args_list
    assert calls[0].args[0][:3] == ["uv", "python", "find"]
    assert calls[0].kwargs["env"]["HOME"] == str(Path.home())
    assert calls[2].args[0][calls[2].args[0].index("--python") + 1] == "/selected/python"
    assert calls[2].kwargs["env"]["HOME"] == str(root / "state/home")


def test_unavailable_interpreter_does_not_create_a_runtime(tmp_path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    manifest = fixture(bundle)
    with patch("listening_stack.candidate.subprocess.run", side_effect=subprocess.CalledProcessError(2, ["uv", "python", "find"])):
        with pytest.raises(subprocess.CalledProcessError): install(manifest, tmp_path / "runtime")
    assert not (tmp_path / "runtime").exists()


def tool(name, monkeypatch):
    scripts = Path(__file__).parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    return runpy.run_path(str(scripts / name))


def owner(root, name):
    source = root / name
    source.mkdir()
    subprocess.run(["git", "init", "-q", str(source)], check=True)
    (source / "tracked.txt").write_text("tracked")
    subprocess.run(["git", "-C", str(source), "add", "tracked.txt"], check=True)
    subprocess.run(["git", "-C", str(source), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                    "-c", "commit.gpgsign=false", "commit", "-qm", "Synthetic fixture"], check=True)
    return source


def test_late_missing_owner_preflights_before_output(tmp_path, monkeypatch):
    prepare = tool("prepare_local_candidate.py", monkeypatch)["prepare"]
    owner(tmp_path, "oida")
    with pytest.raises(ValueError, match="Missing"): prepare(tmp_path, tmp_path / "out", ["oida", "germ"])
    assert not (tmp_path / "out").exists()
    assert not list(tmp_path.glob(".candidate-snapshot-*"))


def test_snapshot_preserves_untracked_inputs_deletions_and_staging(tmp_path, monkeypatch):
    prepare = tool("prepare_local_candidate.py", monkeypatch)["prepare"]
    source = owner(tmp_path, "oida")
    (source / "tracked.txt").unlink()
    (source / "untracked.txt").write_text("local source")
    index = (source / ".git/index").read_bytes()
    output = tmp_path / "out"
    assert prepare(tmp_path, output, ["oida"])["status"] == "source-ready"
    inventory = json.loads((output / "source-inventory.json").read_text())["oida"]
    assert inventory["deleted"] == ["tracked.txt"]
    assert inventory["candidate_commit"] is None
    assert (output / "sources/oida/untracked.txt").read_text() == "local source"
    assert (source / ".git/index").read_bytes() == index
    assert not (output / "sources/oida/.git").exists()


def test_non_regular_late_owner_has_no_output(tmp_path, monkeypatch):
    prepare = tool("prepare_local_candidate.py", monkeypatch)["prepare"]
    owner(tmp_path, "oida")
    source = owner(tmp_path, "germ")
    (source / "link").symlink_to(source / "tracked.txt")
    with pytest.raises(ValueError, match="non-regular"): prepare(tmp_path, tmp_path / "out", ["oida", "germ"])
    assert not (tmp_path / "out").exists()


def test_assembly_rejects_incomplete_inputs_before_copy(tmp_path, monkeypatch):
    build = tool("build_candidate.py", monkeypatch)["build"]
    inventory = tmp_path / "source-inventory.json"
    inventory.write_text(json.dumps({"oida": {"base_commit": "a" * 40, "source_inputs_sha256": "b" * 64}}))
    with pytest.raises(ValueError): build(tmp_path, tmp_path.parent / (tmp_path.name + "-out"), "listening-stack-core/v1", inventory)
    assert not (tmp_path.parent / (tmp_path.name + "-out")).exists()
