# Security

## Management API trust model

MELTr is designed as a **single-host agent**. The management API defaults to
`api.host: 127.0.0.1` and uses API-key auth for remote access control.

| Client | Auth when a key is configured |
|--------|-------------------------------|
| `GET /api/health` | None (public liveness) |
| Loopback (`127.0.0.1`, `::1`) | None by default (`api.auth.exempt_loopback: true`) |
| Non-loopback (LAN/WAN) | `Authorization: Bearer <key>` required |

**Key-implies-auth:** setting `MELTR_API_KEY` or `api.auth.key` enables auth
even when `api.auth.enabled` is false.

Loopback identity comes from the **TCP peer address** (`request.client.host`),
never from `X-Forwarded-For` or similar headers.

### Why local CLI skips the key

Operator commands (`meltr config reload`, the interactive config editor,
generator controls) talk to the same host’s API. Requiring a Bearer token for
those local calls forces every operator shell to carry `MELTR_API_KEY` for no
extra network security when the API is loopback-only.

### Hardening options

```yaml
api:
  host: 127.0.0.1   # keep loopback-only whenever possible
  auth:
    enabled: true
    key: "your-secret"          # or set MELTR_API_KEY
    exempt_loopback: true       # default; set false to require a key even locally
```

- **Shared multi-user hosts:** set `exempt_loopback: false` so every local
  process must present the key, or keep `api.host: 127.0.0.1` and lock down
  `MELTR_HOME` / the `meltr` service user.
- **Binding to `0.0.0.0`:** remote callers still need the key; any process on
  the same host that connects via loopback does not (unless
  `exempt_loopback: false`). MELTr logs a warning at startup in this case.
- **Browser CSRF / DNS rebinding:** with `exempt_loopback: true`, a page in the
  operator’s browser can call `http://127.0.0.1:<port>/api/...` without a
  Bearer token (peer is loopback). Empty `cors_origins` blocks many
  cross-origin XHR/fetch flows, but simple form POSTs and some no-cors
  requests can still hit mutating routes. If you treat the API key as
  end-to-end protection against browser-originated local attacks, set
  `exempt_loopback: false`.

### Reverse proxies

**Do not** put a public reverse proxy in front of MELTr’s loopback listen
address without terminating authentication at the proxy.

If the proxy connects to `http://127.0.0.1:8080`, every proxied request looks
local and would skip the API key when `exempt_loopback` is true. Prefer:

1. Keep MELTr on loopback and authenticate at the proxy, or
2. Set `api.auth.exempt_loopback: false` and require Bearer tokens end-to-end.

SSH tunnels to `127.0.0.1:8080` are fine — SSH is the auth boundary.

## Reporting issues

Report security issues privately to the maintainers rather than opening a
public GitHub issue with exploit details.
