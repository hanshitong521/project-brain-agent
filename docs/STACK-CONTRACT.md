# 五层栈（project-brain 只占 WHY）

本仓 MCP = **长期记忆 / ADR / 坑**，**不是**代码结构图，也不是需求真源。

全栈 SSOT：`E:/AAAAAA/ai-restriction-document/3、本人编程文档测试/shared/pipeline-contract.md`

| 层 | 系统 | Brain 工具 |
|----|------|------------|
| WHAT | RequirementMind FROZEN | Gate 后 `scripts/sync_requirementmind.py`；**冲突以 FROZEN 为准** |
| **WHY** | **本仓** | `search_project_context` `get_change_context` `save_architecture_decision` `save_bug_memory` `record_task_outcome` |
| CTX | ContextMind | **禁止**用 Brain 查 Java 调用链 / 替代 `context_orient` |
| HOW/DO | ai-design / ai-code | MCP **不**暴露 `build_task_context` / `search_knowledge`。组装仅看板 HTTP。文档段落已并进 `search_project_context.docs` |

## 禁

- MCP 对外只有 WHY 五工具；禁止用 Brain 当 CodeGraph
- 用 `search_project` / 向量检索当 CodeGraph
- 记忆覆盖 FROZEN（须 RM supersede）
- 独立再挂 OpenViking MCP（本仓即 OpenViking 层）

## shejiuPro

`project_id=shejiuPro`。Gate 后：`node scripts/sync-requirementmind-brain.mjs`。
改文件前：`get_change_context(file=…)`。收尾：`record_task_outcome`（`metadata.kind=experience`，30 分钟内勿重复）。
