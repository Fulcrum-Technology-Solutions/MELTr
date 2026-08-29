# HTTP destination presets

MELTr ships example HTTP output definitions in `examples/config.production-http.yaml`. Use these patterns for **Cribl Stream HTTP Source** and **Splunk HEC** endpoints.

Validate any config change before restart:

```bash
meltr config validate
```

## Cribl HTTP Source

Point an HTTP output at your Cribl HTTP collector (path varies by source config):

```yaml
outputs:
  definitions:
    - name: http-cribl
      type: http
      url: https://cribl.example.com:10080/cribl/_bulk
      method: POST
      headers:
        Authorization: "Bearer ${CRIBL_TOKEN}"
        Content-Type: "application/json"
      batch_size: 100
      batch_interval: 5
      timeout: 30
      include_metadata: false   # raw events; see below
```

Set the token in the environment (`export CRIBL_TOKEN=...`) rather than in `config.yaml`.

## Splunk HEC

Splunk expects `Authorization: Splunk <token>` on the collector endpoint:

```yaml
    - name: splunk-hec
      type: http
      url: https://splunk.example.com:8088/services/collector/event
      method: POST
      headers:
        Authorization: "Splunk ${SPLUNK_HEC_TOKEN}"
        Content-Type: "application/json"
      batch_size: 100
      batch_interval: 5
      timeout: 30
      include_metadata: false
```

Use `export SPLUNK_HEC_TOKEN=...` on the host running MELTr.

## `include_metadata`

When `include_metadata: true` on an HTTP output, each POST body is wrapped:

```json
{
  "event": { "...": "rendered template payload" },
  "logforge_metadata": {
    "generated_at": "2026-08-29T14:00:00-04:00",
    "generator": "lab-pipeline::0",
    "template_id": "vendor/product/source/event",
    "vendor": "vendor",
    "product": "product",
    "data_source": "source"
  }
}
```

| Setting | Use when |
|---------|----------|
| `false` (default) | Downstream expects raw JSON/text (typical Splunk HEC `_raw`, Cribl passthrough) |
| `true` | Router needs generator/template context (Cribl pipelines, custom normalizers) |

The wrapper field name remains `logforge_metadata` for compatibility with existing Cribl/Splunk routing rules.

## Interactive setup

`meltr config edit` → Outputs → Add HTTP offers presets for **Bearer**, **Splunk HEC**, and **API Key** auth, plus an `include_metadata` prompt.

## Testing connectivity

There is no separate `meltr outputs test` command in v2.0. Use:

1. `meltr config validate` — schema and reference checks
2. Start the service and watch output metrics: `GET /api/metrics` (requires auth when a key is set)
3. Point a generator or pipeline at the output and inspect the downstream system

For a one-off probe, add a short **burst** schedule on a test generator so emission stops automatically.
