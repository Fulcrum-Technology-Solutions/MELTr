---
name: security-baseline
description: >-
  Use when bringing an FTSC repo up to the security baseline — CI checks,
  pre-commit secret scanning, Dependabot, CODEOWNERS, and profile-specific
  hardening (root, monorepo, or non-js). Run audit.sh first for portfolio triage.
---

# Skill: Apply the FTSC Security Baseline

Bring any FTSC app repo up to the security baseline validated on `ftsc-app-template`.
**Scope: security only.** UI, styling, and design standards are explicitly out of
scope here — do not touch app code beyond what a control requires.

## When to use

- A new repo, or an existing "vibe-coded" app that was never hardened.
- Run **per repo**. Use `scripts/audit.sh` first to see the whole portfolio at once.

## What "baseline-compliant" means

| Control | What it is | Profiles |
|---|---|---|
| CI caller | `.github/workflows/security-checks.yml` calling the reusable workflows in `Fulcrum-Technology-Solutions/.github` | all |
| Secret scanning | TruffleHog in CI + gitleaks in pre-commit | all |
| Pre-commit hook | gitleaks staged scan + `.env`/secret-file guard (+ lint-staged on JS) | all |
| Husky + lint-staged | local lint/format gate | JS only |
| dependabot.yml | grouped npm minor/patch + github-actions | all (ecosystem varies) |
| CODEOWNERS | review routing (enforces on Team+) | all |
| Semgrep (incl. Supabase service_role rule) | SAST via the caller; the custom rule lives in public `.github`, nothing to add per-repo | JS only |

> Enforcement note: branch protection / required checks need **GitHub Team+** on a
> **private** repo. Until then CI is advisory; the pre-commit hook + PR norms are the
> interim controls. Don't promise enforcement you can't deliver on Free.

## Procedure: triage → assess → plan → apply → validate

### 1. Triage — pick the profile

```
web/package.json exists?              → MONOREPO profile  (reference/monorepo/)
  (includes root tooling package.json + app in web/)
package.json at repo root only?       → ROOT profile      (reference/root/)
no package.json (C, Splunk, py)?      → NON-JS profile    (reference/non-js/)
```

**Root vs monorepo — structural diffs (intentional, don't flatten):**

| Piece | Root | Monorepo |
|---|---|---|
| Husky hook path | `.husky/pre-commit` | `web/.husky/pre-commit` |
| `prepare` script | `"husky"` | `"cd .. && husky web/.husky \|\| true"` |
| Pre-commit lint | `npx lint-staged` at root | `cd web && npx lint-staged` |
| CI `working-directory` | (none) | `web` on build/lint/dependency-audit only |
| Semgrep / secrets-scan | whole repo | whole repo (no `working-directory` — reusable workflows scan the tree) |
| Dependabot npm `directory` | `/` | `/web` |

Hook content, lint-staged config, and secret-file guards should otherwise match across JS profiles.

Also note the **package manager** (lockfile): npm / pnpm / bun / yarn. The reference
files assume npm; adjust install + audit commands if different.

### 2. Assess — read-only

Run `scripts/audit.sh <repo>`. It reports profile, package manager, and which
controls are present/missing. **Do not change anything yet.** Watch for:
- `CI caller [org: OTHER-ORG⚠]` → repo points at the wrong/stale org. Repoint to `Fulcrum-Technology-Solutions`.

### 3. Plan

List the exact files to add/change for **this** repo's profile and package manager.
Show the list to the user and get approval before writing. (Approval-gated — don't
batch-apply across repos without a per-repo nod.)

### 4. Apply — copy the right variant, targeted

Copy from `reference/<profile>/`. Don't touch app code. Then:

**ROOT (JS):**
- `reference/root/security-checks.yml` → `.github/workflows/security-checks.yml`
- `reference/root/pre-commit` → `.husky/pre-commit`, then `chmod +x .husky/pre-commit`
- `reference/root/.lintstagedrc.json` → repo root
- `reference/root/CODEOWNERS` → `.github/CODEOWNERS` (set the right `@handle`)
- `reference/root/dependabot.yml` → `.github/dependabot.yml`
- (Optional) Vite apps: add a dependabot `ignore` for `vite` semver-major bumps if you
  want to gate major Vite upgrades manually — stack-specific, not profile-specific.
- Add devDeps + script: `npm i -D husky lint-staged` and `package.json` → `"prepare": "husky"`

**MONOREPO (JS, app in `web/`):**
- Same files, but: caller is `reference/monorepo/security-checks.yml` (`working-directory: web`),
  hook is `reference/monorepo/pre-commit` → `web/.husky/pre-commit`,
  `prepare` (in `web/package.json`) = `"cd .. && husky web/.husky || true"`,
  dependabot npm `directory: "/web"`.

**NON-JS:**
- `reference/non-js/security-checks.yml` → `.github/workflows/security-checks.yml`
- `reference/non-js/pre-commit` → `.githooks/pre-commit`; then
  `git config core.hooksPath .githooks && chmod +x .githooks/pre-commit`
- `reference/non-js/dependabot.yml` → `.github/dependabot.yml` (uncomment `pip` for Python)
- No husky/lint-staged/semgrep/build/lint.

### 5. Validate — must pass before calling it done

- `gitleaks` installed (`brew install gitleaks`).
- Clean install works: `npm ci` (or clean `rm -rf node_modules && npm install`).
- (JS) `npm run build` green.
- Pre-commit **blocks** a planted `AKIA…`-shaped key and a staged `.env`; **passes** a clean file.
- CI caller path resolves (note the doubled `.github/.github/workflows/...@main`).
- Push → Actions run green.

## Gotchas (the expensive lessons — don't relearn them)

- **gitleaks 8.30+** dropped `protect`; use `gitleaks git --staged --redact .`.
- **Husky v9**: hook has no shebang / no `husky.sh` source line. Root `prepare` is just
  `husky`; monorepo is `cd .. && husky web/.husky || true` — the `|| true` stops
  `npm install` / Vercel builds from failing when husky setup can't run.
- **`NODE_ENV=production` skips devDeps** → husky, lint-staged, and build plugins silently
  don't install, and installs then fail on the `prepare: husky` step. `unset NODE_ENV`.
- **Husky chicken-and-egg**: a partial `node_modules` missing husky makes every install
  fail at `prepare`. Fix with a clean `rm -rf node_modules && npm install`.
- **Node ≥ 22.12** required (TanStack Start engine). The shared reusable build/lint
  workflows default to Node 22 — don't pin lower in a caller.
- **secrets-scan** must let TruffleHog auto-derive the commit range; hard-coding base/head
  breaks on merge-to-main ("BASE and HEAD commits are the same").
- **Caller path is doubled**: `Fulcrum-Technology-Solutions/.github/.github/workflows/<f>.yml@main`
  (reusable workflows live under `.github/workflows/` inside a repo literally named `.github`).
- **npm audit** gate is `--audit-level=high`; unfixable moderate vulns won't trip it.
- **Supabase `service_role`** must never sit in a client-bundled env var (`NEXT_PUBLIC_` /
  `VITE_`). The public `.github` Semgrep rule catches it — keep service_role server-only.
- **Templates copy files only** — a repo made from `ftsc-app-template` still needs its own
  Vercel link, env vars, and (on Team) branch protection. Files travel; settings don't.

## Reference layout

```
reference/root/      — JS app, package.json at root
reference/monorepo/  — JS app in web/
reference/non-js/    — firmware / Splunk TA / scripts (secrets + gitleaks only)
scripts/audit.sh     — read-only portfolio scanner
```
