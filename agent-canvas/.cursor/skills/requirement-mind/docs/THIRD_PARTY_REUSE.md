# THIRD_PARTY_REUSE — 外部项目复用记录

原则：不复制粘贴任何外部代码进本仓库，只吸收规则与思想。V1 为纯 Skill（Markdown + 一个 Node 辅助脚本），无任何运行时依赖。

| 项目 | 本地版本 | License | 复用内容 | 是否修改 | 备注 |
|---|---|---|---|---|---|
| Fission-AI/OpenSpec | OpenSpec-main (v1.11.0) | MIT | artifact 依赖与状态流转思想、schemas 组织方式、spec → plan → tasks 流程观 | 否，仅思想 | 不作为运行时依赖 |
| spec-kit | spec-kit-main (Python) | MIT | clarify / analyze / checklist、artifact 交叉一致性检查思路 | 否，仅思想 | 功能重叠部分只吸收规则 |
| bmad-code-org/BMAD-METHOD | BMAD-METHOD-main (v6.11.0) | MIT | 上下文扫描清单思想（读 AGENTS.md/CLAUDE.md/构建文件/结构） | 否，仅思想 | 不引入其安装器与角色体系 |
| adversarial-review-skill | adversarial-review-skill-main | 见其 LICENSE | 独立 reviewer + 默认不可信 + 强制二次验真的编排模式；"reviewer propose, orchestrator confirm" | 否，仅思想 | 与本项目形态最接近的参考 |
| Superpowers | **未下载** | — | 开发前强制理解需求 / Hard Gate / 一次一个核心问题 / A-D 选项规则，按已知内容写入 references/grilling.md | — | 如需精确对齐，后补下载后更新本表与 grilling.md |

本地对照参考（非外部项目）：
- `~/.zcode/skills/grilling`（本地 grilling skill）— 设计树/frontier 模型已完整吸收：整轮 frontier 一起问（Phase 3 批量模式）、每轮回答后重算 frontier（R6）、事实自己查不问用户（R3）+ 取证并行不阻塞整批。决策格式保留 A-D 选项 + ⭐ 推荐 + 冻结语义（本地增强）。
- `RequirementMind_Ultimate 设计文档（内部，2026-09）` — 吸收：Risk Router 分层审查、Human-Only Decision Gate（authority）、Evidence Pack 紧凑输出、Stop Rule、Question Value Score、Eval 闭环；**未采纳**：固定多 Agent 委员会全量讨论（以 LIGHT/FOCUSED/COUNCIL 分层路由替代，见 references/risk-router.md）。

登记时间：2026-08-30。若未来引入任何外部代码/依赖，必须先更新本表（版本、commit、修改原因）。
