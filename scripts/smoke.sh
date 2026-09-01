#!/usr/bin/env bash
# Shared runtime smoke for local machines and Cursor Cloud Agents.
# Same script in both places → comparable results.
#
# Usage:
#   ./scripts/smoke.sh              # disposable MELTR_HOME under /tmp
#   MELTR_HOME=~/.meltr ./scripts/smoke.sh   # reuse an existing home
#   SMOKE_KEEP=1 ./scripts/smoke.sh # keep the temp home and leave API up
#   SMOKE_SKIP_COMMUNITY=1 ./scripts/smoke.sh  # skip live registry pull
#
# Expects: editable install available (`meltr` on PATH or .venv activated).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ -x "$ROOT/.venv/bin/python" ]; then
  # shellcheck disable=SC1091
  source "$ROOT/.venv/bin/activate"
fi

if ! command -v meltr >/dev/null 2>&1; then
  echo "meltr not on PATH; run: source .venv/bin/activate && pip install -e '.[dev]'" >&2
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required for the health check" >&2
  exit 1
fi

cleanup_home=0
if [ -z "${MELTR_HOME:-}" ]; then
  MELTR_HOME="$(mktemp -d "${TMPDIR:-/tmp}/meltr-smoke.XXXXXX")"
  cleanup_home=1
  export MELTR_HOME
fi
export MELTR_HOME

health_url="http://127.0.0.1:8080/api/health"
started_by_smoke=0

cleanup() {
  if [ "$started_by_smoke" -eq 1 ] && [ "${SMOKE_KEEP:-0}" != "1" ]; then
    meltr stop >/dev/null 2>&1 || true
  fi
  if [ "$cleanup_home" -eq 1 ] && [ "${SMOKE_KEEP:-0}" != "1" ]; then
    rm -rf "$MELTR_HOME"
  fi
}
trap cleanup EXIT

echo "==> meltr --version"
meltr --version

echo "==> meltr init (MELTR_HOME=$MELTR_HOME)"
meltr init --force

echo "==> meltr config validate"
meltr config validate

if curl -sf "$health_url" >/dev/null 2>&1; then
  echo "==> API already healthy on 127.0.0.1:8080"
else
  echo "==> meltr start"
  meltr start
  started_by_smoke=1
  ok=0
  for _ in $(seq 1 30); do
    if curl -sf "$health_url" >/dev/null 2>&1; then
      ok=1
      break
    fi
    sleep 1
  done
  if [ "$ok" -ne 1 ]; then
    echo "API not healthy after 30s (MELTR_HOME=$MELTR_HOME)" >&2
    echo "Logs: $MELTR_HOME/logs/meltr.log" >&2
    exit 1
  fi
fi

echo "==> GET $health_url"
curl -sf "$health_url"
echo

community_url="${MELTR_COMMUNITY_API_URL:-https://meltr.ftsc.cloud/api/v1}"
community_url="${community_url%/}"
if [ "${SMOKE_SKIP_COMMUNITY:-0}" = "1" ]; then
  echo "==> skipping community registry (SMOKE_SKIP_COMMUNITY=1)"
elif curl -sf --max-time 15 "$community_url/health" >/dev/null 2>&1; then
  echo "==> community registry $community_url"
  echo "==> meltr templates browse"
  meltr templates browse
  echo "==> meltr templates search apache"
  meltr templates search apache
  echo "==> meltr templates list --remote"
  meltr templates list --remote --page-size 5
  echo "==> meltr templates install apache --vendor"
  meltr templates install apache --vendor --overwrite
  apache_collection="$MELTR_HOME/templates/default/apache/httpd/collection.json"
  if [ ! -f "$apache_collection" ]; then
    echo "Community install did not write $apache_collection" >&2
    exit 1
  fi
  echo "==> meltr templates check-updates"
  meltr templates check-updates
  echo "==> meltr templates compare"
  compare_out="$(meltr templates compare --page-size 5)"
  printf '%s\n' "$compare_out"
  if printf '%s\n' "$compare_out" | grep -q "Available remotely: 0"; then
    echo "templates compare reported 0 remote templates (registry catalog parse failed)" >&2
    exit 1
  fi
  echo "Community pull OK"
else
  echo "==> community registry unreachable; skipping pull smoke ($community_url)"
fi

echo "Smoke OK"
if [ "${SMOKE_KEEP:-0}" = "1" ]; then
  echo "SMOKE_KEEP=1: leaving MELTR_HOME=$MELTR_HOME and API running"
fi
