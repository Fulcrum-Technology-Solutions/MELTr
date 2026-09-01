#!/usr/bin/env bash
# Build meltr-{version}-linux-x86_64.tar.gz (unpacks to ./meltr/): embedded CPython (python-build-standalone)
# + pip --prefix install of the wheel + portable bin/meltr wrapper.
#
# Requires: Linux x86_64, bash, curl, tar, gzip, sha256sum, python3 (build host only for bootstrap if needed).
#
# Usage: scripts/build_linux_tgz.sh <version> [dist_dir]
#   version  — package version (e.g. 1.2.3), must match meltr-{version}-py3-none-any.whl in dist/
#   dist_dir — where the wheel lives (default: dist)

set -euo pipefail

die() { echo "ERROR: $*" >&2; exit 1; }

if [[ "$(uname -s)" != Linux ]]; then
  die "This script must run on Linux (GitHub Actions ubuntu-latest is OK)."
fi
if [[ "$(uname -m)" != x86_64 ]]; then
  die "This script only targets x86_64 (see plan for future aarch64)."
fi

require_cmds() {
  local cmd missing=()
  for cmd in "$@"; do
    command -v "$cmd" >/dev/null 2>&1 || missing+=("$cmd")
  done
  if ((${#missing[@]})); then
    echo "ERROR: missing required commands: ${missing[*]}" >&2
    echo "  RHEL/Fedora/Alma: dnf install -y tar curl coreutils findutils" >&2
    echo "  Debian/Ubuntu:    apt-get update && apt-get install -y tar curl coreutils findutils" >&2
    echo "  Alpine:           apk add tar curl coreutils findutils" >&2
    exit 1
  fi
}
require_cmds curl tar sha256sum mktemp find head tee

VERSION="${1:?usage: $0 <version> [dist_dir]}"
DIST_DIR="${2:-dist}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WHEEL="${ROOT}/${DIST_DIR}/meltr-${VERSION}-py3-none-any.whl"

[[ -f "$WHEEL" ]] || die "Wheel not found: $WHEEL (run python -m build first)"

# Pinned python-build-standalone (astral-sh) — update PBS_* when bumping embedded Python.
PBS_RELEASE="${PBS_RELEASE:-20250115}"
PBS_NAME="${PBS_NAME:-cpython-3.11.11+${PBS_RELEASE}-x86_64-unknown-linux-gnu-install_only.tar.gz}"
PBS_BASE="https://github.com/astral-sh/python-build-standalone/releases/download/${PBS_RELEASE}"
PBS_URL="${PBS_BASE}/${PBS_NAME}"
PBS_SHA_URL="${PBS_URL}.sha256"

WORKDIR="$(mktemp -d)"
cleanup() { rm -rf "$WORKDIR"; }
trap cleanup EXIT

STAGING="$WORKDIR/staging"
PY_TAR="$WORKDIR/${PBS_NAME}"
mkdir -p "$STAGING"

echo "Downloading ${PBS_NAME} ..."
curl -fsSL "$PBS_URL" -o "$PY_TAR"
curl -fsSL "$PBS_SHA_URL" -o "${PY_TAR}.sha256"
# upstream ships a bare 64-hex line; sha256sum -c needs '<hash>  <filename>' (two spaces).
FIRST_LINE="$(tr -d '\r' < "${PY_TAR}.sha256" | head -n1)"
if [[ "$FIRST_LINE" =~ ^[a-fA-F0-9]{64}$ ]]; then
  printf '%s  %s\n' "$FIRST_LINE" "${PBS_NAME}" > "${PY_TAR}.sha256"
fi
( cd "$WORKDIR" && sha256sum -c "${PBS_NAME}.sha256" )

tar -xzf "$PY_TAR" -C "$STAGING"
# install_only layout: python/bin/python3.11 (path updates after mv into bundle dir)
EXTRACTED_PY="$STAGING/python/bin/python3.11"
[[ -x "$EXTRACTED_PY" ]] || die "Expected embedded Python at $EXTRACTED_PY"

# Top-level directory inside the tarball (stable path for `tar -C /opt`).
BUNDLE_DIR="${BUNDLE_DIR:-meltr}"
ARCHIVE_BASENAME="meltr-${VERSION}-linux-x86_64"
OUT_ROOT="$STAGING/${BUNDLE_DIR}"
mkdir -p "$OUT_ROOT"

mv "$STAGING/python" "$OUT_ROOT/python"
PY_BIN="$OUT_ROOT/python/bin/python3.11"
[[ -x "$PY_BIN" ]] || die "Expected embedded Python at $PY_BIN after layout"

APP_PREFIX="$OUT_ROOT/app"
"$PY_BIN" -m pip install --upgrade --no-cache-dir pip
"$PY_BIN" -m pip install --no-cache-dir --upgrade --prefix "$APP_PREFIX" "$WHEEL"

# pip --prefix creates scripts with absolute shebangs; use a relocatable wrapper only.
shopt -s nullglob
for f in "$APP_PREFIX/bin"/*; do
  rm -f "$f"
done
shopt -u nullglob

mkdir -p "$APP_PREFIX/bin"
SITE_PACKAGES="$(find "$APP_PREFIX/lib" -maxdepth 2 -type d -name site-packages 2>/dev/null | head -1)"
[[ -n "$SITE_PACKAGES" && -d "$SITE_PACKAGES" ]] || die "site-packages not found under $APP_PREFIX/lib"

# Symlink-safe implementation launcher (Linux tarball; readlink -f).
cat > "$APP_PREFIX/bin/meltr" << 'WRAPPER'
#!/usr/bin/env sh
# Portable launcher: tarball may be installed under any path (e.g. /opt/meltr).
# Resolve $0 through symlinks so /usr/local/bin links and PATH copies work.
SCRIPT="$(readlink -f "$0")"
ROOT="$(cd "$(dirname "$SCRIPT")/../.." && pwd)"
PY="$ROOT/python/bin/python3.11"
SITE="$ROOT/app/lib/python3.11/site-packages"
export PYTHONPATH="$SITE${PYTHONPATH:+:$PYTHONPATH}"
exec "$PY" -m meltr "$@"
WRAPPER
chmod 755 "$APP_PREFIX/bin/meltr"

# Operator façade: $MELTR_HOME/bin/meltr (Cribl / Splunk UF-style).
mkdir -p "$OUT_ROOT/bin"
cat > "$OUT_ROOT/bin/meltr" << 'FACADE'
#!/usr/bin/env sh
SCRIPT="$(readlink -f "$0")"
ROOT="$(cd "$(dirname "$SCRIPT")/.." && pwd)"
exec "$ROOT/app/bin/meltr" "$@"
FACADE
chmod 755 "$OUT_ROOT/bin/meltr"

# Post-extract helper: profile.d + thin /usr/local/bin wrapper (idempotent).
cat > "$OUT_ROOT/install.sh" << 'INSTALL'
#!/usr/bin/env sh
# Install operator PATH helpers for this MELTr tree (requires root).
set -eu
SCRIPT="$(readlink -f "$0")"
ROOT="$(cd "$(dirname "$SCRIPT")" && pwd)"
FACADE="$ROOT/bin/meltr"

if [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: run as root (e.g. sudo $ROOT/install.sh)" >&2
  exit 1
fi
if [ ! -x "$FACADE" ]; then
  echo "ERROR: missing façade at $FACADE" >&2
  exit 1
fi

mkdir -p /etc/profile.d
printf 'export PATH="%s/bin:${PATH}"\n' "$ROOT" > /etc/profile.d/meltr.sh

mkdir -p /usr/local/bin
printf '#!/bin/sh\nexec "%s/bin/meltr" "$@"\n' "$ROOT" > /usr/local/bin/meltr
chmod 755 /usr/local/bin/meltr

echo "Wrote /etc/profile.d/meltr.sh and /usr/local/bin/meltr"
echo "Next:"
echo "  source /etc/profile.d/meltr.sh   # or open a new login shell"
echo "  meltr init --force"
echo "  sudo meltr service install --user meltr --group meltr"
INSTALL
chmod 755 "$OUT_ROOT/install.sh"

# License files
if [[ -f "$ROOT/LICENSE" ]]; then
  cp -f "$ROOT/LICENSE" "$OUT_ROOT/LICENSE"
else
  echo "WARNING: $ROOT/LICENSE missing; tarball will include an Apache-2.0 reference stub. Add LICENSE to the repo (see NOTICE)." >&2
  cat > "$OUT_ROOT/LICENSE" << 'STUB'
MELTr is licensed under the Apache License, Version 2.0.

This build did not include the full LICENSE file from the repository. Use:
https://www.apache.org/licenses/LICENSE-2.0.txt
STUB
fi
if [[ -f "$ROOT/NOTICE" ]]; then
  cp -f "$ROOT/NOTICE" "$OUT_ROOT/NOTICE"
fi

if [[ -f "$OUT_ROOT/python/LICENSE.txt" ]]; then
  cp -f "$OUT_ROOT/python/LICENSE.txt" "$OUT_ROOT/PYTHON_PSF_LICENSE.txt"
else
  echo "Embedded CPython license: see python/LICENSE.txt (PSF License Agreement for Python)" > "$OUT_ROOT/PYTHON_PSF_LICENSE.txt"
fi

# Third-party notices: use a disposable venv with the same wheel (not shipped)
VENV="$WORKDIR/licvenv"
"$PY_BIN" -m venv "$VENV"
# shellcheck disable=SC1090
source "$VENV/bin/activate"
python -m pip install -q --upgrade pip
python -m pip install -q "$WHEEL" pip-licenses
pip-licenses --from=mixed --format=plain --with-urls --with-authors \
  > "$OUT_ROOT/THIRD_PARTY_NOTICES.txt" || {
  echo "pip-licenses failed; generating minimal notice" >&2
  {
    echo "MELTr dependencies (see PyPI metadata). Regenerate with: pip install pip-licenses && pip-licenses"
    python -m pip freeze
  } > "$OUT_ROOT/THIRD_PARTY_NOTICES.txt"
}
deactivate || true

cat > "$OUT_ROOT/README-TARBALL.md" << EOF
# MELTr ${VERSION} (Linux x86_64 bundle)

This archive contains an embedded CPython build (see PYTHON_PSF_LICENSE.txt), MELTr application
code under \`app/lib/python3.11/site-packages\`, a portable \`app/bin/meltr\` launcher, and an
operator façade at \`bin/meltr\` (Cribl / Splunk UF-style).

**Source:** https://github.com/Fulcrum-Technology-Solutions/MELTr — build from tag \`v${VERSION}\`.

## Quick use

\`\`\`bash
sudo tar xzf ${ARCHIVE_BASENAME}.tar.gz -C /opt   # creates /opt/meltr
sudo /opt/meltr/install.sh                          # profile.d + /usr/local/bin/meltr
meltr init --force
meltr start   # backgrounds on Linux; use --foreground to attach; or \`service install\` + systemctl
\`\`\`

CLI path: \`/opt/meltr/bin/meltr\` (also on PATH after \`install.sh\`). Do **not** raw-symlink
\`app/bin/meltr\` into \`/usr/local/bin\` — use \`install.sh\` or the thin wrapper it installs.

See \`docs/deployment/linux-tarball.md\` in the source tree for full operator documentation.

## Open source

- Apache-2.0: LICENSE
- Project attribution: NOTICE (if present in this bundle)
- Python: PYTHON_PSF_LICENSE.txt (and files under \`python/\`)
- Dependencies: THIRD_PARTY_NOTICES.txt
EOF

ARCHIVE_NAME="${ARCHIVE_BASENAME}.tar.gz"
ARCHIVE_PATH="${ROOT}/${DIST_DIR}/${ARCHIVE_NAME}"
(
  cd "$STAGING"
  tar -czf "$ARCHIVE_PATH" "$BUNDLE_DIR"
)

echo "Created $ARCHIVE_PATH"
sha256sum "$ARCHIVE_PATH" | tee "${ARCHIVE_PATH}.sha256"
