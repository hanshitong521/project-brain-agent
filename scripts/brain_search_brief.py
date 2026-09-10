#!/usr/bin/env python3
"""One-shot Brain search brief for stack-acceptance (no MCP)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

os.environ.setdefault("BRAIN_REPO_ROOT", str(ROOT))

from brain_services.context_memory import ContextMemoryService
from brain_services.memory_simple import get_memory_backend
from brain_services.project_context import ProjectContextService


def _goal_query(repo: Path) -> str:
    task_path = repo / ".contextmind" / "task.active.json"
    if task_path.is_file():
        try:
            task = json.loads(task_path.read_text(encoding="utf-8"))
            goal = (task.get("intent") or {}).get("goal") or task.get("goal") or ""
            if str(goal).strip():
                return str(goal).strip()[:200]
        except (OSError, json.JSONDecodeError):
            pass
    return "shejiu ocean slideFrozen DEC"


def main() -> int:
    project_id = "shejiuPro"
    query = _goal_query(ROOT)
    svc = ContextMemoryService(get_memory_backend(), ProjectContextService())
    out = svc.search_project_context(project_id, query, limit=5)
    brief = {
        "query": query,
        "count": out.get("count", 0),
        "titles": [m.get("title") for m in (out.get("memories") or [])[:5]],
        "kinds": [m.get("kind") for m in (out.get("memories") or [])[:5]],
    }
    print(json.dumps(brief, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
