---
name: auditing-security
description: Perform a systematic security audit of a codebase, checking for OWASP Top 10 vulnerabilities, secrets exposure, and insecure patterns.
---

# Security Audit

Use this skill when the user asks to audit security, check for vulnerabilities, review code for security issues, or harden an application.

## Steps

1. **Scan for hardcoded secrets** — search for API keys, tokens, passwords, and connection strings in source files. Check for patterns like:
   - `password=`, `secret=`, `token=`, `api_key=`
   - Base64-encoded credentials
   - AWS keys (`AKIA...`), Stripe keys (`sk_live_...`), GitHub tokens (`ghp_...`)
   - Files: `.env` committed to git, `config.json` with credentials

2. **Check authentication & authorization**
   - Verify all API routes check authentication before processing.
   - Ensure role-based access control is enforced server-side, not just in the UI.
   - Check that password hashing uses bcrypt/argon2 (not MD5/SHA1).
   - Verify session tokens are HTTP-only, secure, and have reasonable expiry.

3. **Check for injection vulnerabilities**
   - **SQL injection**: look for string concatenation in SQL queries instead of parameterized queries.
   - **XSS**: look for `dangerouslySetInnerHTML`, `innerHTML`, or unescaped user input rendered in templates.
   - **Command injection**: look for `exec()`, `eval()`, `child_process.exec()` with user input.
   - **Path traversal**: check file operations for unsanitized user input in paths.

4. **Review dependency security**
   - Run `pip-audit` / Dependabot alerts (MELTr is Python; not `npm audit` unless a JS subtree exists).
   - Flag outdated dependencies with known CVEs.
   - Check for overly permissive dependency ranges.

5. **Check CORS and CSP configuration**
   - MELTr binds locally by default — still verify API is not exposed without auth when enabled.
   - Verify CORS doesn't use `Access-Control-Allow-Origin: *` in production deployments.
   - Check for Content Security Policy headers when a web UI is in scope.
   - Verify `X-Frame-Options`, `X-Content-Type-Options`, and `Strict-Transport-Security` where HTTP is served publicly.

6. **Review data exposure**
   - Check API responses for leaking sensitive fields (API keys, internal paths, PII from entities).
   - Verify error messages don't expose stack traces or internal details in production.
   - Check logging for secrets / entity dumps being written to logs.
   - Prefer `MELTR_*` env vars; ensure `.env` and home YAML secrets stay out of git.

7. **Generate report** — produce a summary with severity ratings (Critical / High / Medium / Low) for each finding, with the file path, line number, and recommended fix.

## Notes

- This is a code review, not a penetration test. Recommend `pip-audit`, TruffleHog/gitleaks (see `security-baseline`), Semgrep, or `trivy` for automated scanning.
- Always check `.gitignore` to ensure `.env`, credentials, and key files are excluded.
- For FTSC portfolio baseline controls, use `.cursor/skills/security-baseline/SKILL.md`.
- For comprehensive auditing, recommend the OWASP Testing Guide.
