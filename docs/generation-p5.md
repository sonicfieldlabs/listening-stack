# P5 local generation deployment

GERM owns generation requests, capabilities, queueing, cancellation, outputs and lineage. Station consumes `/workspace/capabilities` and continues to submit `/workspace/render` jobs. Existing model identifiers remain valid. The workspace resolves `ace-turbo` to `ace_step/acestep-v15-turbo`, and CPU preset identifiers to the existing `synthesis` provider.

The optional ACE bundle is `~/.local/share/listening-stack-local/ace/`: a separate Python 3.12 environment, pinned checkpoint/runtime inventory, notices, dependency lock and locally evaluated worker. GERM's smaller parent environment additionally needs the declared NumPy and SoundFile dependencies for format/interval validation. It does not import ACE's Torch or Transformers packages.

After provisioning and evaluating the exact worker, create its deployment manifest:

```sh
python -m listening_stack.generation \
  --root "$HOME/.local/share/listening-stack-local/ace" \
  --germ /absolute/path/to/germ \
  --evaluation /absolute/path/to/p5-evaluation/evaluation.json
```

Use the installer environment with Python 3.12 or newer. This command verifies local artifacts and receipts; it does not download weights or run unbounded provisioning. Four passing cases are required, including the maximum admitted duration and both exposed audio-edit operations. Changing the inference worker requires re-evaluation. Never relabel an unevaluated conversion as this deployment.

Set `GERM_ACE_CONFIG` to the resulting `ace/deployment.json` in the existing local supervisor. No extra network port is needed. The authenticated/private Station interface stays at its existing Tailnet address; all inference runs on this machine.

Rollback: remove `GERM_ACE_CONFIG` from the supervisor and restart the idle services. ACE becomes unavailable, while Stable Audio and CPU synthesis remain. Presets explicitly selecting ACE fail with an unavailable-model message; they are not silently rerouted. Keep the model files and generated artifacts unless deliberately uninstalling them.

These historical measurements do not qualify a fresh local candidate.
