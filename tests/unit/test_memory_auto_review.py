from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brain_services.lessons_markdown import render_lessons_markdown
from brain_services.memory_auto_review import VERDICT_PROMOTE, compute_auto_verdict
from brain_services.memory_simple import SimpleMemoryStore


def test_bug_with_files_suggests_promote(tmp_path: Path) -> None:
    store = SimpleMemoryStore(tmp_path / "mem")
    r = store.add(
        "p",
        "[BUG] x\nProblem: p\nCause: c\nFix: f",
        metadata={
            "kind": "bug",
            "lifecycle": "candidate",
            "related_files": ["Foo.java"],
            "importance": "high",
        },
    )
    assert r["auto_verdict"]["verdict"] == VERDICT_PROMOTE


def test_lessons_markdown(tmp_path: Path) -> None:
    store = SimpleMemoryStore(tmp_path / "mem")
    store.add("p", "verified lesson text here enough length", metadata={"kind": "experience", "lifecycle": "verified"})
    items = store.list_all("p")
    md = render_lessons_markdown("p", items)
    assert "# 项目教训" in md
    assert "verified lesson" in md


def test_patch_update(tmp_path: Path) -> None:
    store = SimpleMemoryStore(tmp_path / "mem")
    r = store.add("p", "candidate lesson with enough characters here", metadata={"kind": "experience", "lifecycle": "candidate"})
    out = store.update_by_id("p", r["id"], memory="updated lesson body with enough length", title="T")
    assert out["ok"] is True
