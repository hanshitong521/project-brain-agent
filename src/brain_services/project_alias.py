"""One memory pool for working directories that are really the same project.

An agent launched in the test checkout reports project_id="shejiuTest" while one
in the production checkout reports "shejiuPro"; both must read and write the same
pool or each half of the work is invisible to the other.

Aliases are persisted rather than env-only so every MCP client sees the same
mapping regardless of how it was launched, and so the dashboard can change it at
runtime. BRAIN_PROJECT_ALIASES still works and wins on conflict, because it is
the operator's explicit per-process override.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

DATA_FILE = Path(__file__).resolve().parents[2] / ".data" / "project_aliases.json"
ENV_VAR = "BRAIN_PROJECT_ALIASES"
DEFAULT_PROJECT_ID = "shejiuPro"


def from_env() -> dict[str, str]:
    out: dict[str, str] = {}
    for part in os.environ.get(ENV_VAR, "").split(","):
        src, _, dst = part.partition("=")
        if src.strip() and dst.strip():
            out[src.strip()] = dst.strip()
    return out


def _read_file(data_file: Path) -> tuple[dict[str, str], str | None]:
    try:
        raw = json.loads(data_file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}, None
    except (OSError, ValueError) as exc:
        # A corrupt alias file must not take down a running MCP server, but it
        # must not be silently ignored either -- that would quietly un-share
        # every pool the user configured. Callers surface this via status().
        return {}, "无法读取 %s：%s" % (data_file, exc)
    entries = raw.get("aliases") if isinstance(raw, dict) else None
    if not isinstance(entries, dict):
        return {}, "%s 缺少 aliases 对象" % data_file
    return {
        str(k).strip(): str(v).strip()
        for k, v in entries.items()
        if str(k).strip() and str(v).strip()
    }, None


def flatten(aliases: dict[str, str]) -> dict[str, str]:
    """Collapse chains so one-hop resolution cannot yield inconsistent pools.

    With a=b and b=c stored as-is, resolve("a") lands in pool b while
    resolve("b") lands in pool c -- the two agents that are supposed to share
    still would not. Resolving each target to its own end stops at the first
    non-alias, and a cycle degrades to the entry itself instead of looping.
    """
    out: dict[str, str] = {}
    for src, dst in aliases.items():
        seen = {src}
        while dst in aliases and dst not in seen:
            seen.add(dst)
            dst = aliases[dst]
        if dst != src:
            out[src] = dst
    return out


def load(data_file: Path | str | None = None) -> dict[str, str]:
    """Stored aliases overridden by env. Read on every call, never cached: the
    dashboard edits this file while MCP servers are already running, and a
    module-level cache would keep them on the stale mapping forever."""
    path = Path(data_file) if data_file is not None else DATA_FILE
    stored, _ = _read_file(path)
    stored.update(from_env())
    return flatten(stored)


def resolve(project_id: str | None, data_file: Path | str | None = None) -> str:
    """Map an agent-reported project id to the pool it actually reads/writes."""
    mapping = load(data_file)
    pid = (project_id or "").strip()
    if not pid:
        pid = os.environ.get("BRAIN_DEFAULT_PROJECT_ID", "").strip() or DEFAULT_PROJECT_ID
    return mapping.get(pid, pid)


def save(aliases: dict[str, str], data_file: Path | str | None = None) -> dict[str, str]:
    """Persist aliases, returning what was actually stored (chains flattened).

    Written via a temp file in the same directory plus os.replace: this file
    lives in the .data tree that a truncation incident left full of 0-byte
    files, and a half-written aliases file is the same failure mode.
    """
    path = Path(data_file) if data_file is not None else DATA_FILE
    cleaned = flatten({
        str(k).strip(): str(v).strip()
        for k, v in (aliases or {}).items()
        if str(k).strip() and str(v).strip() and str(k).strip() != str(v).strip()
    })
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump({"aliases": cleaned}, f, ensure_ascii=False, indent=2, sort_keys=True)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return cleaned


def _group(mapping: dict[str, str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for src, dst in mapping.items():
        out.setdefault(dst, []).append(src)
    return {k: sorted(v) for k, v in out.items()}


def groups(data_file: Path | str | None = None) -> dict[str, list[str]]:
    """canonical project id -> alias names pointing at it, for the dashboard."""
    return _group(load(data_file))


def status(data_file: Path | str | None = None) -> dict[str, Any]:
    """Everything the dashboard needs to show, including a loud read error."""
    path = Path(data_file) if data_file is not None else DATA_FILE
    stored, error = _read_file(path)
    env = from_env()
    merged = flatten({**stored, **env})
    conflicts = sorted(k for k in env if k in stored and stored[k] != env[k])
    return {
        "aliases": merged,
        "groups": _group(merged),
        "stored": stored,
        "env": env,
        "env_var": ENV_VAR,
        "data_file": str(path),
        "exists": path.exists(),
        "error": error,
        # Entries where env disagrees with the file: env wins, so the dashboard
        # must say so rather than show a mapping the process is not using.
        "env_overrides": conflicts,
        "default_project_id": os.environ.get("BRAIN_DEFAULT_PROJECT_ID", "").strip()
                              or DEFAULT_PROJECT_ID,
    }
