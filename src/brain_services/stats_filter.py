from __future__ import annotations

from typing import Any

from brain_services.project_context import ProjectContextService


def filter_events_for_dashboard(
    events: list[dict[str, Any]],
    *,
    project_id: str | None = None,
    projects: ProjectContextService | None = None,
) -> list[dict[str, Any]]:
    """Drop demo/fixture-only projects from dashboard stats."""
    svc = projects or ProjectContextService()
    out: list[dict[str, Any]] = []
    for ev in events:
        pid = ev.get("project_id")
        if project_id and pid != project_id:
            continue
        if pid and not svc.is_tracked_project(pid):
            continue
        out.append(ev)
    return out


def filter_memory_projects(
    projects: list[dict[str, Any]],
    *,
    project_id: str | None = None,
    svc: ProjectContextService | None = None,
) -> list[dict[str, Any]]:
    service = svc or ProjectContextService()
    rows = [p for p in projects if service.is_tracked_project(p.get("project_id"))]
    if project_id:
        rows = [p for p in rows if p.get("project_id") == project_id]
    return rows
