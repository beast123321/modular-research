"""Reference-content resolution for modular-research.

Resolution is deliberately local-first. Direct content IDs and IDs embedded in
Douyin URLs are extracted without network I/O. Unresolved share URLs are marked
for a provider fallback; this module itself never performs provider calls.
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qs, urlparse

_DOYIN_VIDEO_PATH = re.compile(r"(?:^|/)video/(\d{10,})/?(?:$|[?#])")
_ID_QUERY_KEYS = ("modal_id", "aweme_id", "item_id")


def _clean_id(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    return text if text.isdigit() else None


def resolve_reference_content(item: dict[str, Any]) -> dict[str, Any]:
    """Resolve a canonical reference item without performing network I/O."""
    if not isinstance(item, dict):
        raise ValueError("reference content item must be an object")

    resolved = dict(item)
    platform = str(resolved.get("platform") or "").strip().lower() or None
    resolved["platform"] = platform

    explicit = _clean_id(resolved.get("content_id"))
    if explicit:
        resolved["content_id"] = explicit
        resolved["resolution_status"] = "resolved_local"
        resolved["provider_fallback_required"] = False
        return resolved

    url = str(resolved.get("url") or "").strip()
    content_id: str | None = None
    if url:
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        for key in _ID_QUERY_KEYS:
            values = query.get(key) or []
            if values:
                content_id = _clean_id(values[0])
                if content_id:
                    break
        if content_id is None:
            match = _DOYIN_VIDEO_PATH.search(parsed.path)
            if match:
                content_id = match.group(1)

    if content_id:
        resolved["content_id"] = content_id
        resolved["resolution_status"] = "resolved_local"
        resolved["provider_fallback_required"] = False
        return resolved

    is_douyin = platform == "douyin" or "douyin.com" in urlparse(url).netloc.lower()
    if url and is_douyin:
        resolved["content_id"] = None
        resolved["resolution_status"] = "provider_required"
        resolved["provider_fallback_required"] = True
    else:
        resolved["content_id"] = None
        resolved["resolution_status"] = "unresolved"
        resolved["provider_fallback_required"] = False
    return resolved
