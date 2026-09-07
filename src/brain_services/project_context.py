from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

FIXTURES_ROOT = Path(__file__).resolve().parents[2] / "fixtures"
# 验收 fixture，不计入生产看板
DEMO_PROJECT_IDS = frozenset({"demo-spring-project", "demo-python-crawler"})


def _env_repo_root(project_id: str) -> Path | None:
    key = f"BRAIN_REPO_ROOT_{re.sub(r'[^A-Za-z0-9_]', '_', project_id).upper()}"
    raw = os.environ.get(key) or os.environ.get("BRAIN_REPO_ROOT")
    if not raw:
        return None
    p = Path(raw)
    return p if p.is_dir() else None


class ProjectContextService:
    def __init__(self, fixtures_root: Path | None = None) -> None:
        self._root = fixtures_root or FIXTURES_ROOT
        self._cache: dict[str, dict[str, Any]] = {}

    def project_yaml_path(self, project_id: str) -> Path:
        return self._root / project_id / "project.yaml"

    def _load(self, project_id: str) -> dict[str, Any]:
        if project_id in self._cache:
            return self._cache[project_id]
        path = self.project_yaml_path(project_id)
        if not path.exists():
            raise KeyError(f"unknown project_id: {project_id}")
        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
        self._cache[project_id] = data
        return data

    def invalidate(self, project_id: str) -> None:
        self._cache.pop(project_id, None)

    def repo_root(self, project_id: str) -> Path | None:
        env = _env_repo_root(project_id)
        if env:
            return env.resolve()
        proj = self._load(project_id)
        raw = (proj.get("project") or {}).get("repo_root")
        if not raw:
            return None
        p = Path(str(raw))
        return p.resolve() if p.is_dir() else None

    def get(self, project_id: str) -> dict[str, Any]:
        return self._load(project_id)

    def search(self, project_id: str, query: str) -> dict[str, Any]:
        proj = self._load(project_id)
        q = query.lower()
        rules = proj.get("rules") or []
        matched = [r for r in rules if q in str(r).lower()] or rules[:3]
        root = self.repo_root(project_id)
        return {
            "project_id": project_id,
            "name": proj.get("project", {}).get("name"),
            "language": proj.get("project", {}).get("language"),
            "framework": proj.get("project", {}).get("framework"),
            "repo_root": str(root) if root else None,
            "rules": matched,
            "metadata": proj.get("project", {}),
        }

    def rules_text(self, project_id: str) -> str:
        proj = self._load(project_id)
        rules = proj.get("rules") or []
        return "\n".join(f"- {r}" for r in rules)

    def list_rules(self, project_id: str) -> list[str]:
        proj = self._load(project_id)
        return list(proj.get("rules") or [])

    def save_rules(self, project_id: str, rules: list[str]) -> None:
        path = self.project_yaml_path(project_id)
        proj = self._load(project_id)
        proj["rules"] = rules
        with path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(proj, f, allow_unicode=True, sort_keys=False)
        self.invalidate(project_id)

    def list_fixture_project_ids(self) -> list[str]:
        if not self._root.is_dir():
            return []
        ids: list[str] = []
        for path in sorted(self._root.iterdir()):
            if path.is_dir() and (path / "project.yaml").is_file():
                ids.append(path.name)
        return ids

    def is_tracked_project(self, project_id: str | None) -> bool:
        """生产统计：非 demo 且配置了 repo_root（真实仓库文档基线）。"""
        if not project_id or project_id in DEMO_PROJECT_IDS:
            return False
        try:
            return self.repo_root(project_id) is not None
        except KeyError:
            return False

    def list_tracked_project_ids(self) -> list[str]:
        return [pid for pid in self.list_fixture_project_ids() if self.is_tracked_project(pid)]
