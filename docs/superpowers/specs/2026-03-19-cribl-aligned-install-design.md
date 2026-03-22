# Cribl-aligned install and run (design spec)

**Goal:** Operator documentation and `init` defaults match a Cribl-style flow: prerequisites → install under `/opt` → filesystem rules → initialize state → run (foreground vs systemd), without CLI “profile” flags.

**Reference:** [Cribl Stream single-instance deployment](https://docs.cribl.io/stream/deploy-single-instance/).

## Decisions

| Area | Decision |
|------|----------|
| Documentation | Added [`docs/deployment/linux-single-instance.md`](../../deployment/linux-single-instance.md) as the primary Linux on-prem guide; README Quick Start trimmed with links to it, DEPLOYMENT, TROUBLESHOOTING. |
| README | Removed duplicate tail section; single license block. |
| `init` defaults | `--create-user` / `--no-create-user` are optional; if omitted, **create service user only when `euid == 0`**, else skip (evaluation / non-root path). Implemented in `default_create_user()` in `src/logforge/cli/init.py`. |
| Service | No systemd template change; documented `LimitNOFILE`, journal, `api start` in deployment doc. |
| Out of scope | Official tarball artifact, `--profile`, Kubernetes docs. |

## Testing

- [`tests/test_init.py`](../../tests/test_init.py): `test_init_without_create_user_flags_defaults_to_non_root_behavior` with `geteuid` patched to non-zero.
- Existing tests continue to pass `--no-create-user` explicitly.

## Spec review

Self-review: design matches attached implementation plan; no open requirements.
