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


def safe_join(base: Path, *parts: str) -> Path:
    """Join parts under base and refuse anything that escapes it."""
    base_resolved = base.resolve()
    target = base_resolved.joinpath(*parts).resolve()
    if base_resolved != target and base_resolved not in target.parents:
        raise ValueError(f"path escapes the output directory: {target}")
    return target
