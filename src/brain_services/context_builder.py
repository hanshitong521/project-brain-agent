from __future__ import annotations

from typing import Any

from brain_core.token_budget import DEFAULT_BUDGET
from brain_services.knowledge_service import KnowledgeService
from brain_services.memory_simple import get_memory_backend
from brain_services.project_context import ProjectContextService

L0_SYSTEM = """You are assisted by Project Brain. Use project rules, memories, and docs only.
Do not load the full repository into context."""


class ContextBuilder:
    def __init__(self) -> None:
        self._projects = ProjectContextService()
        self._memory = get_memory_backend()
        self._knowledge = KnowledgeService(projects=self._projects)
        self._budget = DEFAULT_BUDGET

    def build_task_context(
        self,
        project_id: str,
        task: str,
        budget_tokens: int = 5000,
    ) -> dict[str, Any]:
        budget_tokens = min(budget_tokens, self._budget.absolute_max)
        l0, u0 = self._budget.truncate(L0_SYSTEM, self._budget.l0_max)
        rules = self._projects.rules_text(project_id)
        l1, u1 = self._budget.truncate(rules, self._budget.l1_max)
        mem_hits = self._memory.search(project_id, task, limit=self._budget.memory_max_items)
        mem_text = "\n".join(
            f"- {(m.get('memory') or m.get('content') or m)!s}" for m in mem_hits
        ) or "(no memory hits)"
        know_hits = self._knowledge.search(project_id, task, top_k=2)
        know_text = "\n".join(f"[{h['source']}]\n{h['text']}" for h in know_hits) or "(no docs)"
        l2_raw = f"## Task\n{task}\n\n## Memories\n{mem_text}\n\n## Knowledge\n{know_text}"
        remaining = max(500, budget_tokens - u0 - u1)
        l2, u2 = self._budget.truncate(l2_raw, min(remaining, self._budget.l2_max))
        combined = f"# L0\n{l0}\n\n# L1 Project rules\n{l1}\n\n# L2 Task context\n{l2}"
        usage = u0 + u1 + u2
        baseline, baseline_source = self._knowledge.full_corpus_tokens(project_id)
        knowledge_sources = [
            {
                "path": h.get("source"),
                "abs_path": h.get("abs_path"),
                "excerpt_len": len(h.get("text") or ""),
            }
            for h in know_hits
        ]
        memory_snippets = [
            {
                "id": m.get("id"),
                "preview": str(m.get("memory") or m.get("content") or "")[:120],
            }
            for m in mem_hits
        ]
        result = {
            "project_id": project_id,
            "context": combined,
            "usage_tokens": usage,
            "budget_tokens": budget_tokens,
            "within_budget": usage <= budget_tokens,
            "layers": {"l0": u0, "l1": u1, "l2": u2},
            "baseline_tokens": baseline,
            "baseline_source": baseline_source,
            "saved_tokens": max(0, baseline - usage) if baseline else 0,
            "memory_hits": len(mem_hits),
            "knowledge_hits": len(know_hits),
        }
        try:
            from brain_services.stats_store import record_event

            record_event(
                "context_build",
                project_id=project_id,
                detail=task[:200],
                metrics={
                    "usage_tokens": usage,
                    "budget_tokens": budget_tokens,
                    "baseline_tokens": baseline,
                    "baseline_source": baseline_source,
                    "saved_tokens": result["saved_tokens"],
                    "within_budget": result["within_budget"],
                    "layers": result["layers"],
                    "memory_hits": len(mem_hits),
                    "knowledge_hits": len(know_hits),
                    "knowledge_sources": knowledge_sources,
                    "memory_snippets": memory_snippets,
                },
                source="context_builder",
            )
        except Exception as exc:
            from brain_services.stats_telemetry import log_stats_error

            log_stats_error("context_build", exc, project_id=project_id)
        return result
