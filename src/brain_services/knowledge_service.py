"""Repo doc index for WHY-layer search and full-corpus token baseline."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from brain_core.token_budget import estimate_tokens
from brain_services.project_context import FIXTURES_ROOT, ProjectContextService
from brain_services.rank import excerpt_paragraphs, query_tokens, score_document

_DOC_SUFFIXES = frozenset({".md", ".mdc", ".txt"})
_SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        ".idea",
        "node_modules",
        "target",
        "dist",
        "build",
        ".venv",
        "__pycache__",
        ".contextmind",
        ".requirementmind",
    }
)
_MAX_FILE_BYTES = 120_000
_MAX_CORPUS_FILES = 800


def _fixture_docs_root(project_id: str) -> Path:
    return FIXTURES_ROOT / project_id / "docs"


def _repo_doc_roots(repo: Path) -> list[tuple[Path, str]]:
    """(path, display_prefix) — never pass repo root (would scan whole tree)."""
    roots: list[tuple[Path, str]] = []
    for rel in ("docs",):
        p = repo / rel
        if p.is_dir():
            roots.append((p, rel))
    rules = repo / ".cursor" / "rules"
    if rules.is_dir():
        roots.append((rules, ".cursor/rules"))
    for name in ("AGENTS.md", "README.md"):
        f = repo / name
        if f.is_file():
            roots.append((f, name))
    return roots


_EXCLUDE_PARTS = ("/codegraph/", "\\codegraph\\", "/target/", "\\target\\")


def _iter_doc_files(project_id: str, projects: ProjectContextService) -> list[tuple[str, Path]]:
    """Return (display_rel, abs_path) for knowledge indexing."""
    out: list[tuple[str, Path]] = []
    seen: set[str] = set()

    def add_file(abs_path: Path, display: str) -> None:
        key = str(abs_path.resolve()).lower()
        if key in seen:
            return
        disp = display.replace("\\", "/")
        if any(part in disp for part in _EXCLUDE_PARTS):
            return
        if abs_path.suffix.lower() not in _DOC_SUFFIXES:
            return
        if not abs_path.is_file():
            return
        try:
            if abs_path.stat().st_size > _MAX_FILE_BYTES:
                return
        except OSError:
            return
        seen.add(key)
        out.append((display, abs_path))

    def walk(root: Path, prefix: str) -> None:
        if len(out) >= _MAX_CORPUS_FILES:
            return
        try:
            for entry in sorted(root.iterdir()):
                if entry.name.startswith(".") and entry.name not in (".cursor",):
                    if entry.name != ".cursor":
                        continue
                if entry.is_dir():
                    if entry.name in _SKIP_DIR_NAMES:
                        continue
                    walk(entry, f"{prefix}/{entry.name}" if prefix else entry.name)
                elif entry.is_file():
                    rel = f"{prefix}/{entry.name}" if prefix else entry.name
                    add_file(entry, rel.replace("\\", "/"))
        except OSError:
            return

    fix_docs = _fixture_docs_root(project_id)
    if fix_docs.is_dir():
        walk(fix_docs, f"{project_id}/docs")

    try:
        repo = projects.repo_root(project_id)
    except KeyError:
        repo = None
    if repo and repo.is_dir():
        for root, prefix in _repo_doc_roots(repo):
            if root.is_file():
                add_file(root, prefix)
            else:
                walk(root, prefix)

    return out


class KnowledgeService:
    def __init__(self, projects: ProjectContextService | None = None) -> None:
        self._projects = projects or ProjectContextService()

    def _files(self, project_id: str) -> list[tuple[str, Path]]:
        return _iter_doc_files(project_id, self._projects)

    def full_corpus_tokens(self, project_id: str) -> tuple[int, str]:
        files = self._files(project_id)
        if not files:
            return 0, "none"
        total = 0
        repo = None
        try:
            repo = self._projects.repo_root(project_id)
        except KeyError:
            pass
        source = "repo" if repo else "fixture"
        for _rel, path in files:
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            total += estimate_tokens(text)
        return total, source

    def search(self, project_id: str, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        top_k = min(max(1, top_k), 8)
        tokens = query_tokens(query)
        if not tokens:
            return []
        scored: list[tuple[float, str, Path, str]] = []
        for rel, path in self._files(project_id):
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            s = score_document(rel, text, tokens, query)
            if s <= 0:
                continue
            scored.append((s, rel, path, text))
        scored.sort(key=lambda x: x[0], reverse=True)
        hits: list[dict[str, Any]] = []
        for s, rel, path, text in scored[:top_k]:
            excerpt = excerpt_paragraphs(text, tokens, query, max_chars=1200, max_paras=3)
            hits.append(
                {
                    "source": rel,
                    "abs_path": str(path.resolve()),
                    "score": s,
                    "text": excerpt or text[:1200],
                }
            )
        return hits
