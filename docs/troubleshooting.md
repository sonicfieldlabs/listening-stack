# Troubleshooting

Start with the read-only doctor:

```bash
listening-stack doctor --root "$HOME/SonicField/ListeningStack"
```

## `hf download` reports access denied

Open the exact Stable Audio 3 model page printed by the assistant. Sign in,
review and accept its terms, then authenticate in the same terminal:

```bash
export HF_HOME="$HOME/SonicField/ListeningStack/models/huggingface"
"$HOME/SonicField/ListeningStack/.listening-stack/bin/hf" auth login
"$HOME/SonicField/ListeningStack/.listening-stack/bin/hf" auth whoami
```

Rerun the installer with the same model selection. Existing complete downloads
are reused by the Hugging Face cache.

## A source checkout is dirty

The install assistant never discards local changes. Inspect the reported path:

```bash
git -C "$HOME/SonicField/ListeningStack/src/oida" status
```

Move deliberate development work to a separate clone. Commit or otherwise
resolve changes in the installation checkout only after confirming that they
belong there, then rerun the assistant.

## Oída starts in stub mode

Check that the selected MOSS checkpoint directories contain `config.json` and
one or more `*.safetensors` files, then inspect the generated environment:

```bash
grep '^OIDA_' "$HOME/SonicField/ListeningStack/.listening-stack/stack.env"
listening-stack doctor
```

The installer sets explicit local MOSS paths, disables silent Hub lookup, and
downloads the immutable revisions tested with Oída 0.9.0. Rerun model download
if a checkpoint is incomplete.

## Oída is healthy but a contract or schema check fails

The doctor checks more than `/health`. It reads `/gateway` and the four public
accountable-listening schemas from the same loopback process. A failure usually
means the running daemon predates the pinned source checkout or was started by a
different environment.

```bash
listening-stack stop oida
listening-stack install --component core --models none --yes
listening-stack start oida
listening-stack doctor
```

Do not edit the recorded contract matrix to silence the check. The component
contracts and live schemas must agree at the actual integration boundary.

## A repository is clean but reported as outdated

Listening Stack releases use an immutable compatibility set. A checkout can
match an older recorded installation and still differ from the current
installer's pin. Review the versions and revisions in the install plan, then
rerun the same install command. The assistant fetches only the expected commit
and never resets local work.

## GERM reports its provider unavailable

First confirm that the completed state uses the `full` or `germ` profile. The
default `core` profile deliberately has no GERM checkout, endpoint, or process.

Check provider and model diagnostics:

```bash
curl http://127.0.0.1:5178/diagnostics
curl "http://127.0.0.1:5178/huggingface/status?check_models=true"
```

Apple Silicon MLX needs Xcode command-line tools and the upstream optimized
install. The Python provider needs its optional environment. Stable Audio 3
Medium expects compatible CUDA hardware upstream.

## A port is already in use

The default loopback ports are 8765 for Oída and 5178 for GERM:

```bash
lsof -nP -iTCP:8765 -sTCP:LISTEN
lsof -nP -iTCP:5178 -sTCP:LISTEN
```

Do not kill an unknown process. Stop the owning service or configure the
application deliberately before restarting the stack.

## The executable is not on PATH

The curl bootstrap defaults to `~/.local/bin/listening-stack`. Add it to the
shell path or invoke it directly:

```bash
export PATH="$HOME/.local/bin:$PATH"
"$HOME/.local/bin/listening-stack" status
```
