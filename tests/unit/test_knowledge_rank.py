"""Knowledge ranking: stopwords, path score, top hits."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brain_services.knowledge_service import KnowledgeService


def test_refund_query_hits_refund_design() -> None:
    know = KnowledgeService()
    hits = know.search("demo-spring-project", "这个项目退款模块怎么设计？", top_k=2)
    assert hits
    sources = " ".join(h["source"].lower() for h in hits)
    assert "refund" in sources
    assert "large-appendix" not in sources


def test_stopwords_do_not_match_standard() -> None:
    know = KnowledgeService()
    hits = know.search("demo-spring-project", "the and for with", top_k=5)
    assert hits == []


def test_refund_excerpt_contains_design_not_only_head() -> None:
    know = KnowledgeService()
    hits = know.search("demo-spring-project", "refund idempotent orderId", top_k=1)
    assert hits
    body = hits[0]["text"]
    assert "refund" in body.lower() or "order" in body.lower()
    assert body != body[:80] or len(body) <= 80


def test_builder_uses_two_knowledge_hits() -> None:
    from brain_services.context_builder import ContextBuilder

    out = ContextBuilder().build_task_context(
        "demo-spring-project",
        "refund module design",
        budget_tokens=5000,
    )
    assert out["knowledge_hits"] <= 2
    assert out["within_budget"]
