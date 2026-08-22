#!/usr/bin/env python3
"""Refuse to publish if any private identifier leaks into the repo.

Run before every commit:  python3 scripts/anonymize_check.py
Verify the checker itself: python3 scripts/anonymize_check.py --selftest
"""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

BAD = [
    r"bjkim", r"kims\d+", r"유성", r"아빠", r"텔레그램", r"카카오", r"회계사", r"세무사",
    # real secrets: the prefix must be followed by actual key material
    r"sk-proj-[A-Za-z0-9_-]{8,}",
    r"sk-admin-[A-Za-z0-9_-]{8,}",
    r"sk-svcacct-[A-Za-z0-9_-]{8,}",
    r"tunnel_[0-9a-f]{32}",
    r"org-[A-Za-z0-9]{10,}",
    # a real home path, but not the documented placeholder /Users/you/
    r"/Users/(?!you/)[a-z]",
    # private workspace dirs (product names Hermes/OpenClaw in prose are fine)
    r"\.openclaw", r"/Users/[a-z]+/\.hermes",
]

EXT = {".md", ".mjs", ".js", ".py", ".json", ".sh", ".yml", ".yaml",
       ".txt", ".toml", ".html", ".css", ".svg", ".plist"}

SELF = Path(__file__).name


def scan():
    files = [
        f for f in REPO.rglob("*")
        if f.is_file() and f.suffix in EXT
        and ".git" not in f.parts and "node_modules" not in f.parts
        and f.name != SELF
    ]
    hits = []
    for f in files:
        text = f.read_text(encoding="utf-8", errors="ignore")
        for i, line in enumerate(text.splitlines(), 1):
            for pat in BAD:
                if re.search(pat, line, re.I):
                    hits.append((f.relative_to(REPO), i, pat, line.strip()[:110]))
    return files, hits


def main():
    files, hits = scan()
    print(f"scanned {len(files)} files")
    if hits:
        for path, line_no, pat, line in hits:
            print(f"LEAK {path}:{line_no}  /{pat}/  {line}")
        print(f"\n{len(hits)} leak(s) — do not publish")
        return 1
    print("0 leaks")
    return 0


def selftest():
    """Negative control: a planted leak MUST be caught, and cleanup MUST restore 0."""
    probe = REPO / "_leak_probe.md"
    probe.write_text("contact bjkim via telegram, key sk-proj-abc\n", encoding="utf-8")
    try:
        _, hits = scan()
        assert hits, "SELFTEST FAILED: planted leak was not detected"
        names = {h[0].name for h in hits}
        assert probe.name in names, f"SELFTEST FAILED: probe not among {names}"
    finally:
        probe.unlink()
    _, hits = scan()
    assert not hits, f"SELFTEST FAILED: repo not clean after cleanup: {hits[:3]}"
    print("SELFTEST PASS: leak detected when planted, 0 when removed")
    return 0


if __name__ == "__main__":
    sys.exit(selftest() if "--selftest" in sys.argv else main())
