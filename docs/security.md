# Security and Local State

## Bootstrap

`install.sh` downloads two assets from the latest GitHub release: the Python
zip application and its SHA-256 checksum. It refuses to execute the download
when verification fails or no SHA-256 utility is available.

The bootstrap accepts only one 64-character digest naming exactly
`listening-stack.pyz`; it never passes a downloaded checksum filename to the
checksum utility. The verified executable is written to a temporary file in
the destination directory and atomically replaces the prior executable.

A curl pipe is concise but difficult to inspect. For shared, privileged, or
long-lived machines, download the bootstrap first, read it, pin
`LISTENING_STACK_VERSION`, and then execute it.

The assistant itself should not be run as root. It can invoke `sudo` only when
ffmpeg is missing on a supported Linux package manager and system dependency
installation was not disabled.

## Git Safety

The install root contains dedicated checkouts, not development worktrees. The
assistant refuses roots inside an existing Git repository and refuses symlinked
managed directories. For an existing checkout it:

1. requires a `.git` directory;
2. checks the exact GitHub origin;
3. refuses a dirty worktree;
4. fetches an immutable commit from the release compatibility set;
5. checks out the fetched commit detached and verifies the resulting SHA;
6. records the release label, origin, and commit in local state.

It does not reset, clean, stash, force-push, or rewrite history.

## Secrets

The generated `stack.env` and `state.json` files use owner-only permissions.
They contain paths, ports, provider choices, model IDs, installed commits, and
non-secret runtime settings. They must not contain tokens, API keys, passwords,
Tailscale addresses, personal network names, or model credentials.

Hugging Face authentication remains in the Hugging Face CLI's own credential
store. Network-provider credentials are outside this installer and must remain
in operator-managed environment or secret stores.

The installer writes `state.json` only after application imports and selected
host integrations succeed, so the state file remains a completed-installation
marker rather than an optimistic plan. Its JSON input size and structure are
bounded before lifecycle commands use it.

The version 2 state contract also records the selected profile, exact component
set, and semantic compatibility set for accountable listening. When Oída is
running, the doctor reads only fixed gateway/schema
paths on the configured loopback origin, bounds response sizes, rejects
redirects and non-loopback URLs, and compares the live contracts with that set.
It does not submit recordings or listening content during this check.

## Local Data

The install root can contain:

- downloaded model weights;
- Oída listening events, captures, and memory;
- GERM source material, generated audio, sessions, and lineage when GERM was
  explicitly installed;
- service logs and process state;
- cloned public source.

These directories are not Git repositories except for the dedicated source
checkouts. The installer repository ignores model, state, output, log, vendor,
and environment paths as defense in depth.

The local gateways bind to `127.0.0.1` by default. Exposing them to a LAN,
overlay network, reverse proxy, or public host is a separate operator decision
and is not automated here.

The core environment binds Oída to loopback and gives it one install-root
`AKOUSMATA_PATH`. It contains no GERM endpoint. When GERM is explicitly
selected, the generated environment binds it to loopback, shares the same
store, bounds accepted input roots to GERM output, Oída handoff audio, and the
shared store, bounds model roots to install-managed paths, and keeps cloud image
analysis off.
Lifecycle commands reject edited state that would make them bind or probe a
non-loopback host.

## Process Control

Oída manages its own recorded gateway process. When installed, the assistant records GERM's PID
and process-start token and checks both with its command before sending a
signal. It refuses to stop a reused PID or a process that does not look like
the recorded Uvicorn GERM server. A health endpoint is reused only when its
service identity matches the expected application.

## Reporting

Do not include private recordings, tokens, model files, generated material,
home-directory paths, or full environment dumps in public issues. See
[SECURITY.md](../SECURITY.md) for private vulnerability reporting guidance.
