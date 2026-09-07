# Project Brain — Cursor Agent Prompt

## 行为约束（最高优先级）

允许：
- 选择技术实现细节（设计模式、内部结构、函数拆分）
- 局部重构你正在修改的代码
- 增加必要的测试

禁止：
- 修改 Frozen Business Rules / Frozen Decisions 中的任何决策
- 擅自新增业务含义或默认值
- 修改数据库语义、状态含义、权限规则、验收口径
- 遇到业务未知项时自己猜

发现以下任一情况，立即停止相关部分开发，输出 DEVELOPMENT_BLOCKER 报告：
- 按规格实现会与现有代码/逻辑冲突
- 修改波及规格未提及的代码、表、接口或调用方
- 规格未覆盖且项目里查不到的业务规则

报告格式：
```
BLOCKER-<序号>
类型: SPEC_CODE_CONFLICT | SCOPE_EXPLOSION | NEW_BUSINESS_UNKNOWN | SPEC_INTERNAL
场景:
规格出处:
代码证据: <file:line>
冲突内容:
影响面:
建议问题:
```

---

## 必读规格（按顺序）

1. `PROJECT_BRAIN_AGENT_DEVELOPMENT_SPEC.md` v3.0 — 架构、Token、MCP、开发顺序  
2. `docs/requirementmind/DEVELOPMENT_SPEC.md` — 验收、API、禁止改动清单  
3. `.requirementmind/decisions.json` — DEC-001 … DEC-011  

## 工作目录

- **实现代码：** 新建/使用独立仓 `project-brain-agent`，**不要**在 `openhands-agent-canvas` 的 `src/**` 写 Brain 后端。  
- **本 meta 仓：** 仅规格与 RequirementMind 状态。

## Cursor 专用

严格遵守 `Files Forbidden To Change`（见 DEVELOPMENT_SPEC）；冻结业务规则所在文件只在注释标注处做最小修改。

按 DEVELOPMENT_SPEC §开发顺序实现；每完成一阶段运行对应 Required Tests；遇到 Development Gate 约束冲突立即停止并输出 DEVELOPMENT_BLOCKER 报告。

## v1 第一步

初始化 `project-brain-agent`：`docker-compose.yml`（Qdrant）+ `services/mcp-server` 骨架 + `tests/integration/test_mcp_tools.py` 占位，然后实现 Mem0/LlamaIndex 集成。
