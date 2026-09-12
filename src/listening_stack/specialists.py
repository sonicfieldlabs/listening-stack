"""Prepare an optional P1 deployment from provisioned local artifacts.

No runtime request downloads models. Use the pinned acquisition instructions in docs.
"""

from __future__ import annotations
import hashlib
import json
from pathlib import Path
import subprocess
import time
import argparse

PINS = {
    "tag_events": {
        "adapter": "efficientat-mn04",
        "repository": "EfficientAT",
        "revision": "a425fdce92572e602a1d5634799bd9f1f2efa806",
        "checkpoint": "mn04_as.pt",
        "sha256": "899a8c6217063f6941793102a2780b3dd788ab11fce468d9cf5f0577c453321c",
    },
    "track_beats": {
        "adapter": "beat-this-small",
        "repository": "beat_this",
        "revision": "b95c8ab0c58c2d9fcfd40508ae8dffbc05ac4f5c",
        "checkpoint": "small0.ckpt",
        "sha256": "6074be2c4d490c5f6101fcc374a1ec72ae93456e23bb6019783b849f5dc7d47b",
    },
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_component(repository, revision):
    files = list(repository.rglob("*.py")) + list(
        (repository / "metadata").glob("*.csv")
    )
    inventory = {str(p.relative_to(repository)): sha(p) for p in sorted(files)}
    return dict(
        id=repository.name + ":source",
        revision=revision,
        sha256=hashlib.sha256(
            json.dumps(inventory, sort_keys=True).encode()
        ).hexdigest(),
    )


def prepare(root: Path, oida: Path, fixtures: Path):
    root = root.resolve()
    oida = oida.resolve()
    fixtures = fixtures.resolve()
    worker = oida / "oida/specialists/worker.py"
    python = root / ".venv/bin/python"
    lock = root / "requirements.lock"
    if not lock.is_file():
        raise ValueError("Freeze the validated isolated environment first")
    entries = []
    for task, pin in PINS.items():
        repository = root / pin["repository"]
        checkpoint = root / pin["checkpoint"]
        license = repository / "LICENSE"
        revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repository, text=True
        ).strip()
        if revision != pin["revision"] or sha(checkpoint) != pin["sha256"]:
            raise ValueError("Pinned specialist artifact mismatch")
        if subprocess.check_output(
            ["git", "diff", "--name-only", "HEAD"], cwd=repository, text=True
        ).strip():
            raise ValueError("Upstream source modified")
        rows = []
        for name in [
            "silence",
            "tone_440",
            "high_band_12000",
            "stereo_distinction",
            "regular_impulses",
            "irregular_impulses",
        ]:
            audio = fixtures / (name + ".wav")
            request = root / (task + "-request.json")
            result = root / (task + "-result.json")
            request.write_text(
                json.dumps(
                    dict(
                        task=task,
                        path=str(audio),
                        repository=str(repository),
                        checkpoint=str(checkpoint),
                    )
                )
            )
            started = time.monotonic()
            with (root / (task + "-validation.log")).open("w") as log:
                subprocess.run(
                    [str(python), str(worker), str(request), str(result)],
                    stdout=log,
                    stderr=log,
                    check=True,
                    timeout=60,
                )
            value = json.loads(result.read_text())
            if value["source_sha256"] != sha(audio):
                raise ValueError("Source hash mismatch")
            if name == "silence" and value["result"]["status"] != "undetermined":
                raise ValueError("Silence abstention failed")
            if (
                task == "track_beats"
                and name in ["tone_440", "high_band_12000", "stereo_distinction"]
                and value["result"]["status"] != "undetermined"
            ):
                raise ValueError("Steady-tone abstention failed")
            rows.append(
                dict(
                    fixture=name,
                    source_sha256=sha(audio),
                    duration_seconds=value["duration_seconds"],
                    peak_memory_mib=value["peak_memory_mib"],
                    wall_seconds=time.monotonic() - started,
                    status=value["result"]["status"],
                )
            )
        receipt = root / (task + "-validation.json")
        report = dict(
            status="passed",
            task=task,
            scope="Synthetic local integration and abstention; not domain accuracy validation",
            max_input_seconds=min(row["duration_seconds"] for row in rows),
            peak_memory_mib=max(row["peak_memory_mib"] for row in rows),
            worker_sha256=sha(worker),
            checkpoint_sha256=sha(checkpoint),
            fixtures=rows,
        )
        receipt.write_text(json.dumps(report, indent=2) + "\n")
        # Include source and installed inference code, since a version label is insufficient.
        paths = [worker, checkpoint, license, receipt, lock, python.resolve()]
        paths += list(repository.rglob("*.py"))
        if task == "tag_events":
            paths.append(repository / "metadata/class_labels_indices.csv")
        if task == "track_beats":
            installed = subprocess.check_output(
                [
                    str(python),
                    "-c",
                    "import beat_this; print(next(iter(beat_this.__path__)))",
                ],
                text=True,
            ).strip()
            paths += list(Path(installed).rglob("*.py"))
        files = {str(p): sha(p) for p in paths if "__pycache__" not in p.parts}
        manifest = dict(
            contract="earworm/model-deployment/v1",
            id=pin["adapter"] + "-" + pin["sha256"][:12],
            owner="oida",
            adapter=pin["adapter"],
            capabilities=[task],
            components=[
                dict(
                    id=pin["checkpoint"], revision=pin["sha256"], sha256=pin["sha256"]
                ),
                source_component(repository, revision),
            ],
            runtime_revision=sha(worker),
            license_review=sha(license),
            validation_receipt=sha(receipt),
            enabled=True,
            provisioned=True,
            max_input_seconds=report["max_input_seconds"],
            max_output_seconds=0,
            measured_peak_memory_mib=report["peak_memory_mib"],
        )
        entries.append(
            dict(
                task=task,
                manifest=manifest,
                files=files,
                python=str(python),
                repository=str(repository),
                checkpoint=str(checkpoint),
                receipt=str(receipt),
                license=str(license),
                environment_lock=str(lock),
            )
        )
    destination = root / "deployments.json"
    temporary = root / "deployments.json.tmp"
    temporary.write_text(json.dumps(dict(deployments=entries), indent=2) + "\n")
    temporary.chmod(0o600)
    temporary.replace(destination)
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--oida", type=Path, required=True)
    parser.add_argument("--fixtures", type=Path, required=True)
    args = parser.parse_args()
    print(prepare(args.root, args.oida, args.fixtures))
