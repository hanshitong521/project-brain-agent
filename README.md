# Project Brain Agent v0.1 (v1 demo)

> **单体仓库说明**：OpenHands 前端在 [`agent-canvas/`](./agent-canvas/)（原 `project-brain-mind`）。总览见 [MONOREPO.md](./MONOREPO.md)。
> **在整栈中的位置（只占 WHY）**：见 [docs/STACK-CONTRACT.md](./docs/STACK-CONTRACT.md)。

独立 MCP + HTTP API。默认 **离线演示**（JSONL 记忆 + fixture 文档检索），无需 Docker/OpenAI。

## 安装（Windows，已实测）

```powershell
cd e:\workA\A-skill\A-github-skill-mcp\project-brain-agent
.\scripts\install-and-demo.ps1
```

需要 **Python 3.11**（`py -3.11`）。不要用 3.14 建 venv，很多依赖尚无 wheel。

安装成功后应看到 `pytest` 4 passed 和 T1 的 token 数字；若最后一步报 `SyntaxError`，请拉最新代码（T1 已改为 `scripts\demo_t1.py`，避免 PowerShell 中文乱码）。

**装完自检：**

```powershell
.\scripts\verify-install.ps1
```

<details>
<summary>安装 / 启动失败常见原因</summary>

| 现象 | 处理 |
|------|------|
| 找不到 `requirements.txt` | 必须在仓库根目录执行 `.\scripts\install-and-demo.ps1`，不要 `cd scripts` 后单独跑 |
| `No module named 'brain_services'` | 设置 `$env:PYTHONPATH="src"`，或只用提供的启动脚本 |
| MCP 报 `mcp.server.fastmcp` | `pip install "mcp>=1.6,<2"`（requirements 已限制 &lt;2） |
| 看板打不开 | 先 `.\scripts\start-dashboard-background.ps1`，失败看 `.data\logs\brain-api.err.log` |
| 误建了 `scripts\.venv` | 删掉该目录，只在**根目录**保留 `.venv` |

</details>

**实测结果（本机）：**

| 指标 | 值 |
|------|-----|
| pytest | 4 passed |
| 全量读 fixture 估算 | ~118k tokens |
| Brain 检索上下文 | ~341 tokens |
| T3 预算 | ≤5000 ✓ |

Docker 未启动时走 **离线模式**（JSONL 记忆 + fixture 文档），不依赖 Qdrant/OpenAI。

## 可选：Qdrant + Mem0

默认走 JSONL + fixture，**不必**装 Mem0。若要试向量记忆：

1. 启动 Docker Desktop，然后：`docker compose up -d`
2. 安装可选依赖并设置环境变量：

```powershell
.\.venv\Scripts\python -m pip install -r requirements-full.txt
$env:BRAIN_USE_MEM0="1"
$env:OPENAI_API_KEY="sk-..."
```

看板 list/promote/dedupe 仍需 JSONL 模式（勿设 `BRAIN_USE_MEM0=1`）。

## MCP（Cursor）

**推荐**直接跑 venv Python（Windows 下不要用 `.cmd` 做 stdio）：

```json
{
  "mcpServers": {
    "project-brain": {
      "type": "stdio",
      "command": "e:\\workA\\A-skill\\A-github-skill-mcp\\project-brain-agent\\.venv\\Scripts\\python.exe",
      "args": ["-u", "-m", "brain_mcp.server"],
      "env": {
        "PYTHONPATH": "e:\\workA\\A-skill\\A-github-skill-mcp\\project-brain-agent\\src",
        "PYTHONUTF8": "1"
      }
    }
  }
}
```

对外只有 WHY 五工具：`search_project_context`（含文档命中段 `docs`）、`get_change_context`、`save_architecture_decision`、`save_bug_memory`、`record_task_outcome`。`build_task_context` 仅看板 HTTP。

## 实时统计看板（中文）

**推荐：后台启动（不会出现黑色命令行窗口，避免误关）**

双击或在 PowerShell 执行：

```powershell
cd e:\workA\A-skill\A-github-skill-mcp\project-brain-agent
.\scripts\start-dashboard-background.ps1
```

或双击 **`scripts\start-dashboard-hidden.vbs`**（完全无窗口，仅启动服务）。

浏览器打开：**http://127.0.0.1:18787/dashboard**

停止服务（不要用任务管理器乱关）：

```powershell
.\scripts\stop-dashboard.ps1
```

- 进程 PID 写在 `.data/brain-api.pid`，日志在 `.data/logs/brain-api.log`
- 看板每 **2 秒** SSE 刷新；仅 Web 页面，不弹出命令行框

<details>
<summary>前台调试（会显示黑框，仅开发时用）</summary>

```powershell
$env:PYTHONPATH="src"
.\.venv\Scripts\python -m uvicorn brain_api.app:app --host 127.0.0.1 --port 18787
```

</details>

## shejiuPro 全量基线与「节约为 0」

在 [`fixtures/shejiuPro/project.yaml`](fixtures/shejiuPro/project.yaml) 配置 `project.repo_root`（默认 `e:/workA/shejiuPro`）。全量 token 估算扫描该目录下 `docs/**` 与 `.cursor/rules/**`（可用环境变量 `BRAIN_REPO_ROOT_SHEJIUPRO` 覆盖）。

看板节约为 0 时排查：

1. **API 刚重启**：历史事件在 `.data/stats/events.jsonl`；新版本会从文件合并统计（勿只信内存缓存）。
2. **基线小于实际上下文**：未配置 `repo_root` 时只统计 fixture 小文档，会小于一次组装的 token。
3. **未调用组装**：看板节约来自 HTTP `build_task_context`；MCP 只走 WHY 检索，不写 `context_build`。

看板默认**不含 demo 项目**（`demo-spring-project` 等），只统计 `project.yaml` 里配置了 **`repo_root`** 的真实仓库。节约明细表含 **节约比例**（节约÷全量）。验收 fixture 仍用 `GET /v1/projects?tracked_only=false`。

**重复记忆**：`record_task_outcome` 每次会话结束会写同一 TaskBundle 摘要；`memory_simple` 会按正文指纹去重（忽略 `Ledger:` 后缀）。看板「合并重复记忆」或 `POST /v1/memory/{id}/dedupe` 可清理历史。

**节约明细**：看板「节约明细与统计」按 `context_build` 事件列出每次组装的节约 token、记忆/文档命中，支持日/周/月/年柱状图与命中筛选；API：`GET /v1/stats/savings?project_id=&period=day|week|month|year&hit_filter=`.

## 实测 T1 示例

```powershell
$env:PYTHONPATH="src"
python -c "from brain_services.context_builder import ContextBuilder; from scripts.seed_fixtures import seed_demo_spring; seed_demo_spring(); o=ContextBuilder().build_task_context('demo-spring-project','这个项目退款模块怎么设计？'); print('tokens', o['usage_tokens']); print(o['context'][:800])"
```
