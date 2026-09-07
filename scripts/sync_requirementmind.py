#!/usr/bin/env python3
"""Push FROZEN RequirementMind decisions into project-brain (OpenViking layer)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brain_services.context_memory import ContextMemoryService
from brain_services.memory_simple import SimpleMemoryStore

PROJECT_ID = "shejiuPro"


def load_decisions(rm_dir: Path) -> list[dict]:
    path = rm_dir / "decisions.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        items = data
    else:
        items = data.get("decisions") or data.get("items") or []
    out = []
    for d in items:
        if str(d.get("status", "")).upper() != "FROZEN":
            continue
        text = d.get("text") or d.get("summary") or d.get("decision") or ""
        if not str(text).strip():
            continue
        out.append(
            {
                "id": d.get("id") or d.get("decision_id"),
                "text": str(text).strip(),
                "rationale": str(d.get("rationale") or "").strip(),
            }
        )
    return out


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: sync_requirementmind.py <shejiuPro-root>", file=sys.stderr)
        return 2
    project_root = Path(sys.argv[1]).resolve()
    rm = project_root / ".requirementmind"
    svc = ContextMemoryService(SimpleMemoryStore())
    decisions = load_decisions(rm)
    if not decisions:
        print("No FROZEN decisions to sync.")
        return 0
    synced = 0
    for d in decisions:
        tag = f"[{d['id']}] " if d.get("id") else ""
        svc.save_decision(
            PROJECT_ID,
            f"{tag}{d['text']}",
            rationale=d.get("rationale") or "RequirementMind FROZEN",
            related_files=[],
        )
        synced += 1
    print(f"Synced {synced} decision(s) → brain memory ({PROJECT_ID}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
