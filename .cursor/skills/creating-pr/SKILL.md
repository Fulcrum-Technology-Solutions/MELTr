---
name: creating-pr
description: >-
  Create a clean, review-ready pull request with a good title, structured
  description, and test plan. Use for feature/fix PRs into MELTr default base
  (usually main; develop if that branch exists).
user-invocable: true
---

# Creating a PR

Package work into a pull request that's easy to review and merge.

**MELTr:** default PR base is `main` (protected — open a feature branch PR; do not push directly to `main`). If a `develop` branch is in use, prefer that as the integration base.

Do **not** invent a Vercel/develop→main promotion flow (that lives in other products). For MELTr releases, use tags / `release.yml` when asked.

## Workflow

### 1. Prepare the Branch

```bash
git fetch origin
BASE=main   # or develop if that is the integration branch
git rebase origin/$BASE   # or merge, per project convention

git log origin/$BASE..HEAD --oneline
git diff origin/$BASE --stat
```

Squash fixup commits if the project prefers clean history. Keep logical commits separate if the project prefers granular history.

### 2. Write the Title

Format: `<type>: <short description>`

| Type | When |
|------|------|
| `feat` | New feature |
| `fix` | Bug fix |
| `refactor` | Code change that neither fixes a bug nor adds a feature |
| `docs` | Documentation only |
| `test` | Adding or fixing tests |
| `chore` | Build, CI, deps, or tooling |
| `perf` | Performance improvement |

Examples:
- `feat: enforce MELTR_API_KEY on management API`
- `fix: load bundled entities without importlib.resources`
- `chore: raise pytest coverage floor`

### 3. Write the Description

```markdown
## Summary

1-3 sentences explaining what this PR does and why.

Closes #123

## Changes

- …

## Test Plan

- [ ] `pytest --cov-fail-under=0` (or current floor)
- [ ] `ruff check .` / `black --check .` as relevant
- [ ] Manual: `meltr --help` / affected CLI or API path
```

### 4. Self-Review

Before requesting review:
- Read every line of the diff yourself
- Remove debug leftovers
- Verify: `source .venv/bin/activate && pytest` (and lint/type as relevant)
- Check for files that shouldn't be committed (`.env`, `.venv`, secrets)

### 5. Create the PR

Follow the user rule / `gh pr create` HEREDOC pattern. Push with `-u` if needed. Return the PR URL.

### 6. Request Review

- Tag code owners / domain experts when known
- Large PRs (>400 lines): comment on review order
- Note stacked/dependent PRs in the description

## Tips

- Small PRs get reviewed faster — aim for <300 lines changed
- Respect review-gate: ≥2 review lenses by risk surface before claiming done
- Screenshots only when UI exists (MELTr OSS is primarily CLI/API)
