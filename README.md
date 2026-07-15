# The Listening Stack Installer

> **Public alpha · Open research release · Local-first · Open-source · Under active development**

The Listening Stack Installer prepares [Oída](https://github.com/sonicfieldlabs/oida)
and [GERM](https://github.com/sonicfieldlabs/germ), their local runtimes, and
the models an operator explicitly selects. It checks the host, explains disk
and memory requirements, keeps weights outside Git, and leaves both local
gateways ready to start.

**Oída hears. GERM cultivates. Akousmata remembers. AKOÚŌ structures. Earworm
routes.**

This repository is an installer and operator assistant. Oída, GERM, AKOÚŌ,
Earworm, and Akousmata remain independent repositories with their own histories,
licenses, and releases. The assistant does not duplicate their application
code.

Current installer release: `0.1.0`.

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

- **Full stack:** Oída, GERM, the supporting Oída libraries, selected models,
  and one local Stable Audio 3 provider.
- **Oída only:** Oída and the AKOÚŌ, Earworm, and Akousmata source dependencies
  required by its current `uv` workspace.
- **GERM only:** GERM with its mock path or a selected Stable Audio 3 runtime.
- **Model-free paths:** Oída's deterministic/stub route and GERM's mock route,
  with no weights or hosted account.
- **Optional agent adapters:** Hermes, Codex, Claude, OpenClaw, and OpenCode,
  installed through Oída only after they are selected.

Sources are cloned into a dedicated installation directory. The installer
verifies every existing origin and refuses to update a dirty or unexpected
checkout. It records the exact commits it installed in local state.

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
  --component full \
  --models recommended \
  --provider auto \
  --accept-model-terms \
  --integration codex \
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
- GERM dashboard: `http://127.0.0.1:5178/dashboard`

Both bind to loopback. The generated environment file contains paths and
non-secret settings only. Hugging Face credentials stay in the Hugging Face
CLI's own local credential store and are never copied into this repository or
the installer state.

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
- The doctor can confirm files, imports, origins, and gateway health; it cannot
  certify model output quality or legal fitness for a particular use.
- Stable Audio 3's optimized paths differ across CPU, CUDA, and Apple Silicon.
- Oída and GERM interfaces remain under active development before 1.0.

## Development

The assistant uses only the Python standard library.

```bash
python3 -m unittest discover -s tests -v
python3 scripts/build_release.py
./dist/listening-stack.pyz models --json
bash -n install.sh listening-stack
```

Use a dry run to inspect installation commands without changing the machine:

```bash
./listening-stack install --component full --models recommended \
  --accept-model-terms --yes --dry-run
```

See [CONTRIBUTING.md](CONTRIBUTING.md), [ROADMAP.md](ROADMAP.md), and
[CITATION.cff](CITATION.cff).

## License

The installer source is licensed under Apache-2.0. Installed repositories,
models, datasets, inputs, and outputs retain their own licenses and terms.
