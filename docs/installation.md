# Installation Reference

## Interactive Install

The normal entry point asks five bounded questions:

1. Install Oída, GERM, or both.
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
├── src/                 Oída, GERM, and required sibling repositories
├── vendor/              official MOSS-Audio and Stable Audio 3 source
├── models/              local weights and Hugging Face cache
├── data/                application data and generated material
├── logs/                managed service logs
└── .listening-stack/    non-secret environment and installation state
```

Every one of these paths stays outside the installer repository.

## Model Presets

For `--component oida`:

- `recommended` or `4b`: MOSS-Audio 4B Instruct and Thinking.
- `8b`: MOSS-Audio 8B Instruct and Thinking.
- `all`: all four listed MOSS-Audio checkpoints.
- `none`: deterministic and stub paths only.

For `--component germ`:

- `recommended` or `small`: Stable Audio 3 Small SFX and Small Music.
- `medium`: Stable Audio 3 Medium.
- `all`: both Small checkpoints and Medium.
- `none`: mock provider only.

For `--component full`, use `recommended`, `all`, or `none`.

Individual keys can be comma-separated:

```bash
listening-stack install \
  --component full \
  --models moss-4b-instruct,moss-4b-thinking,stable-small-sfx
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

## Non-Interactive Install

Automation must make the component, model, and gated-terms choices explicit:

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
  | LISTENING_STACK_VERSION=v0.1.0 bash
```

Override the executable destination:

```bash
curl -fsSL \
  https://raw.githubusercontent.com/sonicfieldlabs/listening-stack/main/install.sh \
  | LISTENING_STACK_BIN_DIR="$HOME/bin" bash
```

## Updating an Installation

Rerun the same install command. The assistant checks each origin and requires a
clean installation checkout before fetching the current public-alpha `main`
branch. It records the new exact commits. It never resets a dirty tree.

Application version numbers remain owned by their repositories. Updating an
installer checkout does not rewrite an Oída or GERM version.

## Removing an Installation

Stop managed services first:

```bash
listening-stack stop --root "$HOME/SonicField/ListeningStack"
```

Review the installation directory before deleting it. It may contain generated
audio, local listening records, model caches, and other operator-owned data.
The assistant deliberately does not provide a destructive uninstall command.
