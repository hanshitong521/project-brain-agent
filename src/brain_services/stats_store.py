from __future__ import annotations

import json
import threading
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from brain_services.stats_filter import filter_events_for_dashboard, filter_memory_projects

DATA_DIR = Path(__file__).resolve().parents[2] / ".data" / "stats"
EVENTS_FILE = DATA_DIR / "events.jsonl"
TZ_CN = timezone(timedelta(hours=8))

_lock = threading.Lock()
_recent: deque[dict[str, Any]] = deque(maxlen=500)
_hydrated = False


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_cn() -> str:
    return datetime.now(TZ_CN).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def _load_events_from_file(limit: int | None = None) -> list[dict[str, Any]]:
    if not EVENTS_FILE.exists():
        return []
    try:
        lines = EVENTS_FILE.read_text(encoding="utf-8").strip().splitlines()
    except OSError as exc:
        from brain_services.stats_telemetry import log_stats_error

        log_stats_error("load_events_file", exc)
        return []
    events: list[dict[str, Any]] = []
    for ln in lines:
        if not ln.strip():
            continue
        try:
            events.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    events.sort(key=lambda e: e.get("timestamp_utc") or "", reverse=True)
    if limit is not None:
        return events[:limit]
    return events


def _hydrate_recent_from_file() -> None:
    global _hydrated
    if _hydrated:
        return
    events = _load_events_from_file()
    with _lock:
        if _hydrated:
            return
        for ev in reversed(events[:500]):
            _recent.appendleft(ev)
        _hydrated = True


def record_event(
    event_type: str,
    *,
    project_id: str | None = None,
    detail: str = "",
    metrics: dict[str, Any] | None = None,
    source: str = "api",
) -> dict[str, Any]:
    """Append one telemetry event (persisted + in-memory ring)."""
    event = {
        "id": f"evt-{datetime.now(timezone.utc).timestamp():.6f}",
        "event_type": event_type,
        "event_type_label": _EVENT_LABELS.get(event_type, event_type),
        "project_id": project_id,
        "detail": detail,
        "metrics": metrics or {},
        "source": source,
        "timestamp_utc": _now_iso(),
        "timestamp_cn": _now_cn(),
    }
    with _lock:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        try:
            with EVENTS_FILE.open("a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
        except OSError as exc:
            from brain_services.stats_telemetry import log_stats_error

            log_stats_error("record_event", exc, event_type=event_type, project_id=project_id)
            raise
        _recent.appendleft(event)
    try:
        from brain_services.stats_telemetry import stats_logger

        stats_logger().debug(
            "event %s %s project=%s saved=%s",
            event_type,
            event.get("id"),
            project_id,
            (metrics or {}).get("saved_tokens"),
        )
    except Exception:
        pass
    return event


_EVENT_LABELS = {
    "context_build": "组装任务上下文",
    "context_retrieval": "MCP 检索命中",
    "memory_store": "写入经验记忆",
    "memory_search": "检索经验记忆",
    "knowledge_search": "检索知识文档",
    "token_savings": "Token 节约统计",
    "stack_outcome": "任务栈结果",
    "system": "系统",
}


def load_events(limit: int = 200) -> list[dict[str, Any]]:
    _hydrate_recent_from_file()
    with _lock:
        file_events = _load_events_from_file()
        by_id: dict[str, dict[str, Any]] = {ev["id"]: ev for ev in file_events}
        for ev in _recent:
            by_id[ev["id"]] = ev
        merged = sorted(
            by_id.values(),
            key=lambda e: e.get("timestamp_utc") or "",
            reverse=True,
        )
        return merged[:limit]


def load_all_events() -> list[dict[str, Any]]:
    """Full JSONL scan for savings analytics (not capped by recent ring)."""
    _hydrate_recent_from_file()
    with _lock:
        file_events = _load_events_from_file()
        by_id: dict[str, dict[str, Any]] = {ev["id"]: ev for ev in file_events}
        for ev in _recent:
            by_id[ev["id"]] = ev
        return sorted(
            by_id.values(),
            key=lambda e: e.get("timestamp_utc") or "",
            reverse=True,
        )


def get_event_by_id(event_id: str) -> dict[str, Any] | None:
    for ev in load_events(500):
        if ev.get("id") == event_id:
            return ev
    return None


def memory_store_stats() -> dict[str, Any]:
    from brain_services.memory_simple import SimpleMemoryStore

    mem_dir = Path(__file__).resolve().parents[2] / ".data" / "memories"
    store = SimpleMemoryStore()
    projects: list[dict[str, Any]] = []
    total = 0
    total_removable = 0
    if mem_dir.exists():
        for path in sorted(mem_dir.glob("*.jsonl")):
            count = sum(1 for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip())
            total += count
            pid = path.stem
            preview = store.dedupe_preview(pid) if hasattr(store, "dedupe_preview") else {}
            removable = int(preview.get("removed") or 0)
            total_removable += removable
            projects.append(
                {
                    "project_id": pid,
                    "memory_count": count,
                    "dedupe_removable": removable,
                    "dedupe_unique": int(preview.get("kept") or count),
                    "file": str(path.name),
                    "file_abs": str(path.resolve()),
                    "updated_cn": datetime.fromtimestamp(
                        path.stat().st_mtime, tz=TZ_CN
                    ).strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
    return {
        "total_memories": total,
        "total_dedupe_removable": total_removable,
        "projects": projects,
    }


def _summarize_context_builds(events: list[dict[str, Any]]) -> dict[str, Any]:
    total_builds = 0
    sum_usage = 0
    sum_baseline = 0
    sum_saved = 0
    within_budget = 0
    baseline_below_usage = 0

    for ev in events:
        if ev.get("event_type") != "context_build":
            continue
        m = ev.get("metrics") or {}
        total_builds += 1
        usage = int(m.get("usage_tokens") or 0)
        baseline = int(m.get("baseline_tokens") or 0)
        sum_usage += usage
        if baseline > 0:
            sum_baseline += baseline
            sum_saved += max(0, baseline - usage)
            if baseline < usage:
                baseline_below_usage += 1
        if m.get("within_budget"):
            within_budget += 1

    avg_usage = round(sum_usage / total_builds, 1) if total_builds else 0
    savings_pct = round(100 * sum_saved / sum_baseline, 2) if sum_baseline else 0

    return {
        "context_build_count": total_builds,
        "total_usage_tokens": sum_usage,
        "total_baseline_tokens": sum_baseline,
        "total_saved_tokens": sum_saved,
        "average_context_tokens": avg_usage,
        "savings_percent": savings_pct,
        "within_budget_count": within_budget,
        "within_budget_rate": round(100 * within_budget / total_builds, 1) if total_builds else 100,
        "baseline_below_usage_count": baseline_below_usage,
    }


def _summarize_retrievals(events: list[dict[str, Any]]) -> dict[str, Any]:
    retrievals = [e for e in events if e.get("event_type") == "context_retrieval"]
    n = len(retrievals)
    if not n:
        return {
            "retrieval_count": 0,
            "retrieval_hit_count": 0,
            "retrieval_hit_rate": 0.0,
            "retrieval_memory_hit_rate": 0.0,
            "retrieval_knowledge_hit_rate": 0.0,
            "retrieval_get_change_count": 0,
            "retrieval_search_count": 0,
        }
    any_hits = 0
    mem_hits = 0
    know_hits = 0
    get_change = 0
    search = 0
    for e in retrievals:
        m = e.get("metrics") or {}
        if m.get("any_hit") or int(m.get("memory_hits") or 0) > 0 or int(m.get("knowledge_hits") or 0) > 0:
            any_hits += 1
        if m.get("memory_hit") or int(m.get("memory_hits") or 0) > 0:
            mem_hits += 1
        if m.get("knowledge_hit") or int(m.get("knowledge_hits") or 0) > 0:
            know_hits += 1
        op = m.get("op") or ""
        if op == "get_change_context":
            get_change += 1
        elif op == "search_project_context":
            search += 1
    return {
        "retrieval_count": n,
        "retrieval_hit_count": any_hits,
        "retrieval_hit_rate": round(100 * any_hits / n, 1),
        "retrieval_memory_hit_rate": round(100 * mem_hits / n, 1),
        "retrieval_knowledge_hit_rate": round(100 * know_hits / n, 1),
        "retrieval_get_change_count": get_change,
        "retrieval_search_count": search,
    }


def build_dashboard_payload(project_id: str | None = None) -> dict[str, Any]:
    from brain_services.project_context import ProjectContextService

    projects = ProjectContextService()
    # Wider window: MCP-heavy days drown builds in the old 150-event ring
    all_tracked = filter_events_for_dashboard(load_events(500), project_id=project_id, projects=projects)
    events = all_tracked[:200]
    mem = memory_store_stats()
    mem["projects"] = filter_memory_projects(mem["projects"], project_id=project_id, svc=projects)

    ctx = _summarize_context_builds(events)
    memory_writes = sum(1 for e in events if e.get("event_type") == "memory_store")
    ret = _summarize_retrievals(events)
    outcomes = [e for e in events if e.get("event_type") == "stack_outcome"]
    outcome_with_task = sum(1 for e in outcomes if (e.get("metrics") or {}).get("task_id"))

    today = _now_cn()[:10]
    today_events = [e for e in all_tracked if (e.get("timestamp_cn") or "").startswith(today)]
    today_builds = _summarize_context_builds(today_events)
    today_ret = _summarize_retrievals(today_events)
    today_writes = sum(1 for e in today_events if e.get("event_type") == "memory_store")
    today_outcomes = sum(1 for e in today_events if e.get("event_type") == "stack_outcome")

    tracked_ids = projects.list_tracked_project_ids()
    memory_ids = [p["project_id"] for p in mem["projects"]]
    event_ids = [e.get("project_id") for e in all_tracked if e.get("project_id")]
    project_ids = sorted({*tracked_ids, *memory_ids, *event_ids})

    from brain_services.contextmind_ledger import load_contextmind_cache_ledger

    pid_for_ledger = project_id or (project_ids[0] if len(project_ids) == 1 else None)
    cm_cache = load_contextmind_cache_ledger(pid_for_ledger)

    return {
        "server_time_cn": _now_cn(),
        "server_time_utc": _now_iso(),
        "filter_project_id": project_id,
        "available_project_ids": project_ids,
        "stats_scope": "tracked_repo_only",
        "summary": {
            **ctx,
            "memory_write_count": memory_writes,
            "total_stored_memories": mem["total_memories"],
            "memory_dedupe_removable": mem.get("total_dedupe_removable", 0),
            **ret,
            "stack_outcome_count": len(outcomes),
            "stack_outcome_with_task_id": outcome_with_task,
            "today_date": today,
            "today_context_build_count": today_builds["context_build_count"],
            "today_retrieval_count": today_ret["retrieval_count"],
            "today_retrieval_hit_rate": today_ret["retrieval_hit_rate"],
            "today_retrieval_memory_hit_rate": today_ret["retrieval_memory_hit_rate"],
            "today_retrieval_knowledge_hit_rate": today_ret["retrieval_knowledge_hit_rate"],
            "today_memory_write_count": today_writes,
            "today_stack_outcome_count": today_outcomes,
        },
        "memory_by_project": mem["projects"],
        "recent_events": events[:80],
        "event_type_labels": _EVENT_LABELS,
        "contextmind_cache": cm_cache,
    }
