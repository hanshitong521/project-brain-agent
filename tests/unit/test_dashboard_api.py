"""Dashboard API smoke tests."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fastapi.testclient import TestClient

from brain_api.app import app


def test_list_tracked_projects_only() -> None:
    client = TestClient(app)
    pr = client.get("/v1/projects")
    assert pr.status_code == 200
    ids = pr.json().get("project_ids") or []
    assert "shejiuPro" in ids
    assert "demo-spring-project" not in ids

    all_pr = client.get("/v1/projects", params={"tracked_only": False})
    all_ids = all_pr.json().get("project_ids") or []
    assert "demo-spring-project" in all_ids


def test_dashboard_excludes_demo_events() -> None:
    client = TestClient(app)
    dash = client.get("/v1/stats/dashboard")
    assert dash.status_code == 200
    body = dash.json()
    assert body.get("stats_scope") == "tracked_repo_only"
    avail = body.get("available_project_ids") or []
    assert "demo-spring-project" not in avail
    for ev in body.get("recent_events") or []:
        assert ev.get("project_id") != "demo-spring-project"


def test_savings_ledger_has_percent() -> None:
    client = TestClient(app)
    r = client.get("/v1/stats/savings", params={"project_id": "shejiuPro", "limit": 5})
    assert r.status_code == 200
    data = r.json()
    if data.get("ledger"):
        row = data["ledger"][0]
        assert "savings_percent" in row
        if row.get("baseline_tokens", 0) > 0:
            assert row["savings_percent"] == round(
                100 * row["saved_tokens"] / row["baseline_tokens"], 1
            )
