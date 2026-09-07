from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from urllib.parse import unquote

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel, Field

from brain_services.context_builder import ContextBuilder
from brain_services.knowledge_service import KnowledgeService
from brain_services.memory_simple import DATA_DIR as MEMORY_DATA_DIR
from brain_services.memory_simple import get_memory_backend
from brain_services.project_alias import resolve as resolve_alias
from brain_services.project_alias import save as save_aliases
from brain_services.project_alias import status as alias_status
from brain_services.project_context import FIXTURES_ROOT, ProjectContextService
from brain_services.stats_filter import filter_events_for_dashboard, filter_memory_projects
from brain_services.stats_store import (
    build_dashboard_payload,
    get_event_by_id,
    load_events,
    load_all_events,
    record_event,
)
from brain_services.mcp_activity import (
    annotate_entry as mcp_annotate,
    compress_lessons as mcp_compress,
    get_mcp_activity_bundle,
    compute_mcp_activity_stats,
    link_fix as mcp_link_fix,
    resolve_project_root as mcp_default_root,
    set_primary_project as mcp_set_primary,
    seed_demo_journal,
)
from brain_services.token_analytics import (
    aggregate_retrieval,
    aggregate_savings,
    combined_hit_summary,
    context_build_ledger,
    merge_hit_series,
    retrieval_ledger,
)

_STATIC = Path(__file__).resolve().parent / "static"
_REPO_ROOT = Path(__file__).resolve().parents[2]

app = FastAPI(title="Project Brain API", version="0.1.0")
_projects = ProjectContextService()
_ctx = ContextBuilder()
_memory = get_memory_backend()
_knowledge = KnowledgeService(projects=_projects)

record_event("system", detail="Brain API 进程启动", source="brain_api")


class BuildContextBody(BaseModel):
    project_id: str
    task: str
    budget_tokens: int = Field(default=5000, le=16000)


class RulesBody(BaseModel):
    rules: list[str]


class McpAnnotateBody(BaseModel):
    id: str
    verdict: str | None = None
    resolved: bool | None = None
    note: str | None = None
    adjustment: str | None = None
    archived: bool | None = None
    fixed_by_id: str | None = None
    supersedes_id: str | None = None


class McpLinkFixBody(BaseModel):
    wrong_id: str
    fix_id: str
    adjustment: str = ""


class McpPrimaryBody(BaseModel):
    primaryProjectRoot: str


class McpSeedBody(BaseModel):
    force: bool = False


def _mcp_activity_root() -> Path:
    for pid in ("shejiuPro", *_projects.list_fixture_project_ids()):
        try:
            proj = _projects.get(pid)
            raw = (proj.get("project") or {}).get("repo_root")
            if raw:
                p = Path(str(raw)).resolve()
                if p.is_dir():
                    return p
        except KeyError:
            continue
    return mcp_default_root()


def _allowed_roots() -> list[Path]:
    roots = [
        FIXTURES_ROOT.resolve(),
        MEMORY_DATA_DIR.resolve(),
        _REPO_ROOT.resolve(),
    ]
    for pid_dir in FIXTURES_ROOT.iterdir():
        if not pid_dir.is_dir():
            continue
        try:
            proj = _projects.get(pid_dir.name)
            raw = (proj.get("project") or {}).get("repo_root")
            if raw:
                p = Path(str(raw)).resolve()
                if p.is_dir():
                    roots.append(p)
        except KeyError:
            continue
    return roots


def _resolve_allowed_path(raw_path: str) -> Path:
    path = Path(unquote(raw_path)).resolve()
    for root in _allowed_roots():
        try:
            path.relative_to(root)
            return path
        except ValueError:
            continue
    raise HTTPException(403, "path not allowed")


def _pid(project_id: str) -> str:
    """Memory-pool key for an id reported by an agent or picked in the dashboard."""
    return resolve_alias(project_id)


def _pid_opt(project_id: str | None) -> str | None:
    """Optional filter. Empty must stay empty: it means 全部, and resolving it
    would silently narrow the dashboard to the single default project."""
    return resolve_alias(project_id) if (project_id or "").strip() else None


class AliasesBody(BaseModel):
    aliases: dict[str, str] = Field(default_factory=dict)


@app.get("/")
def root_redirect():
    return RedirectResponse(url="/dashboard", status_code=302)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/dashboard")
def dashboard_page() -> FileResponse:
    path = _STATIC / "dashboard.html"
    if not path.exists():
        raise HTTPException(404, "dashboard not found")
    return FileResponse(path, media_type="text/html; charset=utf-8")


@app.get("/mcp-lab")
def mcp_lab_page() -> FileResponse:
    path = _STATIC / "mcp-lab.html"
    if not path.exists():
        raise HTTPException(404, "mcp-lab not found")
    return FileResponse(path, media_type="text/html; charset=utf-8")


@app.get("/api/nav")
def api_nav() -> dict:
    nex = os.environ.get("NEXMIND_WEB_URL", "").strip()
    return {
        "dashboard": "/dashboard",
        "mcp_lab": "/mcp-lab",
        "nexmind_mcp_lab_query": f"{nex.rstrip('/')}/?view=mcpLab" if nex else None,
    }


@app.get("/api/mcp-activity")
def api_mcp_activity(limit: int = Query(default=200, le=500)) -> dict:
    return get_mcp_activity_bundle(_mcp_activity_root(), limit=limit)


@app.get("/api/mcp-activity/stats")
def api_mcp_activity_stats(
    period: str = Query(default="day", pattern="^(hour|day|week|month|year)$"),
    date_from: str | None = Query(default=None, description="YYYY-MM-DD 北京时间起"),
    date_to: str | None = Query(default=None, description="YYYY-MM-DD 北京时间止"),
    mcp_server: str | None = Query(default=None),
    project: str | None = Query(default=None, description="工作区目录名，如 shejiuPro"),
) -> dict:
    return compute_mcp_activity_stats(
        _mcp_activity_root(),
        period=period,
        date_from=date_from,
        date_to=date_to,
        mcp_server=mcp_server or None,
        project=project or None,
    )


@app.post("/api/mcp-activity/annotate")
def api_mcp_annotate(body: McpAnnotateBody) -> dict:
    try:
        return mcp_annotate(_mcp_activity_root(), body.model_dump(exclude_none=True))
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.post("/api/mcp-activity/compress")
def api_mcp_compress() -> dict:
    lessons = mcp_compress(_mcp_activity_root())
    return {"compressed_lessons": lessons}


@app.post("/api/mcp-activity/link-fix")
def api_mcp_link_fix(body: McpLinkFixBody) -> dict:
    try:
        return mcp_link_fix(_mcp_activity_root(), body.model_dump())
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.post("/api/mcp-activity/primary")
def api_mcp_primary(body: McpPrimaryBody) -> dict:
    try:
        return mcp_set_primary(_mcp_activity_root(), body.model_dump())
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.post("/api/mcp-activity/seed-demo")
def api_mcp_seed_demo(body: McpSeedBody | None = None) -> dict:
    force = bool(body.force) if body else False
    return seed_demo_journal(_mcp_activity_root(), force=force)


@app.get("/v1/stats/dashboard")
def stats_dashboard(project_id: str | None = Query(default=None)) -> dict:
    return build_dashboard_payload(project_id=_pid_opt(project_id))


@app.get("/v1/stats/events")
def stats_events(limit: int = 100) -> dict:
    return {"events": load_events(min(limit, 500))}


@app.get("/v1/stats/events/{event_id}")
def stats_event_one(event_id: str) -> dict:
    ev = get_event_by_id(event_id)
    if not ev:
        raise HTTPException(404, "event not found")
    return ev


@app.get("/v1/stats/savings")
def stats_savings(
    project_id: str | None = Query(default=None),
    period: str = Query(default="day", pattern="^(hour|day|week|month|year)$"),
    hit_filter: str = Query(
        default="all",
        pattern="^(all|memory_hit|knowledge_hit|any_hit|miss)$",
    ),
    limit: int = Query(default=200, le=500),
    date_from: str | None = Query(default=None, description="YYYY-MM-DD 北京时间起"),
    date_to: str | None = Query(default=None, description="YYYY-MM-DD 北京时间止"),
) -> dict:
    events = load_all_events()
    if len(events) > 5000:
        events = events[:5000]
    pid = _pid_opt(project_id)
    ledger = context_build_ledger(
        events,
        project_id=pid,
        hit_filter=hit_filter,
        date_from=date_from or None,
        date_to=date_to or None,
        limit=limit,
    )
    ret_ledger = retrieval_ledger(
        events,
        project_id=pid,
        hit_filter=hit_filter,
        date_from=date_from or None,
        date_to=date_to or None,
        limit=limit,
    )
    build_series = aggregate_savings(ledger, period)
    ret_series = aggregate_retrieval(ret_ledger, period)
    return {
        "filter_project_id": pid,
        "requested_project_id": project_id,
        "period": period,
        "hit_filter": hit_filter,
        "date_from": date_from,
        "date_to": date_to,
        "summary": combined_hit_summary(ledger, ret_ledger),
        "series": merge_hit_series(build_series, ret_series),
        "build_series": build_series,
        "retrieval_series": ret_series,
        "ledger": ledger,
        "retrieval_ledger": ret_ledger[:80],
    }


@app.get("/v1/stats/stream")
async def stats_stream(project_id: str | None = Query(default=None)) -> StreamingResponse:
    pid = _pid_opt(project_id)

    async def generate():
        while True:
            payload = build_dashboard_payload(project_id=pid)
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            await asyncio.sleep(2)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@app.get("/v1/open")
def open_local_path(path: str = Query(..., min_length=1)) -> RedirectResponse:
    resolved = _resolve_allowed_path(path)
    if not resolved.is_file():
        raise HTTPException(404, "file not found")
    uri = resolved.as_uri()
    return RedirectResponse(url=uri, status_code=302)


@app.get("/v1/projects")
def list_projects(tracked_only: bool = Query(default=True)) -> dict:
    ids = (
        _projects.list_tracked_project_ids()
        if tracked_only
        else _projects.list_fixture_project_ids()
    )
    st = alias_status()
    return {
        "project_ids": ids,
        "aliases": st["aliases"],
        "alias_groups": st["groups"],
        "canonical_ids": [i for i in ids if i not in st["aliases"]],
    }


@app.get("/v1/aliases")
def get_aliases() -> dict:
    """Effective alias map, plus stored/env split so the page can show which
    entries came from BRAIN_PROJECT_ALIASES and which the file owns."""
    return alias_status()


@app.put("/v1/aliases")
def put_aliases(body: AliasesBody) -> dict:
    save_aliases(body.aliases)
    return {"ok": True, **alias_status()}


@app.get("/v1/projects/{project_id}")
def get_project(project_id: str) -> dict:
    pid = _pid(project_id)
    try:
        out = _projects.search(pid, "")
    except KeyError:
        raise HTTPException(404, "unknown project") from None
    return {"requested_project_id": project_id, **out}


@app.get("/v1/projects/{project_id}/rules")
def get_rules(project_id: str) -> dict:
    pid = _pid(project_id)
    try:
        rules = _projects.list_rules(pid)
    except KeyError:
        raise HTTPException(404, "unknown project") from None
    return {"project_id": pid, "requested_project_id": project_id, "rules": rules}


@app.put("/v1/projects/{project_id}/rules")
def put_rules(project_id: str, body: RulesBody) -> dict:
    pid = _pid(project_id)
    try:
        _projects.save_rules(pid, body.rules)
    except KeyError:
        raise HTTPException(404, "unknown project") from None
    return {"ok": True, "project_id": pid, "requested_project_id": project_id, "rules": body.rules}


@app.post("/v1/context/build")
def build_context(body: BuildContextBody) -> dict:
    pid = _pid(body.project_id)
    try:
        out = _ctx.build_task_context(pid, body.task, body.budget_tokens)
    except KeyError:
        raise HTTPException(404, "unknown project") from None
    out = {k: v for k, v in out.items() if k != "context"}
    return {"requested_project_id": body.project_id, **out}


@app.get("/v1/memory/{project_id}/dedupe-preview")
def memory_dedupe_preview(project_id: str) -> dict:
    preview_fn = getattr(_memory, "dedupe_preview", None)
    if not callable(preview_fn):
        raise HTTPException(501, "dedupe-preview 需要离线 JSONL 模式")
    pid = _pid(project_id)
    return {"project_id": pid, "requested_project_id": project_id, **preview_fn(pid)}


@app.post("/v1/memory/{project_id}/dedupe")
def memory_dedupe(project_id: str) -> dict:
    dedupe_fn = getattr(_memory, "dedupe_file", None)
    if not callable(dedupe_fn):
        raise HTTPException(501, "dedupe 需要离线 JSONL 模式")
    pid = _pid(project_id)
    return {"project_id": pid, "requested_project_id": project_id, **dedupe_fn(pid)}


@app.post("/v1/memory/{project_id}/backfill-titles")
def memory_backfill_titles(project_id: str) -> dict:
    backfill_fn = getattr(_memory, "backfill_titles", None)
    if not callable(backfill_fn):
        raise HTTPException(501, "backfill-titles 需要离线 JSONL 模式")
    pid = _pid(project_id)
    return {"project_id": pid, "requested_project_id": project_id, **backfill_fn(pid)}


@app.get("/v1/stats/retrieval")
def stats_retrieval(
    project_id: str | None = Query(default=None),
    limit: int = Query(default=100, le=300),
) -> dict:
    """Phoenix RETRIEVER-style ledger for MCP search/get_change_context."""
    pid = _pid_opt(project_id)
    events = [
        e
        for e in load_events(800)
        if e.get("event_type") == "context_retrieval"
        and (not pid or e.get("project_id") == pid)
    ][:limit]
    hit = sum(1 for e in events if (e.get("metrics") or {}).get("any_hit"))
    return {
        "filter_project_id": pid,
        "requested_project_id": project_id,
        "count": len(events),
        "hit_count": hit,
        "hit_rate": round(100 * hit / len(events), 1) if events else 0.0,
        "events": events,
    }


@app.get("/v1/memory/{project_id}")
def memory_list(project_id: str, limit: int = 200) -> dict:
    list_fn = getattr(_memory, "list_all", None)
    if not callable(list_fn):
        raise HTTPException(
            501,
            "memory list 需要离线 JSONL 模式（勿设 BRAIN_USE_MEM0=1）；请重启看板 API",
        )
    pid = _pid(project_id)
    return {
        "project_id": pid,
        "requested_project_id": project_id,
        "items": list_fn(pid, limit=limit),
    }


@app.delete("/v1/memory/{project_id}/{memory_id}")
def memory_delete(project_id: str, memory_id: str) -> dict:
    delete_fn = getattr(_memory, "delete_by_id", None)
    if not callable(delete_fn):
        raise HTTPException(501, "memory delete 需要离线 JSONL 模式")
    pid = _pid(project_id)
    if not delete_fn(pid, memory_id):
        raise HTTPException(404, "memory not found")
    return {"ok": True, "id": memory_id, "project_id": pid}


@app.post("/v1/memory/search")
def memory_search(project_id: str, query: str, limit: int = 5) -> dict:
    pid = _pid(project_id)
    results = _memory.search(pid, query, limit=min(limit, 5))
    record_event(
        "memory_search",
        project_id=pid,
        detail=query[:200],
        metrics={"hit_count": len(results), "limit": limit},
        source="api",
    )
    return {"project_id": pid, "requested_project_id": project_id, "results": results}


@app.post("/v1/knowledge/search")
def knowledge_search(project_id: str, query: str, top_k: int = 5) -> dict:
    pid = _pid(project_id)
    results = _knowledge.search(pid, query, top_k=top_k)
    record_event(
        "knowledge_search",
        project_id=pid,
        detail=query[:200],
        metrics={
            "hit_count": len(results),
            "top_k": top_k,
            "knowledge_sources": [
                {"path": r.get("source"), "abs_path": r.get("abs_path")} for r in results
            ],
        },
        source="api",
    )
    return {"project_id": pid, "requested_project_id": project_id, "results": results}


def main() -> None:
    import uvicorn

    port = int(os.environ.get("BRAIN_API_PORT", "18787"))
    uvicorn.run("brain_api.app:app", host="127.0.0.1", port=port, reload=False)


if __name__ == "__main__":
    main()
