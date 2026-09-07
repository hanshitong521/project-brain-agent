"""Seed demo memories and the demo doc corpus for acceptance tests.

The corpus is generated rather than committed as prose so it can be rebuilt
byte-for-byte: this repo lost files to a mass-truncation incident, and a
fixture that cannot be regenerated stays broken once it is damaged.

`large-appendix.md` is deliberately left alone. It is oversized on purpose --
test_rank.py and test_knowledge_rank.py assert that the 120 KB per-file cap
excludes it -- so the token baseline T3 needs has to come from other docs.
"""

from __future__ import annotations

from pathlib import Path

from brain_services.memory_simple import SimpleMemoryStore
from brain_services.project_context import FIXTURES_ROOT

DOCS = FIXTURES_ROOT / "demo-spring-project" / "docs"

# Each entry is (filename, heading, body sentences). Written deterministically:
# no timestamps, no randomness, so re-running yields identical bytes and git
# stays quiet.
DOC_SPECS = (
    (
        "refund-flow.md",
        "退款主流程",
        (
            "退款入口统一收敛到 RefundService.apply，controller 只做参数校验与鉴权，不得直接操作退款单据。",
            "apply 先按 orderId + reason 计算幂等键，命中已存在单据时直接返回原结果，不重复发起退款。",
            "退款金额以订单实付金额为上限，扣减已退金额与不可退的运费、优惠分摊部分。",
            "渠道退款调用失败时进入重试队列，重试沿用同一幂等键，避免重复退款造成资损。",
            "退款成功后写 refund_record 并发送领域事件，账务与消息通知各自订阅，互不阻塞。",
        ),
    ),
    (
        "refund-idempotency.md",
        "幂等与重试",
        (
            "幂等键由 orderId、reason、requestNo 三段拼接后取指纹，落库唯一索引兜底并发写入。",
            "重试窗口内同一幂等键只允许一条处理中的单据，其余请求返回处理中状态而非新建。",
            "2025-03 的重复退款事故根因是重试路径绕过了幂等键，修复后所有入口共用同一校验。",
            "超时未终态的单据由定时任务扫描，超过阈值转人工，不自动再次发起渠道退款。",
            "并发压测要求同一订单 50 并发退款申请只产生一条成功单据，其余为幂等返回。",
        ),
    ),
    (
        "refund-ads-metrics.md",
        "ADS 口径与对账",
        (
            "ADS 层退款金额口径以终态成功单据为准，处理中与失败单据不计入当日退款额。",
            "跨天退款按渠道回执时间归属日期，与业务库的创建时间可能相差一天，对账需按回执口径。",
            "优惠分摊部分在 ADS 中单列，不并入商品退款金额，避免与营销侧口径冲突。",
            "对账任务每日拉取渠道流水与 refund_record 做双向比对，差异超过阈值告警。",
            "报表侧的退款率分母使用支付成功订单数，不使用下单数，防止未支付订单稀释指标。",
        ),
    ),
    (
        "refund-error-cases.md",
        "异常场景清单",
        (
            "渠道返回余额不足时不重试，直接转人工并通知商户充值，重试只会放大失败量。",
            "订单已部分退款时再次申请需校验剩余可退金额，超额请求返回明确的业务错误码。",
            "重复回调通过幂等键吸收，回调处理必须可重入，不依赖首次处理留下的内存状态。",
            "渠道超时未知态不得当作失败处理，需查询渠道终态后再决定补偿方向。",
            "退款单据状态机只允许前进，禁止从终态回退到处理中，回退会造成重复出款。",
        ),
    ),
)

# Repeats each spec's sentences enough to clear the T3 baseline (>3000 tokens).
# Measured on this CJK prose: ~10 chars/token, so 14 repeats gave 3257 tokens --
# only an 8.5% margin. 20 gives comfortable headroom while every file stays far
# below the 120 KB per-file cap that excludes large-appendix.md.
REPEATS = 20


def seed_demo_spring() -> None:
    store = SimpleMemoryStore()
    store.add(
        "demo-spring-project",
        "Bug fix 2025-03: duplicate refund on retry — fixed by idempotent key orderId+reason in RefundService.apply",
        importance="high",
    )
    store.add(
        "demo-spring-project",
        "Architecture decision: all refund API goes through RefundService, not controllers directly.",
        importance="medium",
    )


def seed_demo_docs() -> list[Path]:
    DOCS.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, heading, sentences in DOC_SPECS:
        lines = ["# %s" % heading, ""]
        for i in range(REPEATS):
            lines.append("## %s（%d）" % (heading, i + 1))
            lines.extend(sentences)
            lines.append("")
        path = DOCS / name
        path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
        written.append(path)
    return written


if __name__ == "__main__":
    seed_demo_spring()
    paths = seed_demo_docs()
    print("Seeded demo-spring-project memories")
    for p in paths:
        print("  %8dB  %s" % (p.stat().st_size, p.relative_to(FIXTURES_ROOT.parent)))
