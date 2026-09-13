# 五层栈（project-brain 只占 WHY）



本仓 MCP = **长期记忆 / ADR / 坑**，**不是**代码结构图，也不是需求真源。



全栈 SSOT：`A-skill/shared/pipeline-contract.md`（机器：`pipeline-contract.yaml`）



记忆分层 SSOT：**`docs/MEMORY-LIFECYCLE.md`**（用 `raw` / `candidate` / `verified`；**禁止**用 L0/L1/L2 指记忆）。



| 层 | 系统 | Brain 工具 |

|----|------|------------|

| WHAT | RequirementMind FROZEN | Gate 后 `scripts/sync_requirementmind.py`；**冲突以 FROZEN 为准** |

| **WHY** | **本仓** | `search_project_context` `get_change_context` `save_architecture_decision` `save_bug_memory` `record_task_outcome` |

| CTX | ContextMind | **禁止**用 Brain 查 Java 调用链 / 替代 `context_orient` |

| HOW/DO | ai-design / ai-code | MCP **不**暴露 `build_task_context` / `search_knowledge`。组装仅看板 HTTP。文档段落已并进 `search_project_context.docs` |



## 检索与写入（记忆门）



| 工具 | 行为（目标合同） |

|------|------------------|

| `search_project_context` / `get_change_context` | 只返回 **verified**（含 grandfather 存量） |

| `record_task_outcome` / `save_bug_memory` | 写入 **candidate**；**不会**立刻被 search 命中 |

| `save_architecture_decision` | 写入 **verified**（ADR） |

| 晋升 verified | Dashboard 或 `POST /v1/memory/{id}/promote`；见 MEMORY-LIFECYCLE |
| TestMind 胶水 | `POST /v1/memory/{project}/candidate`（shejiu `scripts/brain-ingest-testmind-candidate.mjs`） |



## 禁



- MCP 对外只有 WHY 五工具；禁止用 Brain 当 CodeGraph

- 用 `search_project` / 向量检索当 CodeGraph

- 记忆覆盖 FROZEN（须 RM supersede）

- 独立再挂 OpenViking MCP（本仓即 OpenViking 层）

- Agent 自 promote candidate → verified



## shejiuPro



`project_id=shejiuPro`。Gate 后：`node scripts/sync-requirementmind-brain.mjs`（FROZEN → verified）。



改文件前：`get_change_context(file=…)`（**verified** 记忆 + 路径相关的 **candidate** bug/decision + 相关文档）。



收尾：`record_task_outcome` → **candidate**（`metadata.kind=experience`；30 分钟内同指纹去重仍有效）。要进长期检索须在 Dashboard **promote** 或走 TestMind 胶水（见 MEMORY-LIFECYCLE）。


