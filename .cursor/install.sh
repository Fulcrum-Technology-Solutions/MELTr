#!/usr/bin/env bash
# Idempotent Cloud Agent bootstrap for MELTr.
# Safe to run repeatedly and against cached/snapshot state.
set -euo pipefail

cd "$(dirname "$0")/.."

# python venv support is not guaranteed in the base image.
if ! python3 -c "import ensurepip" >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo apt-get install -y -qq python3-venv >/dev/null
fi

if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

python -m pip install --upgrade pip -q
pip install -e ".[dev]"

# Initialise the MELTr state dir (config + directory structure) without clobbering
# an existing config on subsequent runs.
export MELTR_HOME="${MELTR_HOME:-$HOME/.meltr}"
if [ ! -f "$MELTR_HOME/config.yaml" ]; then
  meltr init --force
fi

echo "MELTr install complete: $(meltr --version)"
echo "Runtime smoke (optional): ./scripts/smoke.sh"
