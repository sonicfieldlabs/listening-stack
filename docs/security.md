# Security and Local State

## Bootstrap

`install.sh` downloads two assets from the latest GitHub release: the Python
zip application and its SHA-256 checksum. It refuses to execute the download
when verification fails or no SHA-256 utility is available.

A curl pipe is concise but difficult to inspect. For shared, privileged, or
long-lived machines, download the bootstrap first, read it, pin
`LISTENING_STACK_VERSION`, and then execute it.

The assistant itself should not be run as root. It can invoke `sudo` only when
ffmpeg is missing on a supported Linux package manager and system dependency
installation was not disabled.

## Git Safety

The install root contains dedicated checkouts, not development worktrees. For
an existing checkout the assistant:

1. requires a `.git` directory;
2. checks the exact GitHub origin;
3. refuses a dirty worktree;
4. fetches the configured public-alpha branch;
5. checks out the fetched commit detached;
6. records the commit in local state.

It does not reset, clean, stash, force-push, or rewrite history.

## Secrets

The generated `stack.env` and `state.json` files use owner-only permissions.
They contain paths, ports, provider choices, model IDs, installed commits, and
non-secret runtime settings. They must not contain tokens, API keys, passwords,
Tailscale addresses, personal network names, or model credentials.

Hugging Face authentication remains in the Hugging Face CLI's own credential
store. Network-provider credentials are outside this installer and must remain
in operator-managed environment or secret stores.

## Local Data

The install root can contain:

- downloaded model weights;
- Oída listening events, captures, and memory;
- GERM source material, generated audio, sessions, and lineage;
- service logs and process state;
- cloned public source.

These directories are not Git repositories except for the dedicated source
checkouts. The installer repository ignores model, state, output, log, vendor,
and environment paths as defense in depth.

The local gateways bind to `127.0.0.1` by default. Exposing them to a LAN,
overlay network, reverse proxy, or public host is a separate operator decision
and is not automated here.

## Process Control

Oída manages its own recorded gateway process. The assistant records GERM's PID
and checks its command before sending a signal. It refuses to stop a PID that
does not look like the recorded Uvicorn GERM process.

## Reporting

Do not include private recordings, tokens, model files, generated material,
home-directory paths, or full environment dumps in public issues. See
[SECURITY.md](../SECURITY.md) for private vulnerability reporting guidance.
