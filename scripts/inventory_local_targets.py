"""Start qualification cells from the installed Oída catalogue, without calls.

Catalog support, runtime availability, execution and successful qualification are
different fields. Cloud entries are explicitly outside the author's test scope.
"""
from dataclasses import asdict
import argparse
import hashlib
import json
from pathlib import Path
import sys


def inventory():
    import oida.reasoning.model_catalog as catalog
    path = Path(catalog.__file__).resolve()
    if not path.is_relative_to(Path(sys.prefix).resolve()):
        raise ValueError("Use the installed candidate interpreter with -I")
    rows = []
    for spec in catalog.MODEL_SPECS:
        value = asdict(spec)
        value["locality"] = spec.locality.value
        local = value["locality"] == "local"
        rows.append({"catalog": value, "qualification_status": "pending_local_inventory" if local else "excluded_by_author_cloud_scope",
                     "runtime_observed": False, "model_loaded": False, "canary_executed": False,
                     "fallback_allowed": False, "required_role_cells": list(spec.roles) if local else []})
    return {"scope": "Installed Oída catalog selection only; GERM, specialists and other owner matrices remain separate",
            "catalog_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "targets": rows,
            "cloud_calls_authorized": False, "paid_calls_authorized": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = inventory()
    with args.output.open("x") as stream:
        stream.write(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"catalog_entries": len(report["targets"]),
        "local_pending": sum(t["qualification_status"] == "pending_local_inventory" for t in report["targets"]),
        "excluded_nonlocal": sum(t["qualification_status"] == "excluded_by_author_cloud_scope" for t in report["targets"])}))
