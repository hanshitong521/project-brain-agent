"""Cross-project memory sharing: working dirs that are one project share a pool.

`shejiuPro`, `shejiuTest` and `shejiu-pro1` are byte-identical checkouts of
com.shejiu:shejiu:3.6.5, but each AI agent reports its own directory name as
project_id. Without aliasing, a memory saved from the test checkout is invisible
to the agent in the production one.

The error-injection test is the point of this file: it removes the alias and
asserts the pool SPLITS into two files. A suite that only checked the aliased
case would also pass if resolution were a no-op that happened to return the
canonical name, so the negative case is what makes the positive one mean
something.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from brain_services import project_alias as A
from brain_services.memory_simple import SimpleMemoryStore

CANONICAL = "shejiuPro"
ALIASES = {"shejiuTest": CANONICAL, "shejiu-pro1": CANONICAL}
UNRELATED = "testMind"


@pytest.fixture
def alias_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the module-level default at a throwaway file and neutralise env, so
    a developer's own BRAIN_PROJECT_ALIASES cannot make these tests pass."""
    path = tmp_path / "aliases" / "project_aliases.json"
    monkeypatch.setattr(A, "DATA_FILE", path)
    monkeypatch.setenv(A.ENV_VAR, "")
    monkeypatch.delenv("BRAIN_DEFAULT_PROJECT_ID", raising=False)
    return path


@pytest.fixture
def pool(tmp_path: Path) -> SimpleMemoryStore:
    return SimpleMemoryStore(data_dir=tmp_path / "memories")


# --------------------------------------------------------------------------
# resolution
# --------------------------------------------------------------------------


def test_persisted_aliases_are_read_without_a_file(alias_file: Path) -> None:
    A.save(ALIASES, alias_file)
    assert A.resolve("shejiuTest") == CANONICAL
    assert A.resolve("shejiu-pro1") == CANONICAL
    assert A.resolve(CANONICAL) == CANONICAL


def test_unrelated_project_is_never_merged(alias_file: Path) -> None:
    """testMind is the skill-harness repo, not the shejiu business project.
    Merging it would write harness notes into the production memory pool."""
    A.save(ALIASES, alias_file)
    assert A.resolve(UNRELATED) == UNRELATED


def test_env_still_works_and_overrides_the_file(
    alias_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    A.save({"shejiuTest": CANONICAL}, alias_file)
    monkeypatch.setenv(A.ENV_VAR, "shejiuTest=someOtherPool,extra=canon")
    assert A.resolve("shejiuTest") == "someOtherPool"
    assert A.resolve("extra") == "canon"
    st = A.status(alias_file)
    # The page must be able to say "env disagrees with the file", otherwise it
    # shows a mapping the process is not actually using.
    assert st["env_overrides"] == ["shejiuTest"]
    assert st["stored"] == {"shejiuTest": CANONICAL}


def test_editing_the_file_at_runtime_takes_effect(alias_file: Path) -> None:
    """The old MCP-server implementation cached the map in a module global for
    the life of the process, so a dashboard edit was invisible until restart."""
    A.save({"shejiuTest": CANONICAL}, alias_file)
    assert A.resolve("shejiuTest") == CANONICAL
    A.save({"shejiuTest": "otherPool"}, alias_file)
    assert A.resolve("shejiuTest") == "otherPool"


def test_empty_id_falls_back_to_the_default_project(alias_file: Path) -> None:
    assert A.resolve("") == A.DEFAULT_PROJECT_ID
    assert A.resolve(None) == A.DEFAULT_PROJECT_ID


# --------------------------------------------------------------------------
# chain / cycle handling
# --------------------------------------------------------------------------


def test_chain_is_flattened_so_pools_stay_consistent(alias_file: Path) -> None:
    """a=b and b=c stored as-is would put resolve("a") in pool b while
    resolve("b") went to pool c -- the two agents meant to share still would
    not. Flattening makes every hop end at the same pool."""
    A.save({"a": "b", "b": "c"}, alias_file)
    stored = json.loads(alias_file.read_text(encoding="utf-8"))["aliases"]
    assert stored == {"a": "c", "b": "c"}
    assert A.resolve("a") == A.resolve("b") == "c"


def test_cycle_terminates_instead_of_looping(alias_file: Path) -> None:
    A.save({"a": "b", "b": "a"}, alias_file)
    assert A.load(alias_file) == {}
    assert A.resolve("a") == "a"


def test_self_alias_is_dropped(alias_file: Path) -> None:
    A.save({"shejiuPro": "shejiuPro", "shejiuTest": CANONICAL}, alias_file)
    assert A.load(alias_file) == {"shejiuTest": CANONICAL}


def test_blank_entries_are_dropped(alias_file: Path) -> None:
    A.save({"": CANONICAL, "  ": "x", "shejiuTest": "  "}, alias_file)
    assert A.load(alias_file) == {}


# --------------------------------------------------------------------------
# persistence integrity
# --------------------------------------------------------------------------


def test_corrupt_file_is_reported_not_silently_ignored(
    alias_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A silently-skipped corrupt file would un-share every configured pool and
    the dashboard would just show fewer projects -- no error, no clue."""
    alias_file.parent.mkdir(parents=True, exist_ok=True)
    alias_file.write_text("{ not json", encoding="utf-8")
    monkeypatch.setenv(A.ENV_VAR, "envOnly=canon")
    assert A.load(alias_file) == {"envOnly": "canon"}
    st = A.status(alias_file)
    assert st["error"], "corrupt alias file must surface an error"
    assert st["aliases"] == {"envOnly": "canon"}


def test_save_writes_valid_json_and_leaves_no_temp_file(alias_file: Path) -> None:
    A.save(ALIASES, alias_file)
    assert json.loads(alias_file.read_text(encoding="utf-8"))["aliases"]
    leftovers = [p.name for p in alias_file.parent.iterdir() if p.suffix == ".tmp"]
    assert leftovers == []


def test_groups_maps_canonical_to_its_aliases(alias_file: Path) -> None:
    A.save(ALIASES, alias_file)
    assert A.groups(alias_file) == {CANONICAL: ["shejiu-pro1", "shejiuTest"]}


# --------------------------------------------------------------------------
# the actual requirement: one pool, two working dirs
# --------------------------------------------------------------------------


def _wire_api(monkeypatch: pytest.MonkeyPatch, store: SimpleMemoryStore):
    from fastapi.testclient import TestClient

    from brain_api import app as api

    monkeypatch.setattr(api, "_memory", store)
    return TestClient(api.app)


def _save_as_agent(project_id: str, store: SimpleMemoryStore, text: str) -> str:
    """Write through the same resolution the MCP server uses, so this exercises
    the production path rather than re-implementing it."""
    from brain_mcp.server import _project_id
    from brain_services.context_memory import ContextMemoryService

    svc = ContextMemoryService(memory=store, knowledge=object())
    out = svc.save_decision(_project_id(project_id), text, rationale="r")
    return str(out.get("id") or out)


def test_memory_saved_from_a_test_checkout_is_visible_in_production(
    alias_file: Path, pool: SimpleMemoryStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    A.save(ALIASES, alias_file)
    client = _wire_api(monkeypatch, pool)

    _save_as_agent("shejiuTest", pool, "退款幂等键 orderId+reason")
    _save_as_agent("shejiu-pro1", pool, "红包逻辑调整口径")

    # One pool, not one file per working dir.
    files = sorted(p.name for p in pool._dir.glob("*.jsonl"))
    assert files == ["shejiuPro.jsonl"]

    for name in ("shejiuTest", "shejiu-pro1", CANONICAL):
        body = client.get(f"/v1/memory/{name}").json()
        assert body["project_id"] == CANONICAL
        texts = " ".join(i.get("memory", "") for i in body["items"])
        assert "退款幂等键" in texts and "红包逻辑调整口径" in texts, name

    # Search must cross the alias too.
    hit = client.post(
        "/v1/memory/search", params={"project_id": "shejiuTest", "query": "退款"}
    ).json()
    assert hit["project_id"] == CANONICAL
    assert any("退款" in (r.get("memory") or "") for r in hit["results"])


def test_error_injection_without_the_alias_the_pool_splits(
    alias_file: Path, pool: SimpleMemoryStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """注错必红: delete the mapping and the same operations must produce two
    separate pools, with the production view blind to the test checkout's
    memory. If this passed with the alias present, the test above would be
    asserting nothing."""
    A.save({}, alias_file)
    client = _wire_api(monkeypatch, pool)

    _save_as_agent("shejiuTest", pool, "退款幂等键 orderId+reason")

    files = sorted(p.name for p in pool._dir.glob("*.jsonl"))
    assert files == ["shejiuTest.jsonl"]

    prod = client.get(f"/v1/memory/{CANONICAL}").json()
    assert prod["items"] == [], "production pool must not see the test memory"
    test_view = client.get("/v1/memory/shejiuTest").json()
    assert len(test_view["items"]) == 1


def test_unrelated_project_does_not_leak_into_the_shared_pool(
    alias_file: Path, pool: SimpleMemoryStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    A.save(ALIASES, alias_file)
    client = _wire_api(monkeypatch, pool)

    _save_as_agent(UNRELATED, pool, "skill 安装器的坑")
    _save_as_agent("shejiuTest", pool, "业务口径")

    assert sorted(p.name for p in pool._dir.glob("*.jsonl")) == [
        "shejiuPro.jsonl",
        "testMind.jsonl",
    ]
    prod = client.get(f"/v1/memory/{CANONICAL}").json()
    texts = " ".join(i.get("memory", "") for i in prod["items"])
    assert "skill 安装器" not in texts


# --------------------------------------------------------------------------
# API surface
# --------------------------------------------------------------------------


def test_aliases_endpoint_roundtrip(
    alias_file: Path, monkeypatch: pytest.MonkeyPatch, pool: SimpleMemoryStore
) -> None:
    client = _wire_api(monkeypatch, pool)

    before = client.get("/v1/aliases").json()
    assert before["aliases"] == {} and before["exists"] is False

    put = client.put("/v1/aliases", json={"aliases": ALIASES})
    assert put.status_code == 200
    body = put.json()
    assert body["ok"] is True
    assert body["aliases"] == ALIASES
    assert body["groups"] == {CANONICAL: ["shejiu-pro1", "shejiuTest"]}
    assert alias_file.exists()

    after = client.get("/v1/aliases").json()
    assert after["stored"] == ALIASES


def test_projects_listing_marks_alias_names(
    alias_file: Path, monkeypatch: pytest.MonkeyPatch, pool: SimpleMemoryStore
) -> None:
    """The dropdown must not offer an alias as its own pool: selecting it reads
    the canonical pool, so listing both implies two memories where there is one."""
    A.save(ALIASES, alias_file)
    client = _wire_api(monkeypatch, pool)

    body = client.get("/v1/projects").json()
    assert CANONICAL in body["project_ids"]
    assert body["aliases"] == ALIASES
    assert body["alias_groups"] == {CANONICAL: ["shejiu-pro1", "shejiuTest"]}
    for alias in ALIASES:
        assert alias not in body["canonical_ids"]
    assert CANONICAL in body["canonical_ids"]


def test_optional_stats_filter_still_means_all(
    alias_file: Path, monkeypatch: pytest.MonkeyPatch, pool: SimpleMemoryStore
) -> None:
    """Regression guard: resolve("") returns the default project, so an empty
    filter routed through it would silently narrow 全部 to shejiuPro only."""
    A.save(ALIASES, alias_file)
    client = _wire_api(monkeypatch, pool)

    body = client.get("/v1/stats/dashboard").json()
    assert body.get("filter_project_id") in (None, "")
    ret = client.get("/v1/stats/retrieval").json()
    assert ret["filter_project_id"] in (None, "")

    filtered = client.get("/v1/stats/retrieval", params={"project_id": "shejiuTest"}).json()
    assert filtered["filter_project_id"] == CANONICAL
