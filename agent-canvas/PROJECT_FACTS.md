# 已确认项目事实

扫描范围：`e:\workA\A-skill\project-brain-mind`（当前工作区）+ `C:\Users\Administrator\Downloads\11111`（第三方源码包）。密钥未读取。

## 技术栈

- 当前工作区是 **Agent Canvas**（`@openhands/agent-canvas` 1.16.0），React/TypeScript 前端。证据：`package.json:2`，`AGENTS.md:3`。
- Agent 执行在 **OpenHands Agent Server**（独立仓库 `software-agent-sdk`），版本针 `1.44.1`。证据：`config/defaults.json:3`，`docs/architecture.md:23`。
- 下载目录含 Mem0（`mem0ai` 2.0.20，依赖 Qdrant client + SQLAlchemy）、Qdrant、LlamaIndex、SCIP、Joern（JDK 21）、Superpowers、Semgrep、SWE-agent、OpenRewrite、Ruff、tree-sitter。证据：各 README / `mem0-main/pyproject.toml:5`。
- 下载目录 **没有** OpenHands / software-agent-sdk 源码。证据：`Downloads/11111` 目录列表。

## 目录结构

- Canvas：`src/api`、`src/components`、`scripts`、`docker`、`tools/canvas_ui_tool.py`。证据：`docs/architecture.md:35`。
- 根目录无生产 `docker-compose`；仅 `examples/acp-docker/docker-compose.yml`。
- `.requirementmind/` 扫描时不存在（本次新建）。

## 数据模型

- 未扫描到 PostgreSQL 表 `projects/memories/skills/executions/feedback/code_index`。
- 未扫描到 Qdrant collection `project_memory` 等。
- 应用偏好在 agent-server `misc_settings.app_preferences`。证据：`AGENTS.md` app-preferences 段。

## 已存在接口

- Agent-server 经 `@openhands/typescript-client`（对话、设置、skills、MCP 配置）。
- `SkillsService.getSkills`：本地 user/project skills + 构建期 catalog。证据：`src/api/skills-service.ts:39`。
- MCP：前端配置/健康检查，无 Project Brain 工具实现。证据：`src/api/mcp-health/probe-mcp-server-health.ts:1`。

## 已存在业务规则

- 本仓库禁止塞入后端业务与直打 agent-server HTTP。证据：`AGENTS.md:47`，`src/api/no-direct-agent-server-calls.test.ts:7`。
- 公开 skills 属于 `@openhands/extensions`，不在本仓改。证据：`AGENTS.md:19`。

## 已存在测试

- `npm run lint` / `npm test` / `npm run build`；mock-LLM / live E2E 框架存在。
- 无 Memory/RAG/SCIP/Joern 相关测试。

## 历史决策

- Agent Canvas 从 OpenHands 前端改编，只连 Agent Server。证据：`docs/architecture.md:3`。
- SWE-agent 上游建议改用 mini-swe-agent。证据：`SWE-agent-main/README.md:20`。

## 已知约束

- Requirement Gate 未通过前禁止正式开发。证据：`.cursor/skills/requirement-mind/SKILL.md:11`。
- Semgrep CE 跨文件安全分析能力有限。证据：`semgrep-develop/README.md:45`。
- SCIP Java/TS indexer 不在 `scip-main` 本仓。证据：`scip-main/README.md:35`。
