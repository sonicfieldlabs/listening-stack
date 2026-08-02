"""Installation orchestration for the listening core and optional GERM."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import platform
import shlex
import sys
from typing import Dict, List, Mapping, Sequence, Tuple

from . import __version__
from .catalog import (
    ACCOUNTABLE_LISTENING_CONTRACTS,
    ALL_REPOSITORIES,
    MODELS,
    MOSS_AUDIO_REPOSITORY,
    REPOSITORIES,
    STABLE_AUDIO_REPOSITORY,
    Model,
    Repository,
    normalize_profile,
    profile_includes,
    source_keys,
)
from .system import Runner, executable, is_apple_silicon


STATE_DIRECTORY = ".listening-stack"
STATE_FILENAME = "state.json"
ENV_FILENAME = "stack.env"
MAX_STATE_BYTES = 2 * 1024 * 1024
STATE_CONTRACT = "listening-stack/state/v2"
UV_VERSION = "0.11.29"
UV_INSTALLER_SHA256 = "504a79fd2ed0dcd47e7f04f0792cfd0871f62e24a7fe40fa8ae0f563a369f2bd"
HF_CLI_VERSION = "1.23.0"
ALLOWED_INTEGRATIONS = ("hermes", "codex", "claude", "openclaw", "opencode")


@dataclass
class Selection:
    component: str
    model_keys: List[str]
    integrations: List[str]
    provider: str
    root: Path
    accept_model_terms: bool = False
    install_system_dependencies: bool = True
    start_after_install: bool = False


def state_path(root: Path) -> Path:
    return root / STATE_DIRECTORY / STATE_FILENAME


def environment_path(root: Path) -> Path:
    return root / STATE_DIRECTORY / ENV_FILENAME


def load_state(root: Path) -> Dict[str, object]:
    path = state_path(root)
    if path.is_symlink():
        raise ValueError("Refusing symlinked Listening Stack state at %s" % path)
    if not path.is_file():
        raise FileNotFoundError(
            "No Listening Stack installation state exists at %s" % path
        )
    if path.stat().st_size > MAX_STATE_BYTES:
        raise ValueError("Listening Stack state is unexpectedly large at %s" % path)
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict) or value.get("schema_version") not in {1, 2}:
        raise ValueError("Unsupported or invalid Listening Stack state at %s" % path)
    profile = str(value.get("profile") or value.get("component") or "")
    try:
        canonical_profile = normalize_profile(profile)
    except ValueError as exc:
        raise ValueError(
            "Listening Stack state has an invalid profile at %s" % path
        ) from exc
    if value.get("schema_version") == 2:
        if (
            value.get("contract") != STATE_CONTRACT
            or value.get("profile") != canonical_profile
            or value.get("component") != canonical_profile
        ):
            raise ValueError("Listening Stack state has an invalid contract at %s" % path)
        components = value.get("components")
        if not isinstance(components, list) or components != list(
            source_keys(canonical_profile)
        ):
            raise ValueError(
                "Listening Stack state has an invalid component set at %s" % path
            )
        expected_optional = ["germ"] if canonical_profile == "full" else []
        if value.get("core_components") != list(source_keys("core")) or value.get(
            "optional_components"
        ) != expected_optional:
            raise ValueError(
                "Listening Stack state has invalid profile metadata at %s" % path
            )
        if not isinstance(value.get("contracts"), dict) or not isinstance(
            value.get("repositories"), dict
        ):
            raise ValueError(
                "Listening Stack state has no valid compatibility metadata at %s"
                % path
            )
    if not isinstance(value.get("environment"), dict):
        raise ValueError("Listening Stack state has no valid environment at %s" % path)
    if not isinstance(value.get("commits"), dict):
        raise ValueError("Listening Stack state has no valid commit map at %s" % path)
    return value


class Installer:
    def __init__(self, selection: Selection, runner: Runner) -> None:
        self.selection = selection
        self.profile = normalize_profile(selection.component)
        self.runner = runner
        self.root = selection.root.expanduser().resolve()
        self.src_root = self.root / "src"
        self.vendor_root = self.root / "vendor"
        self.models_root = self.root / "models"
        self.hf_home = self.models_root / "huggingface"
        self.commits: Dict[str, str] = {}
        self.model_revisions: Dict[str, str] = {}
        self.uv = executable("uv") or "uv"
        self.hf = str(self.root / STATE_DIRECTORY / "bin" / "hf")

    @property
    def models(self) -> List[Model]:
        return [MODELS[key] for key in self.selection.model_keys]

    def install(self) -> Dict[str, object]:
        self._validate_selection()
        self._heading("Preparing installation root")
        self._make_directories()

        self._heading("Checking system dependencies")
        self._ensure_base_tools()
        self._ensure_uv()
        self._ensure_python()
        self._ensure_ffmpeg()

        self._heading("Installing Sonic Field sources")
        self._install_sources()

        if any(model.application == "oida" for model in self.models):
            self._heading("Preparing the MOSS-Audio runtime")
            self._install_upstream(
                MOSS_AUDIO_REPOSITORY, self.vendor_root / "MOSS-Audio"
            )

        if any(model.application == "germ" for model in self.models):
            self._heading("Preparing the Stable Audio 3 runtime")
            self._install_upstream(
                STABLE_AUDIO_REPOSITORY, self.vendor_root / "stable-audio-3"
            )

        self._heading("Creating application environments")
        self._sync_applications()

        if self.models:
            self._heading("Downloading selected models")
            self._ensure_hf()
            self._download_models()

        environment = self._environment()
        self._heading("Writing local configuration")
        self._write_environment(environment)

        self._heading("Verifying application imports")
        self._verify_installation(environment)

        if self.selection.integrations:
            self._heading("Installing selected agent integrations")
            self._install_integrations(environment)

        self._heading("Recording completed installation state")
        return self._write_state(environment)

    def _validate_selection(self) -> None:
        self._validate_root()
        normalize_profile(self.selection.component)
        if self.selection.provider not in {"auto", "mlx", "python", "mock"}:
            raise ValueError("provider must be auto, mlx, python, or mock")
        unknown = [key for key in self.selection.model_keys if key not in MODELS]
        if unknown:
            raise ValueError("Unknown models: " + ", ".join(unknown))
        if len(set(self.selection.model_keys)) != len(self.selection.model_keys):
            raise ValueError("Model selections must not contain duplicates")
        allowed_apps = {
            application
            for application in ("oida", "germ")
            if profile_includes(self.profile, application)
        }
        wrong = [
            model.key for model in self.models if model.application not in allowed_apps
        ]
        if wrong:
            raise ValueError(
                "Models do not match the selected component: " + ", ".join(wrong)
            )
        invalid_integrations = [
            item
            for item in self.selection.integrations
            if item not in ALLOWED_INTEGRATIONS
        ]
        if invalid_integrations:
            raise ValueError("Unknown integrations: " + ", ".join(invalid_integrations))
        if len(set(self.selection.integrations)) != len(self.selection.integrations):
            raise ValueError("Integration selections must not contain duplicates")
        if self.selection.integrations and not profile_includes(self.profile, "oida"):
            raise ValueError(
                "Agent integrations are supplied by Oída; install Oída or the full stack first"
            )
        if (
            any(model.gated for model in self.models)
            and not self.selection.accept_model_terms
        ):
            raise ValueError(
                "Stable Audio 3 weights are gated. Review their model pages and pass "
                "--accept-model-terms, or rerun interactively. The installer cannot accept terms for you."
            )
        if (
            any(model.application == "germ" for model in self.models)
            and self.selection.provider == "mlx"
            and not is_apple_silicon()
        ):
            raise ValueError(
                "The Stable Audio 3 MLX provider requires Apple Silicon macOS"
            )
        if (
            any(model.application == "germ" for model in self.models)
            and self.selection.provider == "mock"
        ):
            raise ValueError(
                "Select the MLX or Python provider when downloading Stable Audio 3 models"
            )

    def _validate_root(self) -> None:
        anchor = Path(self.root.anchor)
        if self.root == anchor:
            raise ValueError("Refusing to use the filesystem root as an install root")
        try:
            home = Path.home().expanduser().resolve()
        except OSError:
            home = None
        if home is not None and self.root == home:
            raise ValueError("Refusing to use the home directory as an install root")
        enclosing_repository = next(
            (
                path
                for path in (self.root, *self.root.parents)
                if (path / ".git").exists()
            ),
            None,
        )
        if enclosing_repository is not None:
            raise ValueError(
                "Refusing to install inside an existing Git repository: %s"
                % enclosing_repository
            )
        if "," in str(self.root):
            raise ValueError(
                "The install root cannot contain a comma because GERM path allowlists are comma-separated"
            )

    def _make_directories(self) -> None:
        paths = [
            self.src_root,
            self.vendor_root,
            self.models_root,
            self.hf_home,
            self.models_root / "moss-audio",
            self.root / "data",
            self.root / "data" / "akousmata",
            self.root / "logs",
            self.root / "run",
            self.root / STATE_DIRECTORY,
            self.root / STATE_DIRECTORY / "bin",
            self.root / STATE_DIRECTORY / "tools",
        ]
        if profile_includes(self.profile, "oida"):
            paths.extend((self.root / "data" / "oida", self.root / "data" / "audio"))
        if profile_includes(self.profile, "germ"):
            paths.append(self.root / "data" / "germ")
        for path in paths:
            if path.is_symlink():
                raise RuntimeError(
                    "Refusing to use a symlinked managed directory: %s" % path
                )
            self.runner.note("  create %s" % path)
            if not self.runner.dry_run:
                path.mkdir(parents=True, exist_ok=True)

    def _ensure_base_tools(self) -> None:
        missing = [name for name in ("git", "curl") if not executable(name)]
        if missing:
            raise RuntimeError(
                "Missing required command(s): %s. Install them with your operating system package manager and rerun."
                % ", ".join(missing)
            )
        self.runner.note("  ✓ git")
        self.runner.note("  ✓ curl")
        self.runner.note("  ✓ Python %s" % platform.python_version())
        if sys.version_info < (3, 9):
            raise RuntimeError(
                "The installation assistant requires Python 3.9 or newer"
            )
        if sys.platform == "darwin" and not self.runner.dry_run:
            result = self.runner.capture(["xcode-select", "-p"], check=False)
            if not result:
                self.runner.note(
                    "  ! Xcode command-line tools are missing. Run: xcode-select --install"
                )

    def _ensure_uv(self) -> None:
        found = executable("uv")
        if found:
            self.uv = found
            self.runner.note("  ✓ uv at %s" % found)
            return
        if not self.selection.install_system_dependencies:
            raise RuntimeError(
                "uv is required. Install it from https://docs.astral.sh/uv/ and rerun."
            )
        self.runner.note(
            "  uv is missing; installing tested uv %s with Astral's official installer."
            % UV_VERSION
        )
        script = self.root / STATE_DIRECTORY / "uv-install.sh"
        self.runner.run(
            [
                executable("curl") or "curl",
                "--proto",
                "=https",
                "--tlsv1.2",
                "-LsSf",
                "https://astral.sh/uv/%s/install.sh" % UV_VERSION,
                "-o",
                str(script),
            ]
        )
        install_environment = {"UV_NO_MODIFY_PATH": "1"}
        if self.runner.dry_run:
            self.runner.run(["sh", str(script)], env=install_environment)
            return
        try:
            digest = hashlib.sha256(script.read_bytes()).hexdigest()
            if not hmac.compare_digest(digest, UV_INSTALLER_SHA256):
                raise RuntimeError(
                    "Refusing to run the uv installer because its SHA-256 checksum changed"
                )
            self.runner.run(["sh", str(script)], env=install_environment)
        finally:
            script.unlink(missing_ok=True)
        found = executable("uv")
        if not found:
            raise RuntimeError(
                "uv installation completed but the executable could not be found"
            )
        self.uv = found

    def _ensure_python(self) -> None:
        self.runner.run([self.uv, "python", "install", "3.12"])

    def _ensure_ffmpeg(self) -> None:
        if executable("ffmpeg"):
            self.runner.note("  ✓ ffmpeg")
            return
        if not self.selection.install_system_dependencies:
            self.runner.note("  ! ffmpeg is missing; audio decoding may be incomplete.")
            return
        if executable("brew"):
            self.runner.note("  Installing ffmpeg with Homebrew.")
            self.runner.run([executable("brew") or "brew", "install", "ffmpeg"])
            return
        if executable("apt-get"):
            self.runner.note("  Installing ffmpeg with apt.")
            prefix = [] if os.geteuid() == 0 else ["sudo"]
            self.runner.run(prefix + ["apt-get", "update"])
            self.runner.run(prefix + ["apt-get", "install", "-y", "ffmpeg"])
            return
        if executable("dnf"):
            prefix = [] if os.geteuid() == 0 else ["sudo"]
            self.runner.run(prefix + ["dnf", "install", "-y", "ffmpeg"])
            return
        self.runner.note(
            "  ! ffmpeg is missing and no supported package manager was found."
        )
        self.runner.note("    Install ffmpeg before using model-backed audio decoding.")

    def _source_keys(self) -> Tuple[str, ...]:
        return source_keys(self.profile)

    def _install_sources(self) -> None:
        for key in self._source_keys():
            spec = REPOSITORIES[key]
            self.commits[key] = self._install_repository(spec, self.src_root / key)

    def _install_upstream(self, spec: Repository, destination: Path) -> None:
        self.commits[spec.key] = self._install_repository(spec, destination)

    def _install_repository(self, spec: Repository, destination: Path) -> str:
        if destination.is_symlink():
            raise RuntimeError(
                "Refusing to use a symlinked repository destination: %s" % destination
            )
        if destination.exists() and not (destination / ".git").is_dir():
            raise RuntimeError(
                "Refusing to replace non-Git directory: %s" % destination
            )
        existing = (destination / ".git").is_dir()
        if existing:
            origin = self.runner.capture(
                ["git", "remote", "get-url", "origin"],
                cwd=destination,
                check=False,
            )
            if not origin:
                head = self.runner.capture(
                    ["git", "rev-parse", "--verify", "HEAD"],
                    cwd=destination,
                    check=False,
                )
                entries = [
                    path for path in destination.iterdir() if path.name != ".git"
                ]
                if head or entries:
                    raise RuntimeError(
                        "%s has no origin and is not an empty interrupted checkout"
                        % destination
                    )
                self.runner.run(
                    ["git", "remote", "add", "origin", spec.url], cwd=destination
                )
            elif _normalise_git_url(origin) != _normalise_git_url(spec.url):
                raise RuntimeError(
                    "%s has unexpected origin %s; expected %s"
                    % (destination, origin, spec.url)
                )
            dirty = self.runner.capture(
                ["git", "status", "--porcelain"], cwd=destination
            )
            if dirty:
                raise RuntimeError(
                    "Refusing to update dirty installation checkout: %s" % destination
                )
        else:
            self.runner.run(["git", "init", "--quiet", str(destination)])
            self.runner.run(
                ["git", "remote", "add", "origin", spec.url], cwd=destination
            )
        target = spec.revision or spec.ref
        self.runner.run(
            ["git", "fetch", "--depth", "1", "--no-tags", "origin", target],
            cwd=destination,
        )
        self.runner.run(["git", "checkout", "--detach", "FETCH_HEAD"], cwd=destination)
        commit = self.runner.capture(["git", "rev-parse", "HEAD"], cwd=destination)
        if spec.revision and commit and commit.lower() != spec.revision.lower():
            raise RuntimeError(
                "%s resolved to %s instead of pinned revision %s"
                % (spec.name, commit, spec.revision)
            )
        release = " v%s" % spec.version if spec.version else ""
        self.runner.note(
            "  ✓ %s%s at %s"
            % (spec.name, release, commit[:12] if commit else target[:12])
        )
        return commit or "planned"

    def _sync_applications(self) -> None:
        model_apps = {model.application for model in self.models}
        if profile_includes(self.profile, "oida"):
            command = [
                self.uv,
                "sync",
                "--locked",
                "--python",
                "3.12",
                "--extra",
                "songid",
            ]
            if "oida" in model_apps:
                command.extend(["--extra", "moss"])
            self.runner.run(command, cwd=self.src_root / "oida")
        if profile_includes(self.profile, "germ"):
            command = [self.uv, "sync", "--locked", "--python", "3.12"]
            provider = self._resolved_provider()
            if "germ" in model_apps and provider == "python":
                command.extend(["--extra", "python-provider"])
            self.runner.run(command, cwd=self.src_root / "germ")
            if "germ" in model_apps and provider == "python":
                self.runner.run(
                    [
                        self.uv,
                        "sync",
                        "--locked",
                        "--python",
                        "3.12",
                        "--extra",
                        "ui",
                        "--extra",
                        "lora",
                    ],
                    cwd=self.vendor_root / "stable-audio-3",
                )
            elif "germ" in model_apps and provider == "mlx":
                self.runner.run(
                    ["./install.sh"],
                    cwd=self.vendor_root / "stable-audio-3" / "optimized" / "mlx",
                )

    def _ensure_hf(self) -> None:
        binary = Path(self.hf)
        if binary.is_symlink():
            raise RuntimeError(
                "Refusing to use a symlinked Hugging Face CLI: %s" % binary
            )
        if binary.is_file() and os.access(binary, os.X_OK):
            version = self.runner.capture([str(binary), "--version"], check=False)
            if _reported_version(version) == HF_CLI_VERSION:
                self.runner.note(
                    "  ✓ dedicated Hugging Face CLI %s at %s" % (HF_CLI_VERSION, binary)
                )
                return
            self.runner.note(
                "  Replacing the dedicated Hugging Face CLI with tested version %s."
                % HF_CLI_VERSION
            )
        tool_environment = {
            "UV_TOOL_BIN_DIR": str(binary.parent),
            "UV_TOOL_DIR": str(self.root / STATE_DIRECTORY / "tools"),
        }
        self.runner.run(
            [
                self.uv,
                "tool",
                "install",
                "--force",
                "--python",
                "3.12",
                "huggingface_hub==%s" % HF_CLI_VERSION,
            ],
            env=tool_environment,
        )
        if not self.runner.dry_run and not (
            binary.is_file() and os.access(binary, os.X_OK)
        ):
            raise RuntimeError(
                "Hugging Face CLI installation completed but %s was not created"
                % binary
            )
        if not self.runner.dry_run:
            version = self.runner.capture([str(binary), "--version"], check=False)
            if _reported_version(version) != HF_CLI_VERSION:
                raise RuntimeError(
                    "Hugging Face CLI reports %s instead of pinned version %s"
                    % (version or "no version", HF_CLI_VERSION)
                )

    def _download_models(self) -> None:
        environment = {"HF_HOME": str(self.hf_home)}
        gated = [model for model in self.models if model.gated]
        if gated:
            status = self.runner.capture(
                [self.hf, "auth", "whoami"], env=environment, check=False
            )
            if not status and not self.runner.dry_run:
                print(
                    "\nStable Audio 3 access requires a Hugging Face account that has accepted each selected model's terms."
                )
                for model in gated:
                    print("  - %s" % model.url)
                self.runner.run([self.hf, "auth", "login"], env=environment)
        for model in self.models:
            command = [self.hf, "download", model.model_id]
            if model.application == "oida":
                destination = self._moss_model_path(model)
                if destination.is_symlink():
                    raise RuntimeError(
                        "Refusing to use a symlinked model destination: %s"
                        % destination
                    )
                if model.download_revision:
                    command.extend(["--revision", model.download_revision])
                command.extend(["--local-dir", str(destination)])
            self.runner.run(command, env=environment)
            if model.download_revision:
                self.model_revisions[model.key] = model.download_revision
            elif self.runner.dry_run:
                self.model_revisions[model.key] = "main"
            else:
                resolved = self._cached_hf_revision(model)
                if resolved:
                    self.model_revisions[model.key] = resolved

    def _cached_hf_revision(self, model: Model) -> str:
        repository = "models--" + model.model_id.replace("/", "--")
        reference = self.hf_home / "hub" / repository / "refs" / "main"
        try:
            revision = reference.read_text(encoding="utf-8").strip().lower()
        except OSError:
            return ""
        return revision if _is_commit_revision(revision) else ""

    def _moss_model_path(self, model: Model) -> Path:
        return self.models_root / "moss-audio" / model.model_id.rsplit("/", 1)[-1]

    def _resolved_provider(self) -> str:
        if not any(model.application == "germ" for model in self.models):
            return "mock"
        if self.selection.provider != "auto":
            return self.selection.provider
        return "mlx" if is_apple_silicon() else "python"

    def _environment(self) -> Dict[str, str]:
        akousmata_path = self.root / "data" / "akousmata"
        oida_audio = self.root / "data" / "audio"
        germ_output = self.root / "data" / "germ"
        stable_repo = self.vendor_root / "stable-audio-3"
        environment: Dict[str, str] = {
            "HF_HOME": str(self.hf_home),
            "AKOUSMATA_PATH": str(akousmata_path),
        }
        if profile_includes(self.profile, "oida"):
            environment.update(
                {
                    "OIDA_DATA_DIR": str(self.root / "data" / "oida"),
                    "OIDA_AUDIO_DIR": str(oida_audio),
                    "OIDA_HOST": "127.0.0.1",
                    "OIDA_PORT": "8765",
                    "OIDA_SERVER_URL": "http://127.0.0.1:8765",
                    "OIDA_ALLOW_HF_HUB": "0",
                }
            )
        if profile_includes(self.profile, "germ"):
            germ_input_roots = [str(germ_output), str(akousmata_path)]
            if self.profile == "full":
                germ_input_roots.append(str(oida_audio))
            environment.update(
                {
                    "GERM_HOST": "127.0.0.1",
                    "GERM_PORT": "5178",
                    "GERM_ALLOWED_HOSTS": "localhost,127.0.0.1",
                    "GERM_OUTPUT_DIR": str(germ_output),
                    "GERM_ALLOWED_INPUT_ROOTS": ",".join(germ_input_roots),
                    "GERM_ALLOWED_MODEL_ROOTS": ",".join(
                        (str(stable_repo), str(self.models_root), str(germ_output))
                    ),
                    "GERM_ENABLE_CLOUD_VISION": "0",
                    "GERM_OFFICIAL_REPO_DIR": str(stable_repo),
                    "GERM_MLX_REPO_DIR": str(stable_repo),
                }
            )
        if self.profile == "full":
            environment["OIDA_GERM_URL"] = "http://127.0.0.1:5178"
            environment["GERM_OIDA_URL"] = "http://127.0.0.1:8765"
        moss = [model for model in self.models if model.application == "oida"]
        if moss:
            instruct = _preferred_moss(moss, "instruct")
            thinking = _preferred_moss(moss, "thinking")
            environment.update(
                {
                    "OIDA_ENGINE_PROFILE": "mac-mps",
                    "OIDA_MOSS_AUDIO_REPO": str(self.vendor_root / "MOSS-Audio"),
                    "OIDA_MOSS_INSTRUCT_MODEL": str(self._moss_model_path(instruct)),
                    "OIDA_MOSS_THINKING_MODEL": str(self._moss_model_path(thinking)),
                    "OIDA_REQUIRE_MODEL": "1",
                    "OIDA_MOSS_PREWARM": "0",
                    "OIDA_MOSS_RESIDENT": "single",
                }
            )
        elif profile_includes(self.profile, "oida"):
            environment.update(
                {"OIDA_ENGINE_PROFILE": "stub", "OIDA_REQUIRE_MODEL": "0"}
            )
        if profile_includes(self.profile, "germ"):
            stable = [model for model in self.models if model.application == "germ"]
            provider = self._resolved_provider()
            environment["GERM_ACTIVE_PROVIDER"] = {
                "mlx": "stable_audio_mlx",
                "python": "stable_audio_python",
                "mock": "mock",
            }.get(provider, "mock")
            environment["GERM_DEFAULT_MODEL"] = _preferred_stable_model(stable)
        return environment

    def _write_environment(self, environment: Mapping[str, str]) -> None:
        path = environment_path(self.root)
        lines = [
            "# Generated by the Listening Stack installer. Contains paths and settings, never tokens."
        ]
        for key in sorted(environment):
            lines.append("%s=%s" % (key, shlex.quote(environment[key])))
        self.runner.note("  write %s" % path)
        if not self.runner.dry_run:
            _atomic_write(path, "\n".join(lines) + "\n", mode=0o600)

    def _write_state(self, environment: Mapping[str, str]) -> Dict[str, object]:
        repositories = {
            key: {
                "name": ALL_REPOSITORIES[key].name,
                "url": ALL_REPOSITORIES[key].url,
                "ref": ALL_REPOSITORIES[key].ref,
                "version": ALL_REPOSITORIES[key].version,
                "revision": commit,
            }
            for key, commit in sorted(self.commits.items())
            if key in ALL_REPOSITORIES
        }
        state: Dict[str, object] = {
            "schema_version": 2,
            "contract": STATE_CONTRACT,
            "installer_version": __version__,
            "installed_at": datetime.now(timezone.utc).isoformat(),
            "root": str(self.root),
            "profile": self.profile,
            "component": self.profile,
            "components": list(source_keys(self.profile)),
            "core_components": list(source_keys("core")),
            "optional_components": ["germ"] if self.profile == "full" else [],
            "models": list(self.selection.model_keys),
            "model_revisions": dict(sorted(self.model_revisions.items())),
            "provider": self._resolved_provider(),
            "integrations": list(self.selection.integrations),
            "commits": dict(self.commits),
            "contracts": dict(ACCOUNTABLE_LISTENING_CONTRACTS),
            "repositories": repositories,
            "environment": dict(environment),
        }
        path = state_path(self.root)
        self.runner.note("  write %s" % path)
        if not self.runner.dry_run:
            _atomic_write(
                path, json.dumps(state, indent=2, sort_keys=True) + "\n", mode=0o600
            )
        return state

    def _install_integrations(self, environment: Mapping[str, str]) -> None:
        oida = self.src_root / "oida"
        for integration in self.selection.integrations:
            self.runner.run(
                [self.uv, "run", "oida", "integrate", integration, "--json"],
                cwd=oida,
                env=environment,
            )

    def _verify_installation(self, environment: Mapping[str, str]) -> None:
        if profile_includes(self.profile, "oida"):
            self.runner.run(
                [
                    self.uv,
                    "run",
                    "python",
                    "-c",
                    "import oida; print('Oída import: ok')",
                ],
                cwd=self.src_root / "oida",
                env=environment,
            )
        if profile_includes(self.profile, "germ"):
            germ_models = any(model.application == "germ" for model in self.models)
            provider = self._resolved_provider()
            import_check = "from server.main import app"
            if germ_models and provider == "python":
                import_check = "import stable_audio_3; " + import_check
            self.runner.run(
                [
                    self.uv,
                    "run",
                    "python",
                    "-c",
                    import_check + "; print('GERM import: ' + app.title)",
                ],
                cwd=self.src_root / "germ",
                env=environment,
            )
            if germ_models and provider == "mlx":
                binary = (
                    self.vendor_root / "stable-audio-3" / "optimized" / "mlx" / "sa3"
                )
                self.runner.note("  verify MLX executable at %s" % binary)
                if not self.runner.dry_run and not (
                    binary.is_file() and os.access(binary, os.X_OK)
                ):
                    raise RuntimeError(
                        "Stable Audio 3 MLX installation did not create an executable at %s"
                        % binary
                    )

    def _heading(self, title: str) -> None:
        print("\n%s" % title)


def _preferred_moss(models: Sequence[Model], kind: str) -> Model:
    candidates = [model for model in models if kind in model.key]
    if not candidates:
        # One selected MOSS checkpoint can serve both Oída routes.
        candidates = list(models)
    return sorted(candidates, key=lambda model: (model.size_bytes, model.key))[0]


def _preferred_stable_model(models: Sequence[Model]) -> str:
    if not models:
        return "mock-sine"
    preference = ("stable-small-sfx", "stable-small-music", "stable-medium")
    by_key = {model.key: model for model in models}
    selected = next((by_key[key] for key in preference if key in by_key), models[0])
    return selected.model_id.rsplit("stable-audio-3-", 1)[-1]


def _normalise_git_url(value: str) -> str:
    cleaned = value.strip().removesuffix(".git").rstrip("/")
    if cleaned.startswith("git@github.com:"):
        cleaned = "https://github.com/" + cleaned.split(":", 1)[1]
    return cleaned.lower()


def _is_commit_revision(value: str) -> bool:
    return len(value) == 40 and all(
        character in "0123456789abcdef" for character in value
    )


def _reported_version(value: str) -> str:
    parts = value.strip().split()
    return parts[-1] if parts else ""


def _atomic_write(path: Path, content: str, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    os.chmod(temporary, mode)
    temporary.replace(path)
