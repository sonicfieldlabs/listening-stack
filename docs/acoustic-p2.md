# P2 CLAP provisioning

The optional acoustic retrieval adapter is owned by Akousmata; Station proxies private
operations and GERM continues to own the sound library. Provisioning is separate from use.

The tested local bundle uses Python 3.12, Torch 2.10.0, Transformers 4.57.6 and
`laion/larger_clap_general` at revision `ada0c23a36c4e8582805bb38fec3905903f18b41`.
[The upstream model card](https://huggingface.co/laion/larger_clap_general) documents the
joint audio/text representation and Apache-2.0 label. Retain that pinned card, model config,
processor/tokenizer files and exact weight hashes together.

1. Create a separate Python environment at `<bundle>/.venv`; do not replace the MOSS or
   generation environment. Install the tested packages and audio preprocessing dependencies.
2. Download the pinned model's files into `<bundle>/model`, and retain the Hugging Face API
   revision response including LFS SHA-256 values as `<bundle>/upstream.json`.
3. Freeze the complete environment to `<bundle>/requirements.lock`.
4. Run the Akousmata CLAP worker on a fixed local evaluation set. Preserve the report with
   worker and weight hashes, measured peak memory, maximum tested segment duration and
   the text/tag comparison. This is a provisioning task, never an implicit download on listening.
5. From this repository with Python 3.11 or newer:

   ```sh
   PYTHONPATH=src python -m listening_stack.acoustic \
     --root /path/to/bundle --akousmata /path/to/akousmata \
     --evaluation /path/to/evaluation.json
   ```

The command refuses mismatched weights or stale/failed validation. It writes a private
`deployment.json` with the P0 deployment manifest, distinct embedding-space identity and
artifact inventory. The owner verifies the interpreter, worker, installed CLAP implementation,
model files, environment versions and evaluation receipt before inference.

The current bundle is `~/.local/share/listening-stack-local/clap`. Its supervisor sets
`AKOUSMATA_CLAP_CONFIG`, the loopback GERM origin and allowed local audio roots. The existing
shared heavy-job directory remains unchanged. This limits active managed computation, not
resident MOSS/Stable Audio memory or physical RAM usage.

No cloud service or public deployment is configured. Model checkpoints and private evaluation
recordings remain outside the repositories. The derived index can be rebuilt without editing
original recordings or Auditums; stop indexing before changing its runtime files.
