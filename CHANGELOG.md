# Changelog

## 0.1.2 — 2026-07-16

- Pin the tested compatibility set to Oída 0.6.5, GERM 0.2.5, AKOÚŌ 0.7.0,
  Earworm 0.4.0, and Akousmata 0.4.0, with immutable source revisions for all
  first-party and model-runtime checkouts.
- Adopt Oída's hardened MOSS runtime contract, immutable MOSS checkpoint
  downloads, optional Music ID dependency, and a shared install-root
  Akousmata store; align GERM with its bounded hosts, input roots, model roots,
  and cloud-vision default.
- Harden the bootstrap with strict checksum parsing, atomic executable
  replacement, bounded retries, version validation, and reliable controlling
  terminal detection. Pin and verify the uv installer and keep the Hugging Face
  CLI inside the selected installation root.
- Fix gateway target filtering, configured-port handling, service identity
  checks, component-specific completion output, JSON doctor exit codes, stale
  state reporting, and GERM PID-reuse protection.
- Strengthen doctor checks for pinned source revisions, private state files,
  pinned model-runtime revisions, complete Safetensors checkpoints, real
  provider availability, CUDA guidance, and the shared data boundary.
- Make zipapp builds deterministic and non-destructive, modernize package and
  release metadata, pin CI actions, and expand regression coverage across the
  installer, runtime, doctor, bootstrap, and release artifact.

## 0.1.0 — 2026-07-15

- Open the interactive, standard-library-only installer for Oída, GERM, their
  supporting repositories, selected local models, lifecycle commands, doctor,
  and explicit agent integrations.
