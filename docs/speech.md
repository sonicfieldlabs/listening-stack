# Optional local speech

Use a separate Python 3.12 environment. A separately evaluated runtime may use `mlx-audio==0.5.3`, `silero-vad==6.2.1`, soundfile and scipy; retain the complete `requirements.lock` and installed runtime files. Do not replace the existing Oída/MOSS or specialist environments.

Provision these exact MLX artifacts offline before enabling requests:

| Component | Repository | Revision |
|---|---|---|
| ASR | `mlx-community/Qwen3-ASR-0.6B-4bit` | `313d850181767edf09f00a9c289becca70e58cd0` |
| Word alignment | `mlx-community/Qwen3-ForcedAligner-0.6B-4bit` | `2f652af86ae0c73fe189b9429225c908ce4bf020` |

Keep the complete processor/tokenizer files alongside each model, in `speech/asr` and `speech/aligner`. The admission helper verifies the upstream safetensors SHA-256 for both; code and preprocessing artifacts are included in the local deployment inventory. `speech/upstream.json` maps `asr` and `aligner` to the corresponding `[repository, revision]` pairs. `license-review.json` and archived source notices identify the exact component review.

Upstream references: [Qwen ASR](https://huggingface.co/Qwen/Qwen3-ASR-0.6B), [Qwen ForcedAligner](https://huggingface.co/Qwen/Qwen3-ForcedAligner-0.6B), [MLX Audio](https://github.com/Blaizzy/mlx-audio), [Silero VAD](https://github.com/snakers4/silero-vad). These are separate ASR, alignment and detection operations. The community conversion must be evaluated as its own deployment.

Run the bounded evaluation first. Its receipt must include the worker/checkpoint hashes, actual peak process memory, 60-second admission case, Spanish/read speech and synthetic language transition cases, silence with/without detection, and non-speech cases. `prepare` refuses incomplete or failed receipts. Do not manufacture successful receipts to make a selector available.

```sh
PYTHONPATH=src python -m listening_stack.speech \
  --root /path/to/speech \
  --oida /path/to/oida \
  --receipt /path/to/evaluation.json
```

Set `OIDA_SPEECH_CONFIG=/path/to/speech/deployments.json` in the local service environment. Keep `OIDA_SPECIALISTS_CONFIG` unchanged. The owner registers a `transcribe` capability, with optional alignment within that task. Default Station settings request neither speech nor alignment. Once speech is selected, `speech_vad=true` and `speech_alignment=false` are the defaults. `speech_language` accepts `null` (automatic), `English`, `Spanish`, or `Portuguese`.

The speech worker accepts at most 60 seconds/128 MiB decoded input, analyzes bounded windows of at most 20 seconds, limits generation tokens and interval counts, and never collapses source gaps when returning timing. Cancellation terminates its subprocess. The shared heavy-job lease serializes compute with other managed heavy operations; it is not a bound on total resident model memory.

For rollback, unset only `OIDA_SPEECH_CONFIG` and restart the idle local owner. Existing models, presets, index and records remain usable. Historical speech evidence stays readable.
