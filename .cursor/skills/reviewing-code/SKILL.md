---
name: reviewing-code
description: >-
  Perform a thorough code review focused on correctness, maintainability,
  performance, and best practices for MELTr (Python FastAPI + Typer).
---

# Code Review

Use this skill when the user asks for a code review, feedback on their code, or to check code quality.

## Steps

1. **Understand the change** — read the files or diff to understand what the code is supposed to do. Identify the scope (new feature, bug fix, refactor). Prefer reviewing the **diff**, not the whole repo.

2. **Check correctness**
   - Edge cases: empty input, missing files under `MELTR_HOME`, None, zero, negative rates
   - Error states: silent `except`, swallowed API/CLI failures, PID/systemd races
   - Async / threads: generator loops, HTTP output backpressure, timeouts
   - Off-by-one in batching, schedule windows, path joins

3. **Check maintainability**
   - Single responsibility; clear names
   - Duplication that should share helpers with existing `src/meltr/` patterns
   - Magic numbers → named constants
   - Complexity (deep nesting, mega-CLI modules)

4. **Check performance**
   - Hot paths: template render, entity lookups, output flush
   - Unbounded memory (buffers, reading whole files)
   - Blocking I/O on request path without need
   - N+1 style repeated YAML/API calls in loops

5. **Check type / schema safety** (Python)
   - Pydantic models vs raw dicts at API boundaries
   - Public API return shapes stable
   - Path validation (`validate_path_within_home`) for user-controlled paths

6. **Check testing**
   - Tests for new/changed behavior (not assertion-free / mock theater)
   - Coverage floor may still fail CI — note if behavior changed without tests

7. **Check security** (lightweight; escalate to `auditing-security` / `security-baseline` when warranted)
   - Secrets in logs or responses
   - Authz on API routes when auth is enabled
   - Path traversal / command injection

8. **Report findings** — severity-ordered list with file path + brief fix. Separate must-fix vs nit.

## Notes

- Prefer project conventions in `AGENTS.md` and existing modules over inventing new patterns.
- Cross-check OSS vs Enterprise boundaries: no LLM authoring in MELTr OSS.
