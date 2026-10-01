"""The managed installer must not advertise a newer Oída adapter than it pins."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from listening_stack.catalog import REPOSITORIES
from listening_stack.cli import main
from listening_stack.integration_catalog import select_integrations, supported_integrations
from listening_stack.installer import Installer, Selection
from listening_stack.system import Runner


def pinned_cli():
    folder = Path(__file__).parent / "fixtures/pinned-oida"
    origin = json.loads((folder / "origin.json").read_text())
    assert origin["revision"] == REPOSITORIES["oida"].revision
    path = folder / "cli.py"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == origin["files"]["cli.py"]["sha256"]
    spec = importlib.util.spec_from_file_location("pinned_oida_cli", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("target", supported_integrations())
def test_advertised_adapter_dispatches_through_the_exact_pinned_cli(target, monkeypatch, capsys):
    calls = []
    adapter = SimpleNamespace(install=lambda selected: calls.append(selected) or {"target": selected})
    monkeypatch.setitem(sys.modules, "oida.integrations", adapter)
    pinned_cli()._lifecycle_main(["integrate", target, "--json"])
    assert calls == [target]
    assert json.loads(capsys.readouterr().out) == {"target": target}


def test_pi_is_not_advertised_and_the_pinned_cli_rejects_it():
    assert "pi" not in select_integrations(["all"])
    with pytest.raises(SystemExit) as error:
        pinned_cli()._lifecycle_main(["integrate", "pi", "--json"])
    assert error.value.code == 2


@pytest.mark.parametrize("targets", [["pi"], ["all", "pi"]])
def test_unsupported_install_selection_has_no_filesystem_effect(tmp_path, targets):
    root = tmp_path / "uncreated"
    selection = Selection("core", [], targets, "mock", root)
    with pytest.raises(ValueError, match="unsupported"):
        Installer(selection, Runner(quiet=True)).install()
    assert not root.exists()
    arguments = ["install", "--component", "core", "--no-models", "--root", str(root), "--yes"]
    for target in targets:
        arguments += ["--integration", target]
    with pytest.raises(SystemExit) as error:
        main(arguments)
    assert error.value.code == 1
    assert not root.exists()


def test_all_is_profile_specific_and_unknown_pins_fail_closed():
    assert supported_integrations("germ") == ()
    with pytest.raises(ValueError, match="does not include"):
        select_integrations(["all"], "germ")
    with pytest.raises(ValueError, match="No reviewed"):
        supported_integrations(revision="unreviewed")


def test_existing_install_validates_every_target_before_any_host_write(tmp_path, monkeypatch):
    import listening_stack.cli as cli
    calls = []
    state = {"profile": "core", "commits": {"oida": REPOSITORIES["oida"].revision}, "environment": {}}
    monkeypatch.setattr(cli, "load_state", lambda root: state)
    monkeypatch.setattr(cli.Runner, "run", lambda *args, **kwargs: calls.append((args, kwargs)))
    with pytest.raises(SystemExit) as error:
        main(["integrate", "all", "pi", "--root", str(tmp_path)])
    assert error.value.code == 1
    assert calls == []
    main(["integrate", "all", "--root", str(tmp_path)])
    assert [args[1][-2] for args, _ in calls] == list(supported_integrations())
