"""Installed research support must be observable without consulting a corpus."""
import pytest

# The repository's own lock vendors published Oida 0.13.2, which has no research modules.
# The research cohort lane installs them and requires zero skips, so this cannot hide there.
local_passages = pytest.importorskip("oida.local_passages", reason="research cohort not installed")
sonicfield_discovery = pytest.importorskip("oida.sonicfield_discovery", reason="research cohort not installed")


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
        "reference": "oida/research-reference/v1", "context": "oida/research-context/v1",
        "local_passage": "oida/local-passage/v1", "public_result": "oida/sonicfield-result/v1",
    }
    assert report["recipes"]["names"] == ["selected_context_return", "local_relisten_return"]
    assert report["recipes"]["limits"]["max_steps"] == 5
    assert report["source_read"] == report["model_execution"] == report["owner_activation"] == "not_requested"
    assert report["public_network"] == "not_probed"
    assert report["host_connection"] == "not_configured"
    assert list(tmp_path.iterdir()) == []
