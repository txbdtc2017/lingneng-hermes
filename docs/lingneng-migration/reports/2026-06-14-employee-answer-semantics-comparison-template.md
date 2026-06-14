# Phase 16 Employee Answer Semantics Comparison Template

## Purpose

Use this template to compare LingNengAI reference behavior and LingNeng-Hermes behavior for digital employee answer semantics. No exact live LLM wording is required; evaluate public behavior, scope, tool policy, handoff, and data-gap handling.

## Live Gate

Live checks are disabled unless:

```text
LINGNENG_EMPLOYEE_SEMANTICS_LIVE_TEST_ENABLED=true
```

## Case Table

| Case id | Employee | Scenario | Status | Notes |
| --- | --- | --- | --- | --- |
| boss_assistant:identity | boss_assistant | identity | pending | capability intro |
| boss_assistant:in_scope | boss_assistant | in_scope | pending | business review |
| boss_assistant:out_of_scope | boss_assistant | out_of_scope | pending | medical and legal boundary |
| boss_assistant:handoff | boss_assistant | handoff | pending | content creation handoff |
| boss_assistant:insufficient_data | boss_assistant | insufficient_data | pending | missing store data |
| boss_assistant:tool_needed | boss_assistant | tool_needed | pending | PDF report generation |
| operation_specialist:identity | operation_specialist | identity | pending | capability intro |
| operation_specialist:in_scope | operation_specialist | in_scope | pending | store diagnosis |
| operation_specialist:out_of_scope | operation_specialist | out_of_scope | pending | non-restaurant technical support |
| operation_specialist:handoff | operation_specialist | handoff | pending | menu combo handoff |
| operation_specialist:insufficient_data | operation_specialist | insufficient_data | pending | missing sales and labor data |
| operation_specialist:tool_needed | operation_specialist | tool_needed | pending | chart and report generation |
| product_combo_advisor:identity | product_combo_advisor | identity | pending | capability intro |
| product_combo_advisor:in_scope | product_combo_advisor | in_scope | pending | combo and pricing |
| product_combo_advisor:out_of_scope | product_combo_advisor | out_of_scope | pending | legal contract boundary |
| product_combo_advisor:handoff | product_combo_advisor | handoff | pending | campaign theme handoff |
| product_combo_advisor:insufficient_data | product_combo_advisor | insufficient_data | pending | missing cost and sales data |
| product_combo_advisor:tool_needed | product_combo_advisor | tool_needed | pending | structured comparison chart |
| marketing_planner:identity | marketing_planner | identity | pending | capability intro |
| marketing_planner:in_scope | marketing_planner | in_scope | pending | holiday campaign |
| marketing_planner:out_of_scope | marketing_planner | out_of_scope | pending | unrelated coding task |
| marketing_planner:handoff | marketing_planner | handoff | pending | poster copy handoff |
| marketing_planner:insufficient_data | marketing_planner | insufficient_data | pending | missing audience and budget |
| marketing_planner:tool_needed | marketing_planner | tool_needed | pending | public trend search |
| marketing_content_creator:identity | marketing_content_creator | identity | pending | capability intro |
| marketing_content_creator:in_scope | marketing_content_creator | in_scope | pending | short copy |
| marketing_content_creator:out_of_scope | marketing_content_creator | out_of_scope | pending | medical efficacy claim |
| marketing_content_creator:handoff | marketing_content_creator | handoff | pending | campaign mechanism handoff |
| marketing_content_creator:insufficient_data | marketing_content_creator | insufficient_data | pending | missing product and channel details |
| marketing_content_creator:tool_needed | marketing_content_creator | tool_needed | pending | poster image generation |
| member_operator:identity | member_operator | identity | pending | capability intro |
| member_operator:in_scope | member_operator | in_scope | pending | recall campaign |
| member_operator:out_of_scope | member_operator | out_of_scope | pending | finance audit boundary |
| member_operator:handoff | member_operator | handoff | pending | campaign theme handoff |
| member_operator:insufficient_data | member_operator | insufficient_data | pending | missing member segment data |
| member_operator:tool_needed | member_operator | tool_needed | pending | member report generation |
