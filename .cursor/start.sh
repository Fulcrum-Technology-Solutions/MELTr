#!/usr/bin/env bash
# Per-boot startup for the MELTr management API. Idempotent: no-op if already
# healthy, otherwise launches the background daemon and waits for readiness.
set -euo pipefail

cd "$(dirname "$0")/.."

# shellcheck disable=SC1091
source .venv/bin/activate

export MELTR_HOME="${MELTR_HOME:-$HOME/.meltr}"
[ -f "$MELTR_HOME/config.yaml" ] || meltr init --force

health_url="http://127.0.0.1:8080/api/health"

if curl -sf "$health_url" >/dev/null 2>&1; then
  echo "MELTr API already running"
  exit 0
fi

# 'meltr start' daemonizes on POSIX and returns immediately.
meltr start

for _ in $(seq 1 30); do
  if curl -sf "$health_url" >/dev/null 2>&1; then
    echo "MELTr API healthy on 127.0.0.1:8080 (logs: $MELTR_HOME/logs/meltr.log)"
    exit 0
  fi
  sleep 1
done

echo "MELTr API did not become healthy within 30s" >&2
exit 1
