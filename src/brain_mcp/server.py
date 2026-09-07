from __future__ import annotations

import json
import os
from typing import Any

from mcp.server.fastmcp import FastMCP

from brain_services.context_memory import ContextMemoryService

mcp = FastMCP("project-brain")
_ctx = ContextMemoryService()

_ALIASES: dict[str, str] | None = None


def _aliases() -> dict[str, str]:
    """BRAIN_PROJECT_ALIASES="testMind=shejiuPro,shejiuTest=shejiuPro" — working dirs that
    are really one project share a memory pool even when an agent passes its own name."""
    global _ALIASES
    if _ALIASES is None:
        parsed: dict[str, str] = {}
        for part in os.environ.get("BRAIN_PROJECT_ALIASES", "").split(","):
            src, _, dst = part.partition("=")
            if src.strip() and dst.strip():
                parsed[src.strip()] = dst.strip()
        _ALIASES = parsed
    return _ALIASES


def _project_id(project_id: str | None) -> str:
    pid = (project_id or "").strip() or os.environ.get("BRAIN_DEFAULT_PROJECT_ID", "shejiuPro")
    return _aliases().get(pid, pid)


def _json(out: Any) -> str:
    return json.dumps(out, ensure_ascii=False, indent=2)


@mcp.tool()
def search_project_context(project_id: str, query: str, limit: int = 5) -> str:
    """WHY layer: project rules, memories, and doc excerpts (not Java call graphs)."""
    return _json(_ctx.search_project_context(_project_id(project_id), query, limit=limit))


@mcp.tool()
def get_change_context(project_id: str, file: str, limit: int = 5) -> str:
    """WHY layer: memories/docs tied to a file path before you edit."""
    return _json(_ctx.get_change_context(_project_id(project_id), file, limit=limit))


@mcp.tool()
def save_architecture_decision(
    project_id: str,
    decision: str,
    rationale: str = "",
    related_files: list[str] | None = None,
) -> str:
    """Persist an architecture decision (ADR-style) into project memory."""
    return _json(
        _ctx.save_decision(
            _project_id(project_id),
            decision,
            rationale=rationale,
            related_files=related_files,
        )
    )


@mcp.tool()
def save_bug_memory(
    project_id: str,
    title: str,
    problem: str,
    cause: str = "",
    fix: str = "",
    related_files: list[str] | None = None,
) -> str:
    """Persist a bug pitfall into project memory."""
    return _json(
        _ctx.save_bug(
            _project_id(project_id),
            title,
            problem,
            cause=cause,
            fix=fix,
            related_files=related_files,
        )
    )


@mcp.tool()
def record_task_outcome(project_id: str, summary: str, importance: str = "medium") -> str:
    """End-of-task experience summary (deduped within ~30 minutes)."""
    from brain_services.memory_simple import get_memory_backend

    mem = get_memory_backend()
    out = mem.add(
        _project_id(project_id),
        summary,
        importance=importance,
        metadata={"kind": "experience"},
    )
    return _json(out)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
