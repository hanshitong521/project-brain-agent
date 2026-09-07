from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta, timezone
from typing import Any

TZ_CN = timezone(timedelta(hours=8))


def normalize_memory_text(summary: str) -> str:
    s = summary.strip()
    if " Ledger:" in s:
        s = s.split(" Ledger:", 1)[0].strip()
    s = re.sub(r"\s+", " ", s)
    return s


def memory_fingerprint(summary: str) -> str:
    return hashlib.sha256(normalize_memory_text(summary).encode("utf-8")).hexdigest()[:16]


def _parse_cn_ts(ts: str) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.strptime(ts[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=TZ_CN)
    except ValueError:
        return None


def _bucket_key(dt: datetime, period: str) -> str:
    if period == "hour":
        return dt.strftime("%Y-%m-%d %H:00")
    if period == "day":
        return dt.strftime("%Y-%m-%d")
    if period == "week":
        iso = dt.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"
    if period == "month":
        return dt.strftime("%Y-%m")
    if period == "year":
        return dt.strftime("%Y")
    return dt.strftime("%Y-%m-%d")


def _date_in_range(ts_cn: str, date_from: str | None, date_to: str | None) -> bool:
    if not date_from and not date_to:
        return True
    dt = _parse_cn_ts(ts_cn)
    if not dt:
        return False
    d = dt.date()
    if date_from:
        try:
            if d < datetime.strptime(date_from, "%Y-%m-%d").date():
                return False
        except ValueError:
            return False
    if date_to:
        try:
            if d > datetime.strptime(date_to, "%Y-%m-%d").date():
                return False
        except ValueError:
            return False
    return True


def context_build_ledger(
    events: list[dict[str, Any]],
    *,
    project_id: str | None = None,
    hit_filter: str = "all",
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 200,
    tracked_only: bool = True,
) -> list[dict[str, Any]]:
    from brain_services.project_context import ProjectContextService

    projects = ProjectContextService()
    rows: list[dict[str, Any]] = []
    for ev in events:
        if ev.get("event_type") != "context_build":
            continue
        pid = ev.get("project_id")
        if project_id and pid != project_id:
            continue
        if tracked_only and not projects.is_tracked_project(pid):
            continue
        if not _date_in_range(ev.get("timestamp_cn") or "", date_from, date_to):
            continue
        m = ev.get("metrics") or {}
        mem_h = int(m.get("memory_hits") or 0)
        know_h = int(m.get("knowledge_hits") or 0)
        if hit_filter == "memory_hit" and mem_h <= 0:
            continue
        if hit_filter == "knowledge_hit" and know_h <= 0:
            continue
        if hit_filter == "any_hit" and mem_h <= 0 and know_h <= 0:
            continue
        if hit_filter == "miss" and (mem_h > 0 or know_h > 0):
            continue
        usage = int(m.get("usage_tokens") or 0)
        baseline = int(m.get("baseline_tokens") or 0)
        saved = int(m.get("saved_tokens") or max(0, baseline - usage))
        pct = round(100 * saved / baseline, 1) if baseline > 0 else 0.0
        rows.append(
            {
                "event_id": ev.get("id"),
                "timestamp_cn": ev.get("timestamp_cn"),
                "timestamp_utc": ev.get("timestamp_utc"),
                "project_id": ev.get("project_id"),
                "task": ev.get("detail") or "",
                "usage_tokens": usage,
                "baseline_tokens": baseline,
                "saved_tokens": saved,
                "savings_percent": pct,
                "baseline_source": m.get("baseline_source"),
                "memory_hits": mem_h,
                "knowledge_hits": know_h,
                "memory_hit": mem_h > 0,
                "knowledge_hit": know_h > 0,
                "within_budget": bool(m.get("within_budget")),
                "knowledge_sources": m.get("knowledge_sources") or [],
            }
        )
    return rows[:limit]


def aggregate_savings(
    ledger: list[dict[str, Any]],
    period: str = "day",
) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}
    for row in ledger:
        dt = _parse_cn_ts(row.get("timestamp_cn") or "")
        if not dt:
            continue
        key = _bucket_key(dt, period)
        b = buckets.setdefault(
            key,
            {
                "period": key,
                "build_count": 0,
                "saved_tokens": 0,
                "usage_tokens": 0,
                "baseline_tokens": 0,
                "memory_hit_count": 0,
                "knowledge_hit_count": 0,
                "miss_count": 0,
                "both_hit_count": 0,
            },
        )
        b["build_count"] += 1
        b["saved_tokens"] += int(row.get("saved_tokens") or 0)
        b["usage_tokens"] += int(row.get("usage_tokens") or 0)
        b["baseline_tokens"] += int(row.get("baseline_tokens") or 0)
        if row.get("memory_hit"):
            b["memory_hit_count"] += 1
        if row.get("knowledge_hit"):
            b["knowledge_hit_count"] += 1
        if not row.get("memory_hit") and not row.get("knowledge_hit"):
            b["miss_count"] += 1
        elif row.get("memory_hit") and row.get("knowledge_hit"):
            b["both_hit_count"] = int(b.get("both_hit_count") or 0) + 1
    out = []
    for k in sorted(buckets.keys()):
        b = buckets[k]
        n = int(b["build_count"] or 1)
        b["both_hit_count"] = int(b.get("both_hit_count") or 0)
        b["avg_saved"] = round(b["saved_tokens"] / n)
        b["hit_rate"] = round(100 * (b["build_count"] - b["miss_count"]) / n, 1)
        out.append(b)
    return out


def savings_summary(ledger: list[dict[str, Any]]) -> dict[str, Any]:
    if not ledger:
        return {
            "build_count": 0,
            "total_saved": 0,
            "total_usage": 0,
            "total_baseline": 0,
            "avg_savings_percent": 0.0,
            "memory_hit_rate": 0.0,
            "knowledge_hit_rate": 0.0,
            "any_hit_rate": 0.0,
            "full_miss_rate": 0.0,
        }
    n = len(ledger)
    mem = sum(1 for r in ledger if r.get("memory_hit"))
    know = sum(1 for r in ledger if r.get("knowledge_hit"))
    miss = sum(1 for r in ledger if not r.get("memory_hit") and not r.get("knowledge_hit"))
    return {
        "build_count": n,
        "total_saved": sum(int(r.get("saved_tokens") or 0) for r in ledger),
        "total_usage": sum(int(r.get("usage_tokens") or 0) for r in ledger),
        "total_baseline": sum(int(r.get("baseline_tokens") or 0) for r in ledger),
        "avg_savings_percent": round(
            100
            * sum(int(r.get("saved_tokens") or 0) for r in ledger)
            / sum(int(r.get("baseline_tokens") or 0) for r in ledger),
            1,
        )
        if sum(int(r.get("baseline_tokens") or 0) for r in ledger) > 0
        else 0.0,
        "memory_hit_rate": round(100 * mem / n, 1),
        "knowledge_hit_rate": round(100 * know / n, 1),
        "any_hit_rate": round(100 * (n - miss) / n, 1),
        "full_miss_rate": round(100 * miss / n, 1),
    }


def retrieval_ledger(
    events: list[dict[str, Any]],
    *,
    project_id: str | None = None,
    hit_filter: str = "all",
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 200,
    tracked_only: bool = True,
) -> list[dict[str, Any]]:
    """MCP context_retrieval spans — used when builds are sparse (typical Cursor day)."""
    from brain_services.project_context import ProjectContextService

    projects = ProjectContextService()
    rows: list[dict[str, Any]] = []
    for ev in events:
        if ev.get("event_type") != "context_retrieval":
            continue
        pid = ev.get("project_id")
        if project_id and pid != project_id:
            continue
        if tracked_only and not projects.is_tracked_project(pid):
            continue
        if not _date_in_range(ev.get("timestamp_cn") or "", date_from, date_to):
            continue
        m = ev.get("metrics") or {}
        mem_h = int(m.get("memory_hits") or 0)
        know_h = int(m.get("knowledge_hits") or 0)
        mem_hit = bool(m.get("memory_hit")) if "memory_hit" in m else mem_h > 0
        know_hit = bool(m.get("knowledge_hit")) if "knowledge_hit" in m else know_h > 0
        if hit_filter == "memory_hit" and not mem_hit:
            continue
        if hit_filter == "knowledge_hit" and not know_hit:
            continue
        if hit_filter == "any_hit" and not mem_hit and not know_hit:
            continue
        if hit_filter == "miss" and (mem_hit or know_hit):
            continue
        from brain_services.stats_telemetry import enrich_retrieval_metrics

        m = enrich_retrieval_metrics(pid, m)
        usage = int(m.get("usage_tokens") or 0)
        baseline = int(m.get("baseline_tokens") or 0)
        saved = int(m.get("saved_tokens") or max(0, baseline - usage))
        pct = round(100 * saved / baseline, 1) if baseline > 0 else 0.0
        rows.append(
            {
                "event_id": ev.get("id"),
                "timestamp_cn": ev.get("timestamp_cn"),
                "timestamp_utc": ev.get("timestamp_utc"),
                "project_id": pid,
                "task": ev.get("detail") or "",
                "op": m.get("op") or "",
                "usage_tokens": usage,
                "baseline_tokens": baseline,
                "saved_tokens": saved,
                "savings_percent": pct,
                "memory_hits": mem_h,
                "knowledge_hits": know_h,
                "memory_hit": mem_hit,
                "knowledge_hit": know_hit,
                "within_budget": True,
                "knowledge_sources": m.get("knowledge_sources") or [],
                "source_kind": "retrieval",
                "savings_mode": m.get("savings_mode"),
            }
        )
    return rows[:limit]


def aggregate_retrieval(
    ledger: list[dict[str, Any]],
    period: str = "day",
) -> list[dict[str, Any]]:
    """Same bucket shape as aggregate_savings so hit-mix chart can reuse it."""
    buckets: dict[str, dict[str, Any]] = {}
    for row in ledger:
        dt = _parse_cn_ts(row.get("timestamp_cn") or "")
        if not dt:
            continue
        key = _bucket_key(dt, period)
        b = buckets.setdefault(
            key,
            {
                "period": key,
                "build_count": 0,
                "retrieval_count": 0,
                "saved_tokens": 0,
                "usage_tokens": 0,
                "baseline_tokens": 0,
                "memory_hit_count": 0,
                "knowledge_hit_count": 0,
                "miss_count": 0,
                "both_hit_count": 0,
            },
        )
        b["retrieval_count"] += 1
        b["build_count"] += 1  # chart height reuse
        b["saved_tokens"] += int(row.get("saved_tokens") or 0)
        b["usage_tokens"] += int(row.get("usage_tokens") or 0)
        b["baseline_tokens"] += int(row.get("baseline_tokens") or 0)
        if row.get("memory_hit"):
            b["memory_hit_count"] += 1
        if row.get("knowledge_hit"):
            b["knowledge_hit_count"] += 1
        if not row.get("memory_hit") and not row.get("knowledge_hit"):
            b["miss_count"] += 1
        elif row.get("memory_hit") and row.get("knowledge_hit"):
            b["both_hit_count"] = int(b.get("both_hit_count") or 0) + 1
    out = []
    for k in sorted(buckets.keys()):
        b = buckets[k]
        n = int(b["retrieval_count"] or b["build_count"] or 1)
        b["both_hit_count"] = int(b.get("both_hit_count") or 0)
        b["avg_saved"] = round(int(b.get("saved_tokens") or 0) / n) if n else 0
        b["hit_rate"] = round(100 * (n - b["miss_count"]) / n, 1)
        out.append(b)
    return out


def merge_hit_series(
    build_series: list[dict[str, Any]],
    retrieval_series: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Prefer build buckets; fill empty days from MCP retrieval (incl. estimated savings)."""
    by_period = {b["period"]: dict(b) for b in build_series}
    for r in retrieval_series:
        p = r["period"]
        build_saved = int(by_period.get(p, {}).get("saved_tokens") or 0)
        ret_saved = int(r.get("saved_tokens") or 0)
        if p not in by_period or int(by_period[p].get("build_count") or 0) == 0:
            row = dict(r)
            row["series_source"] = "retrieval"
            by_period[p] = row
        elif build_saved <= 0 and ret_saved > 0:
            by_period[p]["saved_tokens"] = ret_saved
            by_period[p]["usage_tokens"] = int(r.get("usage_tokens") or 0)
            by_period[p]["baseline_tokens"] = int(r.get("baseline_tokens") or 0)
            by_period[p]["retrieval_count"] = int(r.get("retrieval_count") or 0)
            by_period[p]["series_source"] = "retrieval"
            by_period[p]["avg_saved"] = int(r.get("avg_saved") or 0)
        else:
            by_period[p]["retrieval_count"] = int(r.get("retrieval_count") or 0)
            by_period[p]["series_source"] = "build"
    return [by_period[k] for k in sorted(by_period.keys())]


def combined_hit_summary(
    build_ledger: list[dict[str, Any]],
    retrieval_ledger_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build savings + retrieval hit rates in one summary for the dashboard."""
    base = savings_summary(build_ledger)
    n = len(retrieval_ledger_rows)
    if n:
        mem = sum(1 for r in retrieval_ledger_rows if r.get("memory_hit"))
        know = sum(1 for r in retrieval_ledger_rows if r.get("knowledge_hit"))
        miss = sum(
            1
            for r in retrieval_ledger_rows
            if not r.get("memory_hit") and not r.get("knowledge_hit")
        )
        ret_saved = sum(int(r.get("saved_tokens") or 0) for r in retrieval_ledger_rows)
        ret_usage = sum(int(r.get("usage_tokens") or 0) for r in retrieval_ledger_rows)
        ret_baseline = sum(int(r.get("baseline_tokens") or 0) for r in retrieval_ledger_rows)
        base["retrieval_count"] = n
        base["retrieval_memory_hit_rate"] = round(100 * mem / n, 1)
        base["retrieval_knowledge_hit_rate"] = round(100 * know / n, 1)
        base["retrieval_any_hit_rate"] = round(100 * (n - miss) / n, 1)
        base["retrieval_full_miss_rate"] = round(100 * miss / n, 1)
        base["retrieval_total_saved"] = ret_saved
        base["retrieval_total_usage"] = ret_usage
        if base.get("build_count", 0) == 0 and ret_saved > 0:
            base["total_saved"] = ret_saved
            base["total_usage"] = ret_usage
            unit_bl = int(retrieval_ledger_rows[0].get("baseline_tokens") or 0) if retrieval_ledger_rows else 0
            base["total_baseline"] = unit_bl or (ret_baseline // n if n else 0)
            pcts = [float(r.get("savings_percent") or 0) for r in retrieval_ledger_rows if r.get("baseline_tokens")]
            base["avg_savings_percent"] = round(sum(pcts) / len(pcts), 1) if pcts else 0.0
            base["memory_hit_rate"] = base["retrieval_memory_hit_rate"]
            base["knowledge_hit_rate"] = base["retrieval_knowledge_hit_rate"]
            base["any_hit_rate"] = base["retrieval_any_hit_rate"]
            base["full_miss_rate"] = base["retrieval_full_miss_rate"]
            base["hit_source"] = "retrieval"
        elif base.get("build_count", 0) == 0:
            base["memory_hit_rate"] = base["retrieval_memory_hit_rate"]
            base["knowledge_hit_rate"] = base["retrieval_knowledge_hit_rate"]
            base["any_hit_rate"] = base["retrieval_any_hit_rate"]
            base["full_miss_rate"] = base["retrieval_full_miss_rate"]
            base["hit_source"] = "retrieval"
        else:
            base["hit_source"] = "build"
    else:
        base["retrieval_count"] = 0
        base["retrieval_memory_hit_rate"] = 0.0
        base["retrieval_knowledge_hit_rate"] = 0.0
        base["retrieval_any_hit_rate"] = 0.0
        base["retrieval_full_miss_rate"] = 0.0
        base["hit_source"] = "build" if base.get("build_count") else "none"
    return base
