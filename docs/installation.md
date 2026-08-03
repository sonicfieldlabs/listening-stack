# Installation Reference

## Interactive Install

The normal entry point asks bounded questions:

1. Keep the default listening core, add optional GERM, or install GERM alone.
2. Choose a recommended, complete, empty, or custom model set.
3. Choose the Stable Audio 3 provider when GERM weights are selected.
4. Optionally select Oída host integrations.
5. Review storage, memory, terms, and the destination before proceeding.

```bash
listening-stack install
```

The default destination is `~/SonicField/ListeningStack`:

```text
ListeningStack/
├── src/                 selected first-party repositories
├── vendor/              official MOSS-Audio and Stable Audio 3 source
├── models/              local weights and Hugging Face cache
├── data/                selected service data and the Akousmata store
├── logs/                managed service logs
└── .listening-stack/    local tools, non-secret environment, and completed state
```

Every one of these paths stays outside the installer repository.

## Model Presets

For the default `--component core`:

- `recommended` or `4b`: MOSS-Audio 4B Instruct and Thinking.
- `8b`: MOSS-Audio 8B Instruct and Thinking.
- `all`: all four listed MOSS-Audio checkpoints.
- `none`: deterministic and stub paths only.

For `--component germ`:

- `recommended` or `small`: Stable Audio 3 Small SFX and Small Music.
- `medium`: Stable Audio 3 Medium.
- `all`: both Small checkpoints and Medium.
- `none`: mock provider only.

For `--component full`, use `recommended`, `all`, or `none`. This is the
explicit core-plus-GERM profile. The earlier `--component oida` spelling remains
accepted as a compatibility alias for `core`, but new automation should use the
profile name.

Individual keys can be comma-separated:

```bash
listening-stack install \
  --component core \
  --models moss-4b-instruct,moss-4b-thinking
```

Inspect valid keys with `listening-stack models`.

## Stable Audio 3 Access

Stable Audio 3 model repositories are gated. Before downloading one:

1. Open each model page displayed by the assistant.
2. Sign in to Hugging Face.
3. Review and accept the exact Stability AI and component terms.
4. Return to the terminal and confirm that review.
5. Complete `hf auth login` when prompted.

The assistant sets a dedicated `HF_HOME` inside the installation root. Tokens
remain under Hugging Face's credential handling and are not written to stack
state or environment files.

MOSS-Audio checkpoints are downloaded at the immutable revisions tested by
Oída 0.9.1. Stable Audio 3 currently resolves the selected gated model through
its upstream loader; when the Hugging Face cache exposes the resolved `main`
revision, the installer records it in `state.json`.

## Non-Interactive Install

Automation gets the core profile when no component is supplied. Declare the
profile anyway when reproducibility matters. A core-only install needs no GERM
provider or gated-model acknowledgement:

```bash
listening-stack install \
  --component core \
  --models recommended \
  --root /opt/sonicfield/listening-stack \
  --yes
```

Automation that selects GERM must make the model and gated-terms choices
explicit:

```bash
listening-stack install \
  --component germ \
  --models stable-small-sfx \
  --provider python \
  --accept-model-terms \
  --root /opt/sonicfield/listening-stack \
  --yes
```

Use `--skip-system-dependencies` when an administrator has already provisioned
`uv` and ffmpeg. Use `--start` to start the installed local gateways after
imports pass.

The `--accept-model-terms` flag is a user assertion. It does not accept terms
remotely. Downloads still fail if the authenticated account lacks access.

## Pinned Bootstrap

Pin the executable release used by the curl bootstrap:

```bash
curl -fsSL \
  https://raw.githubusercontent.com/sonicfieldlabs/listening-stack/main/install.sh \
  | LISTENING_STACK_VERSION=v0.3.1 bash
```

Override the executable destination:

```bash
curl -fsSL \
  https://raw.githubusercontent.com/sonicfieldlabs/listening-stack/main/install.sh \
  | LISTENING_STACK_BIN_DIR="$HOME/bin" bash
```

## Updating an Installation

Rerun the same install command. The assistant checks each origin and requires a
clean installation checkout before fetching the immutable revisions in the
installer's compatibility set. It records the exact commits and refuses a
checkout that resolves to anything else. It never resets a dirty tree.

Listening Stack 0.3.1 pins Oída 0.9.1, GERM 0.3.1, AKOÚŌ 0.9.0, Earworm
0.6.0, and Akousmata 0.6.0. It also records the exact accountable-listening
contracts in `listening-stack/state/v2`. The state names the canonical profile,
the exact component set, the four core components, and optional components. A
later installer release may publish a newer tested set; an existing 0.3.1
executable continues to reproduce this one.

Application version numbers remain owned by their repositories. Updating an
installer checkout does not rewrite an Oída or GERM version.

Version 0.3 can read version 1 state for lifecycle compatibility. Rerunning the
installer writes version 2 state; it does not infer that an old `oida` selection
included GERM.

After starting Oída, run `listening-stack doctor`. In addition to source and
model checks, it verifies the live gateway manifest plus host-perception,
listening-event, listening-context, and route-outcome schemas. This detects a
process that is healthy at `/health` but semantically incompatible at the
integration boundary.

## Removing an Installation

Stop managed services first:

```bash
listening-stack stop --root "$HOME/SonicField/ListeningStack"
```

Review the installation directory before deleting it. It may contain generated
audio, local listening records, model caches, and other operator-owned data.
The assistant deliberately does not provide a destructive uninstall command.
