"""Resolve Brain persistence directory (memories, stats, aliases).

Default on Windows: ``D:\\shejiu-data\\project-brain``. Override with
``BRAIN_DATA_ROOT`` (exact directory) or ``SHEJIU_DATA_ROOT`` (parent; uses
``project-brain`` subfolder). Falls back to repo ``.data`` when unset elsewhere.
"""

from __future__ import annotations

import os
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
