# MELTr OSS vendor package `.mtb`

**Date:** 2026-08-31  
**Status:** Approved (companion to Templates / Templates-UI)  
**Repo:** MELTr  

## Goal

Hard-cut vendor packages from `.forge` / `extract_forge_package` to `.mtb` / `extract_mtb_package`. Same tar.gz layout. No dual-extension accept-path.

## Changes

- Rename `extract_forge_package` → `extract_mtb_package` (exports, CLI, tests)
- Download/install temp files `{vendor_id}.mtb`
- CLI `--local-file` help: “local .mtb file”
- Docs/glossary already say `.mtb`

## Tests

`tests/test_phase6_coverage.py` package helpers use `.mtb` and `extract_mtb_package`.

## Out of scope

Templates-UI download headers (sibling repo). No `.forge` alias.
