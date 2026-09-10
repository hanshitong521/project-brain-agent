from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

TZ_CN = timezone(timedelta(hours=8))

_EN_WORD = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{2,}")
_CJK_RUN = re.compile(r"[\u4e00-\u9fff]{2,}")

_STOP = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "this",
        "that",
        "from",
        "are",
        "was",
        "you",
        "your",
        "our",
        "into",
        "about",
        "than",
        "then",
        "them",
        "they",
        "have",
        "has",
        "had",
        "not",
        "but",
        "can",
        "how",
        "what",
        "when",
        "where",
        "which",
        "will",
        "would",
        "could",
        "should",
        "just",
        "also",
        "more",
        "some",
        "any",
        "all",
        "via",
        "per",
        "use",
        "using",
        "used",
        "find",
        "look",
        "see",
        "help",
        "still",
        "really",
        "please",
        "这个",
        "怎么",
        "什么",
        "我们",
        "可以",
        "如果",
        "一个",
        "没有",
        "以及",
        "或者",
        "还有",
        "不是",
        "就是",
        "问题",
        "一下",
        "帮忙",
    }
)

_HARNESS = ("token", "contextmind", "headroom", "harness", "mcp", "orient", "proxy", "fetch")
_PRODUCT = (
    "红包",
    "redpacket",
    "anchor",
    "coupon",
    "百应",
    "buyin",
    "refund",
    "退款",
    "战绩",
    "liststats",
    "weekly",
    "weekprofit",
)

_ALIASES = (
    (("退款", "退"), ("refund",)),
    (("设计",), ("design",)),
    (("幂等",), ("idempotent", "orderId")),
    (("红包",), ("redpacket", "red-packet")),
    (("列表",), ("list", "split")),
    (("当前",), ("current",)),
    (("历史",), ("history",)),
    (("战绩", "周报"), ("listStats", "weekProfit", "WeeklyStats", "finc")),
    (("成交",), ("deal", "today_deal")),
)


def query_tokens(query: str) -> list[str]:
    out: list[str] = []
    for w in _EN_WORD.findall(query or ""):
        if w.lower() not in _STOP:
            out.append(w)
    for run in _CJK_RUN.findall(query or ""):
        if run not in _STOP:
            out.append(run)
        for n in (2, 3, 4):
            if len(run) < n:
                continue
            for i in range(0, len(run) - n + 1):
                gram = run[i : i + n]
                if gram not in _STOP:
                    out.append(gram)
    q = query or ""
    for keys, extras in _ALIASES:
        if any(k in q for k in keys):
            out.extend(extras)
    seen: set[str] = set()
    uniq: list[str] = []
    for t in out:
        k = t.lower()
        if k in seen:
            continue
        seen.add(k)
        uniq.append(t)
    return uniq


def token_hit(token: str, text_lower: str, rel_lower: str) -> bool:
    if not token:
        return False
    if any("\u4e00" <= c <= "\u9fff" for c in token):
        return token in text_lower or token.lower() in rel_lower
    pat = re.compile(rf"(?i)\b{re.escape(token)}\b")
    return bool(pat.search(text_lower) or token.lower() in rel_lower)


def score_document(rel: str, text: str, tokens: list[str], query: str) -> float:
    rel_l = rel.replace("\\", "/").lower()
    text_l = text.lower()
    q = (query or "").lower()
    score = 0.0
    hits = 0
    for t in tokens:
        if token_hit(t, text_l, rel_l):
            hits += 1
            score += 3.0
            if t.lower() in rel_l:
                score += 8.0
    if hits == 0:
        return 0.0
    harness = any(k in q for k in _HARNESS)
    product = any(k in q for k in _PRODUCT)
    if harness and any(p in rel_l for p in ("/agents/", ".cursor/rules", "headroom", "token", "contextmind")):
        score += 15.0
    compact = rel_l.replace("-", "").replace("_", "")
    if harness and "anchorredpacket" in compact:
        score -= 25.0
    if product and "anchorredpacket" in compact:
        score += 12.0
    if product and "refund" in rel_l:
        score += 12.0
    return score


def _parse_cn(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.strptime(str(ts)[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=TZ_CN)
    except ValueError:
        return None


_CAMEL = re.compile(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+")
_PATH_REF = re.compile(
    r"(?:[A-Za-z]:)?(?:[/\\][\w.-]+){1,12}\.(?:java|xml|md|yml|yaml|ts|tsx|js|mjs|py|sql|mdc)\b"
    r"|[\w./\\-]{3,}\.(?:java|xml|md|yml|yaml|ts|tsx|js|mjs|py|sql|mdc)\b",
    re.I,
)


def split_camel(name: str) -> list[str]:
    """VProductSelectorWeeklyStatsMapper → product, selector, weekly, stats, mapper…"""
    parts = _CAMEL.findall(name or "")
    out: list[str] = []
    for p in parts:
        if len(p) < 3:
            continue
        if p.isupper() and len(p) <= 4:
            continue
        out.append(p.lower())
    return out


def file_path_needles(file: str) -> list[str]:
    """High-signal path tokens for get_change_context matching."""
    raw = (file or "").replace("\\", "/").strip()
    if not raw:
        return []
    path = Path(raw)
    basename = path.name
    stem = path.stem
    parents = [p.lower() for p in path.parts[:-1] if p not in (".", "..", "/", "")]
    # Drop shallow noise dirs
    skip = {
        "src",
        "main",
        "java",
        "resources",
        "test",
        "modules",
        "com",
        "shejiu",
        "mapper",
        "impl",
        "controller",
        "service",
        "domain",
        "util",
    }
    parent_signal = [p for p in parents if p not in skip and len(p) >= 3]
    needles: list[str] = []
    for n in (
        raw.lower(),
        basename.lower(),
        stem.lower(),
        *split_camel(stem),
        *parent_signal[-3:],
    ):
        if n and n not in needles and len(n) >= 3:
            needles.append(n)
    return needles


def extract_related_paths(text: str, *, limit: int = 12) -> list[str]:
    """Pull file-like refs from memory body for related_files enrichment."""
    found: list[str] = []
    seen: set[str] = set()
    for m in _PATH_REF.finditer(text or ""):
        p = m.group(0).replace("\\", "/")
        key = p.lower()
        if key in seen:
            continue
        seen.add(key)
        found.append(p)
        if len(found) >= limit:
            break
    return found


def score_change_memory(item: dict[str, Any], needles: list[str], file: str) -> float:
    """Path-centric score for get_change_context (stricter than free-text search)."""
    if not needles:
        return 0.0
    text = str(item.get("memory") or item.get("content") or "")
    meta = item.get("metadata") or {}
    related = [str(x).replace("\\", "/").lower() for x in (meta.get("related_files") or [])]
    text_l = text.lower().replace("\\", "/")
    basename = Path((file or "").replace("\\", "/")).name.lower()
    stem = Path(basename).stem.lower() if basename else ""
    score = 0.0
    for n in needles:
        nl = n.lower()
        if not nl:
            continue
        if any(nl == r or nl in r or Path(r).name == nl or Path(r).stem == nl for r in related):
            score += 14.0 if nl in (basename, stem) else 7.0
        if nl in text_l:
            score += 5.0 if nl in (basename, stem) else 2.0
    if score <= 0:
        return 0.0
    kind = str(meta.get("kind") or "experience")
    if kind == "bug":
        score += 5.0
    elif kind == "decision":
        score += 4.0
    else:
        score += 1.0
    seen = _parse_cn(item.get("last_seen_cn") or item.get("created_cn"))
    if seen:
        age_h = max(0.0, (datetime.now(TZ_CN) - seen).total_seconds() / 3600.0)
        score += max(0.0, 2.5 - min(age_h, 72.0) / 48.0)
    score += min(1.5, 0.15 * int(item.get("repeat_count") or 1))
    return score


def score_memory(item: dict[str, Any], tokens: list[str], query: str) -> float:
    text = str(item.get("memory") or item.get("content") or "")
    meta = item.get("metadata") or {}
    related = [str(x) for x in (meta.get("related_files") or [])]
    rel_blob = " ".join(related)
    text_l = text.lower()
    rel_l = rel_blob.replace("\\", "/").lower()
    score = score_document("memory/" + rel_l, text, tokens, query)
    if score <= 0 and tokens:
        return 0.0
    kind = str(meta.get("kind") or "experience")
    if kind == "bug":
        score += 5.0
    elif kind == "decision":
        score += 4.0
    else:
        score += 1.0
    q = (query or "").lower()
    for r in related:
        name = Path(str(r).replace("\\", "/")).name.lower()
        stem = Path(name).stem
        if name and (name in q or stem in q):
            score += 8.0
    # Soft boost when query is a file path and related_files / body mention it
    if "/" in q or "\\" in (query or "") or q.endswith((".java", ".xml", ".md")):
        path_score = score_change_memory(item, file_path_needles(query), query)
        score = max(score, path_score)
    seen = _parse_cn(item.get("last_seen_cn") or item.get("created_cn"))
    if seen:
        age_h = max(0.0, (datetime.now(TZ_CN) - seen).total_seconds() / 3600.0)
        score += max(0.0, 2.5 - min(age_h, 72.0) / 48.0)
    score += min(1.5, 0.15 * int(item.get("repeat_count") or 1))
    return score


def slim_memory(item: dict[str, Any], *, score: float | None = None, preview: int = 160) -> dict[str, Any]:
    from brain_services.memory_title import derive_memory_title

    meta = item.get("metadata") or {}
    body = str(item.get("memory") or item.get("content") or "")
    title = (item.get("title") or meta.get("title") or "").strip() or derive_memory_title(body, meta)
    out: dict[str, Any] = {
        "id": item.get("id"),
        "title": title,
        "memory": body[:preview],
        "kind": meta.get("kind", "experience"),
        "lifecycle": item.get("lifecycle") or meta.get("lifecycle"),
        "importance": item.get("importance"),
        "last_seen_cn": item.get("last_seen_cn"),
        "repeat_count": int(item.get("repeat_count") or 1),
    }
    if meta.get("task_id"):
        out["task_id"] = meta["task_id"]
    related = meta.get("related_files") or []
    if related:
        out["related_files"] = related[:4]
    if score is not None:
        out["score"] = round(float(score), 2)
    return out


def slim_knowledge(hit: dict[str, Any], *, excerpt: int = 120) -> dict[str, Any]:
    text = str(hit.get("text") or "")
    return {
        "source": hit.get("source"),
        "score": round(float(hit.get("score") or 0), 2),
        "text": text[:excerpt],
    }


def dump_mcp(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def excerpt_paragraphs(
    text: str,
    tokens: list[str],
    query: str,
    *,
    max_chars: int = 420,
    max_paras: int = 2,
) -> str:
    """Keep the matching paragraphs, not the file head."""
    if not text:
        return ""
    parts = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    scored: list[tuple[float, str]] = []
    for p in parts:
        s = score_document("para", p, tokens, query)
        if s > 0:
            scored.append((s, p))
    scored.sort(key=lambda x: x[0], reverse=True)
    if scored:
        out: list[str] = []
        used = 0
        for _, p in scored[:max_paras]:
            if used >= max_chars:
                break
            take = p if len(p) <= max_chars - used else p[: max_chars - used].rstrip()
            out.append(take)
            used += len(take)
        return "\n\n".join(out)

    low = text.lower()
    idx = -1
    for t in tokens:
        needle = t.lower()
        if not needle:
            continue
        i = low.find(needle)
        if i >= 0:
            idx = i
            break
    if idx < 0:
        return text[:max_chars]
    start = max(0, idx - 80)
    if start:
        nl = text.rfind("\n", 0, start)
        if nl >= 0:
            start = nl + 1
    end = min(len(text), start + max_chars)
    return text[start:end].strip()
