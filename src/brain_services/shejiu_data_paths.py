"""Project-scoped paths under SHEJIU_DATA_ROOT (shared with ContextMind layout)."""

from __future__ import annotations

import json
import os
from pathlib import Path

from brain_services.data_root import _DEFAULT_SHEJIU, brain_data_root


def shejiu_data_root() -> Path:
    explicit = os.environ.get("SHEJIU_DATA_ROOT", "").strip()
    if explicit:
        return Path(explicit).expanduser().resolve()
    if os.name == "nt":
        return _DEFAULT_SHEJIU.resolve()
    return (Path.home() / "shejiu-data").resolve()


def project_data_key(project_root: Path) -> str:
    cfg_path = project_root / ".contextmind.json"
    if cfg_path.is_file():
        try:
            raw = json.loads(cfg_path.read_text(encoding="utf-8"))
            pid = (raw.get("brain") or {}).get("project_id")
            if pid and str(pid).strip():
                return str(pid).strip()
        except (OSError, ValueError, TypeError):
            pass
    return project_root.name or "default"


def project_contextmind_dir(project_root: Path) -> Path:
    return shejiu_data_root() / "projects" / project_data_key(project_root) / "contextmind"


def project_forgemind_dir(project_root: Path) -> Path:
    return shejiu_data_root() / "projects" / project_data_key(project_root) / "forgemind"


def resolve_forgemind_root(project_root: Path) -> Path:
    """Directory containing mcp-activity.jsonl (under SHEJIU_DATA_ROOT when set)."""
    if os.environ.get("SHEJIU_DATA_ROOT", "").strip() or os.name == "nt":
        return project_forgemind_dir(project_root)
    return project_root / ".forgemind"


def resolve_contextmind_dir(project_root: Path) -> Path:
    if os.environ.get("CONTEXTMIND_TELEMETRY_DB", "").strip():
        return Path(os.environ["CONTEXTMIND_TELEMETRY_DB"]).resolve().parent
    if os.environ.get("SHEJIU_DATA_ROOT", "").strip() or os.name == "nt":
        return project_contextmind_dir(project_root)
    return project_root / ".contextmind"
