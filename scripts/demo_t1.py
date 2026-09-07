# -*- coding: utf-8 -*-
"""T1 live demo (called from install-and-demo.ps1; keep UTF-8 in file, not in PS -c)."""
from brain_services.context_builder import ContextBuilder
from brain_services.knowledge_service import KnowledgeService

c = ContextBuilder()
k = KnowledgeService()
baseline, _src = k.full_corpus_tokens("demo-spring-project")
o = c.build_task_context(
    "demo-spring-project",
    "这个项目退款模块怎么设计？",
    budget_tokens=5000,
)
print("baseline_full_corpus_tokens_est:", baseline)
print("brain_context_tokens_est:", o["usage_tokens"])
print("within_budget:", o["within_budget"])
if baseline:
    print("savings_vs_full_load_pct:", round(100 * (1 - o["usage_tokens"] / baseline), 1))
print("layers:", o.get("layers"))
