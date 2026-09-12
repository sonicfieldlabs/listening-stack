"""Policy-aware bundle restore; never replace the current store or its ledger."""

from pathlib import Path
import json
import hashlib

CONTRACTS = [
    "earworm/listening-memories/v1",
    "earworm/akousma/v1.6",
    "earworm/akousma/v1.7",
    "earworm/akousma/v1.8",
]


def restore(bundle: Path, current_store: Path, *, supported_contracts=None):
    current_store = current_store.expanduser().resolve()
    if not (current_store / "index.sqlite").is_file():
        raise ValueError(
            "Select the current initialized store, including its forgetting ledger"
        )
    if bundle.stat().st_size > 32 * 1024 * 1024:
        raise ValueError("Restore bundle exceeds 32 MiB")
    try:
        from akousma import AkousmataStore
        from akousmata_app.bundles import import_bundle
    except ImportError as exc:
        raise RuntimeError(
            "Restore requires the installed Akousmata/Earworm core environment"
        ) from exc
    with AkousmataStore(current_store) as store:
        before = store.forgetting_receipts()
        receipt = import_bundle(
            store,
            bundle.read_bytes(),
            supported_contracts=CONTRACTS if supported_contracts is None else supported_contracts,
        )
        after = store.forgetting_receipts()
        if not {r["receipt_id"] for r in before} <= {r["receipt_id"] for r in after}:
            raise RuntimeError("Current forgetting ledger changed unexpectedly")
    return dict(
        contract="listening-stack/memory-restore/v1",
        import_receipt=receipt,
        current_ledger_preserved=True,
        current_ledger_sha256=hashlib.sha256(
            json.dumps(after, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        database_replaced=False,
        runtime_rollback="Use the prior pinned runtime; records and current revocations are not rolled back",
    )
