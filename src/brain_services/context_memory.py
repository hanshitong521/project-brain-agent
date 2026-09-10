from __future__ import annotations

from pathlib import Path
from typing import Any

from brain_services.memory_lifecycle import LIFECYCLE_CANDIDATE, LIFECYCLE_VERIFIED, is_searchable
from brain_services.memory_simple import get_memory_backend
from brain_services.project_context import ProjectContextService
from brain_services.rank import (
    extract_related_paths,
    file_path_needles,
    score_change_memory,
    slim_knowledge,
    slim_memory,
)

MEMORY_KINDS = frozenset({"experience", "decision", "bug"})


def _basename_key(file: str) -> str:
    name = Path(file.replace("\\", "/")).name
    return name.lower()


def format_decision(decision: str, rationale: str = "", related: list[str] | None = None) -> str:
    lines = ["[DECISION]", decision.strip()]
    if rationale.strip():
        lines.append(f"Rationale: {rationale.strip()}")
    if related:
        lines.append("Related: " + ", ".join(related))
    return "\n".join(lines)


def format_bug(
    title: str,
    problem: str,
    cause: str = "",
    fix: str = "",
    related: list[str] | None = None,
) -> str:
    lines = [f"[BUG] {title.strip()}", f"Problem: {problem.strip()}"]
    if cause.strip():
        lines.append(f"Cause: {cause.strip()}")
    if fix.strip():
        lines.append(f"Fix: {fix.strip()}")
    if related:
        lines.append("Related: " + ", ".join(related))
    return "\n".join(lines)


def _merge_related(explicit: list[str] | None, *bodies: str) -> list[str]:
    """Union explicit related_files with paths scraped from text bodies."""
    out: list[str] = []
    seen: set[str] = set()
    for p in list(explicit or []) + [x for b in bodies for x in extract_related_paths(b)]:
        key = p.replace("\\", "/").lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(p.replace("\\", "/"))
        if len(out) >= 16:
            break
    return out


class ContextMemoryService:
    """OpenViking-layer semantics on top of project-brain JSONL memory."""

    def __init__(
        self,
        memory: Any | None = None,
        projects: ProjectContextService | None = None,
        knowledge: Any | None = None,
    ) -> None:
        self._memory = memory or get_memory_backend()
        self._projects = projects or ProjectContextService()
        self._knowledge = knowledge

    def _knowledge_svc(self) -> Any:
        know = self._knowledge
        if know is None:
            from brain_services.knowledge_service import KnowledgeService

            know = KnowledgeService(projects=self._projects)
            self._knowledge = know
        return know

    def save_decision(
        self,
        project_id: str,
        decision: str,
        rationale: str = "",
        related_files: list[str] | None = None,
        importance: str = "high",
    ) -> dict[str, Any]:
        related = _merge_related(related_files, decision, rationale)
        body = format_decision(decision, rationale, related)
        meta = {
            "kind": "decision",
            "lifecycle": LIFECYCLE_VERIFIED,
            "source": "agent",
            "decision": decision.strip(),
            "rationale": rationale.strip(),
            "related_files": related,
        }
        return self._memory.add(project_id, body, importance=importance, metadata=meta)

    def save_bug(
        self,
        project_id: str,
        title: str,
        problem: str,
        cause: str = "",
        fix: str = "",
        related_files: list[str] | None = None,
        importance: str = "high",
    ) -> dict[str, Any]:
        related = _merge_related(related_files, title, problem, cause, fix)
        body = format_bug(title, problem, cause, fix, related)
        meta = {
            "kind": "bug",
            "lifecycle": LIFECYCLE_CANDIDATE,
            "source": "agent",
            "title": title.strip(),
            "related_files": related,
        }
        return self._memory.add(project_id, body, importance=importance, metadata=meta)

    def search_project_context(
        self,
        project_id: str,
        query: str,
        limit: int = 5,
        kinds: list[str] | None = None,
    ) -> dict[str, Any]:
        limit = min(max(1, limit), 8)
        mem_hits = self._memory.search(project_id, query, limit=limit * 2)
        if kinds:
            allowed = {k for k in kinds if k in MEMORY_KINDS}
            if allowed:
                mem_hits = [
                    h
                    for h in mem_hits
                    if (h.get("metadata") or {}).get("kind", "experience") in allowed
                ]
        mem_hits = mem_hits[:limit]
        try:
            proj = self._projects.search(project_id, query)
        except KeyError:
            proj = {"project_id": project_id, "error": "unknown project_id"}
        project_slim = {
            "name": proj.get("name"),
            "language": proj.get("language"),
            "rules": (proj.get("rules") or [])[:4],
        }
        if proj.get("error"):
            project_slim["error"] = proj["error"]
        docs: list[dict[str, Any]] = []
        try:
            docs = [slim_knowledge(h) for h in self._knowledge_svc().search(project_id, query, top_k=2)]
        except Exception:
            docs = []
        result = {
            "layer": "openviking",
            "project_id": project_id,
            "query": query,
            "project": project_slim,
            "memories": [slim_memory(h) for h in mem_hits],
            "docs": docs,
            "count": len(mem_hits),
            "doc_count": len(docs),
        }
        self._record_retrieval(
            project_id,
            op="search_project_context",
            detail=query[:200],
            memory_hits=len(mem_hits),
            knowledge_hits=len(docs),
            titles=[slim_memory(h).get("title") for h in mem_hits[:5]],
            payload=result,
        )
        return result

    def get_change_context(self, project_id: str, file: str, limit: int = 5) -> dict[str, Any]:
        limit = min(max(1, limit), 8)
        needles = file_path_needles(file)
        basename = _basename_key(file)
        stem = Path(basename).stem
        list_fn = getattr(self._memory, "list_all", None)
        raw_items = list_fn(project_id, limit=500) if callable(list_fn) else []
        items = [it for it in raw_items if is_searchable(it)]
        scored: list[tuple[float, dict[str, Any]]] = []
        for item in items:
            s = score_change_memory(item, needles, file)
            if s > 0:
                scored.append((s, item))
        scored.sort(key=lambda x: (-x[0], x[1].get("last_seen_cn") or ""))
        hits = [it for _, it in scored[:limit]]

        # Knowledge: path-aware queries (basename → stem → camel tokens)
        docs_raw: list[dict[str, Any]] = []
        know = self._knowledge_svc()
        queries: list[str] = []
        for q in (
            " ".join(needles[:8]),
            f"{stem} {basename}",
            stem,
            " ".join(needles[2:6]),
        ):
            q = (q or "").strip()
            if q and q not in queries:
                queries.append(q)
        seen_src: set[str] = set()
        for q in queries:
            try:
                for h in know.search(project_id, q, top_k=2):
                    key = str(h.get("abs_path") or h.get("source") or "")
                    if key in seen_src:
                        continue
                    seen_src.add(key)
                    docs_raw.append(h)
            except Exception:
                continue
            if len(docs_raw) >= 2:
                break
        docs_raw = docs_raw[:2]
        docs = [slim_knowledge(h) for h in docs_raw]

        risk = "low"
        if any((h.get("metadata") or {}).get("kind") == "bug" for h in hits):
            risk = "high"
        elif any((h.get("metadata") or {}).get("kind") == "decision" for h in hits):
            risk = "medium"
        elif docs:
            risk = "medium"
        rules_snippet = ""
        try:
            rules_snippet = self._projects.rules_text(project_id)[:200]
        except KeyError:
            pass
        repo = None
        try:
            repo = self._projects.repo_root(project_id)
        except KeyError:
            pass
        result = {
            "layer": "openviking",
            "project_id": project_id,
            "file": file,
            "change_risk": risk,
            "repo_root": str(repo) if repo else None,
            "memories": [slim_memory(h, score=s) for s, h in scored[:limit]],
            "docs": docs,
            "doc_count": len(docs),
            "path_needles": needles[:12],
            "project_rules_excerpt": rules_snippet,
            "note": "Code location: use ContextMind context_orient / context_fetch (not Brain).",
        }
        self._record_retrieval(
            project_id,
            op="get_change_context",
            detail=file[:200],
            memory_hits=len(hits),
            knowledge_hits=len(docs),
            titles=[slim_memory(h).get("title") for h in hits[:5]],
            extra={
                "change_risk": risk,
                "path_needles": needles[:8],
                "knowledge_sources": [
                    {
                        "path": h.get("source"),
                        "abs_path": h.get("abs_path"),
                        "excerpt_len": len(h.get("text") or ""),
                    }
                    for h in docs_raw
                ],
            },
            payload=result,
        )
        return result

    def _record_retrieval(
        self,
        project_id: str,
        *,
        op: str,
        detail: str,
        memory_hits: int,
        knowledge_hits: int,
        titles: list[Any] | None = None,
        extra: dict[str, Any] | None = None,
        payload: Any | None = None,
    ) -> None:
        """Phoenix RETRIEVER-style span: named op + hit counts (Cursor MCP path)."""
        try:
            from brain_services.stats_store import record_event
            from brain_services.stats_telemetry import log_stats_error, retrieval_token_metrics

            metrics: dict[str, Any] = {
                "op": op,
                "span_kind": "RETRIEVER",
                "memory_hits": memory_hits,
                "knowledge_hits": knowledge_hits,
                "memory_hit": memory_hits > 0,
                "knowledge_hit": knowledge_hits > 0,
                "any_hit": memory_hits > 0 or knowledge_hits > 0,
                "titles": [t for t in (titles or []) if t][:5],
            }
            if extra:
                metrics.update(extra)
            if payload is not None:
                metrics.update(retrieval_token_metrics(project_id, payload))
            record_event(
                "context_retrieval",
                project_id=project_id,
                detail=f"{op}: {detail}"[:240],
                metrics=metrics,
                source="mcp",
            )
        except Exception as exc:
            from brain_services.stats_telemetry import log_stats_error

            log_stats_error("context_retrieval", exc, project_id=project_id, op=op)
