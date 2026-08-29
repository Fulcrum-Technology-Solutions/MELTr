#!/usr/bin/env bash
# FTSC security-baseline audit (READ-ONLY). Reports which controls a repo has.
# Usage:
#   ./audit.sh <repo-path>           # audit one repo
#   ./audit.sh <dir-of-repos>/*      # audit many (shell glob)
# Makes no changes. Exit 0 always; this is a report, not a gate.

set -u
ORG="Fulcrum-Technology-Solutions"

audit_repo() {
  local repo="$1"
  [ -d "$repo/.git" ] || { return; }
  local name; name="$(basename "$repo")"

  # --- profile detection ---
  # web/package.json wins over a root tooling-only package.json
  local profile pkg
  if [ -f "$repo/web/package.json" ]; then
    pkg="$repo/web/package.json"
    if [ -f "$repo/package.json" ]; then
      profile="monorepo (web/, root tooling)"
    else
      profile="monorepo (web/)"
    fi
  elif [ -f "$repo/package.json" ]; then
    profile="root"; pkg="$repo/package.json"
  else
    profile="non-js"; pkg=""
  fi

  # --- pkg manager ---
  local pm="-"
  if [ -n "$pkg" ]; then
    local d; d="$(dirname "$pkg")"
    [ -f "$d/package-lock.json" ] && pm="npm"
    [ -f "$d/pnpm-lock.yaml" ] && pm="pnpm"
    [ -f "$d/bun.lockb" ] && pm="bun"
    [ -f "$d/yarn.lock" ] && pm="yarn"
  fi

  # --- checks ---
  local cc="$repo/.github/workflows/security-checks.yml"
  local has_caller="MISSING" caller_org="-"
  if [ -f "$cc" ]; then
    has_caller="present"
    grep -q "$ORG/.github" "$cc" && caller_org="$ORG" || caller_org="OTHER-ORG⚠"
  fi
  local hook="MISSING"
  [ -f "$repo/.husky/pre-commit" ] && hook=".husky"
  [ -f "$repo/web/.husky/pre-commit" ] && hook="web/.husky"
  [ -f "$repo/.githooks/pre-commit" ] && hook=".githooks"
  local co="MISSING"; [ -f "$repo/.github/CODEOWNERS" ] && co="present"
  local db="MISSING"; [ -f "$repo/.github/dependabot.yml" ] && db="present"
  local ls="MISSING"
  { [ -f "$repo/.lintstagedrc.json" ] || [ -f "$repo/web/.lintstagedrc.json" ]; } && ls="present"

  printf '\n=== %s ===\n' "$name"
  printf '  profile        : %s (pm: %s)\n' "$profile" "$pm"
  printf '  CI caller      : %s' "$has_caller"
  [ "$has_caller" = "present" ] && printf '  [org: %s]' "$caller_org"; printf '\n'
  printf '  pre-commit     : %s\n' "$hook"
  printf '  CODEOWNERS     : %s\n' "$co"
  printf '  dependabot.yml : %s\n' "$db"
  [ "$profile" != "non-js" ] && printf '  lint-staged    : %s\n' "$ls"
}

[ $# -eq 0 ] && { echo "usage: $0 <repo-path> [more-paths...]"; exit 1; }
echo "FTSC security-baseline audit (read-only)"
echo "gitleaks: $(command -v gitleaks >/dev/null 2>&1 && gitleaks version 2>/dev/null || echo 'NOT INSTALLED — brew install gitleaks')"
for arg in "$@"; do audit_repo "$arg"; done
echo ""
