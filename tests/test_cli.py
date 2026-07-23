from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from listening_stack.cli import main  # noqa: E402


class CliTests(unittest.TestCase):
    def test_models_json(self):
        output = StringIO()
        with redirect_stdout(output):
            main(["models", "--json"])
        self.assertIn("moss-4b-instruct", output.getvalue())
        self.assertIn("stable-small-sfx", output.getvalue())

    def test_noninteractive_dry_run(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = StringIO()
            with redirect_stdout(output):
                main(
                    [
                        "install",
                        "--component",
                        "full",
                        "--no-models",
                        "--root",
                        str(Path(temporary) / "stack"),
                        "--yes",
                        "--dry-run",
                    ]
                )
            self.assertIn("Dry run complete", output.getvalue())
            self.assertIn("Oída v0.8.0", output.getvalue())
            self.assertIn("GERM v0.2.5", output.getvalue())
            self.assertIn("oida/gateway/v0.4", output.getvalue())
            self.assertIn("earworm/auditum/v1", output.getvalue())

    def test_models_and_no_models_are_mutually_exclusive(self):
        with self.assertRaises(SystemExit) as raised:
            main(["install", "--models", "none", "--no-models"])
        self.assertEqual(raised.exception.code, 2)

    def test_status_target_is_forwarded(self):
        output = StringIO()
        with (
            patch(
                "listening_stack.cli.runtime_status",
                return_value={"component": "full", "oida": {"running": False}},
            ) as mocked,
            redirect_stdout(output),
        ):
            main(["status", "oida", "--root", "/tmp/listening-stack-test"])
        mocked.assert_called_once_with(
            Path("/tmp/listening-stack-test").resolve(), "oida"
        )
        self.assertIn("component: full", output.getvalue())

    def test_json_doctor_failure_has_nonzero_exit(self):
        result = {
            "ok": False,
            "summary": {"pass": 0, "info": 0, "warn": 0, "fail": 1},
            "checks": [],
            "runtime": {},
        }
        output = StringIO()
        with (
            patch("listening_stack.cli.run_doctor", return_value=result),
            redirect_stdout(output),
            self.assertRaises(SystemExit) as raised,
        ):
            main(["doctor", "--json"])
        self.assertEqual(raised.exception.code, 1)
        self.assertIn('"ok": false', output.getvalue())


if __name__ == "__main__":
    unittest.main()
