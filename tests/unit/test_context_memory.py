"""OpenViking-layer (context memory) tests."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brain_services.context_memory import ContextMemoryService
from brain_services.memory_simple import SimpleMemoryStore
from brain_services.project_context import ProjectContextService


def test_save_decision_and_search(tmp_path: Path) -> None:
    mem = SimpleMemoryStore(tmp_path / "mem")
    svc = ContextMemoryService(mem, ProjectContextService(ROOT / "fixtures"))
    svc.save_decision(
        "shejiuPro",
        "退款不直接改订单主状态",
        rationale="影响结算",
        related_files=["RefundService.java"],
    )
    out = svc.search_project_context("shejiuPro", "退款 订单")
    assert out["count"] >= 1
    assert out["layer"] == "openviking"


def test_get_change_context_scores_file(tmp_path: Path) -> None:
    mem = SimpleMemoryStore(tmp_path / "mem")
    svc = ContextMemoryService(mem, ProjectContextService(ROOT / "fixtures"))
    svc.save_bug(
        "shejiuPro",
        "重复领红包",
        problem="锁失效",
        fix="Redis SETNX",
        related_files=["TRedPacketTaskServiceImpl.java"],
    )
    ctx = svc.get_change_context("shejiuPro", "shejiu-modules/shejiu-product/.../TRedPacketTaskServiceImpl.java")
    assert ctx["change_risk"] == "high"
    assert len(ctx["memories"]) >= 1
    assert "docs" in ctx
    assert isinstance(ctx.get("path_needles"), list)


def test_decision_dedup(tmp_path: Path) -> None:
    mem = SimpleMemoryStore(tmp_path / "mem")
    svc = ContextMemoryService(mem, ProjectContextService(ROOT / "fixtures"))
    r1 = svc.save_decision("shejiuPro", "same decision", "r1")
    r2 = svc.save_decision("shejiuPro", "same decision", "r2")
    assert r1["deduplicated"] is False
    assert r2["deduplicated"] is True
