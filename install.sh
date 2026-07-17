#!/usr/bin/env bash
set -euo pipefail

REPOSITORY="sonicfieldlabs/listening-stack"
VERSION="${LISTENING_STACK_VERSION:-latest}"

if [ -n "${LISTENING_STACK_BIN_DIR:-}" ]; then
  BIN_DIR="$LISTENING_STACK_BIN_DIR"
elif [ -n "${HOME:-}" ]; then
  BIN_DIR="$HOME/.local/bin"
else
  echo "HOME is unset; set LISTENING_STACK_BIN_DIR to an explicit destination." >&2
  exit 1
fi

if [ "$VERSION" != "latest" ] && ! [[ "$VERSION" =~ ^v[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.-]+)?([+][0-9A-Za-z.-]+)?$ ]]; then
  echo "LISTENING_STACK_VERSION must be 'latest' or a v-prefixed semantic version." >&2
  exit 1
fi

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
INSTALL_TMP=""
cleanup() {
  if [ -n "$INSTALL_TMP" ]; then
    rm -f "$INSTALL_TMP"
  fi
  if [ -n "$TMP_DIR" ]; then
    rm -rf "$TMP_DIR"
  fi
}
trap cleanup EXIT

echo "Downloading the Listening Stack assistant..."
curl --proto '=https' --tlsv1.2 --retry 3 -fsSL \
  "$RELEASE_BASE/listening-stack.pyz" \
  -o "$TMP_DIR/listening-stack.pyz"
curl --proto '=https' --tlsv1.2 --retry 3 -fsSL \
  "$RELEASE_BASE/listening-stack.pyz.sha256" \
  -o "$TMP_DIR/listening-stack.pyz.sha256"

EXPECTED=""
CHECKSUM_NAME=""
EXTRA=""
if ! IFS=' ' read -r EXPECTED CHECKSUM_NAME EXTRA < "$TMP_DIR/listening-stack.pyz.sha256"; then
  echo "The downloaded checksum file is empty or unreadable." >&2
  exit 1
fi
CHECKSUM_LINES="$(awk 'END { print NR + 0 }' "$TMP_DIR/listening-stack.pyz.sha256")"
case "$EXPECTED" in
  *[!0-9A-Fa-f]*|'')
    echo "The downloaded checksum is not a SHA-256 digest." >&2
    exit 1
    ;;
esac
if [ "$CHECKSUM_LINES" -ne 1 ] || [ "${#EXPECTED}" -ne 64 ] || [ "$CHECKSUM_NAME" != "listening-stack.pyz" ] || [ -n "$EXTRA" ]; then
  echo "The downloaded checksum file has an unexpected format." >&2
  exit 1
fi
EXPECTED="$(printf '%s' "$EXPECTED" | tr '[:upper:]' '[:lower:]')"

if command -v sha256sum >/dev/null 2>&1; then
  ACTUAL="$(sha256sum "$TMP_DIR/listening-stack.pyz")"
  ACTUAL="${ACTUAL%% *}"
elif command -v shasum >/dev/null 2>&1; then
  ACTUAL="$(shasum -a 256 "$TMP_DIR/listening-stack.pyz")"
  ACTUAL="${ACTUAL%% *}"
else
  echo "A SHA-256 tool is required to verify the downloaded executable." >&2
  exit 1
fi
if [ "$EXPECTED" != "$ACTUAL" ]; then
  echo "Checksum verification failed." >&2
  exit 1
fi

mkdir -p "$BIN_DIR"
if [ -d "$BIN_DIR/listening-stack" ]; then
  echo "Refusing to replace a directory at $BIN_DIR/listening-stack." >&2
  exit 1
fi
INSTALL_TMP="$(mktemp "$BIN_DIR/.listening-stack.XXXXXX")"
install -m 0755 "$TMP_DIR/listening-stack.pyz" "$INSTALL_TMP"
mv -f "$INSTALL_TMP" "$BIN_DIR/listening-stack"
INSTALL_TMP=""

case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *)
    echo "Installed to $BIN_DIR/listening-stack. Add $BIN_DIR to PATH for later commands."
    ;;
esac

DEFAULTED_TO_INTERACTIVE=0
if [ "$#" -eq 0 ]; then
  set -- install
  DEFAULTED_TO_INTERACTIVE=1
fi

if [ -t 0 ]; then
  exec "$BIN_DIR/listening-stack" "$@"
fi

if [ -r /dev/tty ] && ( : </dev/tty ) 2>/dev/null; then
  exec "$BIN_DIR/listening-stack" "$@" </dev/tty
fi

if [ "$DEFAULTED_TO_INTERACTIVE" -eq 0 ]; then
  exec "$BIN_DIR/listening-stack" "$@" </dev/null
fi

echo "The assistant needs a terminal for interactive choices." >&2
echo "Run $BIN_DIR/listening-stack install, or pass non-interactive flags." >&2
exit 1
