"""Stats persistence diagnostics + MCP retrieval token estimates."""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

from brain_services.token_budget import estimate_tokens

_LOG_DIR = Path(__file__).resolve().parents[2] / ".data" / "stats"
_LOG_FILE = _LOG_DIR / "brain_stats.log"

_logger: logging.Logger | None = None


def stats_logger() -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    log = logging.getLogger("project_brain.stats")
    log.setLevel(logging.DEBUG)
    if not log.handlers:
        fh = logging.FileHandler(_LOG_FILE, encoding="utf-8")
        fh.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        )
        log.addHandler(fh)
    _logger = log
    return log


def log_stats_error(where: str, exc: BaseException, **ctx: Any) -> None:
    parts = [f"{where}: {type(exc).__name__}: {exc}"]
    if ctx:
        parts.append(json.dumps(ctx, ensure_ascii=False)[:500])
    stats_logger().warning(" ".join(parts))


@lru_cache(maxsize=32)
def _cached_baseline(project_id: str) -> tuple[int, str]:
    from brain_services.knowledge_service import KnowledgeService
    from brain_services.project_context import ProjectContextService

    return KnowledgeService(projects=ProjectContextService()).full_corpus_tokens(project_id)


def retrieval_token_metrics(project_id: str, payload: Any) -> dict[str, Any]:
    """Estimate savings vs loading indexed project docs (same baseline as context_build)."""
    try:
        text = json.dumps(payload, ensure_ascii=False) if not isinstance(payload, str) else payload
    except (TypeError, ValueError):
        text = str(payload)
    usage = estimate_tokens(text)
    baseline, baseline_source = _cached_baseline(project_id)
    if baseline <= 0:
        return {
            "usage_tokens": usage,
            "baseline_tokens": 0,
            "saved_tokens": 0,
            "baseline_source": baseline_source,
            "savings_mode": "none",
        }
    saved = max(0, baseline - usage)
    return {
        "usage_tokens": usage,
        "baseline_tokens": baseline,
        "saved_tokens": saved,
        "baseline_source": baseline_source,
        "savings_mode": "retrieval_est",
    }


def enrich_retrieval_metrics(project_id: str | None, metrics: dict[str, Any]) -> dict[str, Any]:
    """Backfill token fields for older context_retrieval rows."""
    if int(metrics.get("baseline_tokens") or 0) > 0:
        return metrics
    if not project_id:
        return metrics
    mem_h = int(metrics.get("memory_hits") or 0)
    know_h = int(metrics.get("knowledge_hits") or 0)
    if mem_h <= 0 and know_h <= 0 and not metrics.get("any_hit"):
        return metrics
    baseline, baseline_source = _cached_baseline(project_id)
    if baseline <= 0:
        return metrics
    # Historical rows lack payload size — conservative MCP response estimate
    usage = int(metrics.get("usage_tokens") or 0)
    if usage <= 0:
        usage = 400 + 120 * mem_h + 200 * know_h
    saved = max(0, baseline - usage)
    out = dict(metrics)
    out.update(
        {
            "usage_tokens": usage,
            "baseline_tokens": baseline,
            "saved_tokens": saved,
            "baseline_source": baseline_source,
            "savings_mode": out.get("savings_mode") or "retrieval_backfill",
        }
    )
    return out
