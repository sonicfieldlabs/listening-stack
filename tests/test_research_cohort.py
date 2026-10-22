"""Installed research support must be observable without consulting a corpus."""

import importlib
import os

import pytest


def research_module(name):
    if os.environ.get("LISTENING_STACK_REQUIRE_RESEARCH") == "1":
        return importlib.import_module(name)
    return pytest.importorskip(name, reason="research cohort not installed")


local_passages = research_module("oida.local_passages")
sonicfield_discovery = research_module("oida.sonicfield_discovery")


def test_diagnostic_does_not_read_sources_or_contact_an_owner(tmp_path, monkeypatch):
    import socket
    from pathlib import Path

    from listening_stack.research_support import installed_capabilities

    def forbidden(*args, **kwargs):
        raise AssertionError("Declaration inspection attempted external work")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(local_passages, "ROOTS", {"aleph": Path("unavailable-source")})
    monkeypatch.setattr(sonicfield_discovery.httpx, "AsyncClient", forbidden)
    report = installed_capabilities()
    assert report["contracts"] == {
        "reference": "oida/research-reference/v1",
        "context": "oida/research-context/v1",
        "local_passage": "oida/local-passage/v1",
        "public_result": "oida/sonicfield-result/v1",
    }
    assert report["recipes"]["names"] == [
        "selected_context_return",
        "local_relisten_return",
    ]
    assert report["recipes"]["limits"]["max_steps"] == 5
    assert (
        report["source_read"]
        == report["model_execution"]
        == report["owner_activation"]
        == "not_requested"
    )
    assert report["public_network"] == "not_probed"
    assert report["host_connection"] == "not_configured"
    assert list(tmp_path.iterdir()) == []
