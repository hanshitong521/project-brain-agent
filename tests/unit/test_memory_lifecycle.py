"""Memory lifecycle gate tests."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brain_services.memory_lifecycle import LIFECYCLE_CANDIDATE, LIFECYCLE_VERIFIED, looks_like_secret
from brain_services.memory_simple import SimpleMemoryStore


def test_secret_rejected(tmp_path: Path) -> None:
    store = SimpleMemoryStore(tmp_path / "mem")
    out = store.add("p", "password=supersecret123", metadata={"kind": "experience"})
    assert out.get("rejected") is True
    assert len(store.list_all("p")) == 0


def test_outcome_candidate_not_in_search(tmp_path: Path) -> None:
    store = SimpleMemoryStore(tmp_path / "mem")
    store.add("p", "unique lesson about coupons", metadata={"kind": "experience", "lifecycle": "candidate"})
    hits = store.search("p", "coupon")
    assert len(hits) == 0


def test_promote_then_search(tmp_path: Path) -> None:
    store = SimpleMemoryStore(tmp_path / "mem")
    r = store.add("p", "coupon concurrency queue", metadata={"kind": "experience", "lifecycle": "candidate"})
    mid = r["id"]
    assert store.search("p", "coupon") == []
    assert store.promote("p", mid)["ok"] is True
    assert len(store.search("p", "coupon")) == 1


def test_grandfather_searchable(tmp_path: Path) -> None:
    store = SimpleMemoryStore(tmp_path / "mem")
    path = tmp_path / "mem" / "p.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '{"id":"old1","memory":"legacy fact about redis","importance":"medium","metadata":{"kind":"experience"}}\n',
        encoding="utf-8",
    )
    assert len(store.search("p", "redis")) == 1
    row = store.list_all("p")[0]
    assert row.get("grandfathered") is True


def test_conflict_with_verified(tmp_path: Path) -> None:
    store = SimpleMemoryStore(tmp_path / "mem")
    store.add("p", "same body text", metadata={"kind": "decision", "lifecycle": "verified", "decision": "x"})
    r2 = store.add("p", "same body text", metadata={"kind": "experience", "lifecycle": "candidate"})
    assert r2.get("conflict") is True
    assert store.search("p", "same").__len__() == 1


def test_looks_like_secret() -> None:
    assert looks_like_secret("api_key=abc") is True
    assert looks_like_secret("normal summary") is False
