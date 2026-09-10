#!/usr/bin/env python3
"""Rebuild experience memory jsonl from stats events (after truncation or path move).

Usage:
  python scripts/backfill_memories_from_stats.py [project_id] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brain_services.memory_simple import SimpleMemoryStore, normalize_memory_text  # noqa: E402
from brain_services.stats_store import EVENTS_FILE  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("project_id", nargs="?", default="shejiuPro")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    pid = args.project_id.strip()
    if not EVENTS_FILE.is_file():
        print(f"no events file: {EVENTS_FILE}", file=sys.stderr)
        return 1

    seen: set[str] = set()
    rows: list[tuple[str, str]] = []
    with EVENTS_FILE.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ev.get("event_type") != "memory_store":
                continue
            if (ev.get("project_id") or "").strip() != pid:
                continue
            detail = str(ev.get("detail") or "").strip()
            if not detail:
                continue
            key = normalize_memory_text(detail)
            if key in seen:
                continue
            seen.add(key)
            importance = str((ev.get("metrics") or {}).get("importance") or "medium")
            rows.append((detail, importance))

    store = SimpleMemoryStore()
    existing = store._read_all(pid)  # noqa: SLF001 — one-off repair CLI
    if existing and not args.dry_run:
        print(f"{pid}: already has {len(existing)} memories; use --dry-run to preview only")
        return 2

    print(f"project={pid} unique memory_store events={len(rows)} from {EVENTS_FILE}")
    if args.dry_run:
        for detail, imp in rows[:20]:
            print(f"  [{imp}] {detail[:120]}{'…' if len(detail) > 120 else ''}")
        if len(rows) > 20:
            print(f"  … and {len(rows) - 20} more")
        return 0

    added = 0
    for detail, importance in rows:
        store.add(pid, detail, importance=importance, metadata={"kind": "experience", "source": "backfill_stats"})
        added += 1
    print(f"added {added} memories -> {store._path(pid)}")  # noqa: SLF001
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
