"""Seed demo memories for acceptance tests."""

from __future__ import annotations

from brain_services.memory_simple import SimpleMemoryStore


def seed_demo_spring() -> None:
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


if __name__ == "__main__":
    seed_demo_spring()
    print("Seeded demo-spring-project memories")
