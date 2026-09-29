import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from listening_stack.candidate import verify, install, CONTRACT, PHASE5, PHASE7, PHASE9, PHASE17, TELAR, KHIPU, KHIPU_SAFETY


class CandidateTests(unittest.TestCase):
    def test_safety_profile_refuses_old_dependency_versions_without_changing_history(self):
        self.assertEqual(KHIPU["akousma"], "0.8.1")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wheels = []
            for name, version in KHIPU_SAFETY.items():
                path = root / (name.replace("-", "_") + "-" + version + "-py3-none-any.whl")
                with zipfile.ZipFile(path, "w") as archive:
                    archive.writestr(name + ".dist-info/METADATA", f"Name: {name}\nVersion: {version}\n")
                wheels.append(dict(file=path.name, distribution=name, version=version, sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
            value = dict(contract=CONTRACT, published=False, compatibility_profile="khipu-safety/v1", wheels=wheels)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps(value))
            verify(manifest)
            value["compatibility_profile"] = "khipu-local/v1"
            manifest.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, "exact declared"):
                verify(manifest)
            value["compatibility_profile"] = "khipu-safety/v1"
            wheel = next(item for item in wheels if item["distribution"] == "akousma")
            with zipfile.ZipFile(root / wheel["file"], "w") as archive:
                archive.writestr("akousma.dist-info/METADATA", "Name: akousma\nVersion: 0.8.1\n")
            wheel.update(version="0.8.1", sha256=hashlib.sha256((root / wheel["file"]).read_bytes()).hexdigest())
            manifest.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, "exact declared"):
                verify(manifest)

    def test_khipu_profile_admits_the_renamed_wheel_and_refuses_it_beside_telar(self):
        self.assertEqual(KHIPU["sonicfield-khipu"], "0.5.0")
        self.assertNotIn("sonicfield-telar", KHIPU)
        self.assertEqual({k: v for k, v in KHIPU.items() if k != "sonicfield-khipu"},
                         {k: v for k, v in TELAR.items() if k != "sonicfield-telar"})
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wheels = []
            for name, version in [*KHIPU.items(), ("sonicfield-telar", "0.4.0")]:
                path = root / (name.replace("-", "_") + "-" + version + "-py3-none-any.whl")
                with zipfile.ZipFile(path, "w") as archive:
                    archive.writestr(name + ".dist-info/METADATA", f"Name: {name}\nVersion: {version}\n")
                wheels.append(dict(file=path.name, distribution=name, version=version, sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
            manifest = root / "manifest.json"
            value = dict(contract=CONTRACT, published=False, compatibility_profile="khipu-local/v1", wheels=wheels[:-1])
            manifest.write_text(json.dumps(value))
            self.assertEqual(verify(manifest)["compatibility_profile"], "khipu-local/v1")
            value["wheels"] = wheels
            manifest.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, "exactly one"):
                verify(manifest)

    def test_telar_profile_preserves_legacy_and_refuses_mixed_applications(self):
        self.assertIn("listeningstackweb", PHASE17)
        self.assertNotIn("listeningstackweb", TELAR)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wheels = []
            for name, version in TELAR.items():
                path = root / (name.replace("-", "_") + "-" + version + "-py3-none-any.whl")
                with zipfile.ZipFile(path, "w") as archive:
                    archive.writestr(name + ".dist-info/METADATA", f"Name: {name}\nVersion: {version}\n")
                wheels.append(dict(file=path.name, distribution=name, version=version, sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
            value = dict(contract=CONTRACT, published=False, compatibility_profile="telar-local/v1", wheels=wheels)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps(value))
            self.assertEqual(verify(manifest)["compatibility_profile"], "telar-local/v1")
            value["compatibility_profile"] = "centaur-phase17/v1"
            manifest.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, "Candidate profile"):
                verify(manifest)
            value["compatibility_profile"] = "telar-local/v1"
            legacy = root / "listeningstackweb-0.4.0-py3-none-any.whl"
            with zipfile.ZipFile(legacy, "w") as archive:
                archive.writestr("listeningstackweb.dist-info/METADATA", "Name: listeningstackweb\nVersion: 0.4.0\n")
            wheels.append(dict(file=legacy.name, distribution="listeningstackweb", version="0.4.0", sha256=hashlib.sha256(legacy.read_bytes()).hexdigest()))
            manifest.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, "exactly one"):
                verify(manifest)

    def test_phase17_preserves_historical_profiles_and_refuses_wrong_central(self):
        self.assertEqual(PHASE9["listeningstackweb"], "0.2.1")
        self.assertEqual(PHASE17["listeningstackweb"], "0.4.0")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for central_version in ("0.4.0", "0.2.1"):
                wheels = []
                for name, version in {**PHASE17, "listeningstackweb": central_version}.items():
                    path = root / (name.replace("-", "_") + "-" + version + "-py3-none-any.whl")
                    with zipfile.ZipFile(path, "w") as archive:
                        archive.writestr(name + ".dist-info/METADATA", f"Name: {name}\nVersion: {version}\n")
                    wheels.append(dict(file=path.name, distribution=name, version=version,
                                       sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
                manifest = root / "manifest.json"
                manifest.write_text(json.dumps(dict(contract=CONTRACT, published=False,
                    compatibility_profile="centaur-phase17/v1", wheels=wheels)))
                if central_version == "0.4.0":
                    self.assertEqual(verify(manifest)["compatibility_profile"], "centaur-phase17/v1")
                else:
                    with patch("listening_stack.candidate.subprocess.run") as run:
                        with self.assertRaisesRegex(ValueError, "Candidate profile"):
                            install(manifest, root / "candidate")
                        run.assert_not_called()
                        self.assertFalse((root / "candidate").exists())

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

    def test_phase9_requires_matching_contract_versions_before_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self.fixture(root)
            value = json.loads(manifest.read_text())
            value["compatibility_profile"] = "centaur-phase9/v1"
            manifest.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, "Candidate profile"):
                verify(manifest)
            wheels = []
            for name, version in PHASE9.items():
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
                verify(manifest)["compatibility_profile"], "centaur-phase9/v1"
            )
