# Optional local planning provider (P4)

The Station reuses Oída's existing provider interface. The optional gateway is hosted by the existing Oída environment; inference runs in a separate MLX environment. No saved provider selection is rewritten.

On this workstation, the isolated bundle is `~/.local/share/listening-stack-local/reasoner/`, with exact checkpoint revisions, runtime lock, component notices, evaluation receipt and file hashes. Qwen3.5-4B passed 11/12 bounded task checks and is admitted under host guards; SmolLM3-3B passed 1/12 and remains withheld. The default installer does not provision this research runtime.

Recreate the deployment manifest only after reviewing the pinned files and local evaluation:

```sh
python -m listening_stack.planning \
  --root "$HOME/.local/share/listening-stack-local/reasoner" \
  --oida /absolute/path/to/oida \
  --evaluation /absolute/path/to/p4-evaluation/evaluation.json
```

Use Python 3.12 or newer with the installer package available. This command provisions from existing local artifacts; it does not install dependencies or download models. A different inference worker requires a new evaluation receipt. Changed checkpoint or runtime files invalidate admission. The credential is private and should never be copied into browser configuration.

Set `OIDA_LOCAL_REASONING_CONFIG` to the resulting `deployments.json` for Oída and the gateway. Run `python -m uvicorn oida.reasoning.local.gateway:create_app --factory --host 127.0.0.1 --port 5194` in the Oída environment, with its source and shared akousma package available. The gateway uses the manifest's separate Python for inference, the existing shared heavy-job resource directory, and no inference-time downloads. The private local supervisor starts this service with the rest of the stack.

To disable P4, stop the supervisor, remove its planning service entry and `OIDA_LOCAL_REASONING_CONFIG`, then restart. Keep the listening/model/data directories. If a saved preset explicitly selected `local_ecology`, choose another existing provider; unavailable selections fail explicitly rather than silently substituting a model. All other provider configurations and listening records remain intact.

## Isolated candidate endpoints

The optional deployment JSON can set `base_url`, for example
`http://127.0.0.1:55194/v1`, to match an independently launched candidate gateway.
Omitting it preserves the historical `http://127.0.0.1:5194/v1` default.
Only valid loopback HTTP(S) endpoints are admitted; URL credentials, queries,
fragments and external hosts are refused without replacing built-in providers.
This field does not launch a gateway, change its listen port, copy credentials
or qualify a model. Use a separate manifest and private token for the candidate;
leave the existing service configuration unchanged. Rebind worker paths only
after confirming exact bytes against the retained evaluation, then verify the
complete selected artifact/runtime inventory before inference.
