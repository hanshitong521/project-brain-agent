from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def seed_demo_spring() -> None:
    from brain_services.memory_simple import SimpleMemoryStore

    store = SimpleMemoryStore()
    store.add(
        "demo-spring-project",
        "Bug fix 2025-03: duplicate refund on retry — fixed by idempotent key orderId+reason in RefundService.apply",
        importance="high",
    )
    store.add(
        "demo-spring-project",
        "Architecture decision: all refund API goes through RefundService, not controllers directly.",
        importance="medium",
    )


def pytest_configure() -> None:
    seed_demo_spring()
