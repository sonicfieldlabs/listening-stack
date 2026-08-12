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
    germ_interoperability_metadata,
    MEMORY_ACCOUNT_CAPABILITIES,
    MODELS,
    REPOSITORIES,
)
from listening_stack.doctor import (  # noqa: E402
    OIDA_SCHEMA_PATHS,
    _check_germ_boundary,
    _check_germ_interoperability,
    _check_model,
    _check_oida_accountability_contracts,
    _check_private_file,
    _check_repository,
    _fetch_local_json,
)


def _gateway_manifest():
    return {
        "version": "0.10.0",
        "contract": "oida/gateway/v0.6",
        "components": {
            "akouo": {"contract": "akouo/v0.9"},
            "earworm": {
                "contract": "earworm/v0.7",
                "akousma_schema": "1.6",
            },
            "akousmata": {"contract": "akousmata/v0.7"},
        },
        "schemas": {
            "host_perception": "/gateway/schema/host-perception",
            "listening_event": "/gateway/schema/listening-event",
            "listening_context": "/gateway/schema/listening-context",
            "route_outcome": "/gateway/schema/route-outcome",
        },
        "memory_accounts": dict(MEMORY_ACCOUNT_CAPABILITIES),
    }


class DoctorTests(unittest.TestCase):
    def test_germ_interoperability_state_is_compared_to_current_release_set(self):
        current = {"germ_interoperability": germ_interoperability_metadata()}
        self.assertEqual(_check_germ_interoperability(current).status, "pass")
        current["germ_interoperability"]["contracts"]["masa_version"] = "0.1.0"
        self.assertEqual(_check_germ_interoperability(current).status, "warn")

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
        self.assertIn("v0.10.0", check.detail)

    def test_oida_live_contracts_verify_manifest_and_four_schemas(self):
        manifest = _gateway_manifest()
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
        self.assertEqual(
            [call.args[1] for call in fetch.call_args_list],
            ["/gateway", *list(OIDA_SCHEMA_PATHS.values())],
        )
        self.assertEqual(len(checks), 6)
        self.assertTrue(all(check.status == "pass" for check in checks))

    def test_oida_live_contracts_fail_closed_on_semantic_drift(self):
        manifest = _gateway_manifest()
        manifest["components"]["earworm"]["contract"] = "earworm/v0.5"
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
        by_name = {check.name: check for check in checks}
        self.assertEqual(by_name["contract:oida-gateway"].status, "fail")
        self.assertEqual(by_name["schema:listening-event"].status, "fail")

    def test_oida_memory_account_capabilities_fail_closed(self):
        manifest = _gateway_manifest()
        manifest["memory_accounts"]["machine_core_immutable"] = False
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
        ):
            checks = _check_oida_accountability_contracts("http://127.0.0.1:8765")
        by_name = {check.name: check for check in checks}
        self.assertEqual(by_name["contract:oida-gateway"].status, "pass")
        self.assertEqual(by_name["capability:memory-accounts"].status, "fail")
        self.assertIn(
            "machine_core_immutable=False",
            by_name["capability:memory-accounts"].detail,
        )

    def test_gateway_contract_fetch_rejects_non_loopback_urls(self):
        with self.assertRaisesRegex(ValueError, "loopback"):
            _fetch_local_json("https://example.com", "/gateway")

    def test_gateway_contract_fetch_is_an_explicit_bodyless_get(self):
        class Response:
            def __init__(self, url):
                self.url = url

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def geturl(self):
                return self.url

            def read(self, _limit):
                return b"{}"

        def open_request(request, *, timeout):
            self.assertEqual(request.get_method(), "GET")
            self.assertIsNone(request.data)
            self.assertEqual(timeout, 2.0)
            return Response(request.full_url)

        with patch("listening_stack.doctor.urlopen", side_effect=open_request):
            self.assertEqual(
                _fetch_local_json("http://127.0.0.1:8765", "/gateway"),
                {},
            )


if __name__ == "__main__":
    unittest.main()
