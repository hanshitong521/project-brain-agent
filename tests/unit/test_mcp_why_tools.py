"""MCP exposes only WHY five tools."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brain_mcp.server import WHY_TOOLS, mcp


def test_mcp_lists_exactly_why_five_tools() -> None:
    tools = asyncio.run(mcp.list_tools())
    names = sorted(t.name for t in tools)
    assert names == sorted(WHY_TOOLS)
    assert len(names) == 5
    assert "search_knowledge" not in names
    assert "build_task_context" not in names
    assert "search_memory" not in names
    assert "search_project" not in names
