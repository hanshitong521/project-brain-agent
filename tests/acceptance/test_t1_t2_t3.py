"""Acceptance T1–T3 against v1 spec (offline demo backend)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brain_services.context_builder import ContextBuilder
from brain_services.knowledge_service import KnowledgeService
def test_t1_refund_design_question() -> None:
    ctx = ContextBuilder()
    out = ctx.build_task_context(
        "demo-spring-project",
        "这个项目退款模块怎么设计？",
        budget_tokens=5000,
    )
    text = out["context"].lower()
    assert "refund" in text or "退款" in text
    assert out["usage_tokens"] <= 5000
    assert out["within_budget"]


def test_t2_memory_and_context_for_service_change() -> None:
    ctx = ContextBuilder()
    out = ctx.build_task_context(
        "demo-spring-project",
        "修改 RefundService apply 方法 幂等",
        budget_tokens=5000,
    )
    assert "refundservice" in out["context"].lower() or "RefundService" in out["context"]
    assert "idempotent" in out["context"].lower() or "幂等" in out["context"] or "orderId" in out["context"]


def test_t3_token_vs_full_corpus() -> None:
    know = KnowledgeService()
    baseline, _src = know.full_corpus_tokens("demo-spring-project")
    ctx = ContextBuilder()
    out = ctx.build_task_context(
        "demo-spring-project",
        "refund module",
        budget_tokens=5000,
    )
    assert out["usage_tokens"] <= 5000
    # Full corpus load >> retrieval path (spec T3: ~30k vs ≤5k)
    assert baseline > 3000, f"baseline tokens={baseline}"
    assert out["usage_tokens"] < baseline
