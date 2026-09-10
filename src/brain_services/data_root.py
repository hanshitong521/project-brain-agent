"""Resolve Brain persistence directory (memories, stats, aliases).

Default on Windows: ``D:\\shejiu-data\\project-brain``. Override with
``BRAIN_DATA_ROOT`` (exact directory) or ``SHEJIU_DATA_ROOT`` (parent; uses
``project-brain`` subfolder). Falls back to repo ``.data`` when unset elsewhere.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LEGACY_DATA = _REPO_ROOT / ".data"
_DEFAULT_SHEJIU = Path(r"D:\shejiu-data")


def brain_data_root() -> Path:
    explicit = os.environ.get("BRAIN_DATA_ROOT", "").strip()
    if explicit:
        return Path(explicit).expanduser().resolve()
    base = os.environ.get("SHEJIU_DATA_ROOT", "").strip()
    if base:
        return (Path(base).expanduser().resolve() / "project-brain")
    if os.name == "nt":
        return (_DEFAULT_SHEJIU / "project-brain").resolve()
    return _LEGACY_DATA.resolve()


def migrate_legacy_data_if_needed() -> Path:
    """Copy repo ``.data`` into ``brain_data_root()`` once when target is empty."""
    target = brain_data_root()
    legacy = _LEGACY_DATA
    if target.resolve() == legacy.resolve():
        target.mkdir(parents=True, exist_ok=True)
        return target

    target.mkdir(parents=True, exist_ok=True)
    if not legacy.is_dir():
        return target

    def _needs_seed() -> bool:
        if (target / "project_aliases.json").is_file():
            return False
        if any(target.joinpath("memories").glob("*.jsonl")):
            return False
        if (target / "stats" / "events.jsonl").is_file():
            return False
        return True

    if not _needs_seed() and not any(legacy.iterdir()):
        return target
    if not _needs_seed():
        return target

    for name in ("memories", "stats", "qdrant"):
        src = legacy / name
        dst = target / name
        if src.is_dir() and not dst.exists():
            shutil.copytree(src, dst)
    alias_src = legacy / "project_aliases.json"
    alias_dst = target / "project_aliases.json"
    if alias_src.is_file() and not alias_dst.is_file():
        shutil.copy2(alias_src, alias_dst)

    return target
