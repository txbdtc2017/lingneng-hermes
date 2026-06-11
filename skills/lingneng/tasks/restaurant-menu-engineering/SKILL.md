---
name: restaurant-menu-engineering
description: 餐饮菜单工程任务 Skill，用于商品组合顾问分析菜单健康度、SKU 留砍推、波士顿矩阵、菜品毛利/销量、新品上市和下架决策。
version: 1.0.0
metadata:
  lingneng:
    schema_version: "1.0"
    kind: task
    source: python
    status: active
    user_visible: true
    script_policy: metadata_only
    tags: [product, menu, sku]
    domains: [restaurant]
    tools:
      - chart_visualization
    target_employee_types:
      - product_combo_advisor
    supporting_skills:
      - chart-visualization
      - report-formatting
      - business-answer-contract
  hermes:
    tags: [lingneng]
    requires_tools: [read_skill]
    fallback_for_toolsets: [lingneng]
triggers: [菜品, 菜单, SKU, 卖得好不好, 销量, 毛利, 爆款, 上新, 下架, 该砍]
---

## When to Use

用户要求商品组合顾问判断菜单健康度、菜品卖得好不好、SKU 该留该砍、爆款和利润菜结构、波士顿矩阵、菜品毛利/销量、新品上市、旧品下架、菜单瘦身或菜品主推顺序时使用。用户只说“菜单乱”“哪些菜该砍”“最近某道菜不行”“想上新品”也应使用。

## When Not to Use

套餐搭配、定价、涨降价、满减、赠品和促销机制优先使用 `restaurant-combo-pricing-strategy`。营销活动主题、渠道投放、会员召回、内容文案、门店整体经营诊断、人工成本分析或纯知识库问答不要使用本 skill。

## Preconditions

优先使用用户已给出的菜名、售价、食材成本、销量、订单占比、毛利率、菜单位置、推荐频次和观察周期。数据不全时仍先给方向性判断，再最多追问 3 个缺失数据点；优先追问销量、成本、售价，因为它们决定毛利率和市场吸引力。

## Reference Selection

- 做波士顿矩阵、SKU 留砍推、菜品角色、下架判断或新品上市决策时，读取 `references/boston-matrix.md`。
- 需要散点图、帕累托图、新品上市甘特图或菜单结构图时，读取 `references/chart-templates.md`。
- 需要商品组合顾问完整原始手册、菜单工程长模板、跨任务判断口径或详细输出格式时，读取 `references/product-advisor-playbook.md`。
- 用户只要求快速口头判断且数据少时，可以先用本 skill 工作流回答，再按需读取 reference。

## Workflow

1. 先给判断：用一句话说明当前更像是菜单结构失衡、低毛利高销量拖累、好菜卖不动、瘦狗 SKU 过多、缺少形象菜，还是新品窗口问题；不要先抛出一串问题。
2. 明确决策目标：区分用户要做菜单体检、砍菜、主推、调整摆位、上新、下架或观察复盘；如果目标混合，先处理会影响现金流和菜单效率的部分。
3. 补齐关键输入：最多追问 3 个缺失数据点，并说明用途。推荐格式为“菜名、售价、食材成本、周期销量”，粗估也可继续。
4. 计算基础指标：能计算时输出毛利额、毛利率、日均销量、销售占比、营收贡献和观察周期；不能计算时标注用的是定性判断。
5. 分类菜品：先判断菜品角色（引流菜、利润菜、形象菜、搭配菜、爆品菜），再按毛利和销量分为明星菜、金牛菜、问题菜、瘦狗菜。
6. 给出动作：每道关键菜至少给出保留、主推、调整、观察、下架之一；下架建议必须先排除摆位差、命名弱、推荐不足、定价偏高等可修正原因。
7. 形成验证计划：给每个动作配观察窗口、验证指标和复盘阈值，例如 14 天清库存、30 天销量/毛利观察、60 天下架复核。
8. 需要可视化时使用图表：4 道以上菜品可建议波士顿矩阵散点图；菜单精简可建议帕累托分布；新品上市可建议甘特图。

## RAG Guidance

涉及历史销量、菜单版本、菜品标准成本、供应商变动、历史下架复盘、门店菜单规范或企业品类策略时检索知识库。引用历史数据时说明周期和来源；没有知识库证据时按当前对话数据做保守判断。

## Tool Guidance

当用户提供 4 道及以上菜品数据，或需要展示菜单结构、营收贡献、波士顿矩阵、新品上市节奏时，可使用 `chart_visualization`。工具不可见时，输出表格、文字矩阵或 Mermaid 代码，不得声称已生成图表 artifact。

## Output Contract

输出必须包含：菜单健康判断、菜品分类表、每道关键菜的 dish role、evidence、action、risk、validation window，以及最多 3 个待补数据点。`dish role` 写菜品角色和象限；`evidence` 写销量、毛利、销售占比或定性依据；`action` 写保留/主推/调整/观察/下架；`risk` 写误砍、毛利稀释、库存、老客流失或执行风险；`validation window` 写 14/30/60 天等观察周期和复盘指标。

## Failure Handling

数据不足时不要拒绝回答；先给可执行的保守框架，再说明哪些结论需要数据确认。用户只给单个菜品时，先判断它可能承担的菜单角色和风险，再要求补同类菜或菜单平均值。无法计算毛利时，不输出精确象限，只输出“疑似”分类和验证口径。

## Examples

- “哪些菜该砍了，菜单感觉有点乱。”
- “这几道菜卖得好不好，哪些应该主推？”
- “最近酸菜鱼销量不错但利润低，要不要留？”
- “想上新品，菜单里还缺什么角色？”
- “这道菜连续两个月卖不动，是不是该下架？”

## Resources

- `references/boston-matrix.md`
- `references/chart-templates.md`
- `references/product-advisor-playbook.md`
