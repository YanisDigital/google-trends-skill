#!/usr/bin/env python3
"""Build the archive for the Claude app's skill upload.

The archive holds one folder, google-trends/, with SKILL.md directly inside it: no plugin
manifest, no tests, no CI files. Files are read from git at REF (default HEAD), so local junk such
as __pycache__ never ends up in it, and an older tag can be packaged with the current tool.

Usage: python tools/build_skill_zip.py [--ref REF] OUTPUT.zip
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import zipfile
from pathlib import Path

SKILL_DIR = "skills/google-trends/"
ARCHIVE_ROOT = "google-trends/"


def git(*args: str) -> bytes:
    return subprocess.run(["git", *args], capture_output=True, check=True).stdout


def build(ref: str, out: Path) -> list[str]:
    files = [f for f in git("ls-tree", "-r", "-z", "--name-only", ref, "--", SKILL_DIR).decode().split("\0") if f]
    if SKILL_DIR + "SKILL.md" not in files:
        raise SystemExit(f"{SKILL_DIR}SKILL.md not found at {ref}")
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(files):
            # fixed timestamp and mode: the same ref always gives the same archive
            info = zipfile.ZipInfo(ARCHIVE_ROOT + f[len(SKILL_DIR):], date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, git("show", f"{ref}:{f}"))
    names = zipfile.ZipFile(out).namelist()
    bad = [n for n in names if not n.startswith(ARCHIVE_ROOT) or ".claude-plugin" in n or "__pycache__" in n]
    if bad or ARCHIVE_ROOT + "SKILL.md" not in names:
        raise SystemExit(f"unexpected archive layout: {bad or names}")
    return names


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("output", type=Path)
    ap.add_argument("--ref", default="HEAD", help="git ref to package (default HEAD)")
    a = ap.parse_args()
    names = build(a.ref, a.output)
    print(f"{a.output}: {len(names)} files from {a.ref}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
