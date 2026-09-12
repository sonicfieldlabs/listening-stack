import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from listening_stack.candidate import verify, install, CONTRACT, PHASE5, PHASE7


class CandidateTests(unittest.TestCase):
    def fixture(self, root):
        wheels = []
        for name in (
            "sonicfield-oida",
            "akousma",
            "akousmata",
            "akouo-contract",
            "sonicfield-listening-stack",
            "listeningstackweb",
        ):
            file = name.replace("-", "_") + "-1.0-py3-none-any.whl"
            p = root / file
            with zipfile.ZipFile(p, "w") as z:
                z.writestr(
                    name + ".dist-info/METADATA", f"Name: {name}\nVersion: 1.0\n"
                )
            wheels.append(
                dict(
                    file=file,
                    distribution=name,
                    version="1.0",
                    sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
                )
            )
        manifest = root / "manifest.json"
        manifest.write_text(
            json.dumps(dict(contract=CONTRACT, published=False, wheels=wheels))
        )
        return manifest

    def test_tampering_refused_before_environment_or_subprocess(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self.fixture(root)
            verify(manifest)
            first = json.loads(manifest.read_text())["wheels"][0]["file"]
            (root / first).write_bytes(b"tampered")
            with patch("listening_stack.candidate.subprocess.run") as run:
                with self.assertRaisesRegex(ValueError, "checksum"):
                    install(manifest, root / "target")
                run.assert_not_called()
                self.assertFalse((root / "target").exists())

    def test_existing_environment_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self.fixture(root)
            with patch("listening_stack.candidate.subprocess.run") as run:
                with self.assertRaisesRegex(ValueError, "existing environments"):
                    install(manifest, root)
                run.assert_not_called()

    def test_paths_duplicates_and_release_promotion_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self.fixture(root)
            base = json.loads(manifest.read_text())
            for mutation in ("path", "duplicate", "published"):
                value = json.loads(json.dumps(base))
                if mutation == "path":
                    value["wheels"][0]["file"] = "../outside.whl"
                elif mutation == "duplicate":
                    value["wheels"].append(value["wheels"][0])
                else:
                    value["published"] = True
                manifest.write_text(json.dumps(value))
                with self.assertRaises(ValueError):
                    verify(manifest)

    def test_phase5_requires_matching_contract_versions_before_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self.fixture(root)
            value = json.loads(manifest.read_text())
            value["compatibility_profile"] = "centaur-phase5/v1"
            manifest.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, "Candidate profile"):
                verify(manifest)
            wheels = []
            for name, version in PHASE5.items():
                path = root / (
                    name.replace("-", "_") + "-" + version + "-py3-none-any.whl"
                )
                with zipfile.ZipFile(path, "w") as archive:
                    archive.writestr(
                        name + ".dist-info/METADATA",
                        f"Name: {name}\nVersion: {version}\n",
                    )
                wheels.append(
                    dict(
                        file=path.name,
                        distribution=name,
                        version=version,
                        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    )
                )
            value["wheels"] = wheels
            manifest.write_text(json.dumps(value))
            self.assertEqual(
                verify(manifest)["compatibility_profile"], "centaur-phase5/v1"
            )

    def test_phase7_requires_matching_contract_versions_before_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self.fixture(root)
            value = json.loads(manifest.read_text())
            value["compatibility_profile"] = "centaur-phase7/v1"
            manifest.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, "Candidate profile"):
                verify(manifest)
            wheels = []
            for name, version in PHASE7.items():
                path = root / (
                    name.replace("-", "_") + "-" + version + "-py3-none-any.whl"
                )
                with zipfile.ZipFile(path, "w") as archive:
                    archive.writestr(
                        name + ".dist-info/METADATA",
                        f"Name: {name}\nVersion: {version}\n",
                    )
                wheels.append(
                    dict(
                        file=path.name,
                        distribution=name,
                        version=version,
                        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    )
                )
            value["wheels"] = wheels
            manifest.write_text(json.dumps(value))
            self.assertEqual(
                verify(manifest)["compatibility_profile"], "centaur-phase7/v1"
            )
