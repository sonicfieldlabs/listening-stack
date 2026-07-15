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
hf auth login
hf auth whoami
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

Check that the selected MOSS checkpoint directories contain `config.json`, and
inspect the generated environment:

```bash
grep '^OIDA_' "$HOME/SonicField/ListeningStack/.listening-stack/stack.env"
listening-stack doctor
```

The installer sets explicit local MOSS paths. It does not silently enable Hub
lookup. Rerun model download if a checkpoint is incomplete.

## GERM reports its provider unavailable

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
