"""Load ContextMind cache ledger snapshot written by hooks / contextmind report."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from brain_services.project_context import FIXTURES_ROOT, ProjectContextService

SNAPSHOT_REL = Path(".contextmind") / "cache-ledger.json"


def _env_ledger_path() -> Path | None:
    raw = os.environ.get("CONTEXTMIND_LEDGER_PATH")
    if not raw:
        return None
    p = Path(raw)
    return p if p.is_file() else None


def resolve_cache_ledger_path(project_id: str | None) -> Path | None:
    env = _env_ledger_path()
    if env:
        return env
    if not project_id:
        return None
    try:
        root = ProjectContextService().repo_root(project_id)
    except KeyError:
        return None
    if not root:
        return None
    path = root / SNAPSHOT_REL
    if path.is_file():
        return path
    fixture = FIXTURES_ROOT / project_id / SNAPSHOT_REL
    return fixture if fixture.is_file() else None


def load_contextmind_cache_ledger(project_id: str | None = None) -> dict[str, Any] | None:
    path = resolve_cache_ledger_path(project_id)
    if not path:
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    data = dict(data)
    data["snapshot_path"] = str(path)
    return data
