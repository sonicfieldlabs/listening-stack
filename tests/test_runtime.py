import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from listening_stack.runtime import (  # noqa: E402
    _environment,
    _health_identity,
    _health_url,
    _pid_is_germ,
    start,
    status,
)


class RuntimeTests(unittest.TestCase):
    def write_state(self, root: Path, **changes):
        state = {
            "schema_version": 1,
            "installer_version": "0.2.0",
            "root": str(root),
            "component": "full",
            "models": [],
            "provider": "mock",
            "integrations": [],
            "commits": {},
            "environment": {
                "OIDA_HOST": "127.0.0.1",
                "OIDA_PORT": "9876",
                "GERM_HOST": "127.0.0.1",
                "GERM_PORT": "9877",
            },
        }
        state.update(changes)
        directory = root / ".listening-stack"
        directory.mkdir(parents=True)
        (directory / "state.json").write_text(json.dumps(state), encoding="utf-8")

    def test_status_filters_target_and_uses_recorded_port(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "stack"
            self.write_state(root)
            seen = []

            def fake_status(url):
                seen.append(url)
                return {"running": False, "url": url.rsplit("/health", 1)[0]}

            with patch("listening_stack.runtime._http_status", side_effect=fake_status):
                result = status(root, "germ")
            self.assertNotIn("oida", result)
            self.assertIn("germ", result)
            self.assertEqual(seen, ["http://127.0.0.1:9877/health"])

    def test_runtime_rejects_non_loopback_state(self):
        with self.assertRaisesRegex(ValueError, "must remain loopback"):
            _environment(
                {
                    "environment": {
                        "OIDA_HOST": "example.com",
                        "OIDA_PORT": "8765",
                        "GERM_HOST": "127.0.0.1",
                        "GERM_PORT": "5178",
                    }
                }
            )

    def test_runtime_normalizes_and_probes_configured_loopback_host(self):
        environment = _environment(
            {
                "environment": {
                    "OIDA_HOST": " ::1 ",
                    "OIDA_PORT": "9876",
                    "GERM_HOST": "localhost",
                    "GERM_PORT": " 9877 ",
                }
            }
        )
        self.assertEqual(_health_url(environment, "OIDA"), "http://[::1]:9876/health")
        self.assertEqual(
            _health_url(environment, "GERM"), "http://localhost:9877/health"
        )
        self.assertEqual(environment["GERM_PORT"], "9877")

    def test_start_refuses_an_unexpected_service_on_germ_port(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "stack"
            self.write_state(root, component="germ")
            unexpected = {
                "running": True,
                "url": "http://127.0.0.1:9877",
                "health": {"server": "not-germ"},
            }
            with patch("listening_stack.runtime._http_status", return_value=unexpected):
                with self.assertRaisesRegex(RuntimeError, "not germ"):
                    start(root, "germ")

    def test_status_marks_an_unexpected_service_as_not_running(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "stack"
            self.write_state(root, component="germ")
            unexpected = {
                "running": True,
                "url": "http://127.0.0.1:9877",
                "health": {"server": "another-service"},
            }
            with patch("listening_stack.runtime._http_status", return_value=unexpected):
                result = status(root, "germ")
            self.assertFalse(result["germ"]["running"])
            self.assertTrue(result["germ"]["identity_mismatch"])
            self.assertIn("not germ", result["germ"]["detail"])

    def test_failed_germ_start_terminates_new_process_and_clears_pid(self):
        class FakeProcess:
            pid = 4321
            returncode = None

            def __init__(self):
                self.terminated = False

            def poll(self):
                return self.returncode

            def terminate(self):
                self.terminated = True

            def wait(self, timeout):
                self.returncode = -15
                return self.returncode

            def kill(self):
                self.returncode = -9

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "stack"
            self.write_state(root, component="germ")
            process = FakeProcess()
            with (
                patch(
                    "listening_stack.runtime._http_status",
                    return_value={"running": False},
                ),
                patch("listening_stack.runtime.subprocess.Popen", return_value=process),
                patch(
                    "listening_stack.runtime._process_start_token", return_value="now"
                ),
                patch(
                    "listening_stack.runtime._wait_for",
                    side_effect=RuntimeError("not ready"),
                ),
            ):
                with self.assertRaisesRegex(RuntimeError, "not ready"):
                    start(root, "germ")
            self.assertTrue(process.terminated)
            runtime = json.loads(
                (root / ".listening-stack" / "runtime.json").read_text(encoding="utf-8")
            )
            self.assertEqual(runtime, {})

    def test_health_identity_supports_both_upstream_contracts(self):
        self.assertEqual(_health_identity({"health": {"name": "oida"}}), "oida")
        self.assertEqual(_health_identity({"health": {"server": "germ"}}), "germ")

    def test_pid_identity_checks_recorded_start_token(self):
        command = "uv run uvicorn server.main:app"
        with (
            patch("subprocess.check_output", return_value=command),
            patch("listening_stack.runtime._process_start_token", return_value="now"),
        ):
            self.assertTrue(_pid_is_germ(123, "now"))
            self.assertFalse(_pid_is_germ(123, "earlier"))


if __name__ == "__main__":
    unittest.main()
