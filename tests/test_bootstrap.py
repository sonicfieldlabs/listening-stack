import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class BootstrapTests(unittest.TestCase):
    def fixture(
        self,
        temporary: str,
        checksum_name: str = "listening-stack.pyz",
        checksum_extra: str = "",
    ):
        root = Path(temporary)
        fixtures = root / "fixtures"
        fake_bin = root / "fake-bin"
        install_bin = root / "installed-bin"
        temp_dir = root / "tmp"
        home = root / "home"
        for directory in (fixtures, fake_bin, temp_dir, home):
            directory.mkdir(parents=True)

        executable = fixtures / "listening-stack.pyz"
        executable.write_text(
            "#!/usr/bin/env bash\nprintf 'dummy:%s\\n' \"$*\"\n",
            encoding="utf-8",
        )
        digest = hashlib.sha256(executable.read_bytes()).hexdigest()
        (fixtures / "listening-stack.pyz.sha256").write_text(
            "%s  %s\n%s" % (digest, checksum_name, checksum_extra), encoding="utf-8"
        )

        curl = fake_bin / "curl"
        curl.write_text(
            """#!/usr/bin/env python3
import os
from pathlib import Path
import shutil
import sys

arguments = sys.argv[1:]
destination = Path(arguments[arguments.index("-o") + 1])
url = next(value for value in arguments if value.startswith("https://"))
name = "listening-stack.pyz.sha256" if url.endswith(".sha256") else "listening-stack.pyz"
shutil.copyfile(Path(os.environ["BOOTSTRAP_FIXTURES"]) / name, destination)
""",
            encoding="utf-8",
        )
        os.chmod(curl, 0o755)
        environment = os.environ.copy()
        environment.update(
            {
                "BOOTSTRAP_FIXTURES": str(fixtures),
                "HOME": str(home),
                "LISTENING_STACK_BIN_DIR": str(install_bin),
                "LISTENING_STACK_VERSION": "v0.3.3",
                "PATH": str(fake_bin) + os.pathsep + environment.get("PATH", ""),
                "TMPDIR": str(temp_dir),
            }
        )
        return install_bin, environment

    def test_noninteractive_arguments_run_without_a_controlling_terminal(self):
        with tempfile.TemporaryDirectory() as temporary:
            install_bin, environment = self.fixture(temporary)
            result = subprocess.run(
                ["bash", str(ROOT / "install.sh"), "models", "--json"],
                env=environment,
                stdin=subprocess.DEVNULL,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("dummy:models --json", result.stdout)
            self.assertTrue((install_bin / "listening-stack").is_file())
            self.assertFalse(list(install_bin.glob(".listening-stack.*")))

    def test_explicit_destination_works_when_home_is_unset(self):
        with tempfile.TemporaryDirectory() as temporary:
            _install_bin, environment = self.fixture(temporary)
            environment.pop("HOME", None)
            result = subprocess.run(
                ["bash", str(ROOT / "install.sh"), "models", "--json"],
                env=environment,
                stdin=subprocess.DEVNULL,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_additional_checksum_line_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            install_bin, environment = self.fixture(
                temporary,
                checksum_extra="0" * 64 + "  listening-stack.pyz\n",
            )
            result = subprocess.run(
                ["bash", str(ROOT / "install.sh"), "models", "--json"],
                env=environment,
                stdin=subprocess.DEVNULL,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unexpected format", result.stderr)
            self.assertFalse((install_bin / "listening-stack").exists())

    def test_invalid_release_tag_is_rejected_before_download(self):
        with tempfile.TemporaryDirectory() as temporary:
            install_bin, environment = self.fixture(temporary)
            environment["LISTENING_STACK_VERSION"] = "v0.3.3/../../unexpected"
            result = subprocess.run(
                ["bash", str(ROOT / "install.sh"), "models", "--json"],
                env=environment,
                stdin=subprocess.DEVNULL,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("semantic version", result.stderr)
            self.assertFalse((install_bin / "listening-stack").exists())

    def test_checksum_filename_injection_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            install_bin, environment = self.fixture(
                temporary, checksum_name="../../unexpected"
            )
            result = subprocess.run(
                ["bash", str(ROOT / "install.sh"), "models", "--json"],
                env=environment,
                stdin=subprocess.DEVNULL,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unexpected format", result.stderr)
            self.assertFalse((install_bin / "listening-stack").exists())


if __name__ == "__main__":
    unittest.main()
