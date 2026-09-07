# shejiuPro token 路由（L1 知识，非常驻）

## 主路径

1. `context_orient` 一次（query=FQCN 或 `Foo.java`）
2. `context_fetch` 按行（默认 ≤80 行；禁 `selector=raw` 除非用户明确要求全文）
3. Mapper/SQL：Grep xml；禁整份 ServiceImpl Read

## 红包

- 数学：`com.shejiu.product.redpacket.RedPacketScheduleMath`
- 任务服务：`com.shejiu.product.service.impl.TRedPacketTaskServiceImpl`
- tick 与任务状态一致；验：`RedPacketScheduleMathTest` + product compile

## 自我进化

- ContextMind：`node .cursor/contextmind/cli.mjs report --json`（三列账本）；极致见 `docs/agent-stack/PEAK.md`
- Project Brain：`record_task_outcome`，project_id=`shejiuPro`（禁 MCP `build_task_context`）
- 任务结束写一句可检索摘要（决策、坑、验收命令）
