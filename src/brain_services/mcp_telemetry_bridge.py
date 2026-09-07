"""Map ContextMind telemetry tool_name -> MCP server label for MCP Lab."""
from __future__ import annotations

CONTEXTMIND_TOOLS = frozenset(
    {
        "context_orient",
        "context_fetch",
        "context_find",
        "context_get",
        "context_impact",
        "context_run",
    }
)

BRAIN_TOOLS = frozenset(
    {
        "search_project_context",
        "get_change_context",
        "save_architecture_decision",
        "save_bug_memory",
        "record_task_outcome",
    }
)


def infer_mcp_server(tool_name: str) -> str:
    t = (tool_name or "").strip()
    if t in CONTEXTMIND_TOOLS or t.startswith("context_"):
        return "contextmind"
    if t in BRAIN_TOOLS or "brain" in t.lower():
        return "project-brain"
    if t.startswith("MCP:"):
        return t[4:].split("/")[0] or "mcp"
    if t in ("mysql", "ads-mysql"):
        return "ads-mysql"
    if "codegraph" in t.lower():
        return "codegraph"
    return "mcp"
