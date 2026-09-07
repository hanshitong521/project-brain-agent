"""Ranked memory/knowledge search and compact MCP dumps."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brain_services.knowledge_service import KnowledgeService
from brain_services.memory_simple import SimpleMemoryStore
from brain_services.rank import dump_mcp, excerpt_paragraphs, query_tokens
from brain_services.token_analytics import aggregate_savings, savings_summary


def test_refund_query_hits_refund_design() -> None:
    know = KnowledgeService()
    hits = know.search("demo-spring-project", "这个项目退款模块怎么设计？", top_k=2)
    assert hits
    sources = " ".join(h["source"].lower() for h in hits)
    assert "refund" in sources
    assert "large-appendix" not in sources


def test_cjk_bigrams_from_compound_query() -> None:
    q = "\u8fbe\u4eba\u7ea2\u5305\u5f53\u524d\u5217\u8868"  # 达人红包当前列表
    toks = query_tokens(q)
    assert "\u7ea2\u5305" in toks  # 红包
    assert "\u5217\u8868" in toks  # 列表


def test_memory_ranks_product_over_harness_noise(tmp_path: Path) -> None:
    store = SimpleMemoryStore(tmp_path / "mem")
    store.add("p", "token harness install notes for contextmind")
    store.add(
        "p",
        "\u7ea2\u5305\u5217\u8868\u53e3\u5f84\uff1a\u5f53\u524d=\u5f00+\u6682\u505c+\u9886\u53d6\u672a\u622a\u6b62",
        metadata={"kind": "decision"},
    )
    hits = store.search("p", "\u8fbe\u4eba\u7ea2\u5305\u5f53\u524d\u5217\u8868", limit=1)
    assert hits
    assert "\u7ea2\u5305" in (hits[0].get("memory") or "")


def test_stopwords_query_tokens_empty() -> None:
    assert query_tokens("the and for with") == []


def test_dump_mcp_is_compact() -> None:
    s = dump_mcp({"a": 1, "b": [2]})
    assert "\n" not in s
    assert json.loads(s)["a"] == 1


def test_excerpt_paragraphs_skips_preamble() -> None:
    text = (
        "Table of contents\n\n"
        "Intro filler " * 20 + "\n\n"
        "Refund design: use orderId for idempotent refund API.\n\n"
        "Appendix noise."
    )
    toks = query_tokens("refund orderId idempotent")
    ex = excerpt_paragraphs(text, toks, "refund module design", max_chars=200)
    assert "Refund design" in ex
    assert "Table of contents" not in ex


def test_search_project_context_includes_docs(tmp_path: Path) -> None:
    from brain_services.context_memory import ContextMemoryService
    from brain_services.project_context import ProjectContextService

    fixtures = ROOT / "fixtures"
    mem = SimpleMemoryStore(tmp_path / "mem")
    svc = ContextMemoryService(mem, ProjectContextService(fixtures))
    out = svc.search_project_context("demo-spring-project", "refund module design", limit=3)
    assert "docs" in out
    assert isinstance(out["docs"], list)
    if out["docs"]:
        assert "source" in out["docs"][0]
        assert "text" in out["docs"][0]


def test_hour_bucket_and_any_hit_rate() -> None:
    ledger = [
        {
            "timestamp_cn": "2026-09-04 10:15:00",
            "saved_tokens": 100,
            "usage_tokens": 10,
            "baseline_tokens": 110,
            "memory_hit": True,
            "knowledge_hit": False,
        },
        {
            "timestamp_cn": "2026-09-04 10:40:00",
            "saved_tokens": 50,
            "usage_tokens": 20,
            "baseline_tokens": 70,
            "memory_hit": False,
            "knowledge_hit": False,
        },
    ]
    series = aggregate_savings(ledger, "hour")
    assert len(series) == 1
    assert series[0]["period"] == "2026-09-04 10:00"
    assert series[0]["miss_count"] == 1
    s = savings_summary(ledger)
    assert s["any_hit_rate"] == 50.0
    assert s["full_miss_rate"] == 50.0
