"""Rule-based auto verdict for lessons (no LLM). Human can override in Dashboard."""

from __future__ import annotations

from typing import Any

from brain_services.memory_lifecycle import (
    LIFECYCLE_CANDIDATE,
    LIFECYCLE_REJECTED,
    LIFECYCLE_VERIFIED,
    STATUS_CONFLICT,
    effective_lifecycle,
)

VERDICT_PROMOTE = "promote"
VERDICT_REVIEW = "review"
VERDICT_REJECT = "reject"
VERDICT_HOLD = "hold"  # already verified / no action


def compute_auto_verdict(item: dict[str, Any]) -> dict[str, Any]:
    """Return {verdict, reasons[], score 0-1}."""
    lc = effective_lifecycle(item)
    meta = item.get("metadata") or {}
    kind = str(meta.get("kind") or item.get("kind") or "experience")
    source = str(item.get("source") or meta.get("source") or "agent")
    importance = str(item.get("importance") or "medium").lower()
    status = str(item.get("status") or "ok")
    body = str(item.get("memory") or item.get("content") or "").strip()
    repeat = int(item.get("repeat_count") or 1)
    related = meta.get("related_files") or []
    reasons: list[str] = []

    if lc == LIFECYCLE_REJECTED:
        return {"verdict": VERDICT_REJECT, "reasons": ["已驳回"], "score": 0.0}
    if lc == LIFECYCLE_VERIFIED:
        return {"verdict": VERDICT_HOLD, "reasons": ["已在长期教训库"], "score": 1.0}

    score = 0.35
    if status == STATUS_CONFLICT:
        reasons.append("与已有 verified 冲突，需人工合并或 supersede")
        return {"verdict": VERDICT_REVIEW, "reasons": reasons, "score": 0.2}

    if len(body) < 24:
        reasons.append("正文过短，信息不足")
        return {"verdict": VERDICT_REJECT, "reasons": reasons, "score": 0.15}

    if kind == "bug":
        score += 0.25
        reasons.append("结构化 bug 教训")
        if related:
            score += 0.15
            reasons.append("含 related_files，改代码前应召回")
    if source == "testmind":
        score += 0.3
        reasons.append("TestMind 证据来源")
    if meta.get("idempotency_key"):
        score += 0.1
        reasons.append("带幂等键，可防重复写入")
    if repeat >= 2:
        score += 0.2
        reasons.append(f"重复出现 {repeat} 次")
    if importance == "high":
        score += 0.1

    score = min(1.0, score)
    if score >= 0.75:
        return {"verdict": VERDICT_PROMOTE, "reasons": reasons or ["建议进入长期教训库"], "score": score}
    if score >= 0.45:
        return {"verdict": VERDICT_REVIEW, "reasons": reasons or ["建议人工看一眼"], "score": score}
    return {"verdict": VERDICT_REVIEW, "reasons": reasons or ["默认待审"], "score": score}


def should_auto_promote(item: dict[str, Any], mode: str) -> bool:
    """mode: off | testmind | aggressive"""
    if mode in ("", "off", "0", "false"):
        return False
    review = compute_auto_verdict(item)
    if review["verdict"] != VERDICT_PROMOTE:
        return False
    meta = item.get("metadata") or {}
    source = str(item.get("source") or meta.get("source") or "")
    kind = str(meta.get("kind") or "experience")
    if mode == "testmind":
        return source == "testmind" and bool(meta.get("idempotency_key"))
    if mode == "aggressive":
        return kind in ("bug", "experience") and review.get("score", 0) >= 0.75
    return False
