# PROJECT_BRAIN_AGENT_DEVELOPMENT_SPEC.md

**Version:** 3.0  
**Status:** READY_FOR_DEVELOPMENT（RequirementMind Gate 2026-09-03）  
**Canonical copy:** `docs/requirementmind/DEVELOPMENT_SPEC.md`

---

## 0. AI 开发约束（必读）

**身份：** 你是 Project Brain Agent 的实现工程师，在**独立仓库** `project-brain-agent` 工作，不是在 OpenHands Agent Canvas 前端仓里堆后端。

**目标：** 交付 v1 最小闭环 — MCP 中间层 + Mem0 经验 + LlamaIndex 知识 + Qdrant + Token 预算 + fixture 验收。

**禁止：**

- 修改 OpenHands Agent Loop / fork `software-agent-sdk`
- 在 `@openhands/agent-canvas` 的 `src/**` 实现 Memory/RAG 服务
- Vendor `Downloads/11111` 第三方源码
- Mem0 与 LlamaIndex 写入**同一个** Qdrant collection
- v1 接入 SCIP / Joern / Skill Evolution / Semgrep 流水线 / 真实业务项目

**决策原则：** 以 `.requirementmind/decisions.json` 中 DEC-001…DEC-011 为准；冲突时输出 DEVELOPMENT_BLOCKER，禁止自猜业务规则。

**遇到未知：** 规格未写且代码库无证据 → BLOCKER，退回 RequirementMind。

---

## 1. 为什么做（Problem）

| 痛点 | v1 如何应对 |
|------|-------------|
| Cursor 无长期记忆 | Mem0 + `memory_experience` |
| 全项目读取消耗 Token | `build_task_context` 预算 ≤5000（T3） |
| AI 不了解项目规则 | `project-context-service` + fixture ingest |
| 重复犯错 | 任务结束 `record_task_outcome` |

---

## 2. 总体架构（真实边界）

```
        Cursor                    OpenHands Agent Server
           \                            /
            \                          /
             -------- MCP (stdio/SSE) --------
                          |
                 project-brain-agent
                          |
     +--------------------+--------------------+
     |                    |                    |
 project-context    memory-service      knowledge-service
 (YAML/rules)       (Mem0 OSS)          (LlamaIndex)
                          \                /
                           Qdrant
              collections: memory_experience
                           knowledge_document
                           code_index (v1 可空)
                           skill_index (v1 可空)
```

**OpenHands 角色：** 已发布的 **agent-server** 仅作执行宿主；Brain 不嵌入其进程 [DEC-004]。

**Agent Canvas 角色：** UI；v1 **默认不改** Canvas 代码 [Q-009 默认 A]。

---

## 3. 仓库与职责

| 仓库 | 职责 |
|------|------|
| `project-brain-agent`（新建） | brain-api、mcp-server、memory/knowledge/context、compose、测试、fixture |
| `OpenHands/software-agent-sdk` | Agent Loop — **只消费，不改** |
| `openhands-agent-canvas`（本 meta 仓） | 前端 — v1 不实现 Brain |

**推荐目录：**

```
project-brain-agent/
  services/brain-api/
  services/mcp-server/
  services/memory-service/
  services/knowledge-service/
  services/project-context-service/
  packages/brain-core/          # token 分层
  docker-compose.yml
  fixtures/demo-spring-project/
  fixtures/demo-python-crawler/
  tests/
```

---

## 4. 第三方组件（运行时）

| 组件 | v1 用法 | 获取方式 |
|------|---------|----------|
| Mem0 | 经验记忆 | `pip install mem0ai` |
| LlamaIndex | 文档 RAG | `pip install llama-index-core` + Qdrant 集成包 |
| Qdrant | 向量库 | Docker `qdrant/qdrant:6333` |
| Postgres | 可选 | Mem0/项目注册，不重复自研 memories 表 |
| SCIP/Joern/Semgrep | **v1 不用** | 二期 |

---

## 5. Token 规范（AI 必须遵守）

### 5.1 分层

| 层 | 内容 | v1 预算（token） |
|----|------|------------------|
| L0 System | Brain 行为约束摘要 | ~500 |
| L1 Project | rules + metadata | ~2000 |
| L2 Task | memory + knowledge 检索 | ~5000 合计上限 |
| L3 Deep | 大文件/全库 | v1 禁止默认加载 |

### 5.2 硬上限

```yaml
context:
  max_tokens: 16000          # 绝对上限
  task_retrieval_max: 5000   # T3 验收
memory:
  max_items: 5
skill:
  max_active: 0              # v1 无 skill-engine
code:
  max_files: 20              # v1 仅 fixture 小集
```

### 5.3 禁止

- 全仓库 glob 读入上下文
- 全量 Mem0 dump
- 未调用 `build_task_context` 就把多 collection 拼满

---

## 6. MCP 设计（v1）

| Tool | 输入 | 输出 |
|------|------|------|
| `search_project` | project_id, query | rules, stack, paths |
| `search_memory` | project_id, query, limit≤5 | Mem0 条目 |
| `search_knowledge` | project_id, query, top_k | 文档 chunks |
| `build_task_context` | project_id, task, budget_tokens | L0+L1+L2 文本 + usage |
| `record_task_outcome` | project_id, summary, importance | ok / id |

**异常：** `isError=true` + message；Qdrant down → 明确 503 语义。

---

## 7. Agent 执行流程（v1 标准）

```
需求
 → search_project / build_task_context（理解+检索）
 → 宿主 Agent 改代码（Cursor 或 OpenHands）
 → record_task_outcome（总结沉淀）
```

T2 验收：**不强制** Skill 引擎；可选返回空 skill 或固定 demo 文案 [DEC-011]。

---

## 8. 开发顺序（必须按序）

1. `docker-compose` + Qdrant + health  
2. `project-context-service` + fixture 注册  
3. `memory-service`（Mem0 → `memory_experience`）  
4. `knowledge-service`（LlamaIndex → `knowledge_document`）  
5. `brain-core` Token 预算  
6. `brain-api` HTTP  
7. `mcp-server` 五工具  
8. 集成测试 + T1/T2/T3  

---

## 9. Docker 部署（v1）

```yaml
# 目标 compose 服务名
services:
  qdrant:
  postgres:          # optional
  brain-api:
  mcp-server:
```

OpenHands / Canvas **不在** 同一 compose 内；用户本机已有 agent-server 时仅配 MCP URL。

---

## 10. 验收标准（Gate）

| ID | 场景 | 通过条件 |
|----|------|----------|
| T1 | 「退款模块怎么设计？」 | rules + memory/knowledge 命中，≤5000 token |
| T2 | 修改 fixture Service 方法 | Memory→context→Agent 能定位文件 |
| T3 | Token 对比 | 检索路径 ≤5000 vs 全量读 ~30000 基线 |

Fixture only [DEC-008] — 不用真实淘宝/抖音/生产 Spring。

---

## 11. 性能指标（v1 可测）

| 指标 | v1 目标 |
|------|---------|
| 检索上下文 Token | ≤5000（T3） |
| Memory 命中 | 集成测试有命中即可 |
| 修改成功率 | T2 手动/半自动通过 |

「降低 70–90%」为方向性目标 [ASM-003]，**不是** v1 阻塞项。

---

## 12. v1 明确不做

- OpenHands 核心改动  
- SCIP / Joern / Evolution / Semgrep Agent Review  
- 自动测试 Agent  
- 四真实业务项目  
- Canvas MCP 配置 UI（默认；见 Open Questions）

---

## 13. 与旧版 17 章大纲关系

旧大纲是**理想架构**；v3 以 **DEC + 扫描事实** 为准。未列入 v3 Scope 的章节（Skill 目录规范、Evolution、Joern 等）**不得**在 v1 实现。

---

## 14. 冻结决策索引

完整 JSON：`.requirementmind/decisions.json`（DEC-001 … DEC-011）。

---

## 15. 下一步 Coding Agent

1. 阅读 `docs/requirementmind/DEVELOPMENT_SPEC.md` 全文  
2. 初始化 `project-brain-agent` 仓库  
3. 按 §8 开发顺序实现  
4. 对照 §10 跑验收  
5. 冲突 → DEVELOPMENT_BLOCKER 格式（见 `.agent-prompts/cursor.md`）

---

*End of PROJECT_BRAIN_AGENT_DEVELOPMENT_SPEC v3.0*
