from __future__ import annotations

import re
from typing import Any

from mcp.server.fastmcp import FastMCP

_ARABIC_MAP = str.maketrans({"ي": "ی", "ك": "ک", "ى": "ی", "ؤ": "و", "إ": "ا", "أ": "ا"})
_SPACE_FIXES = [
    (r"\b(ن?می)\s+([آ-ی])", r"\1‌\2"),
    (r"\b([آ-ی]+)\s+(ها|های|تر|ترین)\b", r"\1‌\2"),
]


def _normalize(text: str, persian_digits: bool = False) -> str:
    value = text.translate(_ARABIC_MAP).replace("ـ", "")
    value = re.sub(r"[ \t]+", " ", value)
    for pattern, replacement in _SPACE_FIXES:
        value = re.sub(pattern, replacement, value)
    value = re.sub(r"\s+([،؛؟.!])", r"\1", value)
    value = value.replace("“", "«").replace("”", "»").replace("„", "«")
    value = re.sub(r"\s*—\s*", "، ", value)
    if persian_digits:
        value = value.translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))
    return value.strip()


def _register_hint(deliverable: str, audience: str) -> str:
    value = f"{deliverable} {audience}".lower()
    if any(x in value for x in ("مقاله", "پایان", "academic", "research", "report")):
        return "academic"
    if any(x in value for x in ("نامه", "سازمان", "اداره", "official letter")):
        return "formal-administrative"
    if any(x in value for x in ("instagram", "telegram", "chat", "caption", "شبکه")):
        return "colloquial-written"
    return "formal-human"


def register_persian_writing_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    def dana_normalize_persian(text: str, persian_digits: bool = False) -> dict[str, Any]:
        """Normalize Persian characters, whitespace, punctuation and common نیم‌فاصله patterns."""
        normalized = _normalize(text, persian_digits)
        return {"text": normalized, "changed": normalized != text}

    @mcp.tool()
    def dana_lint_persian(text: str) -> dict[str, Any]:
        """Report common Persian typography and AI-style issues without rewriting the text."""
        issues: list[dict[str, str]] = []
        if re.search(r"[يك]", text):
            issues.append({"type": "characters", "message": "Arabic ي/ك found; use Persian ی/ک."})
        if "—" in text or "–" in text:
            issues.append({"type": "punctuation", "message": "Avoid em/en dashes in Persian prose; use punctuation or restructure."})
        if re.search(r"\b(می|نمی)\s+[آ-ی]", text):
            issues.append({"type": "orthography", "message": "Check نیم‌فاصله after می/نمی."})
        if "می‌باشد" in text:
            issues.append({"type": "style", "message": "Consider a more direct Persian verb instead of می‌باشد."})
        if re.search(r"\b(لازم به ذکر است|در دنیای امروز|شایان ذکر است)\b", text):
            issues.append({"type": "style", "message": "Possible inflated AI-style phrase; prefer direct wording."})
        return {"ok": not issues, "issues": issues, "normalized_preview": _normalize(text)}

    @mcp.tool()
    def dana_prepare_persian_text(text: str, deliverable: str = "text", audience: str = "", persian_digits: bool = False) -> dict[str, Any]:
        """Run a practical Persian-writing pass: register hint, normalization and quality checks."""
        normalized = _normalize(text, persian_digits)
        lint = dana_lint_persian(normalized)
        return {
            "register": _register_hint(deliverable, audience),
            "text": normalized,
            "quality": lint,
            "rtl_recommendation": "Use direction: rtl, text-align: start, and a Persian-capable font such as Vazirmatn.",
        }
