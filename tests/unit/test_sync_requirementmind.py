"""RequirementMind → Brain sync (scoped revoke)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from brain_services.context_memory import ContextMemoryService
from brain_services.memory_simple import SimpleMemoryStore


def test_revoke_rm_decisions_scoped_by_session(tmp_path: Path) -> None:
    mem = SimpleMemoryStore(tmp_path / "mem")
    svc = ContextMemoryService(mem)
    svc.save_decision(
        "shejiuPro",
        "[DEC-KEEP] keep me",
        rationale="RequirementMind FROZEN",
        rm_decision_id="DEC-KEEP",
        rm_session="ocean-brand-lock",
    )
    svc.save_decision(
        "shejiuPro",
        "[DEC-GONE] wrong",
        rationale="RequirementMind FROZEN",
        rm_decision_id="DEC-GONE",
        rm_session="ocean-brand-lock",
    )
    svc.save_decision(
        "shejiuPro",
        "[DEC-OTHER-SESSION] other",
        rationale="RequirementMind FROZEN",
        rm_decision_id="DEC-OTHER-SESSION",
        rm_session="red-packet",
    )
    out = svc.revoke_scoped_rm_decisions(
        "shejiuPro", "ocean-brand-lock", {"DEC-KEEP"}
    )
    assert out["removed"] == 1
    assert out["revoked_ids"] == ["DEC-GONE"]
    hits = mem.search("shejiuPro", "DEC-GONE", limit=5)
    assert not any("DEC-GONE" in (h.get("memory") or "") for h in hits)
    hits_other = mem.search("shejiuPro", "DEC-OTHER-SESSION", limit=5)
    assert any("DEC-OTHER-SESSION" in (h.get("memory") or "") for h in hits_other)


def test_sync_script_revoke_then_sync(tmp_path: Path) -> None:
    rm = tmp_path / ".requirementmind"
    rm.mkdir()
    (rm / "active-session.json").write_text(
        json.dumps({"session_id": "test-session", "session_path": "sessions/test-session"}),
        encoding="utf-8",
    )
    sess = rm / "sessions" / "test-session"
    sess.mkdir(parents=True)
    decisions = [
        {
            "id": "DEC-A",
            "status": "FROZEN",
            "decision": "only A",
        }
    ]
    (sess / "decisions.json").write_text(json.dumps(decisions), encoding="utf-8")
    mem_dir = tmp_path / "brain-mem"
    mem_dir.mkdir()
    store = SimpleMemoryStore(mem_dir)
    svc = ContextMemoryService(store)
    svc.save_decision(
        "shejiuPro",
        "[DEC-B] stale",
        rationale="RequirementMind FROZEN",
        rm_decision_id="DEC-B",
        rm_session="test-session",
    )
    active = {d["id"] for d in decisions if d.get("id")}
    revoke = svc.revoke_scoped_rm_decisions("shejiuPro", "test-session", active)
    assert revoke["removed"] == 1
    for d in decisions:
        tag = f"[{d['id']}] "
        svc.save_decision(
            "shejiuPro",
            f"{tag}{d['decision']}",
            rationale="RequirementMind FROZEN",
            rm_decision_id=d["id"],
            rm_session="test-session",
        )
    all_items = store.list_all("shejiuPro", limit=50)
    bodies = " ".join(str(i.get("memory") or "") for i in all_items)
    assert "DEC-B" not in bodies
    assert "DEC-A" in bodies


def test_backfill_tags_only_matching_session_frozen(tmp_path: Path) -> None:
    rm = tmp_path / ".requirementmind"
    rm.mkdir()
    (rm / "active-session.json").write_text(
        json.dumps({"session_id": "ocean", "session_path": "sessions/ocean"}),
        encoding="utf-8",
    )
    sess = rm / "sessions" / "ocean"
    sess.mkdir(parents=True)
    (sess / "decisions.json").write_text(
        json.dumps(
            [{"id": "DEC-001", "status": "FROZEN", "decision": "ocean freeze slide"}]
        ),
        encoding="utf-8",
    )
    mem = SimpleMemoryStore(tmp_path / "mem")
    mem.add(
        "shejiuPro",
        "[DECISION]\n[DEC-001] ocean freeze slide\nRationale: RequirementMind FROZEN",
        importance="high",
        metadata={
            "kind": "decision",
            "decision": "[DEC-001] ocean freeze slide",
            "rationale": "RequirementMind FROZEN",
            "task_id": "DECISION",
        },
    )
    mem.add(
        "shejiuPro",
        "[DECISION]\n[DEC-001] red packet other text\nRationale: RequirementMind FROZEN",
        importance="high",
        metadata={
            "kind": "decision",
            "decision": "[DEC-001] red packet other text",
            "rationale": "RequirementMind FROZEN",
            "task_id": "DECISION",
        },
    )
    sys.path.insert(0, str(ROOT / "scripts"))
    from backfill_rm_decision_tags import backfill_tags, load_frozen_decisions

    session_id, frozen = load_frozen_decisions(rm)
    stats = backfill_tags(mem, "shejiuPro", session_id, frozen)
    assert stats["updated"] == 1
    items = mem.list_all("shejiuPro", 10)
    tagged = [i for i in items if (i.get("metadata") or {}).get("rm_decision_id") == "DEC-001"]
    assert len(tagged) == 1
    assert "ocean freeze" in (tagged[0].get("memory") or "")
