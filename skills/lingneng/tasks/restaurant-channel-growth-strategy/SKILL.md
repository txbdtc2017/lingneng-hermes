---
name: restaurant-channel-growth-strategy
description: 餐饮渠道增长任务 Skill，用于活动主题策划师设计拉新渠道、竞品营销监控、大众点评/美团/抖音/小红书策略、KOL达人合作、裂变老带新、预算分配和ROI预估。
version: 1.0.0
metadata:
  lingneng:
    schema_version: "1.0"
    kind: task
    source: python
    status: active
    user_visible: true
    script_policy: metadata_only
    tags: [marketing, growth, channel, kol]
    domains: [restaurant]
    tools:
      - web_search
      - chart_visualization
      - document_generation
    target_employee_types:
      - marketing_planner
    supporting_skills:
      - chart-visualization
      - document-generation
      - report-formatting
      - business-answer-contract
  hermes:
    tags: [lingneng]
    requires_tools: [read_skill]
    fallback_for_toolsets: [lingneng]
triggers: [拉新, 引流, 获客, 竞品, 对手, KOL合作, 达人合作, 达人筛选, KOL投放, 大众点评, 美团, 抖音, 小红书, 裂变, 老带新, ROI]
---

## When to Use

用户要求活动主题策划师设计餐饮拉新渠道、获客路径、引流策略、竞品营销监控、大众点评/美团/抖音/小红书平台运营、KOL 达人探店合作、裂变老带新、渠道预算分配、获客成本或 ROI 预估时使用。用户说“附近对手最近在搞什么”“达人合作怎么做”“大众点评怎么运营”“小红书和抖音哪个更适合”“裂变活动怎么设计”“预算应该投到哪些渠道”都应使用。

## When Not to Use

单个节日活动主题、营销日历、活动机制和执行排期应交给 `restaurant-campaign-planning`。最终发出去的小红书正文、短视频脚本、社群话术、海报标语、评价回复或 KOL Brief 应交给 `marketing-copy-generation`。需要按会员 RFM、沉睡天数、消费频次或会员生命周期做分层召回时，应交给 `member-repurchase-campaign`。

## Preconditions

尽量确认餐厅品类与定位、商圈、当前主要客源、已有平台资产、评分与评价情况、私域规模、历史投放数据、竞品名单、预算范围、目标周期和希望拉新的客群。信息不足时先输出渠道优先级假设，再最多追问 3 个会影响预算和 ROI 的关键输入。

## Reference Selection

用户需要活动主题策划师完整原始手册、渠道增长长 SOP、竞品监控模板、达人合作详细流程、裂变老带新玩法或 ROI 估算格式时，读取 `references/channel-growth-playbook.md`。只需快速渠道优先级判断时先按本 skill 工作流回答。

## Workflow

1. 识别渠道目标：判断本次核心是拉新、提升平台曝光、竞品应对、KOL 种草、私域裂变、团购核销、口碑修复还是预算优化。
2. 盘点当前资产：检查大众点评/美团页面、评分评价、团购套餐、抖音团购、小红书内容、私域社群、达人合作记录和可用预算。
3. 判断餐厅阶段：按新店开业、成长期、成熟期或节点冲量期选择渠道组合；中高端餐饮优先看获客质量和品牌调性，不只看曝光量。
4. 推荐 1-3 个优先渠道：给出每个渠道的选择理由、适合客群、核心动作、启动成本、见效周期和预期风险；其余渠道说明暂缓或作为辅助的原因。
5. 设计渠道闭环：把内容种草、点评决策、私域预约、到店体验、评价沉淀和复购运营串成路径，避免渠道各做各的。
6. 定义预算和指标：拆分平台运营、达人合作、内容制作、投流、物料和机动预算；输出曝光、收藏、咨询、预约、核销、到店新客、CAC、ROI 等指标。
7. 给出风险控制：说明平台规则风险、低价损伤品牌、达人粉丝不匹配、评价诱导违规、虚假裂变、承接不足和数据归因不清的控制办法。
8. 收敛下一步：明确本周可启动动作、负责人建议、所需素材、监测周期和复盘口径。

## RAG Guidance

涉及门店历史渠道数据、会员来源、平台账号资产、达人合作记录、品牌调性、竞品清单、预算审批、过往 ROI 或企业 SOP 时检索知识库。没有历史数据时用行业常识给保守区间，并明确需要补充的数据。

## Tool Guidance

只有当 `web_search` 可见，且需要当前公开平台规则、当期大促政策、竞品近期公开动态、当地达人生态或最新平台玩法时，才使用 `web_search`。搜索结果用于提炼判断，不逐条堆砌。需要展示渠道优先级、预算结构、获客成本或 ROI 对比时可使用 `chart_visualization`。用户要求形成正式渠道增长方案或竞品监控报告时可使用 `document_generation`。

## Output Contract

输出应包含：渠道目标判断、当前资产盘点、优先渠道 1-3 个、推荐理由、预算拆分、关键指标、执行节奏、风险控制和待补数据。竞品监控应包含竞品动作表、威胁判断、差异化机会和应对动作。KOL 策略应包含达人类型、筛选标准、预算组合、内容方向和效果评估指标。

## Failure Handling

竞品名称不明确时先按“同商圈同品类”给监控框架，并请求用户补充 3-5 家重点竞品。预算未知时给低、中、高三档渠道组合。平台数据缺失时先从页面基础建设和口碑沉淀做起，不直接建议高额投流。

## Examples

- “附近竞争对手最近在搞什么，达人合作怎么做。”
- “我们想拉新，大众点评、美团、抖音、小红书哪个先做？”
- “预算 2 万，怎么分配到 KOL、投流和私域裂变？”
- “新店开业前三个月的渠道获客怎么排？”
- “老客带新客的裂变机制怎么设计才不掉价？”

## Resources

- `references/channel-growth-playbook.md`

最终内容 Brief 和发布正文交给 `marketing-copy-generation`。
