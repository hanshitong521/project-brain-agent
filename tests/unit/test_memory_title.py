"""Unit tests for Phoenix-style memory titles."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from brain_services.memory_simple import SimpleMemoryStore
from brain_services.memory_title import derive_memory_title, enrich_memory_metadata


def test_derive_bug_and_decision_titles() -> None:
    assert "DEC-009" in derive_memory_title(
        "[DECISION]\n[DEC-009] A. 不删 type3",
        {"kind": "decision", "decision": "[DEC-009] A. 不删 type3"},
    )
    assert "监控成交" in derive_memory_title(
        "[BUG] 监控成交只加订单\nProblem: x",
        {"kind": "bug", "title": "监控成交只加订单"},
    )


def test_derive_task_prefix() -> None:
    t = derive_memory_title(
        "[anchor-list-claim-window] 当前列表口径 Ledger: tool_saved~1",
        {"kind": "experience"},
    )
    assert "anchor-list-claim-window" in t
    assert "Ledger" not in t


def test_add_persists_title(tmp_path: Path) -> None:
    store = SimpleMemoryStore(tmp_path)
    out = store.add(
        "shejiuPro",
        "[tok] press tokens",
        metadata={"kind": "experience", "task_id": "tok"},
    )
    assert out["deduplicated"] is False
    assert out.get("title")
    items = store.list_all("shejiuPro")
    assert items[-1]["title"]
    assert items[-1]["metadata"]["title"] == items[-1]["title"]


def test_backfill_titles(tmp_path: Path) -> None:
    store = SimpleMemoryStore(tmp_path)
    path = store._path("p1")
    path.write_text(
        '{"id":"a1","memory":"[BUG] 旧坑\\nProblem: x","metadata":{"kind":"bug","title":"旧坑"},"repeat_count":1}\n',
        encoding="utf-8",
    )
    r = store.backfill_titles("p1")
    assert r["total"] == 1
    items = store.list_all("p1")
    assert items[0]["title"] == "旧坑"


def test_enrich_sets_kind() -> None:
    meta = enrich_memory_metadata("hello world", None)
    assert meta["kind"] == "experience"
    assert meta["title"]
