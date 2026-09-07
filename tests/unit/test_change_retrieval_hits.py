"""get_change path needles + retrieval ledger hit analytics."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brain_services.context_memory import ContextMemoryService
from brain_services.memory_simple import SimpleMemoryStore
from brain_services.project_context import ProjectContextService
from brain_services.rank import extract_related_paths, file_path_needles, score_change_memory
from brain_services.token_analytics import (
    combined_hit_summary,
    merge_hit_series,
    retrieval_ledger,
)


def test_file_path_needles_camel() -> None:
    needles = file_path_needles(
        "shejiu-modules/shejiu-product/src/main/resources/mapper/product/VProductSelectorWeeklyStatsMapper.xml"
    )
    joined = " ".join(needles)
    assert "vproductselectorweeklystatsmapper.xml" in joined or "vproductselectorweeklystatsmapper" in joined
    assert "weekly" in joined or "stats" in joined or "selector" in joined
    assert "product" in joined


def test_extract_related_paths() -> None:
    text = "Fix in TCommonServiceImpl.java and VProductSelectorWeeklyStatsMapper.xml under mapper/"
    paths = extract_related_paths(text)
    assert any("TCommonServiceImpl.java" in p for p in paths)
    assert any("VProductSelectorWeeklyStatsMapper.xml" in p for p in paths)


def test_get_change_hits_mapper_with_related(tmp_path: Path) -> None:
    mem = SimpleMemoryStore(tmp_path / "mem")
    svc = ContextMemoryService(mem, ProjectContextService(ROOT / "fixtures"))
    svc.save_bug(
        "shejiuPro",
        "周战绩 listStats 与日表不一致",
        problem="VProductSelectorWeeklyStatsMapper 口径漏退款",
        fix="对齐 finc total_profit_with_refund",
        related_files=[
            "shejiu-modules/shejiu-product/src/main/resources/mapper/product/VProductSelectorWeeklyStatsMapper.xml",
            "TCommonServiceImpl.java",
        ],
    )
    ctx = svc.get_change_context(
        "shejiuPro",
        "shejiu-modules/shejiu-product/src/main/resources/mapper/product/VProductSelectorWeeklyStatsMapper.xml",
    )
    assert len(ctx["memories"]) >= 1
    assert ctx["change_risk"] == "high"
    assert "docs" in ctx
    assert isinstance(ctx["docs"], list)


def test_get_change_soft_match_stem_in_body(tmp_path: Path) -> None:
    mem = SimpleMemoryStore(tmp_path / "mem")
    svc = ContextMemoryService(mem, ProjectContextService(ROOT / "fixtures"))
    mem.add(
        "shejiuPro",
        "weekProfitAmount 周战绩 listStats 对齐日表；触达 VProductSelectorWeeklyStatsMapper 与 listForStatisAdmin",
        metadata={"kind": "bug", "title": "周战绩口径"},
    )
    ctx = svc.get_change_context(
        "shejiuPro",
        "mapper/product/VProductSelectorWeeklyStatsMapper.xml",
    )
    assert len(ctx["memories"]) >= 1


def test_score_change_memory_related_beats_noise() -> None:
    item = {
        "memory": "unrelated token harness",
        "metadata": {
            "kind": "bug",
            "related_files": ["VProductSelectorWeeklyStatsMapper.xml"],
        },
        "repeat_count": 1,
    }
    needles = file_path_needles("VProductSelectorWeeklyStatsMapper.xml")
    assert score_change_memory(item, needles, "VProductSelectorWeeklyStatsMapper.xml") > 10


def test_retrieval_ledger_and_combined_summary() -> None:
    events = [
        {
            "id": "1",
            "event_type": "context_retrieval",
            "project_id": "shejiuPro",
            "timestamp_cn": "2026-09-05 14:00:00.000",
            "detail": "get_change_context: foo",
            "metrics": {
                "op": "get_change_context",
                "memory_hits": 0,
                "knowledge_hits": 1,
                "memory_hit": False,
                "knowledge_hit": True,
                "any_hit": True,
            },
        },
        {
            "id": "2",
            "event_type": "context_retrieval",
            "project_id": "demo-spring-project",
            "timestamp_cn": "2026-09-05 14:01:00.000",
            "detail": "search",
            "metrics": {"memory_hits": 1, "knowledge_hits": 0, "any_hit": True},
        },
    ]
    rows = retrieval_ledger(events, date_from="2026-09-05", date_to="2026-09-05")
    assert len(rows) == 1
    assert rows[0]["knowledge_hit"] is True
    summary = combined_hit_summary([], rows)
    assert summary["build_count"] == 0
    assert summary["retrieval_count"] == 1
    assert summary["hit_source"] == "retrieval"
    assert summary["any_hit_rate"] == 100.0
    assert summary["knowledge_hit_rate"] == 100.0


def test_merge_hit_series_fills_empty_day() -> None:
    build = [
        {
            "period": "2026-09-04",
            "build_count": 2,
            "saved_tokens": 100,
            "usage_tokens": 10,
            "baseline_tokens": 110,
            "memory_hit_count": 2,
            "knowledge_hit_count": 2,
            "miss_count": 0,
            "both_hit_count": 2,
            "hit_rate": 100.0,
            "avg_saved": 50,
        }
    ]
    ret = [
        {
            "period": "2026-09-05",
            "build_count": 3,
            "retrieval_count": 3,
            "saved_tokens": 0,
            "usage_tokens": 0,
            "baseline_tokens": 0,
            "memory_hit_count": 2,
            "knowledge_hit_count": 1,
            "miss_count": 1,
            "both_hit_count": 1,
            "hit_rate": 66.7,
            "avg_saved": 0,
        }
    ]
    merged = merge_hit_series(build, ret)
    periods = [m["period"] for m in merged]
    assert "2026-09-04" in periods and "2026-09-05" in periods
    day5 = next(m for m in merged if m["period"] == "2026-09-05")
    assert day5.get("series_source") == "retrieval"
