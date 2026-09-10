"""Active RM session + TaskBundle scope for memory ranking."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_DEC_IN_QUERY = re.compile(r"\b(DEC-[A-Za-z0-9_-]+)\b", re.I)
_DEC_IN_BODY = re.compile(r"\[(DEC-[^\]]+)\]", re.I)


@dataclass
class ActiveScope:
    rm_session: str | None = None
    task_id: str | None = None
    frozen_decision_ids: set[str] = field(default_factory=set)


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def load_active_scope(repo_root: Path | None) -> ActiveScope:
    if not repo_root or not repo_root.is_dir():
        return ActiveScope()
    scope = ActiveScope()
    rm = _read_json(repo_root / ".requirementmind" / "active-session.json")
    if rm:
        sid = str(rm.get("session_id") or rm.get("id") or "").strip()
        if sid:
            scope.rm_session = sid
        dec_path = repo_root / ".requirementmind" / "sessions" / sid / "decisions.json"
        if not dec_path.is_file():
            dec_path = repo_root / ".requirementmind" / "decisions.json"
        dec_doc = _read_json(dec_path) if dec_path.is_file() else None
        if dec_doc:
            for d in dec_doc.get("decisions") or dec_doc.get("items") or []:
                if not isinstance(d, dict):
                    continue
                if str(d.get("status") or "").upper() != "FROZEN":
                    continue
                did = str(d.get("id") or d.get("decision_id") or "").strip()
                if did:
                    scope.frozen_decision_ids.add(did)
    task = _read_json(repo_root / ".contextmind" / "task.active.json")
    if task:
        tid = str(task.get("task_id") or task.get("id") or "").strip()
        if tid:
            scope.task_id = tid
    return scope


def try_load_scope_for_project(project_id: str) -> ActiveScope:
    try:
        from brain_services.project_context import ProjectContextService

        root = ProjectContextService().repo_root(project_id)
        return load_active_scope(root)
    except KeyError:
        return ActiveScope()


def decision_id_from_item(item: dict[str, Any]) -> str | None:
    meta = item.get("metadata") or {}
    raw = meta.get("rm_decision_id")
    if raw:
        return str(raw).strip()
    body = str(item.get("memory") or item.get("content") or "")
    m = _DEC_IN_BODY.search(body)
    return m.group(1) if m else None


def dec_ids_in_query(query: str) -> set[str]:
    return {m.group(1).upper() for m in _DEC_IN_QUERY.finditer(query or "")}


def session_score_delta(item: dict[str, Any], scope: ActiveScope | None, query: str) -> float:
    if not scope:
        return 0.0
    meta = item.get("metadata") or {}
    delta = 0.0
    item_session = str(meta.get("rm_session") or "").strip()
    item_task = str(meta.get("task_id") or "").strip()
    if scope.rm_session and item_session == scope.rm_session:
        delta += 10.0
    if scope.task_id and item_task == scope.task_id:
        delta += 6.0
    dec = decision_id_from_item(item)
    q_decs = dec_ids_in_query(query)
    if dec and q_decs:
        dec_u = dec.upper()
        if dec_u in q_decs:
            if scope.rm_session and item_session == scope.rm_session:
                delta += 18.0
            elif item_session and scope.rm_session and item_session != scope.rm_session:
                delta -= 22.0
            elif dec_u in {d.upper() for d in scope.frozen_decision_ids}:
                delta += 12.0
            else:
                delta -= 8.0
    elif dec and scope.frozen_decision_ids and dec.upper() in {d.upper() for d in scope.frozen_decision_ids}:
        delta += 4.0
    return delta


def drop_foreign_dec_hits(
    scored: list[tuple[float, dict[str, Any]]],
    query: str,
    scope: ActiveScope | None,
) -> list[tuple[float, dict[str, Any]]]:
    """When query names DEC-00x, drop same-id rows from other RM sessions."""
    q_decs = dec_ids_in_query(query)
    if not q_decs or not scope or not scope.rm_session:
        return scored
    kept: list[tuple[float, dict[str, Any]]] = []
    for s, item in scored:
        dec = decision_id_from_item(item)
        if dec and dec.upper() in q_decs:
            sess = str((item.get("metadata") or {}).get("rm_session") or "").strip()
            if sess != scope.rm_session:
                continue
        kept.append((s, item))
    return kept


def pick_with_kind_quota(
    scored: list[tuple[float, dict[str, Any]]],
    limit: int,
    *,
    scope: ActiveScope | None,
) -> list[dict[str, Any]]:
    """Prefer at least one bug + one active-session decision when available."""
    limit = min(max(1, limit), 8)
    if not scored:
        return []
    ordered = [it for _, it in sorted(scored, key=lambda x: (-x[0], x[1].get("last_seen_cn") or ""))]
    picked: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    def take(item: dict[str, Any]) -> bool:
        iid = str(item.get("id") or "")
        if iid and iid in seen_ids:
            return False
        if len(picked) >= limit:
            return False
        picked.append(item)
        if iid:
            seen_ids.add(iid)
        return True

    for kind in ("bug", "decision"):
        for item in ordered:
            meta = item.get("metadata") or {}
            if meta.get("kind") != kind:
                continue
            if kind == "decision" and scope and scope.rm_session:
                if str(meta.get("rm_session") or "") != scope.rm_session:
                    continue
            if take(item):
                break

    for item in ordered:
        if len(picked) >= limit:
            break
        take(item)
    return picked[:limit]
