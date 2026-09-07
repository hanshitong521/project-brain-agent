"""Phoenix-style display names for memory rows (OpenInference: every span has a name)."""

from __future__ import annotations

import re
from typing import Any

_TASK_PREFIX = re.compile(r"^\[([^\]]{1,80})\]\s*")
_DEC_ID = re.compile(r"\[DEC-(\d+)\]")
_BUG_HEAD = re.compile(r"^\[BUG\]\s*(.+)$", re.MULTILINE)
_DECISION_HEAD = re.compile(r"^\[DECISION\]\s*\n?(.*)$", re.MULTILINE)


def derive_memory_title(
    summary: str,
    metadata: dict[str, Any] | None = None,
    *,
    max_len: int = 72,
) -> str:
    """Stable short title for dashboard / MCP slim rows."""
    meta = metadata or {}
    explicit = (meta.get("title") or "").strip()
    if explicit:
        return _clip(explicit, max_len)

    kind = str(meta.get("kind") or "experience")
    if kind == "bug":
        t = (meta.get("title") or "").strip()
        if t:
            return _clip(t, max_len)
        m = _BUG_HEAD.search(summary or "")
        if m:
            return _clip(m.group(1).strip(), max_len)

    if kind == "decision":
        decision = (meta.get("decision") or "").strip()
        if decision:
            dec = _DEC_ID.search(decision)
            if dec:
                rest = decision
                rest = re.sub(r"^\[DEC-\d+\]\s*", "", rest)
                rest = re.sub(r"^[ABC]\.\s*", "", rest).strip()
                return _clip(f"DEC-{dec.group(1)} {rest}", max_len)
            return _clip(decision, max_len)
        m = _DECISION_HEAD.search(summary or "")
        if m and m.group(1).strip():
            return _clip(m.group(1).strip(), max_len)

    task_id = (meta.get("task_id") or "").strip()
    body = (summary or "").strip()
    m = _TASK_PREFIX.match(body)
    if m:
        tid = m.group(1).strip()
        rest = body[m.end() :].strip()
        rest = re.sub(r"\s+Ledger:.*$", "", rest, flags=re.I).strip()
        if rest:
            return _clip(f"{tid} · {rest}", max_len)
        return _clip(tid, max_len)
    if task_id:
        rest = re.sub(r"\s+Ledger:.*$", "", body, flags=re.I).strip()
        if rest.startswith(f"[{task_id}]"):
            rest = rest[len(task_id) + 2 :].strip()
        return _clip(f"{task_id} · {rest}" if rest else task_id, max_len)

    # experience / bare: first line, strip ledger noise
    first = body.split("\n", 1)[0]
    first = re.sub(r"\s+Ledger:.*$", "", first, flags=re.I).strip()
    return _clip(first or "untitled", max_len)


def parse_task_id_from_summary(summary: str) -> str | None:
    m = _TASK_PREFIX.match((summary or "").strip())
    return m.group(1).strip() if m else None


def enrich_memory_metadata(
    summary: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Ensure kind + title (+ task_id / related_files when present) on write."""
    from brain_services.rank import extract_related_paths

    meta = dict(metadata or {})
    kind = str(meta.get("kind") or "experience")
    if kind not in ("experience", "decision", "bug"):
        kind = "experience"
    meta["kind"] = kind
    if not meta.get("task_id"):
        tid = parse_task_id_from_summary(summary)
        if tid:
            meta["task_id"] = tid
    # Auto-harvest file paths so get_change_context can bind memories to files
    existing = [str(x) for x in (meta.get("related_files") or []) if str(x).strip()]
    scraped = extract_related_paths(summary or "")
    if existing or scraped:
        seen: set[str] = set()
        merged: list[str] = []
        for p in existing + scraped:
            key = p.replace("\\", "/").lower()
            if key in seen:
                continue
            seen.add(key)
            merged.append(p.replace("\\", "/"))
            if len(merged) >= 16:
                break
        meta["related_files"] = merged
    meta["title"] = derive_memory_title(summary, meta)
    return meta


def _clip(s: str, max_len: int) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 1].rstrip() + "…"
