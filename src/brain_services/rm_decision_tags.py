"""Tag legacy decision rows with rm_decision_id / rm_session from active RM session."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from brain_services.memory_simple import SimpleMemoryStore
from brain_services.session_scope import decision_id_from_item


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_frozen_decisions(rm_dir: Path) -> tuple[str | None, dict[str, str]]:
    active_path = rm_dir / "active-session.json"
    if not active_path.is_file():
        return None, {}
    active = _read_json(active_path)
    if not isinstance(active, dict):
        return None, {}
    session_id = str(active.get("session_id") or active.get("id") or "").strip() or None
    if not session_id:
        return None, {}
    rel = str(active.get("session_path") or f"sessions/{session_id}").strip()
    dec_path = rm_dir / rel / "decisions.json"
    if not dec_path.is_file():
        dec_path = rm_dir / "decisions.json"
    if not dec_path.is_file():
        return session_id, {}
    raw = _read_json(dec_path)
    items = raw if isinstance(raw, list) else (raw.get("decisions") or raw.get("items") or [])
    frozen: dict[str, str] = {}
    for d in items:
        if not isinstance(d, dict):
            continue
        if str(d.get("status") or "").upper() != "FROZEN":
            continue
        did = str(d.get("id") or d.get("decision_id") or "").strip()
        text = str(d.get("decision") or d.get("text") or d.get("summary") or "").strip()
        if did and text:
            frozen[did] = text
    return session_id, frozen


def _matches_frozen_text(item: dict[str, Any], dec_id: str, expected: str) -> bool:
    body = str(item.get("memory") or item.get("content") or "")
    meta = item.get("metadata") or {}
    decision_field = str(meta.get("decision") or "")
    needle = expected.strip()
    if not needle:
        return False
    if needle in body or needle in decision_field:
        return True
    tagged = f"[{dec_id}]"
    return tagged in body and needle in body


def backfill_tags(
    store: SimpleMemoryStore,
    project_id: str,
    session_id: str | None,
    frozen: dict[str, str],
) -> dict[str, int]:
    if not session_id or not frozen:
        return {"updated": 0}
    items = store._read_all(project_id)
    updated = 0
    for item in items:
        dec = decision_id_from_item(item)
        if not dec or dec not in frozen:
            continue
        if not _matches_frozen_text(item, dec, frozen[dec]):
            continue
        meta = item.setdefault("metadata", {})
        if meta.get("rm_decision_id") == dec and meta.get("rm_session") == session_id:
            continue
        meta["rm_decision_id"] = dec
        meta["rm_session"] = session_id
        meta.setdefault("source", "requirementmind")
        updated += 1
    if updated:
        store._write_all(project_id, items)
    return {"updated": updated}
