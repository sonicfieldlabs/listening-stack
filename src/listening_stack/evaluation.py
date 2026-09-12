"""Private deterministic fixtures for transport/view checks, not model quality claims."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import struct
import wave


def create_evaluation(root: Path) -> Path:
    root = Path(root)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    manifest_path = root / "manifest.json"
    if manifest_path.exists():
        raise FileExistsError(
            "Evaluation baseline already exists; verify instead of overwriting"
        )
    entries = []
    for name in (
        "silence",
        "tone_440",
        "high_band_12000",
        "stereo_distinction",
        "regular_impulses",
        "irregular_impulses",
    ):
        rate, channels, seconds = 48000, 2, 2
        frames = bytearray()
        impulses = {1200, 7200, 23000, 51000, 74000}
        for i in range(rate * seconds):
            left = right = 0.0
            if name == "tone_440":
                left = right = 0.2 * math.sin(2 * math.pi * 440 * i / rate)
            if name == "high_band_12000":
                left = right = 0.2 * math.sin(2 * math.pi * 12000 * i / rate)
            if name == "stereo_distinction":
                left = 0.2 * math.sin(2 * math.pi * 440 * i / rate)
                right = 0.2 * math.sin(2 * math.pi * 880 * i / rate)
            if name == "regular_impulses" and i % 12000 < 24:
                left = right = 0.2
            if name == "irregular_impulses" and i in impulses:
                left = right = 0.2
            frames.extend(struct.pack("<hh", round(left * 32767), round(right * 32767)))
        path = root / f"{name}.wav"
        if path.exists():
            raise FileExistsError(path)
        with wave.open(str(path), "wb") as stream:
            stream.setparams((channels, 2, rate, 0, "NONE", "not compressed"))
            stream.writeframes(frames)
        path.chmod(0o600)
        entries.append(
            dict(
                file=path.name,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                sample_rate_hz=rate,
                channels=channels,
                duration_seconds=seconds,
                label_basis="deterministic synthesis; not environmental or perceptual ground truth",
                split="transport_regression",
            )
        )
    manifest_path.write_text(
        json.dumps(
            dict(
                contract="listening-stack/private-evaluation/v1",
                fixtures=entries,
                quality_holdout_status="Human-curated speech/music/field holdout required before model promotion",
            ),
            indent=2,
        )
        + "\n"
    )
    manifest_path.chmod(0o600)
    return manifest_path


def verify_evaluation(root: Path) -> list[str]:
    root = Path(root).resolve()
    manifest = json.loads((root / "manifest.json").read_text())
    errors = []
    for item in manifest["fixtures"]:
        path = (root / item["file"]).resolve()
        if path.parent != root:
            errors.append("fixture outside private evaluation root")
            continue
        if (
            not path.is_file()
            or hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]
        ):
            errors.append(f"fixture changed: {item['file']}")
    return errors
