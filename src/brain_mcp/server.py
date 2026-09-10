from __future__ import annotations

import sys
from pathlib import Path

# Cursor / MCP may ignore cwd; resolve src from package location (not relative PYTHONPATH).
_SRC_ROOT = Path(__file__).resolve().parent.parent
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

from mcp.server.fastmcp import FastMCP
from mcp.types import Tool as MCPTool

from brain_services.context_memory import ContextMemoryService
from brain_services.knowledge_service import KnowledgeService
from brain_services.memory_simple import get_memory_backend
from brain_services.project_alias import resolve as _resolve_alias
from brain_services.project_context import ProjectContextService
from brain_services.rank import dump_mcp

WHY_TOOLS = (
    "search_project_context",
    "get_change_context",
    "save_architecture_decision",
    "save_bug_memory",
    "record_task_outcome",
)


class CursorFastMCP(FastMCP):
    """Cursor rejects tools/list rows that carry FastMCP 1.29 outputSchema."""

    async def list_tools(self) -> list[MCPTool]:
        tools = await super().list_tools()
        for t in tools:
            t.outputSchema = None
            t.icons = None
            t.title = None
        return tools


mcp = CursorFastMCP("project-brain")
_projects = ProjectContextService()
_memory = get_memory_backend()
_knowledge = KnowledgeService(projects=_projects)
_ov = ContextMemoryService(_memory, _projects, _knowledge)


def _project_id(project_id: str) -> str:
    """shejiuPro / shejiuTest / shejiu-pro1 are one project, so their agents must
    read and write one pool instead of three half-empty ones."""
    return _resolve_alias(project_id)


@mcp.tool()
def search_project_context(
    project_id: str,
    query: str,
    limit: int = 5,
) -> str:
    """WHY: rules + ranked memories + matching doc paragraphs. Not a code graph."""
    out = _ov.search_project_context(_project_id(project_id), query, limit=limit)
    return dump_mcp(out)


@mcp.tool()
def get_change_context(project_id: str, file: str, limit: int = 5) -> str:
    """WHY: risks/decisions/bugs before editing a file. Code location: context_orient."""
    out = _ov.get_change_context(_project_id(project_id), file, limit=limit)
    return dump_mcp(out)


@mcp.tool()
def save_architecture_decision(
    project_id: str,
    decision: str,
    rationale: str = "",
    related_files: str = "",
) -> str:
    """WHY: store ADR-style decision (dedup, bound to project_id)."""
    files = [f.strip() for f in related_files.split(",") if f.strip()] if related_files else []
    out = _ov.save_decision(_project_id(project_id), decision, rationale, files)
    return dump_mcp({"ok": True, **out})


@mcp.tool()
def save_bug_memory(
    project_id: str,
    title: str,
    problem: str,
    cause: str = "",
    fix: str = "",
    related_files: str = "",
) -> str:
    """WHY: store bug lesson (dedup, project_id)."""
    files = [f.strip() for f in related_files.split(",") if f.strip()] if related_files else []
    out = _ov.save_bug(_project_id(project_id), title, problem, cause, fix, files)
    return dump_mcp({"ok": True, **out})


@mcp.tool()
def record_task_outcome(
    project_id: str,
    summary: str,
    importance: str = "medium",
    title: str = "",
    task_id: str = "",
    related_files: str = "",
) -> str:
    """WHY: persist task summary to experience memory (title/task_id for dashboard)."""
    from brain_services.stats_store import record_event

    pid = _project_id(project_id)
    files = [f.strip() for f in related_files.split(",") if f.strip()] if related_files else []
    meta: dict = {"kind": "experience", "lifecycle": "candidate", "source": "agent"}
    if title.strip():
        meta["title"] = title.strip()
    if task_id.strip():
        meta["task_id"] = task_id.strip()
    if files:
        meta["related_files"] = files
    mid = _memory.add(pid, summary, importance=importance, metadata=meta)
    try:
        record_event(
            "stack_outcome",
            project_id=pid,
            detail=(title.strip() or summary)[:200],
            metrics={
                "task_id": task_id.strip() or None,
                "importance": importance,
                "memory_id": mid.get("id") if isinstance(mid, dict) else mid,
            },
            source="mcp",
        )
    except Exception:
        pass
    if isinstance(mid, dict):
        return dump_mcp({"ok": True, **mid})
    return dump_mcp({"ok": True, "id": mid})


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
