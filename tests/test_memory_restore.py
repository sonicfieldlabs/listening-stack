from pathlib import Path
import pytest
from listening_stack.memory_restore import restore


def test_restore_refuses_missing_current_ledger(tmp_path):
    with pytest.raises(ValueError, match="initialized"):
        restore(tmp_path/"archive.zip", tmp_path/"missing")


@pytest.mark.parametrize("version", ["1.7.0", "1.8.0"])
def test_bundle_upgrade_retry_and_current_revocation(tmp_path, monkeypatch, version):
    akousma = pytest.importorskip("akousma")
    bundles = pytest.importorskip("akousmata_app.bundles")
    source_root=tmp_path/"source"; target_root=tmp_path/"current"
    monkeypatch.setenv("AKOUSMATA_PATH",str(source_root))
    with akousma.AkousmataStore(source_root) as source, akousma.AkousmataStore(target_root) as target:
        record=akousma.new_akousma(audio={"asset_id":"synthetic", "uri":"file:///unavailable/synthetic.wav"},originating_app="restore-fixture")
        record["schema_version"] = version
        record["provenance"]["consent_status"]="owned"
        source.put(record, supported_versions=[version])
        result=bundles.export_bundle(source,[record["akousma_id"]])
    archive=Path(result["archive"])
    with pytest.raises(ValueError):
        restore(archive, target_root, supported_contracts=[])
    assert restore(archive,target_root)["current_ledger_preserved"]
    with akousma.AkousmataStore(target_root) as target:
        assert target.get(record["akousma_id"])["schema_version"] == version
    assert restore(archive,target_root)["import_receipt"]["records"][0]["outcome"]=="reused"
    with akousma.AkousmataStore(target_root) as target:
        target.forget(record["akousma_id"])
    with pytest.raises(ValueError,match="forgetting"):
        restore(archive,target_root)
    with akousma.AkousmataStore(target_root) as target:
        assert target.get(record["akousma_id"]) is None
        assert target.forgotten(record["akousma_id"])
