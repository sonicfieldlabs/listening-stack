# Models, Access, and Hardware

The Listening Stack is model-agnostic at its contracts. The default core offers
one concrete local model family for Oída. A second family is available only when
the optional GERM component is selected.

## MOSS-Audio for Oída

Oída is an agentic listening gateway. It combines deterministic signal evidence,
AKOÚŌ claim structure, bounded re-listening, and optional model passes. Its
current embedded listening path is developed and tested first with:

- [MOSS-Audio 4B Instruct](https://huggingface.co/OpenMOSS-Team/MOSS-Audio-4B-Instruct)
- [MOSS-Audio 4B Thinking](https://huggingface.co/OpenMOSS-Team/MOSS-Audio-4B-Thinking)
- [MOSS-Audio 8B Instruct](https://huggingface.co/OpenMOSS-Team/MOSS-Audio-8B-Instruct)
- [MOSS-Audio 8B Thinking](https://huggingface.co/OpenMOSS-Team/MOSS-Audio-8B-Thinking)

The upstream [MOSS-Audio repository](https://github.com/OpenMOSS/MOSS-Audio)
describes speech, sound, music, captioning, question answering, temporal
localization, and complex reasoning. The released source and checkpoints are
identified as Apache-2.0.

The installer downloads checkpoints into `models/moss-audio/` and configures
explicit local paths. Oída does not need silent Hub lookup. The Instruct model
serves direct and transcription routes; the Thinking model serves deeper,
music, and targeted re-listening routes. Oída consumes a final model response
as bounded evidence and does not expose private reasoning traces.

Listening Stack 0.3.1 downloads each MOSS checkpoint by the immutable commit
audited for this release. Oída 0.9.1's embedded loader requires Safetensors and
uses its locked Torch 2.10, TorchAudio 2.10, TorchCodec 0.10, and Transformers
5.14 runtime. The installer also prepares Oída's optional Music ID dependency;
identification remains opt-in per listen and may contact the service used by
ShazamIO when an operator enables it.

Oída's current planning guidance is 16 GB minimum and 24 GB suggested for 4B,
or 24 GB minimum and 48 GB suggested for 8B. Apple Silicon and CUDA are the
practical accelerated routes. CPU execution is possible but can be slow.

## Stable Audio 3 for Optional GERM

GERM's cultivation graph is provider-agnostic, and its mock route works without
a model. Its first real-model implementation is specifically designed around
[Stable Audio 3](https://github.com/Stability-AI/stable-audio-3):

- [Small SFX](https://huggingface.co/stabilityai/stable-audio-3-small-sfx),
  a 433M sound-effect model with variable generation up to 120 seconds.
- [Small Music](https://huggingface.co/stabilityai/stable-audio-3-small-music),
  a 433M music model with variable generation up to 120 seconds.
- [Medium](https://huggingface.co/stabilityai/stable-audio-3-medium), a 1.4B
  higher-quality model with generation up to 380 seconds.

The upstream release provides text-to-audio, audio-to-audio editing,
inpainting and continuation, variable-length generation, and LoRA
personalization. GERM places those operations inside its own graph, Micro/Matter
system, job control, source handling, metadata, comparison, and sonic lineage.

Upstream currently identifies the Small models as CPU-capable and Medium as a
CUDA path. Its published performance table reports peak VRAM up to about 2.4 GB
for Small and 6.52 GB for Medium, before application and host overhead. The
installer uses more conservative system-memory guidance.

On Apple Silicon, the assistant can prepare the upstream optimized MLX route.
On other supported systems it prepares the Python provider; Small can fall back
to CPU, while Medium should be selected only with compatible CUDA hardware.

## License Precision

The Stable Audio 3 code repository is MIT. The model repositories are gated and
identify the Stability AI Community License. The model cards also identify
additional component terms, including Gemma terms for text conditioning. The
exact terms shown on the selected model page control.

Local availability and downloadable weights do not make those weights
unrestricted open-source software. GERM does not redistribute them, accept
terms, or decide whether a use is permitted.

For a publication or release, record:

- exact model ID and revision;
- model, code, and component licenses in effect at download time;
- provider and hardware route;
- input and source-sound rights;
- prompts, seeds, parameters, parents, and transformations retained by GERM;
- the Oída apparatus and evidence route used for any later listening.

## Storage and Memory

The CLI queries the official Hugging Face API's current `usedStorage` field.
Its static values are fallbacks for offline planning.

Live size requests run concurrently with bounded response sizes, so one slow
model endpoint does not serialize the entire planning pass. The resulting size
is advisory; model identity and source revision remain separate provenance.

Disk estimates include all selected checkpoint bytes, a 15% margin for download
and extraction behavior, and a fixed reserve for source and Python environments.
RAM guidance uses the largest model expected to be resident. Only the explicit
full profile sums the largest selected Oída and GERM models for the
concurrent-app estimate.

Use:

```bash
listening-stack models --live
listening-stack doctor
```

The doctor reports installed RAM, free disk, provider compatibility, model
presence, repository origins, local gateway health, and Oída's live accountable-
listening contracts. It verifies structure and compatibility, not the truth or
quality of a model's sonic interpretation.
