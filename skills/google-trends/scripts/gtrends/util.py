"""Small shared helpers: text sanitising, safe paths, spreadsheet-injection guard."""
from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path

_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
_FORMULA_START = ("=", "+", "-", "@", "\t", "\r")


def clean_text(value: object, limit: int = 200) -> str:
    """Return a printable, length-limited string. Trends text is untrusted input."""
    text = _CONTROL.sub("", str(value if value is not None else "")).strip()
    return text[:limit]


def spreadsheet_safe(value: object) -> object:
    """Neutralise CSV/XLSX formula injection: text starting with = + - @ gets a leading apostrophe."""
    if isinstance(value, str) and value.startswith(_FORMULA_START):
        return "'" + value
    return value


def slugify(text: str, limit: int = 48) -> str:
    """Filesystem-safe slug (letters of any script, digits, dashes) plus a short hash."""
    norm = unicodedata.normalize("NFKC", text).lower()
    norm = re.sub(r"[^\w]+", "-", norm, flags=re.UNICODE).strip("-_")
    norm = norm[:limit].strip("-_")
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:6]
    return f"{norm}-{digest}" if norm else digest


MAX_INPUT_BYTES = 5_000_000
OUTPUT_GITIGNORE = "# Created by google-trends-skill: reports describe your research, keep them out of git.\n*\n"


def read_text_capped(path: str | Path, limit: int = MAX_INPUT_BYTES) -> str:
    """Read a UTF-8 file, refusing anything larger than `limit` bytes."""
    p = Path(path)
    if p.stat().st_size > limit:
        raise ValueError(f"{p} is larger than {limit // 1_000_000} MB; refusing to read it")
    return p.read_text(encoding="utf-8-sig")


def prepare_output_dir(out: Path) -> bool:
    """Create the output folder. A folder created here gets a .gitignore that ignores everything
    in it, so reports never land in the user's own repository by accident. An existing folder is
    left as it is; returns whether it is protected by our .gitignore."""
    if out.exists():
        return (out / ".gitignore").is_file()
    out.mkdir(parents=True)
    (out / ".gitignore").write_text(OUTPUT_GITIGNORE, encoding="utf-8")
    return True


_MD_SPECIAL = ("\\", "`", "*", "_", "[", "]", "|", "<", ">", "!", "#")


def md_escape(text: object, limit: int = 200) -> str:
    """Escape untrusted text for Markdown: no links, images, HTML or table breaks."""
    s = clean_text(text, limit)
    for ch in _MD_SPECIAL:
        s = s.replace(ch, "\\" + ch)
    return s.replace("\n", " ")


def safe_join(base: Path, *parts: str) -> Path:
    """Join parts under base and refuse anything that escapes it."""
    base_resolved = base.resolve()
    target = base_resolved.joinpath(*parts).resolve()
    if base_resolved != target and base_resolved not in target.parents:
        raise ValueError(f"path escapes the output directory: {target}")
    return target
