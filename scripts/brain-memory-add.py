#!/usr/bin/env python3
"""CLI: append one line to Project Brain experience memory.

Usage:
  brain-memory-add.py <project_id> <summary> [importance] [json_metadata]

json_metadata example:
  {"kind":"experience","task_id":"anchor-list","title":"列表口径"}
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brain_services.memory_simple import SimpleMemoryStore  # noqa: E402


def main() -> int:
    if len(sys.argv) < 3:
        print(
            "usage: brain-memory-add.py <project_id> <summary> [importance] [json_metadata]",
            file=sys.stderr,
        )
        return 2
    project_id = sys.argv[1]
    summary = sys.argv[2]
    importance = sys.argv[3] if len(sys.argv) > 3 else "medium"
    metadata: dict = {"kind": "experience"}
    if len(sys.argv) > 4 and sys.argv[4].strip():
        try:
            extra = json.loads(sys.argv[4])
            if isinstance(extra, dict):
                metadata.update(extra)
                metadata.setdefault("kind", "experience")
        except json.JSONDecodeError as e:
            print(f"invalid json_metadata: {e}", file=sys.stderr)
            return 2
    result = SimpleMemoryStore().add(
        project_id, summary, importance=importance, metadata=metadata
    )
    print(json.dumps(result, ensure_ascii=False) if isinstance(result, dict) else result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
