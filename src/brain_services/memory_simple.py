from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from brain_services.memory_auto_review import compute_auto_verdict, should_auto_promote
from brain_services.memory_lifecycle import (
    LIFECYCLE_CANDIDATE,
    LIFECYCLE_REJECTED,
    LIFECYCLE_VERIFIED,
    STATUS_CONFLICT,
    STATUS_OK,
    default_lifecycle_for_kind,
    effective_lifecycle,
    is_searchable,
    looks_like_secret,
    normalize_record,
)
from brain_services.memory_title import enrich_memory_metadata
from brain_services.token_analytics import memory_fingerprint, normalize_memory_text

DATA_DIR = Path(__file__).resolve().parents[2] / ".data" / "memories"
TZ_CN = timezone(timedelta(hours=8))


def _enrich_item(item: dict[str, Any]) -> dict[str, Any]:
    out = normalize_record(item)
    out["auto_verdict"] = compute_auto_verdict(out)
    return out


def _auto_promote_mode() -> str:
    return (os.environ.get("BRAIN_AUTO_PROMOTE") or "off").strip().lower()


class SimpleMemoryStore:
    """File-backed experience memory for offline demo (DEC-007 semantic: experience only)."""

    def __init__(self, data_dir: Path | None = None) -> None:
        self._dir = data_dir or DATA_DIR
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path(self, project_id: str) -> Path:
        return self._dir / f"{project_id}.jsonl"

    def _read_all(self, project_id: str) -> list[dict[str, Any]]:
        path = self._path(project_id)
        if not path.exists():
            return []
        items: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                items.append(json.loads(line))
        return items

    def _write_all(self, project_id: str, items: list[dict[str, Any]]) -> None:
        path = self._path(project_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for item in items:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

    def _verified_items(self, project_id: str) -> list[dict[str, Any]]:
        return [it for it in self._read_all(project_id) if is_searchable(it)]

    def search(self, project_id: str, query: str, limit: int = 5) -> list[dict[str, Any]]:
        from brain_services.rank import query_tokens, score_memory

        limit = min(max(1, limit), 8)
        items = self._verified_items(project_id)
        tokens = query_tokens(query or "")
        if not (query or "").strip() or not tokens:
            return [_enrich_item(it) for it in items[-limit:]]
        scored: list[tuple[float, dict[str, Any]]] = []
        for item in items:
            s = score_memory(item, tokens, query)
            if s > 0:
                scored.append((s, item))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [_enrich_item(it) for _, it in scored[:limit]]

    def add(
        self,
        project_id: str,
        summary: str,
        importance: str = "medium",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        import uuid

        if looks_like_secret(summary):
            return {"rejected": True, "reason": "secret", "id": None}

        meta_in = enrich_memory_metadata(summary, metadata or {})
        kind = str(meta_in.get("kind") or "experience")
        lifecycle = str(meta_in.get("lifecycle") or default_lifecycle_for_kind(kind)).lower()
        if lifecycle not in (LIFECYCLE_CANDIDATE, LIFECYCLE_VERIFIED, LIFECYCLE_REJECTED):
            lifecycle = default_lifecycle_for_kind(kind)
        meta_in["lifecycle"] = lifecycle
        meta_in.setdefault("source", meta_in.get("source") or "agent")

        title = str(meta_in.get("title") or "")
        norm = normalize_memory_text(summary)
        fp = memory_fingerprint(summary)
        explicit_idem = (metadata or {}).get("idempotency_key")
        if explicit_idem:
            meta_in["idempotency_key"] = str(explicit_idem)
        decision_key = None
        if meta_in.get("kind") == "decision" and meta_in.get("decision"):
            decision_key = memory_fingerprint(str(meta_in["decision"]))
        bug_key = None
        if meta_in.get("kind") == "bug" and meta_in.get("title"):
            bug_key = memory_fingerprint(str(meta_in["title"]) + "|" + norm[:200])
        now_cn = datetime.now(TZ_CN).strftime("%Y-%m-%d %H:%M:%S")
        items = self._read_all(project_id)
        if explicit_idem:
            for item in reversed(items):
                if str(item.get("metadata", {}).get("idempotency_key") or "") == str(explicit_idem):
                    return {
                        "id": str(item.get("id")),
                        "title": title,
                        "deduplicated": True,
                        "no_op": True,
                        "lifecycle": effective_lifecycle(item),
                    }
        for item in reversed(items):
            existing = item.get("memory") or item.get("content") or ""
            meta = item.get("metadata") or {}
            same_body = memory_fingerprint(existing) == fp or normalize_memory_text(existing) == norm
            same_decision = (
                decision_key
                and meta.get("kind") == "decision"
                and meta.get("decision")
                and memory_fingerprint(str(meta["decision"])) == decision_key
            )
            same_bug = (
                bug_key
                and meta.get("kind") == "bug"
                and meta.get("title")
                and memory_fingerprint(str(meta["title"]) + "|" + normalize_memory_text(existing)[:200])
                == bug_key
            )
            if not (same_body or same_decision or same_bug):
                continue
            ex_lc = effective_lifecycle(item)
            if lifecycle == LIFECYCLE_CANDIDATE and ex_lc == LIFECYCLE_VERIFIED:
                break
            prev_seen = item.get("last_seen_cn")
            skip_event = False
            if prev_seen:
                try:
                    prev_dt = datetime.strptime(str(prev_seen)[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=TZ_CN)
                    skip_event = datetime.now(TZ_CN) - prev_dt < timedelta(minutes=30)
                except ValueError:
                    skip_event = False
            item["last_seen_cn"] = now_cn
            item["repeat_count"] = int(item.get("repeat_count") or 1) + 1
            item.setdefault("metadata", {}).update(meta_in)
            item["title"] = title
            item["metadata"]["title"] = title
            if not item.get("lifecycle"):
                item["lifecycle"] = lifecycle
            self._write_all(project_id, items)
            if skip_event:
                return {
                    "id": str(item.get("id")),
                    "title": title,
                    "deduplicated": True,
                    "repeat_count": item["repeat_count"],
                    "event_skipped": True,
                }
            try:
                from brain_services.stats_store import record_event

                record_event(
                    "memory_store",
                    project_id=project_id,
                    detail=f"[dedup] {title or norm[:200]}",
                    metrics={
                        "importance": item.get("importance", importance),
                        "memory_id": item.get("id"),
                        "title": title,
                        "kind": meta_in.get("kind"),
                        "deduplicated": True,
                        "repeat_count": item["repeat_count"],
                    },
                    source="memory_store",
                )
            except Exception:
                pass
            return {
                "id": str(item.get("id")),
                "title": title,
                "deduplicated": True,
                "repeat_count": item["repeat_count"],
            }

        status = STATUS_OK
        conflicts_with: list[str] = []
        if lifecycle == LIFECYCLE_CANDIDATE:
            for v in items:
                if not is_searchable(v):
                    continue
                vbody = v.get("memory") or v.get("content") or ""
                if memory_fingerprint(vbody) == fp or normalize_memory_text(vbody) == norm:
                    status = STATUS_CONFLICT
                    vid = str(v.get("id") or "")
                    if vid:
                        conflicts_with.append(vid)
                    break

        record: dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "title": title,
            "memory": summary.strip(),
            "importance": importance,
            "metadata": meta_in,
            "fingerprint": fp,
            "lifecycle": lifecycle,
            "status": status,
            "source": meta_in.get("source") or "agent",
            "confidence": 0.5 if lifecycle == LIFECYCLE_CANDIDATE else 0.85,
            "evidence": list(meta_in.get("evidence") or []),
            "conflicts_with": conflicts_with,
            "supersedes": None,
            "created_cn": now_cn,
            "last_seen_cn": now_cn,
            "verified_at": now_cn if lifecycle == LIFECYCLE_VERIFIED else None,
            "repeat_count": 1,
        }
        record["auto_verdict"] = compute_auto_verdict(record)
        items.append(record)
        self._write_all(project_id, items)
        auto_promoted = False
        mode = _auto_promote_mode()
        if lifecycle == LIFECYCLE_CANDIDATE and should_auto_promote(record, mode):
            pr = self.promote(project_id, record["id"])
            auto_promoted = bool(pr.get("ok"))
            if auto_promoted:
                lifecycle = LIFECYCLE_VERIFIED
        try:
            from brain_services.stats_store import record_event

            record_event(
                "memory_store",
                project_id=project_id,
                detail=title or summary[:300],
                metrics={
                    "importance": importance,
                    "memory_id": record["id"],
                    "title": title,
                    "kind": meta_in.get("kind"),
                    "deduplicated": False,
                    "auto_verdict": record["auto_verdict"].get("verdict"),
                    "auto_promoted": auto_promoted,
                },
                source="memory_store",
            )
        except Exception:
            pass
        return {
            "id": record["id"],
            "title": title,
            "deduplicated": False,
            "repeat_count": 1,
            "lifecycle": lifecycle,
            "status": status,
            "conflict": status == STATUS_CONFLICT,
            "auto_verdict": record["auto_verdict"],
            "auto_promoted": auto_promoted,
        }

    def _merge_duplicates(self, items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
        """Merge rows by memory fingerprint; return (kept, removed_count)."""
        seen: dict[str, dict[str, Any]] = {}
        order: list[str] = []
        for item in items:
            text = item.get("memory") or item.get("content") or ""
            fp = memory_fingerprint(text)
            if fp in seen:
                prev = seen[fp]
                prev["repeat_count"] = int(prev.get("repeat_count") or 1) + int(
                    item.get("repeat_count") or 1
                )
                prev["last_seen_cn"] = item.get("last_seen_cn") or item.get("created_cn") or prev.get(
                    "last_seen_cn"
                )
                continue
            seen[fp] = item
            order.append(fp)
        kept = [seen[fp] for fp in order]
        removed = len(items) - len(kept)
        return kept, removed

    def dedupe_preview(self, project_id: str) -> dict[str, int]:
        """Dry-run: how many JSONL rows would be removed."""
        items = self._read_all(project_id)
        kept, removed = self._merge_duplicates(items)
        return {"before": len(items), "kept": len(kept), "removed": removed}

    def dedupe_file(self, project_id: str) -> dict[str, int]:
        """Keep newest row per normalized memory text."""
        items = self._read_all(project_id)
        kept, removed = self._merge_duplicates(items)
        if removed:
            self._write_all(project_id, kept)
        return {"kept": len(kept), "removed": removed, "before": len(items)}

    def list_all(
        self,
        project_id: str,
        limit: int = 200,
        lifecycle: str | None = None,
    ) -> list[dict[str, Any]]:
        items = self._read_all(project_id)
        if lifecycle:
            want = lifecycle.strip().lower()
            items = [it for it in items if effective_lifecycle(it) == want]
        for i, item in enumerate(items):
            if not item.get("id"):
                item["id"] = f"line-{i + 1}"
            meta = item.get("metadata") or {}
            if not item.get("title") and not meta.get("title"):
                from brain_services.memory_title import derive_memory_title

                t = derive_memory_title(str(item.get("memory") or ""), meta)
                item["title"] = t
            elif not item.get("title") and meta.get("title"):
                item["title"] = meta["title"]
        return [_enrich_item(it) for it in items[-limit:]]

    def promote(self, project_id: str, memory_id: str) -> dict[str, Any]:
        items = self._read_all(project_id)
        now_cn = datetime.now(TZ_CN).strftime("%Y-%m-%d %H:%M:%S")
        for item in items:
            if str(item.get("id")) != memory_id:
                continue
            if effective_lifecycle(item) != LIFECYCLE_CANDIDATE:
                return {"ok": False, "error": "not_candidate", "id": memory_id}
            item["lifecycle"] = LIFECYCLE_VERIFIED
            item["verified_at"] = now_cn
            item["confidence"] = max(float(item.get("confidence") or 0), 0.85)
            if (item.get("status") or STATUS_OK) == STATUS_CONFLICT:
                item["status"] = STATUS_OK
            meta = item.setdefault("metadata", {})
            meta["lifecycle"] = LIFECYCLE_VERIFIED
            self._write_all(project_id, items)
            return {"ok": True, "id": memory_id, "lifecycle": LIFECYCLE_VERIFIED}
        return {"ok": False, "error": "not_found", "id": memory_id}

    def reject(self, project_id: str, memory_id: str) -> dict[str, Any]:
        items = self._read_all(project_id)
        for item in items:
            if str(item.get("id")) != memory_id:
                continue
            if effective_lifecycle(item) != LIFECYCLE_CANDIDATE:
                return {"ok": False, "error": "not_candidate", "id": memory_id}
            item["lifecycle"] = LIFECYCLE_REJECTED
            meta = item.setdefault("metadata", {})
            meta["lifecycle"] = LIFECYCLE_REJECTED
            self._write_all(project_id, items)
            return {"ok": True, "id": memory_id, "lifecycle": LIFECYCLE_REJECTED}
        return {"ok": False, "error": "not_found", "id": memory_id}

    def backfill_titles(self, project_id: str) -> dict[str, int]:
        """Persist Phoenix-style display names + harvested related_files onto JSONL rows."""
        from brain_services.memory_title import enrich_memory_metadata

        items = self._read_all(project_id)
        updated = 0
        related_updated = 0
        for item in items:
            body = str(item.get("memory") or item.get("content") or "")
            prev_meta = dict(item.get("metadata") or {})
            prev_related = [str(x) for x in (prev_meta.get("related_files") or [])]
            meta = enrich_memory_metadata(body, prev_meta)
            title = str(meta.get("title") or "")
            prev = (item.get("title") or prev_meta.get("title") or "").strip()
            new_related = [str(x) for x in (meta.get("related_files") or [])]
            changed = (
                prev != title
                or prev_meta.get("kind") != meta.get("kind")
                or prev_related != new_related
            )
            if changed:
                updated += 1
            if prev_related != new_related:
                related_updated += 1
            item["title"] = title
            item["metadata"] = meta
        if updated:
            self._write_all(project_id, items)
        return {
            "total": len(items),
            "updated": updated,
            "related_files_updated": related_updated,
        }

    def get_by_id(self, project_id: str, memory_id: str) -> dict[str, Any] | None:
        for item in self._read_all(project_id):
            if str(item.get("id")) == memory_id:
                return _enrich_item(item)
        return None

    def update_by_id(
        self,
        project_id: str,
        memory_id: str,
        *,
        memory: str | None = None,
        title: str | None = None,
        applies_when: list[str] | None = None,
        do_not_use_when: list[str] | None = None,
        human_note: str | None = None,
        importance: str | None = None,
    ) -> dict[str, Any]:
        items = self._read_all(project_id)
        now_cn = datetime.now(TZ_CN).strftime("%Y-%m-%d %H:%M:%S")
        for item in items:
            if str(item.get("id")) != memory_id:
                continue
            if memory is not None:
                if looks_like_secret(memory):
                    return {"ok": False, "error": "secret"}
                item["memory"] = memory.strip()
                item["fingerprint"] = memory_fingerprint(memory)
            if title is not None:
                item["title"] = title.strip()
                item.setdefault("metadata", {})["title"] = title.strip()
            meta = item.setdefault("metadata", {})
            if applies_when is not None:
                item["applies_when"] = applies_when
                meta["applies_when"] = applies_when
            if do_not_use_when is not None:
                item["do_not_use_when"] = do_not_use_when
                meta["do_not_use_when"] = do_not_use_when
            if human_note is not None:
                item["human_note"] = human_note.strip()
                meta["human_note"] = human_note.strip()
            if importance is not None:
                item["importance"] = importance
            item["edited_cn"] = now_cn
            item["auto_verdict"] = compute_auto_verdict(item)
            self._write_all(project_id, items)
            return {"ok": True, "id": memory_id, "item": _enrich_item(item)}
        return {"ok": False, "error": "not_found", "id": memory_id}

    def delete_by_id(self, project_id: str, memory_id: str) -> bool:
        items = self._read_all(project_id)
        kept = [it for it in items if it.get("id") != memory_id]
        if len(kept) == len(items):
            return False
        self._write_all(project_id, kept)
        return True


def get_memory_backend():
    if os.environ.get("BRAIN_USE_MEM0") == "1":
        from brain_services.memory_service import MemoryService

        return MemoryService()
    return SimpleMemoryStore()
