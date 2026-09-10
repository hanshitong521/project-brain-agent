# Memory lifecycle (WHY)

Prompt 检索只读 **verified**。磁盘可留 **raw**。禁止用 **L0/L1/L2** 称呼记忆分层（那是 Token-Mind `build_task_context` 的预算层名）。

全栈合同：`A-skill/shared/pipeline-contract.yaml`（INV-007/008 为方向；本文件描述当前落地切片）。

## Layers

| id | 存哪 | 进 `search_project_context`？ |
|----|------|--------------------------------|
| raw | ContextMind `telemetry` / `execution.jsonl` / Brain `stats/events.jsonl` | 否 |
| candidate | `.data/memories/{project_id}.jsonl`，字段 `lifecycle=candidate` | 否 |
| verified | 同一 JSONL，`lifecycle=verified` | 是 |

- **单文件单写**：不新建 `{project}_candidates.jsonl`。
- 本切片用 JSONL `lifecycle` 字段；**不等于**宣称 CanonicalMemoryV3 gate 已 PASS。

## Writes

| 入口 | lifecycle |
|------|-----------|
| `record_task_outcome` / `save_bug_memory` | candidate |
| `save_architecture_decision` | verified |
| RM Gate 后 sync（FROZEN / constitution） | verified |
| Dashboard **promote** / TestMind 胶水（FAIL→FIX→PASS 或 `add_regression_case`） | candidate → verified |
| 单次绿测、无证据推测、一次性用户口令 | 不写 verified；疑似密钥正文拒绝落盘 |

**存量**：无 `lifecycle` 字段的行视为 `verified` + `grandfathered=true`（search 不空窗；Dashboard 标「未取证」）。

## Conflicts

- 新 candidate 与已有 verified 近重复 → `status=conflict`，**不覆盖** verified 正文。
- **supersede** 保留旧行，对齐 RequirementMind FROZEN supersede 语义。
- 证据元数据：`relative_ref` + `content_hash`（INV-010）；禁止盘符路径写入记忆元数据。

## 系统自动评判（auto_verdict）

规则引擎（非 LLM）在写入/列表时计算：`promote` | `review` | `reject` | `hold`。  
典型 **promote**：`kind=bug` + `related_files`、TestMind 来源、重复 ≥2 次。  
Dashboard [`/lessons`](/lessons) 可编辑正文 / `applies_when`；`POST .../apply-auto-promote` 批量采纳建议。  
环境变量 `BRAIN_AUTO_PROMOTE=testmind|aggressive|off`（默认 off）可在写入时自动晋升部分 candidate。

## MCP 与晋升

- MCP 对外仍 **五工具**；Coding Agent **不自 promote**。
- 人：Dashboard Candidate Inbox → promote / reject。
- 自动化：`POST /v1/memory/{project}/candidate`、`POST .../promote`（`brain_api`）；不为此新增 MCP tool。

## MemoryRecord（实现目标字段）

单行 JSONL；未知字段忽略。

| 字段 | 说明 |
|------|------|
| `lifecycle` | `candidate` \| `verified` \| `rejected` |
| `kind` | `experience` \| `decision` \| `bug` \| `constitution` |
| `status` | `ok` \| `conflict` \| `superseded` |
| `source` | `agent` \| `requirementmind` \| `testmind` \| `human` |
| `evidence` | `[{ relative_ref, content_hash }]` |
| `supersedes` / `conflicts_with` | id 链 |
| `idempotency_key` | 重放 NO_OP（对齐 INV-008） |

## P1（规格已冻结，本文档不代为实现）

- TaskBundle 扩展 `must_read` / `meta.handoff_summary`（**不**新建平行 yaml）。
- `.requirementmind/constitution.yaml` + Gate + sync。
- `applies_when` / `do_not_use_when` 排序；verified compaction。

规格与代码冲突 → `DEVELOPMENT_BLOCKER`，禁止私裁。
