"""RM decision id extraction from memory rows."""

from __future__ import annotations

import re
from typing import Any

_DEC_IN_BODY = re.compile(r"\[(DEC-[^\]]+)\]", re.I)


def decision_id_from_item(item: dict[str, Any]) -> str | None:
    meta = item.get("metadata") or {}
    raw = meta.get("rm_decision_id")
    if raw:
        return str(raw).strip()
    body = str(item.get("memory") or item.get("content") or "")
    m = _DEC_IN_BODY.search(body)
    return m.group(1) if m else None
