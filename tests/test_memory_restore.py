from pathlib import Path
import pytest
from listening_stack.memory_restore import restore


def test_restore_refuses_missing_current_ledger(tmp_path):
    with pytest.raises(ValueError, match="initialized"):
        restore(tmp_path/"archive.zip", tmp_path/"missing")


def test_bundle_upgrade_retry_and_current_revocation(tmp_path, monkeypatch):
    akousma = pytest.importorskip("akousma")
    bundles = pytest.importorskip("akousmata_app.bundles")
    source_root=tmp_path/"source"; target_root=tmp_path/"current"
    monkeypatch.setenv("AKOUSMATA_PATH",str(source_root))
    with akousma.AkousmataStore(source_root) as source, akousma.AkousmataStore(target_root) as target:
        record=akousma.new_akousma(audio={"asset_id":"synthetic", "uri":"file:///unavailable/synthetic.wav"},originating_app="restore-fixture")
        record["provenance"]["consent_status"]="owned"
        source.put(record)
        result=bundles.export_bundle(source,[record["akousma_id"]])
    archive=Path(result["archive"])
    assert restore(archive,target_root)["current_ledger_preserved"]
    assert restore(archive,target_root)["import_receipt"]["records"][0]["outcome"]=="reused"
    with akousma.AkousmataStore(target_root) as target:
        target.forget(record["akousma_id"])
    with pytest.raises(ValueError,match="forgetting"):
        restore(archive,target_root)
    with akousma.AkousmataStore(target_root) as target:
        assert target.get(record["akousma_id"]) is None
        assert target.forgotten(record["akousma_id"])
