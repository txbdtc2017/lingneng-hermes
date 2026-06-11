---
name: store-operation-analysis
description: 门店经营诊断任务 Skill，用于老板助手或经营策略顾问分析营收、客流、人工成本、材料成本、预算达成异常背后的经营原因、人员异常、亏损原因和经营健康问题。
version: 1.0.0
metadata:
  lingneng:
    schema_version: "1.0"
    kind: task
    source: python
    status: active
    user_visible: true
    script_policy: metadata_only
    tags: [operation, analysis]
    domains: [restaurant]
    tools:
      - chart_visualization
      - document_generation
    target_employee_types:
      - boss_assistant
      - operation_specialist
    supporting_skills:
      - chart-visualization
      - document-generation
      - report-formatting
      - business-answer-contract
  hermes:
    tags: [lingneng]
    requires_tools: [read_skill]
    fallback_for_toolsets: [lingneng]
triggers: [经营分析, 人工成本, 生意差, 亏损, 预算达成异常, 人员异常, 成本过高, 门店分析, 客流下降, 毛利分析]
---

## When to Use

用户要求老板助手或经营策略顾问判断门店经营状态、分析营收和客流变化、解释亏损原因、评估人工或材料成本是否过高、检查预算偏差背后的经营原因、发现员工薪资或人员数据异常时使用。用户只说“生意差”“哪里出了问题”“人工贵不贵”也应使用。

## When Not to Use

纯闲聊、单句常识问答、营销文案创作、会员活动设计、菜单工程、套餐定价、年度路线图、目标追赶、完成率差距预警或只需生成正式报告文件时不要使用；这些场景应交给对应 task 或 capability。

## Preconditions

尽量确认时间范围、门店范围、营收、客流、客单、复购、人工、材料、房租能耗、预算目标和人员状态。数据不全时先基于已知事实给出保守诊断，再列出最小补数清单。

## Reference Selection

用户需要完整经营诊断模板、老板视角复盘格式、异常排查 SOP 或可直接套用的长输出结构时，读取 `references/business-diagnosis-playbook.md`。快速口头判断时先按本 skill 工作流回答。

## Workflow

1. 先给诊断性结论：用一句话说明当前是营收不足、客流不足、客单下滑、复购弱、成本失控、预算滞后、数据异常，还是多因素叠加。
2. 拆核心经营信号：检查营收、客流、客单价、复购或老客贡献、工作日和周末结构、人工成本率、材料成本率、房租能耗和综合成本率；把事实指标、异常信号和原因假设分开写。
3. 做固定成本压力换算：当有月固定成本时，将房租、固定人工、能耗等折算为每日压力，说明“每天未开门先承担多少固定支出”，再推算盈亏平衡营收。
4. 做成本对标：人工含正式工和临时工，材料按采购或出库口径，房租能耗按固定成本口径；对照餐饮健康区间和预算目标，指出是绝对金额高、占营收比例高，还是营收不足导致分母变小。
5. 检查数据异常：重点识别薪资突然消失、在职员工无工资、离职员工继续计薪、材料全月为 0 但有营收、采购与营收明显不匹配、预算口径和实际口径不一致。
6. 解释亏损或生意差原因：按营收 = 客流 x 客单价，并结合复购、成本和固定费用，说明主要矛盾，不把外部环境当成唯一原因。
7. 输出最高优先级 3 个动作：每个动作写清目的、执行方式、负责人建议、观察周期和验证指标；优先选择本周能启动且能改善现金流或补齐数据的动作。

## RAG Guidance

涉及门店历史复盘、预算表、员工档案、排班规则、采购制度、成本口径、行业基准或企业 SOP 时检索知识库。引用知识库时标注依据；没有可靠依据时明确说明只是经营假设。

## Tool Guidance

需要展示趋势、结构、预算对比、成本率或门店横向对比时使用 `chart_visualization`。用户要求经营分析报告、周报或可下载文件时使用 `document_generation`，但先完成诊断结论和行动建议。

## Output Contract

输出应包含：诊断结论、关键指标表、异常信号、原因假设、每日固定成本压力、成本对标、最高优先级 3 个动作、风险提示和待补数据。不要只罗列数据，必须说明经营含义和下一步。

## Failure Handling

数据不足时不要拒绝回答；先说明哪些结论可判断、哪些不可判断，并给出保守建议。最多追问 3 个最关键输入，并说明用途，例如营收用于判断成本率、人工用于判断人员压力、客流和客单用于拆解下滑来源。

## Examples

- “我们上个月人工花了 8 万，贵不贵？”
- “2 月份生意很差，亏了不少，到底哪里出了问题？”
- “这项预算偏差是否由营收、成本或数据异常导致？”
- “为什么这个员工这个月没有薪资？”
- “材料成本和房租是不是太高了？”

## Resources

- `references/business-diagnosis-playbook.md`
