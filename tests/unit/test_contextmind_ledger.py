"""Tests for ContextMind cache ledger snapshot loading."""

from pathlib import Path

from brain_services.contextmind_ledger import load_contextmind_cache_ledger, resolve_cache_ledger_path


def test_resolve_shejiu_fixture_path():
    path = resolve_cache_ledger_path("shejiuPro")
    assert path is not None
    assert path.name == "cache-ledger.json"


def test_load_snapshot_if_present():
    path = resolve_cache_ledger_path("shejiuPro")
    if not path or not Path(path).is_file():
        return
    doc = load_contextmind_cache_ledger("shejiuPro")
    assert doc is not None
    assert doc.get("schema") == "contextmind-cache-ledger/v1"
