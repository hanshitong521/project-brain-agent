# Project Brain（单体仓库）

本仓库包含两部分，**日常以 Brain 为主**：

| 目录 | 说明 |
|------|------|
| **根目录 `src/`、`scripts/`、`fixtures/`** | **Project Brain** — MCP、记忆、知识检索、Token 预算、统计看板 |
| **`agent-canvas/`** | **OpenHands Agent Canvas** 前端（原 `project-brain-mind`），可选；需要图形界面时再 `npm ci` + `npm run dev` |

原独立目录 `project-brain-mind` 已合并进 `agent-canvas/`，请勿再单独维护。

## Brain（推荐日常使用）

```powershell
cd e:\workA\A-skill\project-brain-agent
.\scripts\start-dashboard-hidden.vbs
```

看板：http://127.0.0.1:18787/dashboard  

**统一菜单**：先启动 [dev-hub](../dev-hub/README.md)（http://127.0.0.1:18888/），各看板顶栏可互相跳转。

停止：`.\scripts\stop-dashboard.ps1`

详见根目录 [README.md](./README.md)（Brain 安装与测试）。

## Agent Canvas（可选）

```powershell
cd agent-canvas
npm ci
npm run dev
```

见 `agent-canvas/README.md`、`agent-canvas/AGENTS.md`。

## 规格与需求

- [PROJECT_BRAIN_AGENT_DEVELOPMENT_SPEC.md](./PROJECT_BRAIN_AGENT_DEVELOPMENT_SPEC.md)
- [docs/requirementmind/DEVELOPMENT_SPEC.md](./docs/requirementmind/DEVELOPMENT_SPEC.md)
- 状态机读：`.requirementmind/`

## Cursor 工作区

请 **只打开本仓库根目录** `project-brain-agent`，不要再打开已删除的 `project-brain-mind`。
