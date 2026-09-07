#!/usr/bin/env python3
"""Backfill Phoenix-style display titles onto existing JSONL memories."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brain_services.memory_simple import SimpleMemoryStore  # noqa: E402


def main() -> int:
    project_id = sys.argv[1] if len(sys.argv) > 1 else "shejiuPro"
    out = SimpleMemoryStore().backfill_titles(project_id)
    print(json.dumps({"project_id": project_id, **out}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
