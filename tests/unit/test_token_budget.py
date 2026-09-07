import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brain_core.token_budget import estimate_tokens, DEFAULT_BUDGET


def test_truncate_respects_max() -> None:
    long = "x" * 10000
    text, used = DEFAULT_BUDGET.truncate(long, 100)
    assert used == 100
    assert len(text) < len(long)
