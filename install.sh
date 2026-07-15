#!/usr/bin/env bash
set -euo pipefail

REPOSITORY="sonicfieldlabs/listening-stack"
BIN_DIR="${LISTENING_STACK_BIN_DIR:-$HOME/.local/bin}"
VERSION="${LISTENING_STACK_VERSION:-latest}"

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required to download the Listening Stack assistant." >&2
  exit 1
fi
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3.9 or newer is required to run the Listening Stack assistant." >&2
  exit 1
fi

PYTHON_OK="$(python3 -c 'import sys; print(int(sys.version_info >= (3, 9)))')"
if [ "$PYTHON_OK" != "1" ]; then
  echo "Python 3.9 or newer is required; found $(python3 --version 2>&1)." >&2
  exit 1
fi

if [ "$VERSION" = "latest" ]; then
  RELEASE_BASE="https://github.com/$REPOSITORY/releases/latest/download"
else
  RELEASE_BASE="https://github.com/$REPOSITORY/releases/download/$VERSION"
fi

TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/listening-stack.XXXXXX")"
trap 'rm -rf "$TMP_DIR"' EXIT

echo "Downloading the Listening Stack assistant..."
curl --proto '=https' --tlsv1.2 -fsSL \
  "$RELEASE_BASE/listening-stack.pyz" \
  -o "$TMP_DIR/listening-stack.pyz"
curl --proto '=https' --tlsv1.2 -fsSL \
  "$RELEASE_BASE/listening-stack.pyz.sha256" \
  -o "$TMP_DIR/listening-stack.pyz.sha256"

if command -v sha256sum >/dev/null 2>&1; then
  (cd "$TMP_DIR" && sha256sum -c listening-stack.pyz.sha256)
elif command -v shasum >/dev/null 2>&1; then
  EXPECTED="$(awk '{print $1}' "$TMP_DIR/listening-stack.pyz.sha256")"
  ACTUAL="$(shasum -a 256 "$TMP_DIR/listening-stack.pyz" | awk '{print $1}')"
  if [ "$EXPECTED" != "$ACTUAL" ]; then
    echo "Checksum verification failed." >&2
    exit 1
  fi
else
  echo "A SHA-256 tool is required to verify the downloaded executable." >&2
  exit 1
fi

mkdir -p "$BIN_DIR"
install -m 0755 "$TMP_DIR/listening-stack.pyz" "$BIN_DIR/listening-stack"

case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *)
    echo "Installed to $BIN_DIR/listening-stack. Add $BIN_DIR to PATH for later commands."
    ;;
esac

if [ "$#" -eq 0 ]; then
  set -- install
fi

if [ -r /dev/tty ]; then
  exec "$BIN_DIR/listening-stack" "$@" </dev/tty
fi

if [ -t 0 ]; then
  exec "$BIN_DIR/listening-stack" "$@"
fi

echo "The assistant needs a terminal for interactive choices." >&2
echo "Run $BIN_DIR/listening-stack install, or pass non-interactive flags." >&2
exit 1
