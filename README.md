# The Listening Stack Installer

> **Public alpha · Open research release · Local-first · Open-source · Under active development**

The Listening Stack Installer prepares the accountable listening core:
[AKOÚŌ](https://github.com/sonicfieldlabs/akouo),
[Earworm](https://github.com/sonicfieldlabs/earworm),
[Akousmata](https://github.com/sonicfieldlabs/akousmata), and
[Oída](https://github.com/sonicfieldlabs/oida). [GERM](https://github.com/sonicfieldlabs/germ)
is available as an explicit optional installation. The assistant checks the
host, explains disk and memory requirements, keeps weights outside Git, and
prepares only the services and models an operator selected.

**Oída listens. AKOÚŌ structures claims. Earworm addresses auditums. Akousmata
renders and audits memory. GERM optionally cultivates.**

This repository is an installer and operator assistant. Oída, GERM, AKOÚŌ,
Earworm, and Akousmata remain independent repositories with their own histories,
licenses, and releases. The assistant does not duplicate their application
code.

Current installer candidate: `0.5.0` (unpublished).

## Quick Start

Run the interactive assistant:

```bash
curl -fsSL https://raw.githubusercontent.com/sonicfieldlabs/listening-stack/main/install.sh | bash
```

The bootstrap downloads the latest `listening-stack.pyz` release asset,
verifies its SHA-256 checksum, installs it to `~/.local/bin/listening-stack`,
and opens the assistant in the current terminal.

For the more inspectable route:

```bash
curl -fsSLo listening-stack-install.sh \
  https://raw.githubusercontent.com/sonicfieldlabs/listening-stack/main/install.sh
less listening-stack-install.sh
bash listening-stack-install.sh
```

You can also download `listening-stack.pyz` and its checksum from the
[latest release](https://github.com/sonicfieldlabs/listening-stack/releases/latest),
mark it executable, and run it directly:

```bash
chmod +x listening-stack.pyz
./listening-stack.pyz install
```

## What the Assistant Can Install

- **Core profile (default):** AKOÚŌ, Earworm, Akousmata, Oída, and any selected
  MOSS-Audio models. It neither installs nor configures GERM.
- **Full profile:** the core plus an explicitly selected GERM installation and,
  when requested, one local Stable Audio 3 provider.
- **GERM only:** GERM with its mock path or a selected Stable Audio 3 runtime.
- **Model-free paths:** the core's deterministic/stub route and, only in a
  GERM-containing profile, GERM's mock route, with no weights or hosted account.
- **Optional agent adapters:** Hermes, Codex, Claude, OpenClaw, and OpenCode,
  installed through Oída only after they are selected.

Sources are cloned into a dedicated installation directory. The installer
verifies every existing origin and refuses to update a dirty or unexpected
checkout. Release `0.4.1` installs one immutable compatibility set and records
the exact commits it installed in local state:

| Component | Tested release |
| --- | --- |
| Oída | 0.10.0 |
| GERM | 0.5.0 |
| AKOÚŌ | 0.9.2 |
| Earworm / Akousma schema | 0.7.0 / 1.6 |
| Akousmata | 0.7.0 |

The official MOSS-Audio source is pinned to the revision tested with Oída
0.10.0. Stable Audio 3 source is pinned to the same revision locked by GERM
0.5.0. Rerunning this installer therefore reproduces the compatibility set;
it does not silently advance a checkout to a newer moving branch.

For a GERM-containing profile, state also records the exact MASA 0.2.0 and
Cosmoaudition 0.2.0 release commits and the MASA schemas, Cosmoaudition
modulation/signal-catalog contracts, and GERM bridge contract reviewed with
GERM 0.5.0. Those repositories remain independent compatibility references;
the Listening Stack does not clone, run, or configure either one.

## Accountable Listening Contract

Release 0.4.1 installs listening as an explicit, inspectable chain:

1. AKOÚŌ owns routing and claim discipline under `akouo/v0.9`, including
   situated `akouo/listening-context/v2`, attributable listening passes,
   provenance and cuts, explicit route decisions, and declared ensembles.
2. Oída owns runtime perception and the decision-first gateway. A successful
   perception pass emits `oida/listening-event/v0.3` through
   `oida/gateway/v0.6`; a refusal before perception emits
   `oida/route-outcome/v0.1` instead of
   fabricating an empty hearing.
3. Earworm 0.7 and Akousma schema 1.6 own addressable records, lossless
   `auditum.listenings[].listener_type` classification, append-only lineage,
   disagreement, decision-only records, action receipts, revision, and
   forgetting receipts. “Tokenized” here means structured, addressable, and
   versioned—never a financial token.
4. Akousmata 0.7 renders, queries, and structurally audits separate human and
   machine records. Human edits create new revision records; the machine
   listening core remains immutable.

Capability and authority stay separate. A host may declare what its apparatus
can perceive, but Oída recomputes the effective context and defaults operational
authority to observe-only. Prompts, transcripts, contextual descriptions, and
machine observations remain attributed evidence rather than being relabeled as
embodied hearing.
Unsupported measurements remain absent rather than being inferred from model
prose. A pause, refusal, withholding, or forgetting decision is recorded as a
decision, not confused with honest absence or an undetermined claim. Distinct
routes remain distinct listenings; multiple listeners become an ear swarm only
when they remain attributable and demonstrably redirect one another.

The installer records this semantic compatibility matrix, the selected profile,
and its exact component set in `listening-stack/state/v2` state.
When Oída is running, `listening-stack doctor` reads the live gateway manifest
and all four public schemas to verify the contract at the actual integration
boundary. Its GET-only manifest check also verifies separate human/machine
records, listener-type classification, additive human revisions, and immutable
machine listening cores. It never creates or edits a record. See
[Accountable listening architecture](docs/accountable-listening.md).

## Model Choices

| Model | Used by | Approx. download | Planning RAM | Access |
| --- | --- | ---: | ---: | --- |
| MOSS-Audio 4B Instruct | Oída | 10.45 GB | 24 GB suggested | Apache-2.0; public |
| MOSS-Audio 4B Thinking | Oída | 10.45 GB | 24 GB suggested | Apache-2.0; public |
| MOSS-Audio 8B Instruct | Oída | 18.11 GB | 48 GB suggested | Apache-2.0; public |
| MOSS-Audio 8B Thinking | Oída | 18.11 GB | 48 GB suggested | Apache-2.0; public |
| Stable Audio 3 Small SFX | GERM | 3.49 GB | 16 GB suggested | Gated; Stability AI Community License and component terms |
| Stable Audio 3 Small Music | GERM | 3.49 GB | 16 GB suggested | Gated; Stability AI Community License and component terms |
| Stable Audio 3 Medium | GERM | 10.45 GB | 24 GB suggested | Gated; Stability AI Community License and component terms |

The CLI refreshes storage sizes from the official Hugging Face API before an
interactive install. Run `listening-stack models --live` to inspect the current
catalog at any time.

The recommended full selection needs about 46 GB of free disk after model
download headroom and Python environments are included. The all-model selection
plans for about 100 GB. Storage is additive. RAM is not additive unless Oída
and GERM keep models resident at the same time: the recommended set suggests
24 GB for one active model or about 40 GB for both applications to load their
largest selected model concurrently.

These RAM figures are conservative installer guidance, not upstream guarantees.
Actual use depends on device, precision, audio duration, provider, and resident
model policy.

## Model and License Boundary

MOSS-Audio code and released model checkpoints are Apache-2.0. Oída is developed
and tested first against the 4B Instruct and Thinking checkpoints while
remaining model-agnostic at its gateway boundary.

Oída 0.10.0 requires Safetensors for its embedded model loader and pins its
compatible Torch, TorchAudio, TorchCodec, and Transformers releases. The
installer downloads MOSS checkpoints by immutable Hugging Face commit and the
doctor verifies both model configuration and Safetensors weights.

Stable Audio 3's repository code is MIT. Its downloadable weights are a
separate matter: the listed checkpoints are gated and currently identify the
Stability AI Community License plus additional component terms. They should
not be described simply as unrestricted open-source weights. GERM can run
locally with them, but the operator must review and accept the exact model
terms on Hugging Face. The installer displays every selected model page and
cannot accept those terms on anyone's behalf.

See [Models, access, and hardware](docs/models.md) for the exact upstream links,
runtime paths, and attribution guidance.

## Requirements

- macOS or Linux.
- Python 3.9 or newer for the assistant. It asks `uv` to install Python 3.12
  for Oída and compatible project environments.
- Git and curl.
- ffmpeg for complete audio decoding. The assistant can install it through
  Homebrew, apt, or dnf when available.
- Xcode command-line tools for native Apple Silicon build steps.
- A Hugging Face account only for gated Stable Audio 3 weights.

When `uv` is absent, the assistant downloads the checksum-pinned official
installer for tested `uv` 0.12.09 without modifying shell startup files. A
pinned Hugging Face CLI is installed inside the selected Listening Stack root,
not into the host's global tool directory.

The Stable Audio 3 Small models have an upstream CPU path. GERM can prepare its
MLX route on Apple Silicon. Stable Audio 3 Medium expects CUDA in the upstream
release. MOSS-Audio can use CUDA, Apple Metal through Oída's embedded route, or
CPU with materially different speed.

## Commands

```bash
listening-stack install
listening-stack models --live
listening-stack doctor
listening-stack start
listening-stack status
listening-stack stop
```

Start or stop one gateway:

```bash
listening-stack start oida
listening-stack start germ
listening-stack stop germ
```

Run a reproducible non-interactive install:

```bash
listening-stack install \
  --component core \
  --models recommended \
  --integration codex \
  --root "$HOME/SonicField/ListeningStack" \
  --yes
```

Add GERM only by selecting it explicitly:

```bash
listening-stack install \
  --component full \
  --models recommended \
  --provider auto \
  --accept-model-terms \
  --root "$HOME/SonicField/ListeningStack" \
  --yes
```

`--accept-model-terms` records only the operator's confirmation that they have
reviewed the relevant pages. It does not click through a license or create a
Hugging Face account. See the [installation reference](docs/installation.md)
for presets, individual model keys, dry runs, and automation.

## Local Services

After `listening-stack start`:

- Oída gateway and agent: `http://127.0.0.1:8765`
- GERM dashboard, only when installed: `http://127.0.0.1:5178/dashboard`

Both bind to loopback. The generated environment file contains paths and
non-secret settings only. Hugging Face credentials stay in the Hugging Face
CLI's own local credential store and are never copied into this repository or
the installer state.

The core uses one explicit `AKOUSMATA_PATH` under the installation root. When
GERM is selected, Oída and GERM share that path; GERM's allowed hosts, input
roots, and model roots are bounded to generated loopback and install-root
paths. A core-only install records no GERM URL, creates no GERM data directory,
and does not probe or start GERM.

Oída's public schema boundary is available at:

- `http://127.0.0.1:8765/gateway/schema/host-perception`
- `http://127.0.0.1:8765/gateway/schema/listening-event`
- `http://127.0.0.1:8765/gateway/schema/listening-context`
- `http://127.0.0.1:8765/gateway/schema/route-outcome`

## Agent Integrations

Oída exposes the agentic listening gateway. The assistant can install its
skills, MCP configuration, or plugin material for:

```bash
listening-stack integrate hermes
listening-stack integrate codex
listening-stack integrate claude
listening-stack integrate openclaw
listening-stack integrate opencode
```

These are explicit host mutations. Existing configuration is preserved or
backed up by Oída's integration layer where supported. GERM does not install
separate host adapters; agents reach cultivation through the Oída gateway and
the stack's local services.

## Safety and Data Boundaries

- The bootstrap verifies the release checksum before execution.
- Component and model-runtime source checkouts use immutable revisions.
- The recorded semantic contracts are verified against Oída's live manifest and
  schemas rather than inferred from package versions alone.
- No model, token, recording, generated sound, log, machine path, or installer
  state is committed to this repository.
- Model terms are displayed before gated downloads.
- Existing source checkouts must have the expected GitHub origin and a clean
  worktree before the assistant updates them.
- Only processes recorded by the local lifecycle managers are stopped.
- Network providers remain outside this install path unless an application
  operator enables them separately.

Read [Security and local state](docs/security.md) before using the installer on
a shared machine.

## Public-Alpha Limits

- Downloads are large and can be interrupted by network or access restrictions.
- Model availability, upstream terms, and hardware compatibility can change.
- The doctor can confirm files, imports, origins, gateway health, and listening
  contracts; it cannot
  certify model output quality or legal fitness for a particular use.
- Stable Audio 3's optimized paths differ across CPU, CUDA, and Apple Silicon.
- Oída and the optional GERM interface remain under active development before 1.0.
- Stable Audio 3's Python loader resolves gated model revisions through its
  upstream Hugging Face contract; the exact resolved cache revision is recorded
  in installer state when available.

## Development

See [local installation verification](docs/local-verification.md) for isolated
core checks, bundled-schema verification and configuration rollback limits.

The assistant uses only the Python standard library. Tests are split into a
unit environment with `.[test]` and an owner environment with `.[owner-test]`.
Use Python 3.11+; CI exercises 3.11, 3.12 and 3.13, and the GERM interpreter
verification cases execute on 3.12. No sibling environment is required.

In a fresh unit virtual environment:

```bash
python -m pip install '.[test]'
python -I scripts/check_tests.py unit --junitxml /tmp/installer-unit.xml
python scripts/build_release.py
./dist/listening-stack.pyz models --json
bash -n install.sh listening-stack
```

In a separate fresh owner-test virtual environment using Python 3.12 or newer
(the bundled Oída owner package requires 3.12):

```bash
shasum -a 256 -c vendor/SHA256SUMS
python -m pip install --find-links vendor '.[owner-test]'
python -I scripts/check_tests.py owners --junitxml /tmp/installer-owners.xml
```

The owner test wheels are explicitly unpublished fixtures; they do not change
the public installer pins. Managed adapter availability follows the selected
Oída revision: the pinned 0.10.0 supports Hermes, Codex, Claude, OpenClaw and
OpenCode. Pi belongs to newer Oída candidates and is refused by this managed
profile before installation changes. `all` expands only to supported adapters.
The release workflow reuses the complete CI workflow before publishing.

Use a dry run to inspect installation commands without changing the machine:

```bash
./listening-stack install --component core --models recommended --yes --dry-run
./listening-stack install --component full --models none --yes --dry-run
```

See [CONTRIBUTING.md](CONTRIBUTING.md), [CHANGELOG.md](CHANGELOG.md),
[CITATION.cff](CITATION.cff).

## License

The installer source is licensed under Apache-2.0. Installed repositories,
models, datasets, inputs, and outputs retain their own licenses and terms.

D5 local integration: [memory-restore](docs/memory-restore.md). Unreleased; no automatic publication.

Local development setup: [checksum-pinned offline candidate, component ownership and rollback](docs/candidate-release.md).
Published release pins remain unchanged; uncommitted builds use a separate candidate manifest.

### Optional native spectral workers

`python -m listening_stack.spectral --python /isolated/venv/bin/python
--worker /checkout/oida/oida/spectral_worker.py --destination /local/spectral-workers.json`
qualifies a separately provisioned Python 3.12 environment with NumPy 1.26.4,
SciPy 1.14.1, NSGT 0.19 and Kymatio 0.3.0. Install NumPy, setuptools and wheel
before NSGT, using `--no-build-isolation` for NSGT. Qualification applies a
source-hash-guarded integer-window compatibility fix to NSGT and records it.
The manifest binds code, interpreter, libraries, notices and synthetic results.
Set `OIDA_SPECTRAL_WORKERS_CONFIG` only to enable a qualified deployment; default
installation and published core pins do not enable these optional workers.

### Evaluated research instruments

The optional P7 admission helper, `python -m listening_stack.research`, provisions
an already downloaded and evaluated IIL guitar RAVE export and Basic Pitch ONNX.
It requires `--root`, `--germ` and `--evaluation` paths, verifies the exact worker,
checkpoint, runtime and evaluation evidence, and writes `deployments.json`.
The existing generation/listening settings are not migrated or replaced.
The helper requires independently reviewed evaluation and license evidence.
It does not enable a research instrument in the default installation.
