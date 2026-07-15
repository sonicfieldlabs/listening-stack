from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import sys
import tempfile
import unittest


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


if __name__ == "__main__":
    unittest.main()
