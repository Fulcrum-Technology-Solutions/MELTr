#!/usr/bin/env python3
"""Fail CI if unexpected LogForge / pipeline product strings remain in scanned paths.

Pure-Python scanner (no ripgrep dependency) for portable CI.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALLOWLIST_PATH = Path(__file__).with_name("logforge_string_allowlist.txt")

PATTERN = re.compile(
    r"logforge|LogForge|LOGFORGE|logforge_metadata|\bpipelines\b|\bPipeline\b"
)

SCAN_TARGETS = [
    "src",
    "tests",
    "examples",
    "docs",
    "README.md",
    "DEPLOYMENT.md",
    "scripts",
]

# Relative path prefixes / exact files to skip
EXCLUDE_PREFIXES = (
    "docs/superpowers/",
)
EXCLUDE_FILES = {
    "scripts/check_logforge_strings.py",
    "scripts/logforge_string_allowlist.txt",
}

TEXT_SUFFIXES = {
    ".py",
    ".md",
    ".yml",
    ".yaml",
    ".toml",
    ".txt",
    ".sh",
    ".j2",
    ".json",
}


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


def _iter_files() -> list[Path]:
    files: list[Path] = []
    for target in SCAN_TARGETS:
        path = ROOT / target
        if not path.exists():
            continue
        if path.is_file():
            files.append(path)
            continue
        for child in path.rglob("*"):
            if not child.is_file():
                continue
            if child.suffix.lower() not in TEXT_SUFFIXES and child.name not in {
                "Dockerfile",
                "Makefile",
            }:
                continue
            files.append(child)
    return files


def collect_hits() -> list[tuple[str, int, str]]:
    hits: list[tuple[str, int, str]] = []
    for path in _iter_files():
        rel = path.relative_to(ROOT).as_posix()
        if rel in EXCLUDE_FILES:
            continue
        if any(rel.startswith(prefix) for prefix in EXCLUDE_PREFIXES):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            if PATTERN.search(line):
                hits.append((rel, line_no, line))
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
