#!/usr/bin/env python3
"""Fail CI if unexpected LogForge / pipeline product strings remain in scanned paths."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALLOWLIST_PATH = Path(__file__).with_name("logforge_string_allowlist.txt")

PATTERN = r"logforge|LogForge|LOGFORGE|logforge_metadata|\bpipelines\b|\bPipeline\b"

SCAN_TARGETS = [
    "src",
    "tests",
    "examples",
    "docs",
    "README.md",
    "DEPLOYMENT.md",
    "scripts",
]

EXCLUDE_GLOBS = [
    "docs/superpowers/**",
    "scripts/check_logforge_strings.py",
    "scripts/logforge_string_allowlist.txt",
]


def load_allowlist(path: Path) -> list[str]:
    rules: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        rules.append(line)
    return rules


def line_allowed(rel_path: str, line_no: int, line: str, rules: list[str]) -> bool:
    for rule in rules:
        if rule.startswith("re:"):
            if re.search(rule[3:], line):
                return True
            continue

        if ":" in rule and not rule.startswith("http"):
            prefix, _, needle = rule.partition(":")
            if not rel_path.startswith(prefix.rstrip("/")):
                continue
            if needle.isdigit():
                if int(needle) == line_no:
                    return True
                continue
            if needle in line:
                return True
            continue

        if rule in line:
            return True
    return False


def collect_hits() -> list[tuple[str, int, str]]:
    cmd = ["rg", "-n", "--no-heading", PATTERN, *SCAN_TARGETS]
    for glob in EXCLUDE_GLOBS:
        cmd.extend(["--glob", f"!{glob}"])
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False)
    if proc.returncode not in (0, 1):
        print(proc.stderr or proc.stdout, file=sys.stderr)
        raise SystemExit(f"rg failed with exit code {proc.returncode}")

    hits: list[tuple[str, int, str]] = []
    for raw in proc.stdout.splitlines():
        if not raw.strip():
            continue
        path_part, _, rest = raw.partition(":")
        line_no_str, _, content = rest.partition(":")
        hits.append((path_part, int(line_no_str), content))
    return hits


def main() -> int:
    if not ALLOWLIST_PATH.is_file():
        print(f"Missing allowlist: {ALLOWLIST_PATH}", file=sys.stderr)
        return 2

    rules = load_allowlist(ALLOWLIST_PATH)
    violations: list[str] = []

    for rel_path, line_no, content in collect_hits():
        if line_allowed(rel_path, line_no, content, rules):
            continue
        violations.append(f"{rel_path}:{line_no}:{content}")

    if violations:
        print(
            "Unexpected LogForge / pipeline strings (fix or allowlist intentionally):\n",
            file=sys.stderr,
        )
        for item in sorted(violations):
            print(f"  {item}", file=sys.stderr)
        print(
            f"\n{len(violations)} violation(s). See scripts/logforge_string_allowlist.txt",
            file=sys.stderr,
        )
        return 1

    print("OK: no unexpected LogForge / pipeline strings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
