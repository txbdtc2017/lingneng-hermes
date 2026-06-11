---
name: restaurant-combo-pricing-strategy
description: 餐饮套餐定价任务 Skill，用于商品组合顾问设计套餐、菜品搭配、价格带、定价优化、涨降价、满减、赠品和促销机制。
version: 1.0.0
metadata:
  lingneng:
    schema_version: "1.0"
    kind: task
    source: python
    status: active
    user_visible: true
    script_policy: metadata_only
    tags: [product, combo, pricing, promotion]
    domains: [restaurant]
    tools:
      - chart_visualization
      - web_search
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
triggers: [套餐, 搭配, 定价, 涨价, 降价, 满减, 赠品, 促销, 价格]
---

## When to Use

用户要求商品组合顾问设计餐饮套餐、菜品搭配、组合销售、价格带、菜品定价、涨价、降价、满减、赠品、折扣、促销机制、节令菜价格策略或竞品价格对比时使用。用户只说“套餐怎么设计”“这道菜定多少钱”“想搞满减”“价格要不要调”也应使用。

## When Not to Use

菜单健康度、SKU 留砍推、波士顿矩阵、新品是否上架或菜品是否下架优先使用 `restaurant-menu-engineering`。活动主题包装、渠道投放、会员分层、文案生成、门店整体经营诊断、成本会计核算或纯知识库问答不要使用本 skill。

## Preconditions

尽量具备菜品名称、单品价格、食材成本、目标毛利率、当前客单价、订单搭配、目标人群、场景、竞品价格、历史促销效果和活动周期。缺少信息时先用已知数据给出可落地方案，再最多追问 3 个关键输入。

## Reference Selection

- 套餐、搭配、组合销售、套餐命名和套餐结构问题读取 `references/combo-design.md`。
- 定价、涨降价、满减、赠品、折扣、节令菜价格和促销机制读取 `references/pricing-promo.md`。
- 需要套餐结构图、价格区间对比图、活动节奏图或菜单结构图时读取 `references/chart-templates.md`。
- 需要商品组合顾问完整原始手册、套餐和定价跨场景判断口径或详细输出格式时，读取 `references/product-advisor-playbook.md`。

## Workflow

1. 识别目标：判断用户是在提升客单价、提高毛利、降低决策成本、消化库存、引流新客、节日冲量，还是测试涨降价。
2. 建立底线：可行时先计算成本底线、套餐综合毛利率或满减后的最低毛利空间；没有成本时用保守区间并标注风险。
3. 比较锚点：结合当前单品价、客单价、价格心理门槛和竞品/市场价格锚点，判断价格是偏低、合理、可上探还是需要降阻力。
4. 设计组合：套餐优先使用“主菜 + 主食/配菜 + 高毛利饮品/小食”结构；促销优先匹配目标，不做无差别全场打折。
5. 设定价格：套餐价通常参考单品合计的 85%-92%，满减门槛参考客单价的 1.3-1.5 倍，优惠额控制在毛利空间内。
6. 给出执行细节：说明套餐命名、适用人群、上架位置、推荐话术、参与菜品、排除项和与活动/内容/会员协作的边界。
7. 给验证指标：至少包含套餐渗透率、客单价变化、综合毛利率、单点销量蚕食、优惠核销率、复购或差评风险，并设 14/30 天观察窗口。
8. 需要可视化时输出图表建议或代码：套餐体系可用 Mermaid mindmap，价格对比可用图表模板，促销排期可用流程或甘特图。

## RAG Guidance

涉及门店历史订单搭配、客单价、单品成本、套餐销售、促销核销、会员权益、企业价格规则或过往活动复盘时检索知识库。引用数据时说明时间范围和口径；没有内部数据时明确使用经验区间。

## Tool Guidance

只有在需要当前竞品价格、市场价格带、同城同品类菜单信息或近期市场趋势，且 `web_search` 对当前运行环境可见时，才使用联网搜索。需要展示套餐结构、定价区间、促销档位或验证指标时可使用 `chart_visualization`；工具不可见时输出可复制的表格、Mermaid 或计算口径。

## Output Contract

输出必须包含：目标判断、成本底线或缺失说明、价格/竞品锚点、套餐或促销方案、建议价格、预期毛利影响、执行动作、风险、验证指标和观察窗口。套餐方案至少写清组成、单品合计、套餐价、优惠感知、综合毛利率和推荐理由；定价方案至少写清当前价、成本底线、建议价、价格心理和测试策略。

## Failure Handling

缺少成本时，不给“保证不亏”的结论，只给目标毛利率倒推公式和需要补齐的成本项。缺少竞品数据且 `web_search` 不可见时，使用用户提供的市场印象或经验价格带，并提示需要后续校验。促销目标不清时，先按提升客单价给保守方案，再追问目标、客单价和毛利底线。

## Examples

- “套餐怎么设计，这道菜定多少钱？”
- “红烧肉现在 68 元，要不要涨价？”
- “想做一个双人套餐，把客单价拉到 180 元。”
- “满减怎么设才不会亏？”
- “端午节令菜要不要涨价，还是做限定套餐？”

## Resources

- `references/combo-design.md`
- `references/pricing-promo.md`
- `references/chart-templates.md`
- `references/product-advisor-playbook.md`
