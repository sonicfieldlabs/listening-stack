# Contributing

The Listening Stack Installer is public-alpha infrastructure. Contributions
should keep installation actions explicit, reversible where possible, and
testable without downloading model weights.

## Useful Contribution Areas

1. **Host fixtures:** add mocked doctor and dependency reports for supported
   macOS and Linux hardware without publishing personal paths or machine data.
2. **Provider checks:** improve bounded MLX, CUDA, and CPU preflight logic using
   official upstream requirements.
3. **Accessible terminal flow:** test the assistant with screen readers, narrow
   terminals, keyboard-only input, and non-interactive automation.
4. **Interrupted-download recovery:** add deterministic fixtures for partial
   Hugging Face cache and network failure states.
5. **Integration contracts:** test Oída adapter installation against temporary
   Hermes, Codex, Claude, OpenClaw, and OpenCode configuration homes.

## Development

```bash
python3 -m unittest discover -s tests -v
python3 scripts/build_release.py
first="$(shasum -a 256 dist/listening-stack.pyz | cut -d' ' -f1)"
python3 scripts/build_release.py
test "$first" = "$(shasum -a 256 dist/listening-stack.pyz | cut -d' ' -f1)"
./dist/listening-stack.pyz models --json
bash -n install.sh listening-stack
```

All unit and dry-run tests must avoid real package installation, host config
changes, model downloads, and service startup.

## Pull Requests

- State the operating system and Python version used for tests.
- Include a dry-run transcript for changed install flows.
- Cite official upstream documentation for model, license, or hardware claims.
- Update `CHANGELOG.md`, package version, citation version, and release artifact
  together when preparing a release.
- Do not include recordings, credentials, weights, generated outputs, local
  state, home-directory paths, private hostnames, or network addresses.
- Do not silently broaden a system mutation. New package-manager, config, or
  network actions need an explicit prompt and documentation.

By contributing, you agree that your contribution is licensed under Apache-2.0.
