"""Render project lessons as Markdown for Dashboard / export."""

from __future__ import annotations

from typing import Any

from brain_services.memory_auto_review import compute_auto_verdict
from brain_services.memory_lifecycle import LIFECYCLE_CANDIDATE, LIFECYCLE_VERIFIED, effective_lifecycle


def _title_of(item: dict[str, Any]) -> str:
    meta = item.get("metadata") or {}
    t = (item.get("title") or meta.get("title") or "").strip()
    if t:
        return t
    body = str(item.get("memory") or item.get("content") or "")
    return body.split("\n")[0][:80] or str(item.get("id") or "lesson")


def render_lessons_markdown(
    project_id: str,
    items: list[dict[str, Any]],
    *,
    include_candidates: bool = True,
) -> str:
    verified = [it for it in items if effective_lifecycle(it) == LIFECYCLE_VERIFIED]
    pending = [it for it in items if effective_lifecycle(it) == LIFECYCLE_CANDIDATE] if include_candidates else []

    lines = [
        f"# 项目教训 · {project_id}",
        "",
        "> 由 Project Brain 生成；编辑请走 Dashboard 或 `PATCH /v1/memory/...`。",
        "",
        f"- **已生效（verified）**：{len(verified)} 条",
        f"- **待审（candidate）**：{len(pending)} 条",
        "",
    ]

    if verified:
        lines.append("## 已生效教训")
        lines.append("")
        for it in verified:
            lines.extend(_lesson_block(it, promoted=True))
    if pending:
        lines.append("## 待审 / 建议")
        lines.append("")
        for it in pending:
            av = it.get("auto_verdict") or compute_auto_verdict(it)
            lines.extend(_lesson_block(it, promoted=False, auto_verdict=av))

    if not verified and not pending:
        lines.append("_暂无教训记录。任务结束后用 `record_task_outcome` / `save_bug_memory`，在 Dashboard 晋升或编辑。_")
        lines.append("")

    return "\n".join(lines)


def _lesson_block(
    item: dict[str, Any],
    *,
    promoted: bool,
    auto_verdict: dict[str, Any] | None = None,
) -> list[str]:
    meta = item.get("metadata") or {}
    kind = meta.get("kind") or item.get("kind") or "experience"
    mid = item.get("id") or ""
    title = _title_of(item)
    body = str(item.get("memory") or item.get("content") or "").strip()
    related = meta.get("related_files") or []
    applies = item.get("applies_when") or meta.get("applies_when") or []
    avoid = item.get("do_not_use_when") or meta.get("do_not_use_when") or []

    lines = [f"### {title}", ""]
    lines.append(f"- **id**: `{mid}`")
    lines.append(f"- **kind**: {kind}")
    lines.append(f"- **lifecycle**: {effective_lifecycle(item)}")
    if item.get("grandfathered"):
        lines.append("- **legacy**: 存量未走记忆门，建议在 Dashboard 复核")
    if auto_verdict and not promoted:
        v = auto_verdict.get("verdict", "review")
        rs = auto_verdict.get("reasons") or []
        lines.append(f"- **系统建议**: `{v}`" + (f" — {'；'.join(rs)}" if rs else ""))
    if related:
        lines.append(f"- **相关文件**: {', '.join(related[:8])}")
    if applies:
        lines.append(f"- **适用场景**: {', '.join(applies[:6])}")
    if avoid:
        lines.append(f"- **勿用于**: {', '.join(avoid[:6])}")
    lines.append("")
    lines.append(body)
    lines.append("")
    return lines
