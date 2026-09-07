# RequirementMind 需求文档

> AI 需求澄清、反驳审查与规格编译系统 —— V1 需求规格
>
> 形态：**Agent Skill**（ZCode / Claude Code 可加载）· 目标项目：**Java 系为主**
> 核心价值：把一句模糊需求，编译成经过取证、追问、反驳、验证、冻结的开发规格，再交给 Coding Agent 执行。
> 原则：先把"做什么"彻底搞清楚，才允许 AI 解决"怎么做"。

---

## 1. 背景与问题

AI Agent 开发最大的风险不是写不出代码，而是：用户只说一句模糊需求 → Agent 补全大量未确认假设 → 没读现有代码/数据库/文档 → 直接开发 → "技术上能跑，业务上是错的"；测试 Agent 沿用同一套错误理解，形成自我证明的假闭环。

RequirementMind 在开发前强制完成：项目事实读取 → 已知/未知/冲突/假设识别 → 关键问题追问 → 决策冻结 → 一致性检查 → 对抗式反驳 → 反驳结果二次验真 → 关键疑问清零 → 规格编译 → 开发准入 Gate。**Gate 不 PASS，不允许开发。**

## 2. 产品形态（已定决策）

| 项 | 决策 |
|---|---|
| 形态 | ZCode / Claude Code **Skill**（Markdown 规则 + Prompt + 少量辅助脚本），类似 adversarial-review-skill 的组织方式 |
| 运行时 | 宿主 Agent（ZCode）自身执行主流程；追问/冻结/编译由主 Agent 完成 |
| Reviewer / Validator | **同一模型 + 全新独立上下文**（subagent 隔离派发），避免与主流程共享盲点；V1 不做多模型配置 |
| 目标项目 | Java 系为主（Maven/Gradle、MyBatis、SQL、Spring）；其他语言走通用扫描兜底 |
| 状态存储 | 目标项目根目录 `.requirementmind/`，全部落盘 JSON，不依赖聊天上下文记忆 |
| 范围 | **V1 完整闭环**（扫描→追问→冻结→反驳→验证→Gate→规格→Prompt 导出） |

## 3. 核心原则（最高优先级规则）

- **R1** 需求未通过 Requirement Gate，不允许正式开发。
- **R2** 模型推理不是业务事实。查不到的业务规则一律进 UNKNOWN，禁止擅自补全。
- **R3** 能从项目取证的问题，禁止问用户。优先级：代码 → 数据库 Schema → 接口定义 → 测试 → 历史文档（README/ADR/AGENTS.md/CLAUDE.md）→ Git 历史 → 配置 → 最后才问用户。
- **R4** 用户确认的决策必须冻结（FROZEN），记录来源与时间。
- **R5** 冻结决策不可被静默覆盖；新旧冲突必须显式 supersede。
- **R6** 每收到一个回答，必须重新分析整个需求，不允许机械执行预设问卷。
- **R7** Adversarial Reviewer 的发现默认不可信，必须二次验证。
- **R8** 没有实际证据，不得把 challenge 判为 CONFIRMED。
- **R9** 结束追问的唯一条件是关键疑问清零（Blocking Questions / Blocking Conflicts / Critical Assumptions = 0），不是问够了 N 个。
- **R10** 最终规格必须能让一个完全不了解对话历史的 Agent 直接完成开发。

## 4. Skill 目录结构

```
requirement-mind/
├── SKILL.md                 # 入口：触发条件 + 工作流编排 + 各阶段规则索引
├── references/
│   ├── scanner.md           # Context Scanner 扫描清单与 Java 优先级
│   ├── parser.md            # KNOWN/UNKNOWN/CONFLICT/ASSUMPTION 拆分规则
│   ├── grilling.md          # 提问规范、优先级、停止条件
│   ├── freezer.md           # 冻结/supersede 规则
│   ├── risk-router.md       # 八维风险评分与审查分层（LIGHT/FOCUSED/COUNCIL）
│   ├── specialists.md       # 专项 Reviewer prompt 片段（security/data/concurrency/compat/testability）
│   ├── eval.md              # Eval 闭环：指标、回填字段与策略阈值
│   ├── reviewer.md          # Adversarial Reviewer 独立上下文 System Prompt
│   ├── validator.md         # Evidence Validator 独立上下文 System Prompt
│   ├── spec-compiler.md     # DEVELOPMENT_SPEC.md 生成规则
│   └── gate.md              # Gate 检查表与判定规则
├── templates/
│   ├── DEVELOPMENT_SPEC.md  # 最终交付物模板
│   └── agent-prompt.md      # 导出 prompt 模板（generic / codex / cursor / claude-code）
├── schemas/                 # *.json 数据模型定义（facts/questions/decisions/…）
├── scripts/
│   ├── state.mjs            # 确定性辅助：frontier 批量输出、freeze 冻结、JSON 校验、blocking 计数、Gate、快照、migrate（旧 questions 补推荐字段）
│   ├── selftest.mjs         # mock 会话确定性自测（46 项断言 + 每轮读取开销计量）
│   └── fixtures/            # mock 会话（红包限时领取场景）+ 旧版 questions 迁移样例
└── docs/
    └── THIRD_PARTY_REUSE.md # 外部项目复用记录
```

## 5. 端到端流程

```
用户需求（一句话）
  ↓ Phase 1  Context Scanner      扫描目标项目 → PROJECT_FACTS + facts.json
  ↓ Phase 2  Requirement Parser   拆分 KNOWN / UNKNOWN / CONFLICT / ASSUMPTION（问题标 authority/value）
  ↓ Phase 2.5 Risk Router         八维评分 → LIGHT/FOCUSED/COUNCIL 分层，决定审查投入
  ↓ Phase 3  Grilling Engine      循环：frontier 取本批（仅 USER_ONLY）→ 整批抛出 →
  │                               用户回答 → freeze 冻结（TECHNICAL/LOW 走 --auto 自治）→ 全量重推演
  ↓ Phase 4  Spec Compiler        生成初步 DEVELOPMENT_SPEC.md
  ↓ Phase 5  Adversarial Review   独立上下文 subagent 攻击规格（Evidence Pack 紧凑块；FOCUSED/COUNCIL 加专项）
  ↓ Phase 6  Evidence Validator   独立上下文 subagent 逐条二次验证
  │                               → CONFIRMED / PLAUSIBLE / REFUTED
  │        CONFIRMED 的高危问题 → 转为 BLOCKING 问题，回到 Phase 3 重新追问
  ↓ Phase 7  Requirement Gate     检查表判定 → BLOCKED / READY_FOR_DEVELOPMENT
  ↓ READY 后
     导出 .agent-prompts/{generic,codex,cursor,claude-code}.md → 交给 Coding Agent
```

## 6. 功能需求

### F1 Context Scanner（Phase 1）

- 扫描优先级（Java 优先）：
  1. 项目规则：AGENTS.md、CLAUDE.md、README、CONTRIBUTING、docs/**、adr/**
  2. 构建与依赖：pom.xml、build.gradle、settings.gradle、Makefile、Dockerfile、docker-compose.yml
  3. 数据库：*.sql、migration/**、schema/**、entity/**、model/**、MyBatis mapper XML
  4. 接口：controller/**、@RestController / @RequestMapping 扫描、openapi/swagger
  5. 测试：src/test/**、测试命名与既有断言风格
  6. Git（环境允许）：git log / blame 用于识别历史决策
  7. 配置：application*.yml / properties（只提取结构性事实，不读密钥）
- 输出：`PROJECT_FACTS.md`（人读）+ `facts.json`（机读，含 source path/line、confidence）
- 约束：只记录**已验证事实**，每条必须带文件级证据来源；扫描不到的领域留空，禁止臆造。

### F2 Requirement Parser（Phase 2）

- 把用户输入拆成四类并落盘：
  - **KNOWN**：能被 facts.json 佐证的部分
  - **UNKNOWN**：项目查不到的业务规则（如到期行为、幂等语义、权限归属）
  - **CONFLICT**：需求与代码/文档现状矛盾（如 status=2 旧代码已有含义）
  - **ASSUMPTION**：模型推断，标注 risk（HIGH 的 assumption 禁止进入最终规格）
- 每条 UNKNOWN 生成的 question 必须标 `authority`（USER_ONLY=业务取舍须问用户 / TECHNICAL=纯工程选择 AI 自治，R11）与 `value`（HIGH/MEDIUM/LOW，价值分 = 决策影响 × 不确定度 × 错误代价 ÷ 获取成本）。
- 每轮追问后**全量重新解析**，不允许只增量补丁。

### F3 Grilling Engine（Phase 3）

- 问题分级：**BLOCKING**（状态机、身份定义、金额计算、并发、幂等、权限、删除语义、核心异常）> **IMPORTANT**（改变体验/结构）> **OPTIONAL**（可用明确默认值，不问）。
- 每个问题固定格式：一句话问题 + 一句话"为什么必须确认" + 2~5 个 A/B/C/D 选项 + **必须**标明推荐项（`⭐ 推荐：X`）+ 一句话推荐理由（可引用 facts）；禁止长篇背景、禁止"还有补充吗"式空问题。
- 每轮整批抛出当前 frontier（仅 **USER_ONLY** 的 BLOCKING+IMPORTANT + OPEN 冲突；TECHNICAL/LOW 值问题 AI 自治裁决 `freeze --auto`；选项依赖未答问题的归下一轮；取证并行不阻塞整批）；回答后 `state.mjs freeze` 冻结并全量重推演。
- 停止条件（R9 + 覆盖率）：`state.mjs stop` 退出码 0（关键计数清零 + risk 高分维度证据可解析）；此后禁止追加提问（R12）。

### F4 Decision Freezer（Phase 3 内）

- 用户答案 → `decisions.json`：id、question_id、decision、source=USER、status=FROZEN、created_at。
- 用户改变主意 → 旧决策置 SUPERSEDED + replaced_by，下游引用自动标记待重审。

### F5 Spec Compiler（Phase 4）

- 输出 `docs/requirementmind/DEVELOPMENT_SPEC.md`，固定章节：Goal / Current System Facts / Scope / Out of Scope / Frozen Business Rules / Database Changes / API Changes / State Machine / Validation / Permission / Concurrency / Idempotency / Exception Handling / Compatibility / Files To Change / Files Forbidden / Acceptance Criteria / Required Tests / Known Risks / Frozen Decisions / Open Questions / Development Gate。
- 规格由 canonical JSON 状态（facts/decisions/…）**单向生成**，禁止手改 Markdown 后反向生效（防文档互相矛盾）。
- 附带 `00-PROJECT_CONTEXT.md` 与 `13-OPEN_QUESTIONS.md`（有余留 OPTIONAL 项时）。

### F6 Adversarial Reviewer（Phase 5，独立上下文 subagent）

- 输入：DEVELOPMENT_SPEC.md + facts.json（只读，无对话历史）。
- 任务：尝试证明规格错误/遗漏/矛盾，攻击维度：隐含假设、边界值、状态冲突、并发、幂等、权限绕过、时间边界、空值、重复请求、回滚重试、外部依赖失败、历史兼容、测试可验证性。
- 输出每条：CLAIM / CHALLENGE / EVIDENCE（文件级）/ COUNTEREXAMPLE / VALIDATION。
- 硬约束：禁止宣判 Bug，所有输出只是 PENDING 的 CLAIM。

### F7 Evidence Validator（Phase 6，独立上下文 subagent）

- 逐条重新取证验证，裁决：**CONFIRMED**（有实际证据）/ **PLAUSIBLE**（合理但证据不足；HIGH 风险必须转用户问题）/ **REFUTED**（质疑不成立，销案不保留）。
- CONFIRMED 且 BLOCKING 级 → 自动转新 BLOCKING 问题回流 Phase 3。

### F8 Requirement Gate（Phase 7）

- 检查表（全部 PASS 才 READY）：Business Goal、Scope、Core Flow、Business Rules、Data Model、API Contract、State Machine、Validation、Permission、Concurrency、Idempotency、Exception Handling、Compatibility、Acceptance Criteria、Testability、Spec Consistency。
- 硬门槛（任一 >0 即 BLOCKED）：Blocking Questions、Blocking Conflicts、Critical Assumptions、Unvalidated High Risks。
- 结果落盘 `gate.json`：BLOCKED（附缺失项清单）/ READY_FOR_DEVELOPMENT。
- **开发期发现新业务未知 → 标记 DEVELOPMENT_BLOCKER，退回本流程，禁止 Coding Agent 自己猜。**

### F9 Prompt Export（收尾）

- 把 READY 的 DEVELOPMENT_SPEC.md 转成各 Agent 最优执行 prompt：generic（默认）、codex、cursor、claude-code，输出到 `.agent-prompts/`。
- 内含开发 Agent 行为约束：允许自定技术细节/局部重构/补测试；禁止改冻结规则、状态语义、权限、验收口径。

### F10 Risk Router（Phase 2.5）

- 八维风险评分（business_criticality / data_impact / concurrency_risk / security_risk / compatibility_risk / irreversibility / blast_radius / evidence_gap，各 0-3）落盘 `risk.json`；score>=2 必须带 FACT/CON/DEC 证据 refs（`stop` 做可解析校验）。
- `state.mjs risk` 分层：LIGHT 0-7 = 主 Agent+Reviewer+Validator；FOCUSED 8-14 = +1 名专项（specialists.md 按最高分维度路由）；COUNCIL 15-24 = +至多 3 名专项且全部 BLOCKING CLAIM 过 Validator。**80% 需求应停在 LIGHT。**

### F11 Eval 闭环（收尾 + Phase 8 后）

- `state.mjs eval` 输出会话指标（自治率、Reviewer 验真率、快照轮次）→ 存 `eval.json`；Phase 8 后回填 missed_requirements / rework_count / not_ask_me。
- 按 references/eval.md 阈值表驱动下次会话策略：authority 松紧、Reviewer confidence 校准、扫描维度扩缩。

## 7. 数据模型（.requirementmind/）

```
session.json     会话与阶段游标（支持中断恢复）
facts.json       FACT-xxx：statement / source{type,path,line} / confidence / status
questions.json   Q-xxx：topic / question / reason / priority(BLOCKING|IMPORTANT|OPTIONAL) / options / recommended_option(A-D) / recommendation_reason / authority(USER_ONLY|TECHNICAL) / value(HIGH|MEDIUM|LOW) / status
decisions.json   DEC-xxx：question_id / decision / source(USER|AI_DEFAULT) / status(FROZEN|SUPERSEDED) / replaced_by / basis
risk.json        八维评分 dimensions{score,refs} / total / tier(LIGHT|FOCUSED|COUNCIL) / specialists（Phase 2.5）
eval.json        会话指标 + 开发后回填（missed_requirements / rework_count / not_ask_me）
assumptions.json ASM-xxx：statement / risk(HIGH|MEDIUM|LOW) / source=MODEL_INFERENCE / status
conflicts.json   CON-xxx：left / right / severity / status
challenges.json  CH-xxx：claim / challenge / evidence[] / status(PENDING_VALIDATION|…)
evidence.json    裁决记录：challenge_id / verdict(CONFIRMED|PLAUSIBLE|REFUTED) / proof
gate.json        检查表结果 + 硬门槛计数 + 最终状态
history/         每轮快照，支持回溯与 supersede 审计
```

会话中断后从 `.requirementmind/` 恢复，不依赖聊天记录（R5/R10 的落盘保障）。

## 8. 外部项目复用策略

| 项目 | 实际形态 | V1 复用方式 |
|---|---|---|
| OpenSpec (v1.11, Node) | Spec 工作流 CLI | 吸收 artifact 依赖/状态流转思想与 schemas 结构；**不作为运行时依赖** |
| spec-kit (Python) | Spec-Driven 工具链 | 吸收 clarify / analyze / 交叉一致性检查规则 |
| BMAD-METHOD (v6.11, Node) | Agent 方法论框架 | 只借鉴上下文扫描清单思想；不引入其安装器/角色体系 |
| adversarial-review-skill | 纯 SKILL.md | 直接借鉴其独立 reviewer + 强制验真的组织方式（与本项目形态最接近） |
| Superpowers | **未下载** | 追问/Hard Gate 规则按已知内容写入 references/grilling.md；如需精确对齐可后补下载 |

约束：不复制粘贴任何外部代码进本仓库；每个项目的复用点、版本、License 记入 `docs/THIRD_PARTY_REUSE.md`。

## 9. 验收标准（完成定义 = 以下全部实测通过，而非"功能写完"）

- **A 不懂不开发**：20 个故意模糊的需求，100% 在关键业务规则未知时保持 BLOCKED。
- **B 不重复问**：已回答的问题不再问（除非出现显式冲突）。
- **C 能查不问**：项目里已有明确答案的问题，不问用户。
- **D Reviewer 不乱报**：20 个假风险，能正确 REFUTED，而不是全部当真。
- **E 真风险能抓**：并发超发、时间边界、status 冲突、空值、权限绕过、幂等缺陷，能被 Reviewer+Validator 实际发现。
- **F Gate 可靠**：任一硬门槛计数 > 0，Gate 必须 BLOCKED。
- **G 闭环跑通**：在真实 Java 项目上完整走一遍 Phase 1→7，产出能被另一个无历史 Agent 直接执行的 DEVELOPMENT_SPEC.md。

## 10. 验证用例（fixtures 驱动）

| Case | 输入 | 验证点 |
|---|---|---|
| 1 简单 CRUD | 明确小需求 | 不过度提问，快速 READY |
| 2 红包限时领取 | 模糊需求 | 时间边界/并发/状态/幂等全部被追问 |
| 3 字段语义冲突 | status=2 已有含义 | 生成 CONFLICT，不覆盖旧语义 |
| 4 文档与代码冲突 | 旧文档过期 | 以代码为权威，不把旧文档当事实 |
| 5 中途改主意 | 用户撤回 DEC | supersede 正确，下游自动重审 |
| 6 Reviewer 报假问题 | 构造假风险 | Validator 判 REFUTED |
| 7 Reviewer 发现真问题 | 构造真缺陷 | CONFIRMED → Gate 退回 BLOCKED |
| 8 绕过 Gate | 直接要求开发 | Gate 强制阻断 |

## 11. V1 明确不做（YAGNI）

Web UI、REST API、多模型配置、monorepo 多包拆分、Prompt Refiner 独立模块（并入 templates）、独立进程的 Agent 角色拆分（ContextAgent 等以 SKILL.md 阶段规则形式存在）。以上全部留待 V2 按实际需要再说。

## 12. V2 展望

Web 三栏状态面板（Facts / Conversation / Gate 状态）、多模型 Reviewer、非 Java 语言的深度扫描器、开发后验收 review（对实现结果再跑一轮 adversarial review）。
