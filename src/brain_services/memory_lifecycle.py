"""Memory gate: raw / candidate / verified (not Token-Mind L0–L2 budget names)."""

from __future__ import annotations

import re
from typing import Any

LIFECYCLE_CANDIDATE = "candidate"
LIFECYCLE_VERIFIED = "verified"
LIFECYCLE_REJECTED = "rejected"

STATUS_OK = "ok"
STATUS_CONFLICT = "conflict"
STATUS_SUPERSEDED = "superseded"

_SECRET_PATTERNS = (
    re.compile(r"(?i)\b(password|passwd|api[_-]?key|secret|token)\s*[=:]\s*\S+"),
    re.compile(r"\bsk-[a-zA-Z0-9]{20,}\b"),
    re.compile(r"(?i)jdbc:[^\s]+"),
)


def looks_like_secret(text: str) -> bool:
    return any(p.search(text or "") for p in _SECRET_PATTERNS)


def effective_lifecycle(item: dict[str, Any]) -> str:
    lc = (item.get("lifecycle") or "").strip().lower()
    if lc in (LIFECYCLE_CANDIDATE, LIFECYCLE_VERIFIED, LIFECYCLE_REJECTED):
        return lc
    return LIFECYCLE_VERIFIED


def is_grandfathered(item: dict[str, Any]) -> bool:
    if item.get("grandfathered") is True:
        return True
    return not (item.get("lifecycle") or "").strip()


def is_searchable(item: dict[str, Any]) -> bool:
    if effective_lifecycle(item) != LIFECYCLE_VERIFIED:
        return False
    if (item.get("status") or STATUS_OK) == STATUS_SUPERSEDED:
        return False
    return True


def is_change_context_eligible(item: dict[str, Any]) -> bool:
    """Path-scoped change hints: verified search pool + candidate bug/decision rows."""
    if (item.get("status") or STATUS_OK) == STATUS_SUPERSEDED:
        return False
    if is_searchable(item):
        return True
    meta = item.get("metadata") or {}
    kind = str(meta.get("kind") or item.get("kind") or "experience")
    if effective_lifecycle(item) == LIFECYCLE_CANDIDATE and kind in ("bug", "decision"):
        return True
    return False


def default_lifecycle_for_kind(kind: str | None) -> str:
    if kind == "decision":
        return LIFECYCLE_VERIFIED
    if kind == "constitution":
        return LIFECYCLE_VERIFIED
    return LIFECYCLE_CANDIDATE


def idempotency_key_for(kind: str, title: str, body: str, fingerprint: str) -> str:
    base = (kind or "experience").strip().lower()
    t = (title or "").strip()[:120]
    return f"{base}|{fingerprint}|{t}"


def normalize_record(item: dict[str, Any]) -> dict[str, Any]:
    """Attach effective lifecycle flags for API/UI without mutating disk on read."""
    out = dict(item)
    lc = effective_lifecycle(item)
    out["lifecycle"] = lc
    out["grandfathered"] = is_grandfathered(item)
    meta = dict(out.get("metadata") or {})
    out["metadata"] = meta
    if meta.get("kind") and not out.get("kind"):
        out["kind"] = meta["kind"]
    out.setdefault("status", STATUS_OK)
    out.setdefault("source", meta.get("source") or "agent")
    return out
