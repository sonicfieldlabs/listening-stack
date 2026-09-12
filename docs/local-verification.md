# Local installation verification

Use a fresh directory outside development checkouts and a model-free core to
verify the installer before selecting model weights:

```bash
listening-stack install --component core --models none \
  --root /absolute/path/to/disposable-stack --yes --skip-system-dependencies
listening-stack doctor --root /absolute/path/to/disposable-stack --json
```

Install system prerequisites first when using `--skip-system-dependencies`.
This still permits the installer to provision Python 3.12 through uv. Source
fetches and locked dependency downloads may use the network; no model download
or agent integration is selected by this command.

The installer and doctor share an isolated core probe. It imports Oída, AKOÚŌ,
Akousma and Akousmata, checks distribution versions and their source/package
locations, reads the bundled listening-context schema, verifies configured
data/model paths, and checks the navigator's selected store. Python runs with
`-I -B`, so cwd/PYTHONPATH cannot provide missing packages and the probe writes no
bytecode or store records. Packaged distributions must originate from the managed
source projects and reside in the managed environment. External editable sources,
missing schemas, version drift and redirected store paths fail the check.

Doctor also checks exact repository pins and live gateway contracts. A schema
may declare the expected contract through `const` or a compatible `enum`; if both
are present, both must permit the expected value. A healthy HTTP endpoint alone
does not establish compatibility. Doctor's schema check verifies advertised
contract versions, not the full semantic equivalence of every schema constraint.

The default port may already belong to another Oída installation. Doctor reports
that process's contracts; it does not prove process ownership or that it is using
the selected store. For an isolated live check, use an unused loopback port in
the disposable installation's environment/state and start its own interpreter
with `python -I -m oida.server --profile stub --host 127.0.0.1 --port PORT`.
Apply that installation's environment to the process, stop the exact process
you started, and restore the temporary configuration after the check. Do not
stop an existing unrelated service to make the test pass.

## Migration and rollback scope

Version 1 installation state remains readable. Rerunning the same profile with
this installer writes version 2 state. Keep copies of `.listening-stack/state.json`
and `stack.env` before testing migration, and verify retained data separately.
They contain local paths and belong in private evidence, not a public report.

Restoring those two files can test configuration rollback at unchanged source
revisions. It does not roll back a Python environment, source update or record
schema migration. Installation updates are not transactional across repositories
and environments; a failed update may leave sources changed with older completed
state. Restore a verified whole installation backup or rerun the pinned installer
to recover. The installer never automatically deletes retained data.

## Optional GERM verification

GERM installation uses Python 3.12. The installer and lifecycle preserve that
selected environment with `uv run --no-sync --python 3.12`; verification and
startup must not replace it using the application's `.python-version` preference.

Doctor runs a separate isolated `environment:germ` probe. It checks the actual
managed source/version, Python 3.12, the installed Akousma version and Git revision,
and the selected GERM output, shared store and model-cache paths. The probe imports
configuration without starting the application or creating store records. Normal
installation additionally checks that the application imports successfully.

## Evidence and remaining checks

The local installation matrix currently has the following evidence. Each live
check uses released repository pins, a separately installed CLI wheel, disposable
roots outside development checkouts and temporary loopback ports. The lifecycle
checks compare environment metadata before/after and confirm that their ports close.

| Environment | Profile | Runtime | Doctor result |
| --- | --- | --- | --- |
| macOS arm64 | core | stub | 28 passed (earlier verification) |
| macOS arm64 | germ | mock | 19 passed; no warnings/failures |
| macOS arm64 | full | stub + mock | 32 passed; no warnings/failures |
| Linux arm64 container | full | stub + mock | 31 passed; one memory warning; no failures |

The container ran an actual fresh installation and both gateways, without mounting
development source trees or exposing ports to the host. Its VM reported 7.7 GB,
below the existing 8 GB recommendation. This is Linux container runtime evidence;
it does not establish native Linux audio devices, GPU providers or x86 host support.

The first optional-profile run exposed GERM verification replacing Python 3.12
with 3.10. The corrected installer and lifecycle preserve 3.12 and packaged dependency
metadata. Regression checks cover dependency/version drift, redirected output paths,
missing interpreters and read-only verification. Synthetic unit fixtures exercise
probe failures; the installation matrix above supplies separate real runtime evidence.

Earlier core verification also covered version 1-to-2 configuration migration and
restoration at unchanged pins. Dependency inventories record distribution metadata
and retained licence-file hashes; absence is not inferred licence approval.

The full supported-host/profile gate remains open for Intel macOS, native Linux
hardware and other architecture checks, real selected model/provider installations,
accelerators, physical devices and agent-host integration. Pi's new adapter belongs
to the later integration work. Previously measured full-model execution in a
separate application environment does not establish installer-profile compatibility.

These checks use released component pins with local installer fixes. The recent
unpublished repository implementations are not silently substituted into the pinned
set. Testing a new combined candidate set and updating release pins remain separate
compatibility/release preparation. The installer version and pins are unchanged.

## Model-install retries and agent runtime binding

The dedicated Hugging Face CLI installed by uv is normally a symlink. Model-install
retries accept it only when it resolves to the exact managed
`.listening-stack/tools/huggingface-hub/bin/hf` target without a redirected parent.
The pinned CLI version is still checked. Foreign targets remain refused. This
prevents the installer from rejecting the tool it created during an earlier run.

A locally cached model may be used for offline model installation after checking
its recorded revision and file hashes. This verifies the local installation path;
it does not establish remote-download availability. Model-free tests do not
substitute for an actual listening call with fallback disabled.

Current Oída adapters persist an allowlist of the selected data/store/model paths
and gateway settings. They do not copy arbitrary environment variables or credentials.
Hermes uses its recorded interpreter before PATH. This runtime-binding improvement
is part of the local Oída candidate, not a silent change to released installer pins.
Existing host registrations need explicit reinstallation to receive it.

Isolated integration verification exercised real Hermes and OpenCode installation
and tool discovery, Claude manifest validation, and MCP initialization/capability
calls for Codex, Claude and OpenClaw bundles. These checks do not claim that every
host's full interactive agent workflow or the new Pi adapter is complete.


A macOS arm64 released-pin core installation with MOSS 4B Instruct completed a
real synthetic listening call, retained its Akousma, and passed all 30 doctor
checks with fallback disabled. The checkpoint was copied locally and its three
weight shards checked against cached revision metadata. An initial decoder failure
exposed an FFmpeg 9/TorchCodec 0.10 mismatch. This released-pin run required
`DYLD_LIBRARY_PATH=/opt/homebrew/opt/ffmpeg@8/lib` in the invoking process; doctor
alone had not detected the decoder failure. Do not infer model readiness from an
import-only doctor pass. The local Oída candidate discovers an existing FFmpeg 8
keg automatically; published pins remain unchanged. This is execution/storage
proof with synthetic input, not a model-quality benchmark or microphone test.
