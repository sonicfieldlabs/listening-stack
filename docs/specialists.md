# Optional CPU listeners

Provisioning is separate from listening. The Oída worker never downloads weights.
The bounded adapter profile is Python 3.12 on Apple Silicon, CPU float32, two Torch threads,
one running specialist job and at most four admitted/waiting jobs per Oída process.
Model environments remain separate from MOSS and GERM.

## Pinned upstream artifacts

| Task | Repository revision | Weight SHA256 |
|---|---|---|
| EfficientAT `mn04_as` | `a425fdce92572e602a1d5634799bd9f1f2efa806` | `899a8c6217063f6941793102a2780b3dd788ab11fce468d9cf5f0577c453321c` |
| Beat This! `small0` | `b95c8ab0c58c2d9fcfd40508ae8dffbc05ac4f5c` | `6074be2c4d490c5f6101fcc374a1ec72ae93456e23bb6019783b849f5dc7d47b` |

Sources: [EfficientAT](https://github.com/fschmid56/EfficientAT),
[Beat This!](https://github.com/CPJKU/beat_this). Their checked-out LICENSE files are
retained and hashed with each deployment. Source and weight identity remain separate.

To reproduce the local profile, create a dedicated directory containing clones named
`EfficientAT` and `beat_this`, check out the revisions above, and create `.venv` with Python
3.12. Install Torch 2.10.0, Torchaudio 2.10.0, Torchvision 0.25.0, SoundFile, SciPy, Librosa
and the pinned local Beat This! package. Retain the complete dependency freeze in the private bundle's `requirements.lock`.
Bind the evaluation to that exact runtime and measure each selected platform separately.

Download the two files explicitly during provisioning:

- Save [EfficientAT weights](https://github.com/fschmid56/EfficientAT/releases/download/v0.0.1/mn04_as_mAP_432.pt) as `mn04_as.pt`.
- Save [Beat This! weights](https://cloud.cp.jku.at/public.php/dav/files/7ik4RrBKTS273gp/small0.ckpt) as `small0.ckpt`.

Verify the hashes above. Preserve original upstream code; do not edit dependencies to
make a mismatched model appear available. Both adapters use `weights_only=True` loading.

## Prepare and admit

From this installer checkout, run:

```sh
PYTHONPATH=src python -m listening_stack.specialists \
  --root /path/to/specialists \
  --oida /path/to/oida \
  --fixtures /path/to/private/ten-second-fixtures
```

The fixtures directory must contain `silence.wav`, `tone_440.wav`, `high_band_12000.wav`,
`stereo_distinction.wav`, `regular_impulses.wav`, and `irregular_impulses.wav`. A synthetic integration corpus may repeat two-second fixtures five times. It is an
integration corpus, not a held-out natural sound or music benchmark; the repeated irregular
impulses are not a claim of globally aperiodic music.

Preparation verifies source revisions and weight hashes, runs each checkpoint on all six
fixtures, checks silence and sustained-tone abstention, measures process peak memory and
elapsed time, hashes the worker and source files, and writes `deployments.json` atomically.
Set `OIDA_SPECIALISTS_CONFIG` to that file in the owner's environment and restart while idle.
A missing or invalid optional deployment remains unavailable while the existing owner works.
Re-prepare after changing worker code, weights, runtime or preprocessing. Do not hand-edit a
receipt to mark an untested model ready.

`max_input_seconds` derives from the fixtures actually tested and the worker independently
rejects excerpts longer than ten seconds. Input/output files live in private temporary
folders and are removed after each job. Runtime cancellation terminates the process and
releases the queue. Peak-memory values are observations, not enforced RAM reservations.

Keep environments, weights, source pins and validation receipts in a private bundle outside source repositories. Configure `OIDA_SPECIALISTS_CONFIG` explicitly and preserve existing model selections.

Domain evaluation remains explicit: labels are uncalibrated hypotheses; beat/downbeat
candidates are fallible; this admission establishes bounded local operation and the tested
abstentions, not general recognition accuracy or musical validity.
