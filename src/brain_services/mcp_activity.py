"""Read/write .forgemind MCP activity journal for the Brain dashboard."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from brain_services.token_analytics import TZ_CN, _bucket_key

from brain_services.mcp_telemetry_bridge import infer_mcp_server

JOURNAL = Path(".forgemind") / "mcp-activity.jsonl"
META = Path(".forgemind") / "mcp-activity-meta.json"


def _read_meta(project_root: Path) -> dict:
    p = project_root / META
    if not p.is_file():
        return {"version": 1, "annotations": {}, "compressed_lessons": []}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"version": 1, "annotations": {}, "compressed_lessons": []}


def _write_meta(project_root: Path, meta: dict) -> None:
    d = project_root / ".forgemind"
    d.mkdir(parents=True, exist_ok=True)
    (project_root / META).write_text(json.dumps(meta, indent=2), encoding="utf-8")


def _is_demo_entry(entry: dict) -> bool:
    if entry.get("demo") is True:
        return True
    eid = str(entry.get("id") or "")
    if eid.startswith("demo-"):
        return True
    sid = str(entry.get("session_id") or "")
    if sid.startswith("demo-session"):
        return True
    return False


def _filter_real(entries: list[dict]) -> list[dict]:
    return [e for e in entries if not _is_demo_entry(e)]


def _entries_from_telemetry(project_root: Path, limit: int = 200) -> list[dict]:
    """Real MCP rows from ContextMind telemetry.db (Output Gate ledger)."""
    import sqlite3

    db_path = project_root / ".contextmind" / "telemetry.db"
    if not db_path.is_file():
        return []
    align = resolve_alignment(project_root)
    root_s = str(project_root.resolve()).replace("\\", "/")
    rows: list[dict] = []
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            """
            SELECT id, ts, session_id, tool_name, success, raw_tokens, emitted_tokens,
                   note, handle_id, gate_latency_ms, hook_latency_ms
            FROM events
            WHERE surface = 'mcp' AND tool_name IS NOT NULL AND tool_name != ''
            ORDER BY id DESC
            LIMIT ?
            """,
            (max(limit * 2, 400),),
        )
        for r in cur.fetchall():
            tool = str(r["tool_name"] or "")
            if tool.startswith("fixture:"):
                continue
            raw_ts = r["ts"]
            dt = None
            if isinstance(raw_ts, (int, float)) and raw_ts > 1_000_000_000:
                dt = datetime.fromtimestamp(float(raw_ts), tz=timezone.utc)
            else:
                s = str(raw_ts or "").strip()
                if s.endswith("Z"):
                    s = s[:-1] + "+00:00"
                try:
                    dt = datetime.fromisoformat(s)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                except ValueError:
                    continue
            at = dt.astimezone(TZ_CN).strftime("%Y-%m-%dT%H:%M:%S%z")
            if len(at) > 5 and at[-2] != ":":
                at = at[:-2] + ":" + at[-2:]
            ok = int(r["success"] or 0) == 1
            status = "success" if ok else "error"
            srv = infer_mcp_server(tool)
            eid = f"tel-{r['id']}"
            note = str(r["note"] or "")
            rows.append(
                {
                    "id": eid,
                    "at": at,
                    "session_id": str(r["session_id"] or ""),
                    "workspace_cwd": root_s,
                    "primary_project_root": align.get("primaryProjectRoot") or root_s,
                    "workspace_aligned": bool(align.get("aligned")),
                    "mcp_server_name": srv,
                    "tool_name": tool,
                    "status": status,
                    "duration_ms": int(r["gate_latency_ms"] or r["hook_latency_ms"] or 0),
                    "summary": f"{srv}/{tool}",
                    "args_preview": {"note": note[:200]} if note else {},
                    "auto_verdict": "helpful" if ok else "failed",
                    "auto_effective": ok,
                    "source": "telemetry",
                    "telemetry_event_id": int(r["id"]),
                    "raw_tokens": int(r["raw_tokens"] or 0),
                    "emitted_tokens": int(r["emitted_tokens"] or 0),
                    "handle_id": r["handle_id"],
                }
            )
        conn.close()
    except (sqlite3.Error, OSError):
        return []
    return rows[:limit]


def _read_journal(project_root: Path, limit: int = 200) -> list[dict]:
    p = project_root / JOURNAL
    if not p.is_file():
        return []
    lines = [ln for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
    tail = lines[-limit:]
    entries: list[dict] = []
    for line in tail:
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    entries.reverse()
    return _filter_real(entries)


def _read_journal_all(project_root: Path, max_lines: int = 50000) -> list[dict]:
    p = project_root / JOURNAL
    if not p.is_file():
        return []
    lines = [ln for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if len(lines) > max_lines:
        lines = lines[-max_lines:]
    entries: list[dict] = []
    for line in lines:
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return _filter_real(entries)


def _merge_activity_entries(
    journal: list[dict], telemetry: list[dict], limit: int
) -> tuple[list[dict], str]:
    by_id: dict[str, dict] = {}
    for e in journal:
        eid = str(e.get("id") or "")
        if eid:
            by_id[eid] = e
    for e in telemetry:
        eid = str(e.get("id") or "")
        if eid and eid not in by_id:
            by_id[eid] = e
    merged = sorted(by_id.values(), key=lambda x: str(x.get("at") or ""), reverse=True)
    source = "journal"
    if telemetry and journal:
        source = "mixed"
    elif telemetry:
        source = "telemetry"
    return merged[:limit], source


def _parse_at(ts: str) -> datetime | None:
    if not ts:
        return None
    s = ts.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TZ_CN)


def _date_in_range_dt(dt: datetime, date_from: str | None, date_to: str | None) -> bool:
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


def _project_label(entry: dict) -> str:
    root = entry.get("primary_project_root") or entry.get("workspace_cwd") or ""
    if root:
        name = Path(str(root)).name
        return name or str(root)
    return "unknown"


def _is_fail_entry(entry: dict) -> bool:
    if entry.get("status") == "error":
        return True
    if entry.get("envelope_status") == "FAIL":
        return True
    if entry.get("auto_verdict") == "failed":
        return True
    return False


def compute_mcp_activity_stats(
    project_root: Path,
    *,
    period: str = "day",
    date_from: str | None = None,
    date_to: str | None = None,
    mcp_server: str | None = None,
    project: str | None = None,
) -> dict:
    entries = _all_real_entries(project_root)
    servers_set: set[str] = set()
    projects_set: set[str] = set()
    filtered: list[dict] = []

    for e in entries:
        srv = str(e.get("mcp_server_name") or "unknown")
        plab = _project_label(e)
        servers_set.add(srv)
        projects_set.add(plab)
        if mcp_server and srv != mcp_server:
            continue
        if project and plab != project and project not in str(
            e.get("primary_project_root") or e.get("workspace_cwd") or ""
        ):
            continue
        dt = _parse_at(str(e.get("at") or ""))
        if not dt:
            continue
        if not _date_in_range_dt(dt, date_from, date_to):
            continue
        filtered.append({**e, "_dt_cn": dt, "_project": plab, "_server": srv})

    summary = {
        "total": len(filtered),
        "success": 0,
        "error": 0,
        "cancelled": 0,
        "envelope_fail": 0,
        "envelope_warn": 0,
        "auto_effective": 0,
        "duration_ms_sum": 0,
        "unique_servers": len({e["_server"] for e in filtered}) if filtered else 0,
        "unique_tools": len({e.get("tool_name") for e in filtered}) if filtered else 0,
        "unique_projects": len({e["_project"] for e in filtered}) if filtered else 0,
    }
    series_map: dict[str, dict] = {}
    by_server: dict[str, dict] = {}
    by_project: dict[str, dict] = {}
    by_tool: dict[str, dict] = {}

    def bump_bucket(bucket: dict, entry: dict) -> None:
        bucket["total"] = int(bucket.get("total", 0)) + 1
        st = entry.get("status") or "success"
        if st == "success":
            bucket["success"] = int(bucket.get("success", 0)) + 1
        elif st == "error":
            bucket["error"] = int(bucket.get("error", 0)) + 1
        elif st == "cancelled":
            bucket["cancelled"] = int(bucket.get("cancelled", 0)) + 1
        if entry.get("envelope_status") == "FAIL":
            bucket["envelope_fail"] = int(bucket.get("envelope_fail", 0)) + 1
        if entry.get("auto_effective"):
            bucket["auto_effective"] = int(bucket.get("auto_effective", 0)) + 1
        bucket["duration_ms_sum"] = int(bucket.get("duration_ms_sum", 0)) + int(
            entry.get("duration_ms") or 0
        )

    for e in filtered:
        st = e.get("status") or "success"
        if st == "success":
            summary["success"] += 1
        elif st == "error":
            summary["error"] += 1
        elif st == "cancelled":
            summary["cancelled"] += 1
        if e.get("envelope_status") == "FAIL":
            summary["envelope_fail"] += 1
        if e.get("envelope_status") == "WARN":
            summary["envelope_warn"] += 1
        if e.get("auto_effective"):
            summary["auto_effective"] += 1
        summary["duration_ms_sum"] += int(e.get("duration_ms") or 0)

        dt: datetime = e["_dt_cn"]
        pk = _bucket_key(dt, period)
        if pk not in series_map:
            series_map[pk] = {"period": pk}
        bump_bucket(series_map[pk], e)

        srv = e["_server"]
        if srv not in by_server:
            by_server[srv] = {"server": srv}
        bump_bucket(by_server[srv], e)

        plab = e["_project"]
        if plab not in by_project:
            by_project[plab] = {
                "project": plab,
                "root": e.get("primary_project_root") or e.get("workspace_cwd"),
            }
        bump_bucket(by_project[plab], e)

        tool_key = f"{srv}|{e.get('tool_name') or '?'}"
        if tool_key not in by_tool:
            by_tool[tool_key] = {
                "server": srv,
                "tool": e.get("tool_name") or "?",
            }
        bump_bucket(by_tool[tool_key], e)

    if summary["total"]:
        summary["avg_duration_ms"] = round(summary["duration_ms_sum"] / summary["total"])
        summary["success_rate"] = round(100 * summary["success"] / summary["total"], 1)
    else:
        summary["avg_duration_ms"] = 0
        summary["success_rate"] = 0.0
    del summary["duration_ms_sum"]

    def finalize_rows(rows: list[dict]) -> list[dict]:
        out = []
        for r in rows:
            t = int(r.get("total") or 0)
            dsum = int(r.pop("duration_ms_sum", 0))
            r["avg_duration_ms"] = round(dsum / t) if t else 0
            out.append(r)
        return out

    series = finalize_rows([series_map[k] for k in sorted(series_map.keys())])
    servers = finalize_rows(sorted(by_server.values(), key=lambda x: -int(x.get("total") or 0)))
    projects = finalize_rows(sorted(by_project.values(), key=lambda x: -int(x.get("total") or 0)))
    tools = finalize_rows(sorted(by_tool.values(), key=lambda x: -int(x.get("total") or 0))[:40])

    return {
        "period": period,
        "date_from": date_from,
        "date_to": date_to,
        "filter_mcp_server": mcp_server,
        "filter_project": project,
        "summary": summary,
        "series": series,
        "by_server": servers,
        "by_project": projects,
        "by_tool": tools,
        "filter_options": {
            "servers": sorted(servers_set),
            "projects": sorted(projects_set),
        },
        "timezone": "Asia/Shanghai (UTC+8)",
    }


def resolve_project_root(explicit: str | None = None) -> Path:
    if explicit:
        return Path(explicit).resolve()
    env = os.environ.get("SHEJIU_REPO_ROOT") or os.environ.get("MCP_ACTIVITY_PROJECT_ROOT")
    if env:
        return Path(env).resolve()
    return Path("e:/workA/shejiuPro").resolve()


def resolve_alignment(project_root: Path) -> dict:
    warnings: list[str] = []
    primary: Path | None = None
    override = project_root / ".forgemind" / "primary-project.json"
    if override.is_file():
        try:
            o = json.loads(override.read_text(encoding="utf-8"))
            if o.get("primaryProjectRoot"):
                primary = Path(str(o["primaryProjectRoot"])).resolve()
        except (json.JSONDecodeError, OSError):
            pass
    mcp_path = project_root / ".cursor" / "mcp.json"
    if mcp_path.is_file():
        try:
            cfg = json.loads(mcp_path.read_text(encoding="utf-8"))
            dirs: set[Path] = set()
            for srv in (cfg.get("mcpServers") or {}).values():
                if not isinstance(srv, dict):
                    continue
                env = srv.get("env") or {}
                for key in ("LABOR_PROJECT_DIR", "CONTEXTMIND_PROJECT_DIR"):
                    v = env.get(key)
                    if v:
                        dirs.add(Path(str(v)).resolve())
            if not primary and len(dirs) == 1:
                primary = next(iter(dirs))
            if not primary and len(dirs) > 1:
                warnings.append(
                    "MCP project dirs disagree — set .forgemind/primary-project.json"
                )
                primary = sorted(dirs, key=lambda p: str(p).lower())[0]
        except (json.JSONDecodeError, OSError):
            pass
    cwd = project_root.resolve()
    aligned = primary is None or str(cwd).lower() == str(primary).lower()
    return {
        "workspaceCwd": str(cwd),
        "primaryProjectRoot": str(primary) if primary else None,
        "aligned": aligned,
        "warnings": warnings,
    }


def _all_real_entries(project_root: Path, max_lines: int = 50000) -> list[dict]:
    journal = _read_journal_all(project_root, max_lines)
    tel = _entries_from_telemetry(project_root, min(max_lines, 5000))
    merged, _ = _merge_activity_entries(journal, tel, max_lines)
    return merged


def get_mcp_activity_bundle(project_root: Path, limit: int = 200) -> dict:
    meta = _read_meta(project_root)
    annotations = meta.get("annotations") or {}
    journal = _read_journal(project_root, limit)
    tel = _entries_from_telemetry(project_root, limit)
    merged, source = _merge_activity_entries(journal, tel, limit)
    entries = []
    for e in merged:
        row = dict(e)
        row["annotation"] = annotations.get(e.get("id")) or None
        entries.append(row)
    return {
        "alignment": resolve_alignment(project_root),
        "entries": entries,
        "compressed_lessons": meta.get("compressed_lessons") or [],
        "data_source": source,
        "journal_real_lines": len(journal),
        "telemetry_rows": len(tel),
    }


def annotate_entry(project_root: Path, body: dict) -> dict:
    entry_id = str(body.get("id") or "")
    if not entry_id:
        raise ValueError("id required")
    meta = _read_meta(project_root)
    annotations = meta.setdefault("annotations", {})
    prev = annotations.get(entry_id) or {}
    now = datetime.now(timezone.utc).isoformat()
    archived = body.get("archived", prev.get("archived", False))
    ann = {
        "verdict": body.get("verdict", prev.get("verdict", "unknown")),
        "resolved": body.get("resolved", prev.get("resolved", False)),
        "note": body.get("note", prev.get("note")),
        "adjustment": body.get("adjustment", prev.get("adjustment")),
        "archived": archived,
        "archived_at": now if archived is True else prev.get("archived_at"),
        "fixed_by_id": body.get("fixed_by_id", prev.get("fixed_by_id")),
        "supersedes_id": body.get("supersedes_id", prev.get("supersedes_id")),
        "updated_at": now,
    }
    annotations[entry_id] = ann
    _write_meta(project_root, meta)
    return ann


def compress_lessons(project_root: Path) -> list[dict]:
    meta = _read_meta(project_root)
    by_key: dict[str, dict] = {
        l["key"]: dict(l) for l in (meta.get("compressed_lessons") or []) if l.get("key")
    }
    entries = _read_journal(project_root, 500)
    annotations = meta.get("annotations") or {}
    for entry in entries:
        eid = entry.get("id")
        ann = annotations.get(eid) or {}
        if not ann.get("archived") or ann.get("verdict") != "wrong":
            continue
        err = (entry.get("error") or entry.get("envelope_status") or "")[:80]
        key = f"{entry.get('mcp_server_name')}|{entry.get('tool_name')}|{err}"
        lesson = (
            ann.get("adjustment")
            or ann.get("note")
            or entry.get("error")
            or entry.get("summary")
            or "wrong MCP call"
        )
        existing = by_key.get(key)
        if existing:
            existing["wrong_count"] = int(existing.get("wrong_count", 0)) + 1
            existing["last_seen"] = entry.get("at")
            existing["lesson"] = lesson
            existing["adjustment"] = ann.get("adjustment")
        else:
            safe = "".join(c if c.isalnum() or c in "|_-" else "_" for c in key[:32])
            by_key[key] = {
                "id": f"lesson-{safe}",
                "key": key,
                "server": entry.get("mcp_server_name"),
                "tool": entry.get("tool_name"),
                "lesson": lesson,
                "adjustment": ann.get("adjustment"),
                "wrong_count": 1,
                "last_seen": entry.get("at"),
                "source_ids": [eid],
            }
    lessons = sorted(by_key.values(), key=lambda x: str(x.get("last_seen") or ""), reverse=True)[
        :80
    ]
    meta["compressed_lessons"] = lessons
    _write_meta(project_root, meta)
    return lessons


def link_fix(project_root: Path, body: dict) -> dict:
    wrong_id = str(body.get("wrong_id") or "")
    fix_id = str(body.get("fix_id") or "")
    adjustment = str(body.get("adjustment") or "")
    if not wrong_id or not fix_id:
        raise ValueError("wrong_id and fix_id required")
    annotate_entry(
        project_root,
        {
            "id": wrong_id,
            "verdict": "superseded",
            "resolved": True,
            "fixed_by_id": fix_id,
            "adjustment": adjustment,
            "archived": True,
        },
    )
    annotate_entry(
        project_root,
        {
            "id": fix_id,
            "verdict": "correct",
            "resolved": True,
            "supersedes_id": wrong_id,
            "note": adjustment,
        },
    )
    return {"ok": True}


def set_primary_project(project_root: Path, body: dict) -> dict:
    root = str(body.get("primaryProjectRoot") or "")
    if not root:
        raise ValueError("primaryProjectRoot required")
    d = project_root / ".forgemind"
    d.mkdir(parents=True, exist_ok=True)
    payload = {
        "primaryProjectRoot": str(Path(root).resolve()),
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }
    (d / "primary-project.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return resolve_alignment(project_root)


def seed_demo_journal(project_root: Path, *, force: bool = False) -> dict:
    """Append demo lines — disabled unless ALLOW_MCP_DEMO_SEED=1 (dev only)."""
    if os.environ.get("ALLOW_MCP_DEMO_SEED") != "1":
        return {
            "ok": False,
            "added": 0,
            "skipped": True,
            "error": "demo seed disabled (set ALLOW_MCP_DEMO_SEED=1 to enable)",
        }
    p = project_root / JOURNAL
    existing = 0
    if p.is_file():
        existing = sum(1 for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip())
        if existing and not force:
            return {"ok": True, "added": 0, "skipped": True, "existing_lines": existing}

    root = project_root.resolve()
    root_s = str(root).replace("\\", "/")
    now = datetime.now(TZ_CN).replace(minute=0, second=0, microsecond=0)
    samples: list[tuple[int, str, str, str, str | None, str | None]] = [
        # day_offset, server, tool, status, envelope, error
        (0, "contextmind", "context_orient", "success", "PASS", None),
        (0, "contextmind", "context_fetch", "success", "PASS", None),
        (0, "project-brain", "semantic_search", "success", None, None),
        (0, "mcp-repo-mind", "labor_verify", "error", "FAIL", "mvn compile exit 1"),
        (1, "contextmind", "context_orient", "success", "PASS", None),
        (1, "project-brain", "get_evidence", "success", None, None),
        (2, "mcp-repo-mind", "labor_diff_guard", "success", "PASS", None),
        (2, "mcp-repo-mind", "labor_bundle_check", "success", "WARN", None),
        (3, "contextmind", "context_fetch", "success", "PASS", None),
        (4, "project-brain", "semantic_search", "success", None, None),
        (5, "contextmind", "context_orient", "error", "FAIL", "query required"),
        (5, "contextmind", "context_orient", "success", "PASS", None),
        (6, "mcp-repo-mind", "labor_verify", "success", "PASS", None),
        (7, "project-brain", "get_evidence", "success", None, None),
        (8, "contextmind", "context_fetch", "success", "PASS", None),
        (10, "mcp-repo-mind", "labor_review", "success", "PASS", None),
        (12, "contextmind", "context_orient", "success", "PASS", None),
        (14, "project-brain", "semantic_search", "cancelled", None, None),
        (15, "mcp-repo-mind", "labor_gap_scan", "success", "PASS", None),
        (18, "contextmind", "context_fetch", "success", "PASS", None),
        (20, "project-brain", "get_evidence", "success", None, None),
        (22, "mcp-repo-mind", "labor_verify", "error", "FAIL", "timeout"),
        (25, "contextmind", "context_orient", "success", "PASS", None),
        (28, "project-brain", "semantic_search", "success", None, None),
    ]
    lines: list[str] = []
    for i, (day_off, srv, tool, status, env, err) in enumerate(samples):
        ts = now - timedelta(days=day_off, hours=(i % 5))
        at = ts.strftime("%Y-%m-%dT%H:%M:%S") + "+08:00"
        auto_effective = status == "success" and env != "FAIL"
        auto_verdict = (
            "failed"
            if status == "error" or env == "FAIL"
            else "cancelled"
            if status == "cancelled"
            else "helpful"
        )
        rec = {
            "id": f"demo-{ts.strftime('%Y%m%d%H%M')}-{i:02d}",
            "at": at,
            "session_id": f"demo-session-{day_off}",
            "workspace_cwd": root_s,
            "primary_project_root": root_s,
            "workspace_aligned": True,
            "mcp_server_name": srv,
            "tool_name": tool,
            "status": status,
            "duration_ms": 120 + (i * 37) % 900,
            "summary": f"{srv}/{tool}",
            "args_preview": {"query": "com.shejiu.product.service.impl.TRedPacketTaskServiceImpl"},
            "envelope_status": env,
            "auto_verdict": auto_verdict,
            "auto_effective": auto_effective,
            "demo": True,
        }
        if err:
            rec["error"] = err
        if status == "success" and env == "PASS":
            rec["response_preview"] = '{"contract_version":1,"status":"PASS","summary":"ok"}'
        lines.append(json.dumps(rec, ensure_ascii=False))

    forgemind = project_root / ".forgemind"
    forgemind.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        for ln in lines:
            f.write(ln + "\n")

    total = sum(1 for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip())
    return {"ok": True, "added": len(lines), "skipped": False, "total_lines": total}
