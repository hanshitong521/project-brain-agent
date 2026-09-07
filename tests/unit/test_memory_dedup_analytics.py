"""Memory dedup and token analytics tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brain_services.memory_simple import SimpleMemoryStore
from brain_services.token_analytics import aggregate_savings, context_build_ledger, normalize_memory_text


def test_normalize_strips_ledger_suffix() -> None:
    a = "hello Ledger: tool_saved~0"
    b = "hello"
    assert normalize_memory_text(a) == normalize_memory_text(b)


def test_memory_dedup_on_add(tmp_path: Path) -> None:
    store = SimpleMemoryStore(tmp_path / "mem")
    s = "[task] same summary"
    r1 = store.add("p", s)
    r2 = store.add("p", s + " Ledger: x")
    assert r1["deduplicated"] is False
    assert r2["deduplicated"] is True
    assert r2.get("event_skipped") is True
    assert len(store.list_all("p")) == 1
    assert store.list_all("p")[0]["repeat_count"] == 2


def test_dedupe_preview(tmp_path: Path) -> None:
    store = SimpleMemoryStore(tmp_path / "mem")
    store.add("p", "same")
    store.add("p", "other")
    path = tmp_path / "mem" / "p.jsonl"
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    dup = json.loads(lines[0])
    dup["id"] = "dup-row"
    path.write_text("\n".join(lines + [json.dumps(dup, ensure_ascii=False)]) + "\n", encoding="utf-8")
    preview = store.dedupe_preview("p")
    assert preview["before"] == 3
    assert preview["removed"] == 1
    assert preview["kept"] == 2
    assert len(store.list_all("p")) == 3


def test_ledger_aggregation() -> None:
    events = [
        {
            "id": "e1",
            "event_type": "context_build",
            "project_id": "shejiuPro",
            "detail": "t1",
            "timestamp_cn": "2026-09-04 10:00:00",
            "metrics": {
                "usage_tokens": 100,
                "baseline_tokens": 1000,
                "saved_tokens": 900,
                "memory_hits": 1,
                "knowledge_hits": 0,
            },
        },
        {
            "id": "e2",
            "event_type": "context_build",
            "project_id": "shejiuPro",
            "detail": "t2",
            "timestamp_cn": "2026-09-04 11:00:00",
            "metrics": {
                "usage_tokens": 200,
                "baseline_tokens": 1000,
                "saved_tokens": 800,
                "memory_hits": 0,
                "knowledge_hits": 1,
            },
        },
    ]
    ledger = context_build_ledger(events, hit_filter="all", limit=10)
    assert len(ledger) == 2
    series = aggregate_savings(ledger, "day")
    assert series[0]["saved_tokens"] == 1700
    miss = context_build_ledger(events, hit_filter="miss", limit=10)
    assert len(miss) == 0
