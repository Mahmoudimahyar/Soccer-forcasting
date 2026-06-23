"""Provider-neutral commentary text normalization (research_only). Preserves language; never invents text."""
from __future__ import annotations
import hashlib
import re


def content_hash(text) -> str:
    return hashlib.sha256(("" if text is None else str(text)).encode("utf-8")).hexdigest()


def normalize_text(text) -> str:
    """Whitespace-collapse + strip. Unicode preserved (multilingual-safe). No translation, no rewriting."""
    if text is None:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip()
