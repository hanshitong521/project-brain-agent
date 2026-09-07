"""Unit tests for stats_store event loading."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import brain_services.stats_store as stats_store
from brain_services.project_context import ProjectContextService


@pytest.fixture()
def isolated_stats(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    data_dir = tmp_path / "stats"
    events_file = data_dir / "events.jsonl"
    monkeypatch.setattr(stats_store, "DATA_DIR", data_dir)
    monkeypatch.setattr(stats_store, "EVENTS_FILE", events_file)
    monkeypatch.setattr(stats_store, "_recent", stats_store.deque(maxlen=500))
    monkeypatch.setattr(stats_store, "_hydrated", False)

    _orig_tracked = ProjectContextService.is_tracked_project

    def _tracked(self, project_id: str | None) -> bool:
        if project_id in ("a", "b"):
            return True
        return _orig_tracked(self, project_id)

    monkeypatch.setattr(ProjectContextService, "is_tracked_project", _tracked)
    return events_file


def test_load_events_reads_file_after_memory_has_only_system(isolated_stats: Path) -> None:
    ctx = {
        "id": "evt-1",
        "event_type": "context_build",
        "project_id": "shejiuPro",
        "detail": "task",
        "metrics": {"usage_tokens": 100, "baseline_tokens": 5000, "within_budget": True},
        "timestamp_utc": "2026-09-04T00:00:00+00:00",
        "timestamp_cn": "2026-09-04 08:00:00",
    }
    isolated_stats.parent.mkdir(parents=True, exist_ok=True)
    isolated_stats.write_text(json.dumps(ctx) + "\n", encoding="utf-8")

    stats_store.record_event("system", detail="startup", source="test")

    events = stats_store.load_events(50)
    assert any(e.get("event_type") == "context_build" for e in events)
    payload = stats_store.build_dashboard_payload()
    assert payload["summary"]["context_build_count"] >= 1
    assert payload["summary"]["total_baseline_tokens"] >= 5000


def test_dashboard_filter_project(isolated_stats: Path) -> None:
    for pid in ("a", "b"):
        stats_store.record_event(
            "context_build",
            project_id=pid,
            metrics={"usage_tokens": 10, "baseline_tokens": 100},
        )
    all_payload = stats_store.build_dashboard_payload()
    assert all_payload["summary"]["context_build_count"] == 2
    b_only = stats_store.build_dashboard_payload(project_id="b")
    assert b_only["summary"]["context_build_count"] == 1
