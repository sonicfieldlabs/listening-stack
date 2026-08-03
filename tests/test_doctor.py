import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from listening_stack.catalog import (  # noqa: E402
    ACCOUNTABLE_LISTENING_CONTRACTS,
    MODELS,
    REPOSITORIES,
)
from listening_stack.doctor import (  # noqa: E402
    _check_germ_boundary,
    _check_model,
    _check_oida_accountability_contracts,
    _check_private_file,
    _check_repository,
    _fetch_local_json,
)


class DoctorTests(unittest.TestCase):
    def test_germ_boundary_accepts_only_the_installer_local_paths(self):
        root = Path("/tmp/listening-stack-fixture")
        environment = {
            "GERM_ALLOWED_HOSTS": "localhost,127.0.0.1",
            "GERM_ALLOWED_INPUT_ROOTS": ",".join(
                (
                    str(root / "data" / "germ"),
                    str(root / "data" / "audio"),
                    str(root / "data" / "akousmata"),
                )
            ),
            "GERM_ALLOWED_MODEL_ROOTS": ",".join(
                (
                    str(root / "vendor" / "stable-audio-3"),
                    str(root / "models"),
                    str(root / "data" / "germ"),
                )
            ),
            "GERM_ENABLE_CLOUD_VISION": "0",
            "GERM_OIDA_URL": "http://127.0.0.1:8765",
        }
        self.assertEqual(_check_germ_boundary(root, environment).status, "pass")
        environment["GERM_ALLOWED_INPUT_ROOTS"] += ",/tmp"
        self.assertEqual(_check_germ_boundary(root, environment).status, "warn")

    def test_private_state_file_warns_on_group_or_world_access(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "state.json"
            path.write_text("{}", encoding="utf-8")
            os.chmod(path, 0o644)
            self.assertEqual(_check_private_file("state", path).status, "warn")
            os.chmod(path, 0o600)
            self.assertEqual(_check_private_file("state", path).status, "pass")

    def test_private_state_file_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "target.json"
            target.write_text("{}", encoding="utf-8")
            link = root / "state.json"
            link.symlink_to(target)
            self.assertEqual(_check_private_file("state", link).status, "fail")

    def test_oida_model_requires_config_and_safetensors(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            model = MODELS["moss-4b-instruct"]
            model_root = (
                root / "models" / "moss-audio" / model.model_id.rsplit("/", 1)[-1]
            )
            model_root.mkdir(parents=True)
            (model_root / "config.json").write_text("{}", encoding="utf-8")
            self.assertEqual(
                _check_model(
                    root, root / "models" / "huggingface" / "hub", model
                ).status,
                "warn",
            )
            (model_root / "model.safetensors").write_bytes(b"fixture")
            self.assertEqual(
                _check_model(
                    root, root / "models" / "huggingface" / "hub", model
                ).status,
                "pass",
            )

    def test_repository_accepts_equivalent_ssh_origin_and_pinned_commit(self):
        spec = REPOSITORIES["oida"]

        def output(command, **_kwargs):
            if command[1:3] == ["remote", "get-url"]:
                return "git@github.com:sonicfieldlabs/oida.git\n"
            if command[1:3] == ["rev-parse", "HEAD"]:
                return spec.revision + "\n"
            return ""

        with (
            tempfile.TemporaryDirectory() as temporary,
            patch("subprocess.check_output", side_effect=output),
        ):
            (Path(temporary) / ".git").mkdir()
            check = _check_repository(Path(temporary), "oida", spec.revision)
        self.assertEqual(check.status, "pass")
        self.assertIn("v0.9.1", check.detail)

    def test_oida_live_contracts_verify_manifest_and_four_schemas(self):
        manifest = {
            "version": "0.9.1",
            "contract": "oida/gateway/v0.5",
            "components": {
                "akouo": {"contract": "akouo/v0.9"},
                "earworm": {"contract": "earworm/v0.6"},
                "akousmata": {"contract": "akousmata/v0.6"},
            },
            "schemas": {
                "host_perception": "/gateway/schema/host-perception",
                "listening_event": "/gateway/schema/listening-event",
                "listening_context": "/gateway/schema/listening-context",
                "route_outcome": "/gateway/schema/route-outcome",
            },
        }
        schemas = [
            {"properties": {"contract": {"const": contract}}}
            for contract in (
                ACCOUNTABLE_LISTENING_CONTRACTS["host_perception"],
                ACCOUNTABLE_LISTENING_CONTRACTS["listening_event"],
                ACCOUNTABLE_LISTENING_CONTRACTS["listening_context"],
                ACCOUNTABLE_LISTENING_CONTRACTS["route_outcome"],
            )
        ]
        with patch(
            "listening_stack.doctor._fetch_local_json",
            side_effect=[manifest, *schemas],
        ) as fetch:
            checks = _check_oida_accountability_contracts("http://127.0.0.1:8765")
        self.assertEqual(fetch.call_count, 5)
        self.assertEqual(len(checks), 5)
        self.assertTrue(all(check.status == "pass" for check in checks))

    def test_oida_live_contracts_fail_closed_on_semantic_drift(self):
        manifest = {
            "version": "0.9.1",
            "contract": "oida/gateway/v0.5",
            "components": {
                "akouo": {"contract": "akouo/v0.9"},
                "earworm": {"contract": "earworm/v0.5"},
                "akousmata": {"contract": "akousmata/v0.6"},
            },
            "schemas": {
                "host_perception": "/gateway/schema/host-perception",
                "listening_event": "/gateway/schema/listening-event",
                "listening_context": "/gateway/schema/listening-context",
                "route_outcome": "/gateway/schema/route-outcome",
            },
        }
        schemas = [
            {"properties": {"contract": {"const": contract}}}
            for contract in (
                ACCOUNTABLE_LISTENING_CONTRACTS["host_perception"],
                "oida/listening-event/v0.1",
                ACCOUNTABLE_LISTENING_CONTRACTS["listening_context"],
                ACCOUNTABLE_LISTENING_CONTRACTS["route_outcome"],
            )
        ]
        with patch(
            "listening_stack.doctor._fetch_local_json",
            side_effect=[manifest, *schemas],
        ):
            checks = _check_oida_accountability_contracts("http://localhost:8765")
        self.assertEqual(checks[0].status, "fail")
        self.assertEqual(checks[2].status, "fail")

    def test_gateway_contract_fetch_rejects_non_loopback_urls(self):
        with self.assertRaisesRegex(ValueError, "loopback"):
            _fetch_local_json("https://example.com", "/gateway")


if __name__ == "__main__":
    unittest.main()
