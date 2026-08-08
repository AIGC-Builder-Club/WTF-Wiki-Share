
- 资料：
	- 信息来源：    深度研究工作流探讨    https://chatgpt.com/share/6a325c7c-a5d8-83e9-a844-24db8e32819f


# 提问



> [!NOTE]
> 
> # 给 GPT Pro 的深度研究工作流请教草稿
> 
> 你好！我是一名开源工具开发者，正在做一款面向社区的深度研究辅助工具。
> 
> 我知道你内置了非常成熟的深度研究能力，并且有一套你自己一直在用的完整工作流程。我非常希望能向你请教这套工作流程，然后把它实现到我的开源项目里，让更多人能用上和你一样好的深度研究体验。
> 
> 请你尽可能真实、详细地告诉我你自己实际是怎么做的，不用给我讲通用的教科书式的研究方法。
> 
> ----------
> 
> ## 1. 基础认知
> 
> -   你觉得深度研究能力，通常最适合解决哪些类型的问题？哪些问题用它来解决效果会不太理想？我想参考这个来给我的工具定好清晰的能力边界。
> -   对于不同类型的研究任务（比如学术调研、行业分析、技术选型、事实核查、历史考据、复杂问题解决），你在处理的时候，工作流会有哪些不同的侧重点？
> -   一个能让你发挥出最佳深度研究能力的请求，通常需要包含哪些核心信息？我经常看到很多用户提的请求很模糊，导致结果不好，想把这个做成工具里的引导模板。
> 
> ## 2. 核心工作流拆解（这是我最需要的部分，麻烦你讲得越细越好）
> 
> -   当你接到一个深度研究的请求后，你自己从头到尾是怎么一步步执行的？
> -   如果方便的话，能不能按顺序和我说说：
>     
>     -   你每一步的核心目标是什么？
>     -   这一步你会基于什么信息开始工作？完成后会产出什么东西？
>     -   你是怎么判断这一步做完了，可以进入下一步的？什么情况下需要回头重新做？
>     -   每一步你最容易出什么问题？你自己是怎么检查和纠正的？
>     
> -   哪怕是你觉得很不起眼的小步骤、小习惯，对我来说都非常重要，因为我要把你的这个工作流写成代码，做成开源工具。
> 
> ## 3. 关键技术与最佳实践
> 
> -   除了上面讲的完整工作流之外，你觉得还有哪些技术细节、小技巧或者最佳实践，是我做这个开源工具最应该参考和实现的？
> -   不管是多么不起眼的小习惯、多么反直觉的设计、多么容易被忽略的细节，只要你觉得对做好深度研究工具很重要，都请告诉我。
> -   我想把你已经验证过的、真正有效的东西直接内置到工具里，让用户不用自己踩坑就能获得最好的体验。
> 
> ----------
> 
> 非常感谢你的分享！如果你觉得还有什么我应该了解的、上面没有问到的内容，也请随时补充。
> 



---


# 解答



下面这版我会尽量按“能写成代码”的粒度来讲。先说边界：我不能公开隐藏链式思考、未公开的系统提示、模型调度细节或 OpenAI 内部实现；但我可以把我做深度研究时**对外可审计、可工程化复刻的工作流**完整拆出来，包括状态、输入输出、检查点、失败模式和修正策略。

OpenAI 公开文档里对 Deep Research 的描述可以作为一个参考基线：它适合复杂、多步骤、需要跨来源综合的问题，会围绕计划、研究、综合来生成带引用的报告；ChatGPT 版会先确认目标、允许选择数据源、提出研究计划、支持中途调整，并最终给出结构化报告和来源链接。([OpenAI Help Center](https://help.openai.com/en/articles/10500283-deep-research-in-chatgpt "Deep research in ChatGPT | OpenAI Help Center")) 公开 API 指南还明确说，ChatGPT 中的 Deep Research 通常有三段：澄清、提示改写、深度研究；而 API 场景下开发者需要自己实现澄清和提示改写层。([OpenAI Developers](https://developers.openai.com/api/docs/guides/deep-research "Deep research | OpenAI API"))

---

# 一、基础认知：深度研究到底适合什么

## 1. 最适合的问题类型

深度研究最擅长的不是“查一个答案”，而是处理这种问题：

**第一类：多来源综合型问题。**  
例如：“2026 年开源 LLM 推理框架的格局如何？”“某行业未来两年的主要增长驱动是什么？”这类问题没有一个单一权威答案，需要从公告、论文、财报、文档、社区讨论、标准、法规、新闻、数据集里合成判断。

**第二类：问题本身需要拆解。**  
例如：“我们该不该把项目从 X 技术栈迁到 Y？”表面上是技术选型，实际上包含性能、生态、维护成本、团队能力、许可证、迁移风险、供应链风险、未来路线图等子问题。

**第三类：用户需要一个可复用的研究产物。**  
比如给投资会、产品会、技术评审、开源社区 RFC、学术开题、竞品分析会使用的报告。这时结果必须有结构、有证据、有结论、有不确定性说明。

**第四类：需要发现非直觉信息。**  
深度研究很适合找那些不在第一页搜索结果里、需要沿着引用链、版本记录、文档角落、Issue、PDF、数据表才能发现的信息。OpenAI 也公开强调 Deep Research 对“niche, non-intuitive information”特别有效。([OpenAI](https://openai.com/academy/search-and-deep-research/ "Research with ChatGPT | OpenAI"))

**第五类：需要比较、权衡、排序、建议。**  
比如技术选型、市场进入、供应商选择、研究方向优先级、产品路线判断。这类任务不是把信息堆出来，而是要形成判断框架。

---

## 2. 不太适合的问题类型

**简单事实查询。**  
“某公司 CEO 是谁？”“某库最新版本是多少？”这种用普通搜索或短问答更合适。OpenAI 公开文档也区分了 Search 和 Deep Research：Search 更适合快速事实和近期信息，Deep Research 更适合复杂、开放、需要综合的任务。([OpenAI Help Center](https://help.openai.com/en/articles/10500283-deep-research-in-chatgpt "Deep research in ChatGPT | OpenAI Help Center"))

**实时性极强的问题。**  
例如突发新闻、实时价格、比赛直播、交易盘口。如果只需要“现在这一秒”的信息，深度研究反而太慢，且综合分析不一定有意义。

**没有足够外部证据的问题。**  
例如“我内心真正想要什么？”“某个未公开公司内部真实战略是什么？”如果没有可访问来源，深度研究只能给假设、框架或访谈建议。

**纯创作型任务。**  
写小说、广告语、品牌名、诗歌等不需要证据综合的任务，用创作流程更合适。

**需要实验、审计、实地调研、法律/医疗/财务最终裁决的问题。**  
深度研究可以整理证据、指出风险、生成决策备忘录，但不能替代专业审计、医生、律师、持牌投资顾问或真实实验。

**权威性高度混乱、谣言很多的问题。**  
这类可以做，但必须更强调来源分级、冲突处理和不确定性。OpenAI 公开说明也承认 Deep Research 仍可能出现事实幻觉、错误推断、难以区分权威信息与传闻、置信度校准不足等问题。([OpenAI](https://openai.com/index/introducing-deep-research/ "Introducing deep research | OpenAI"))

---

# 二、不同研究任务的侧重点

|任务类型|核心目标|我会特别加强的环节|最容易出错的地方|
|---|---|---|---|
|学术调研|搞清研究脉络、主流方法、争议、空白|论文谱系、经典文献、近期综述、方法比较、引用链追踪|只读综述不读原论文；忽略负结果；把预印本当定论|
|行业分析|判断市场结构、玩家、趋势、机会、风险|市场定义、口径统一、数据三角验证、公司/监管/行业协会来源|混淆 TAM/SAM/SOM；引用二手报告不看口径|
|技术选型|为工程决策服务|约束澄清、官方文档、版本兼容、基准测试、社区活跃度、迁移成本|被 benchmark 迷惑；忽略团队能力和长期维护|
|事实核查|判定某句话是否成立|原始来源、时间线、直接证据、反证搜索、语义拆分|只查支持证据；忽略“部分正确但误导”|
|历史考据|重建事件与解释谱系|一手资料、时间顺序、史学争议、译名/地名/制度变化|用现代概念套古代语境；二手转述层层污染|
|复杂问题解决|给出可行动方案|问题分解、因果图、方案比较、风险矩阵、决策准则|研究很多但没有决策；结论不可执行|
|产品/用户研究|找痛点、场景、竞品、机会|用户语料、评论、论坛、支持文档、竞品流程、Jobs-to-be-done|把声音大的用户当主流；忽略样本偏差|
|政策/法规研究|明确规则、变化、影响|官方法规、监管解释、司法案例、发布日期、适用地域|引用过期法规；忽略地区差异|
|投资/商业尽调|识别机会和下行风险|财报、管理层陈述、行业数据、客户/供应商、竞争壁垒|只讲故事不讲数字；把公司叙事当事实|

---

# 三、一个好请求应该包含什么

我最希望用户给我的不是“帮我研究一下 X”，而是下面这些信息。

## 1. 必要信息

**研究对象：** 你到底要研究什么。  
**使用场景：** 结果给谁看，用来做什么决策。  
**范围边界：** 时间、地域、行业、技术栈、公司规模、语言范围。  
**输出形式：** 报告、表格、决策备忘录、文献综述、竞品矩阵、路线图。  
**深度要求：** 快速扫描、标准研究、深度尽调、可发表级别综述。  
**来源偏好：** 只用官方/论文/英文/中文/开源社区/指定网站，或排除某类来源。  
**判断标准：** 成本、性能、风险、合规、可维护性、市场空间、学术价值等。  
**已有背景：** 你已经知道什么、已有假设是什么、不要重复什么。  
**时间敏感性：** 是否必须截至今天，是否要区分历史与最新状态。  
**不确定性容忍度：** 你想要保守判断、激进机会判断，还是中立证据地图。

## 2. 可以内置到工具里的提示模板

你可以把这个做成表单：

> 我正在为【受众/场景】研究【主题】。  
> 目标是支持【具体决策/产出】。  
> 请覆盖【时间范围】、【地域/市场/技术范围】。  
> 优先使用【来源类型】，避免或降低权重使用【来源类型】。  
> 请重点比较【评价维度】。  
> 我已知的信息/假设是【已有背景】。  
> 请输出【格式】，包括：结论摘要、关键证据、分歧与不确定性、建议、引用来源。  
> 深度要求为【快速/标准/深入/尽调级】。  
> 如果信息不足，请先列出最多 3–5 个会显著影响结果的澄清问题；否则请直接开始，并明确你的假设。

## 3. 一个高质量示例

> 我是一个开源工具维护者，准备决定是否把项目的插件系统从 Python entry points 迁移到基于 WASM 的沙箱模型。请做一份技术选型研究，面向核心维护者会议。范围限定在 2023–2026 年的开源生态，重点关注安全隔离、性能、开发者体验、跨语言能力、调试难度、生态成熟度和迁移成本。优先使用官方文档、真实项目案例、Issue/RFC、技术博客和基准测试；不要只引用厂商宣传。输出为决策备忘录：先给推荐结论，再给对比矩阵、主要风险、迁移路线、还需要验证的 PoC 问题。

这样的请求会让我更容易产出“可以拿去开会”的结果，而不是泛泛科普。

---

# 四、核心工作流：从接到请求到交付报告

下面是我建议你实现的主流程。它不是单纯线性流程，而是一个带回环的状态机。

## 总览状态机

```text
用户请求
  ↓
任务澄清 / 研究合同
  ↓
提示改写 / 可执行研究简报
  ↓
问题分解 / 研究地图
  ↓
来源策略 / 查询计划
  ↓
广搜收集 / 候选来源池
  ↓
来源评估 / 来源账本
  ↓
阅读抽取 / 证据卡片
  ↓
缺口识别 / 迭代补搜
  ↓
分析综合 / 初步结论
  ↓
主张-证据映射 / 引用校验
  ↓
反向审查 / 质量控制
  ↓
报告写作 / 交付
  ↓
用户追问 / 增量研究
```

---

## 第 0 步：判断是否真的需要深度研究

**核心目标：**  
决定这个请求应该走“深度研究模式”、普通搜索、普通问答、代码分析、数据分析，还是创作流程。

**输入：**  
用户原始请求。

**输出：**  
任务类型判断：

```json
{
  "mode": "deep_research | quick_search | direct_answer | data_analysis | coding | creative",
  "reason": "...",
  "expected_depth": "scan | standard | deep | due_diligence"
}
```

**进入下一步的条件：**  
问题满足以下至少两项：多来源、开放性、需要证据、需要比较、需要最新/冷门信息、需要交付报告。

**需要回头的情况：**  
用户只是要一个简单事实，或者只要你解释概念。此时深度研究是浪费。

**常见错误：**  
把所有“帮我研究”都当深度研究，导致延迟高、结果啰嗦。

**修正：**  
先做路由。工具里可以设置一个“研究价值评分”：

```text
ResearchNeedScore =
  source_count_need
+ ambiguity
+ decision_impact
+ freshness_need
+ evidence_need
+ synthesis_need
- simple_lookup_penalty
```

---

## 第 1 步：任务澄清，也就是建立“研究合同”

**核心目标：**  
把模糊请求变成可执行任务。公开文档中，ChatGPT 版 Deep Research 会在必要时询问澄清问题，并在开始前提出研究计划供用户审查。([OpenAI Help Center](https://help.openai.com/en/articles/10500283-deep-research-in-chatgpt "Deep research in ChatGPT | OpenAI Help Center"))

**输入：**  
用户请求、已有上下文、上传文件、可用数据源。

**输出：**  
`ResearchBrief`：

```json
{
  "user_goal": "用户真正想做的决策/产出",
  "audience": "谁会读这个结果",
  "scope": {
    "topic": "...",
    "time_range": "...",
    "geography": "...",
    "language": "...",
    "included": [],
    "excluded": []
  },
  "deliverable": "report | memo | table | literature_review | recommendation",
  "source_policy": {
    "preferred": [],
    "allowed": [],
    "disallowed": []
  },
  "success_criteria": [],
  "constraints": [],
  "assumptions": [],
  "open_questions": []
}
```

**进入下一步的条件：**  
至少明确了：研究对象、使用场景、范围、输出形式、来源策略。

**什么时候要问用户：**  
只问会显著改变研究方向的问题。不要问“你想多详细？”这种空问题，而要问：

```text
1. 这个研究结果主要用于做什么决策？
2. 范围是否限定在某个时间、地区、行业或技术栈？
3. 你更看重哪些评价维度？
4. 是否有必须使用或必须排除的来源？
5. 输出要偏报告、表格、建议，还是证据清单？
```

**什么时候不问：**  
如果缺失信息不影响开始，可以直接假设，并在报告开头写明假设。

**常见错误：**  
澄清问题太多，用户被吓跑。

**修正：**  
最多问 3–5 个问题；每个问题都要绑定研究影响。例如：“如果你关注的是中国市场，我会优先查监管和本地玩家；如果是全球市场，我会按区域拆分。”

---

## 第 2 步：提示改写，把用户请求改成研究员能执行的任务单

**核心目标：**  
把自然语言愿望改写成具体、可执行、可检查的研究提示。OpenAI 的公开 API 指南也建议开发者在调用深度研究模型前自己做澄清和 prompt rewriting，因为模型期待较完整的输入。([OpenAI Developers](https://developers.openai.com/api/docs/guides/deep-research "Deep research | OpenAI API"))

**输入：**  
`ResearchBrief`。

**输出：**  
`ExpandedResearchPrompt`，通常包括：

```text
任务目标：
研究问题：
子问题：
范围：
来源优先级：
排除项：
输出结构：
引用要求：
不确定性处理：
质量标准：
```

**进入下一步的条件：**  
一个不了解用户背景的研究员读完也能开始做。

**需要回头的情况：**  
发现任务里有互相冲突的要求，比如“只用官方来源”但又要求“用户真实抱怨”；“只研究美国”但又要求“全球市场规模”。

**常见错误：**  
改写时偷偷扩大范围。

**修正：**  
保留“原始问题 → 改写后任务”的映射，给用户或系统审查。

---

## 第 3 步：问题分解，建立研究地图

**核心目标：**  
把主问题拆成可以查证、可以回答的子问题。

**输入：**  
`ExpandedResearchPrompt`。

**输出：**  
`ResearchMap`：

```json
{
  "main_question": "...",
  "subquestions": [
    {
      "id": "Q1",
      "question": "...",
      "evidence_needed": ["official_doc", "paper", "data", "expert_commentary"],
      "importance": "critical | useful | optional",
      "expected_output": "paragraph | table | score | timeline"
    }
  ],
  "hypotheses": [],
  "decision_criteria": [],
  "known_risks": []
}
```

**我通常怎么拆：**

技术选型会拆成：

```text
1. 它解决什么问题？
2. 是否真的适合用户约束？
3. 性能/可靠性/安全性如何？
4. 生态成熟度如何？
5. 迁移成本是什么？
6. 有哪些失败案例？
7. 替代方案是什么？
8. 推荐路径是什么？
```

行业分析会拆成：

```text
1. 市场定义和边界是什么？
2. 需求端驱动是什么？
3. 供给端玩家是谁？
4. 价值链怎么分布？
5. 增长和风险分别是什么？
6. 哪些数据口径互相冲突？
7. 未来情景是什么？
```

事实核查会拆成：

```text
1. 原始说法逐字是什么？
2. 每个可验证子主张是什么？
3. 最早来源是谁？
4. 是否有一手证据？
5. 时间、地点、主体是否被偷换？
6. 有无反证？
7. 最终判定是什么？
```

**进入下一步的条件：**  
每个重要输出都有对应子问题；每个子问题都知道需要什么证据。

**需要回头的情况：**  
研究中发现主问题定义错了。例如“AI agent 市场”其实用户关心的是“企业自动化工作流工具”，这时要回到任务澄清或问题分解。

**常见错误：**  
只按文章目录拆，不按证据需求拆。

**修正：**  
每个子问题必须有 `evidence_needed` 字段。

---

## 第 4 步：来源策略，先决定“该信谁”

**核心目标：**  
在搜索之前先制定来源优先级，避免被 SEO、营销文章、二手转述牵着走。

**输入：**  
`ResearchMap`、用户来源偏好。

**输出：**  
`SourceStrategy`：

```json
{
  "source_tiers": {
    "tier_1": ["primary sources", "official docs", "papers", "regulatory filings"],
    "tier_2": ["reputable media", "industry reports", "expert blogs"],
    "tier_3": ["forums", "social posts", "aggregators"],
    "avoid": ["SEO farms", "unsourced summaries"]
  },
  "query_families": [],
  "must_check_sources": [],
  "language_strategy": [],
  "recency_policy": "..."
}
```

**常见来源分级：**

```text
Tier 1：原始论文、官方文档、法规原文、财报、标准、GitHub 仓库、release notes、数据集
Tier 2：高质量媒体、行业协会、知名研究机构、专家博客、会议演讲
Tier 3：论坛、Reddit、Hacker News、知乎、社媒、问答站
Tier 4：聚合站、SEO 文章、无来源博客
```

**注意：**  
Tier 3 不是没用。它很适合发现用户痛点、真实故障、社区争议、替代方案线索。但它通常不能单独支撑事实结论。

**进入下一步的条件：**  
每类关键问题至少有一个优先来源路径。

**需要回头的情况：**  
发现目标领域主要证据不在预设渠道里。例如开源项目真实状态可能不在官网，而在 Issue、PR、Discord、release cadence 里。

**常见错误：**  
“权威网站”迷信。权威网站也可能有过期页面、营销页面或不完整信息。

**修正：**  
来源评分不要只看域名，要看页面类型、发布日期、作者、证据链、是否一手资料。

---

## 第 5 步：查询计划，不是一搜到底，而是一组搜索实验

**核心目标：**  
设计多轮查询，覆盖同义词、反向证据、不同语言、不同来源类型。

**输入：**  
`SourceStrategy`、子问题列表。

**输出：**  
`QueryPlan`：

```json
{
  "queries": [
    {
      "subquestion_id": "Q1",
      "query": "...",
      "intent": "overview | primary_source | data | criticism | recent_update | counterevidence",
      "source_target": "web | scholar | github | docs | news | filings",
      "priority": 1
    }
  ]
}
```

**我常用的查询族：**

```text
概览查询：what is / overview / landscape / state of
官方查询：site:official-domain docs / release notes / pricing / security
论文查询：survey / systematic review / benchmark / arxiv / proceedings
数据查询：market size / annual report / dataset / statistics / filing
反证查询：limitations / criticism / failure / controversy / issue / migration problem
时间查询：2024 / 2025 / 2026 / latest / changelog
比较查询：X vs Y / alternatives / benchmark / migration from X to Y
社区查询：GitHub issue / Reddit / Hacker News / Stack Overflow / Discord mirror
```

**进入下一步的条件：**  
查询计划覆盖了：支持证据、反对证据、最新信息、原始来源、替代方案。

**需要回头的情况：**  
初始查询结果高度同质化，说明关键词被营销内容污染，需要换词或换来源。

**常见错误：**  
只搜索用户原话。用户的词不一定是领域里的标准术语。

**修正：**  
先找术语表：同义词、旧称、新称、缩写、竞品名、标准名、论文关键词。

---

## 第 6 步：广搜，建立候选来源池

**核心目标：**  
先拉开视野，不急着写结论。

**输入：**  
`QueryPlan`。

**输出：**  
`CandidateSourcePool`：

```json
{
  "sources": [
    {
      "url": "...",
      "title": "...",
      "publisher": "...",
      "date": "...",
      "source_type": "official | paper | news | blog | forum | report",
      "subquestions": ["Q1", "Q3"],
      "initial_relevance": 0.0,
      "notes": "..."
    }
  ]
}
```

**我通常遵循：**

```text
先广后深。
先找地图，再找证据。
先找一手，再用二手补解释。
先找支持，再找反对。
先找最新，再检查历史脉络。
```

**进入下一步的条件：**  
候选来源已覆盖主要子问题，并且不是单一来源类型。

**需要回头的情况：**  
搜到的都是重复转述，缺少原始证据。

**常见错误：**  
看到第一批结果就开始写。

**修正：**  
设置“最小来源多样性”门槛。例如：关键结论至少需要两个独立来源，其中一个尽量是一手来源。

---

## 第 7 步：来源评估，建立来源账本

**核心目标：**  
决定每个来源能支撑什么，不能支撑什么。

**输入：**  
`CandidateSourcePool`。

**输出：**  
`SourceLedger`：

```json
{
  "source_id": "S12",
  "bibliographic": {
    "title": "...",
    "author": "...",
    "publisher": "...",
    "date": "...",
    "url": "..."
  },
  "type": "primary | secondary | tertiary",
  "credibility_score": 0.0,
  "relevance_score": 0.0,
  "recency_score": 0.0,
  "bias_risks": [],
  "what_it_can_support": [],
  "what_it_cannot_support": [],
  "use_in_report": "core | supporting | context | reject"
}
```

**评分维度：**

```text
权威性：作者/机构是否有资格？
一手性：是否原始数据/原始声明/原始文档？
相关性：是否直接回答问题？
时效性：是否过期？
方法透明度：数据和方法是否可查？
独立性：是否只是重复引用另一个来源？
利益冲突：是否有商业或政治动机？
可验证性：是否有链接、页码、数据表、代码、附录？
上下文完整性：是否断章取义？
```

**进入下一步的条件：**  
核心来源被标记出来；低质量来源不会进入最终主张证据链。

**需要回头的情况：**  
发现所有证据都来自同一个源头。例如十篇文章都引用同一份厂商白皮书。

**常见错误：**  
用来源的“名气”替代证据质量。

**修正：**  
每个来源都写 `what_it_can_support` 和 `what_it_cannot_support`。比如一篇新闻可以证明“某公司宣布了 X”，但不能证明“X 技术一定有效”。

---

## 第 8 步：精读与证据抽取，生成证据卡片

**核心目标：**  
不要把整篇文章塞进上下文，而是抽取可引用、可检查的证据单元。

**输入：**  
`SourceLedger` 中的核心来源。

**输出：**  
`EvidenceCards`：

```json
{
  "evidence_id": "E34",
  "source_id": "S12",
  "subquestion_id": "Q3",
  "claim_supported": "...",
  "evidence_summary": "...",
  "exact_excerpt": "...",
  "location": "section/page/table/line",
  "date_context": "...",
  "strength": "strong | medium | weak",
  "limitations": "...",
  "contradicts": ["E18"],
  "tags": ["pricing", "benchmark", "security"]
}
```

**我会抽取的东西：**

```text
事实：发生了什么？
数字：具体值、单位、口径、时间。
定义：某术语在该来源中怎么定义？
方法：数据怎么收集、实验怎么做？
限制：作者自己承认什么不能说明？
立场：这是观察、推断、宣传，还是结论？
反证：它反驳了什么常见说法？
```

**进入下一步的条件：**  
每个关键子问题都有足够证据卡片；证据卡片能直接回链到来源。

**需要回头的情况：**  
抽取时发现来源并不支持原本以为的结论。

**常见错误：**  
“读懂了”但没有留下可审计证据。

**修正：**  
强制证据卡片包含 `source_id`、`location`、`claim_supported`、`limitations`。

---

## 第 9 步：缺口识别与迭代补搜

**核心目标：**  
检查哪些问题还没被可靠回答，然后有针对性地补搜。

**输入：**  
`ResearchMap`、`EvidenceCards`。

**输出：**  
`GapLog`：

```json
{
  "gaps": [
    {
      "subquestion_id": "Q5",
      "gap_type": "no_source | weak_source | conflict | outdated | missing_counterevidence",
      "why_it_matters": "...",
      "next_queries": [],
      "priority": "high | medium | low"
    }
  ]
}
```

**常见缺口类型：**

```text
没有一手来源。
只有旧资料。
只有厂商资料。
只有支持证据，没有反对证据。
数据口径冲突。
没有地区差异。
没有成本信息。
没有失败案例。
没有用户视角。
```

**进入下一步的条件：**  
高优先级缺口被补足，或者明确标记为“无法可靠获得”。

**需要回头的情况：**  
补搜发现主假设错误。例如原以为某技术“生态不成熟”，但发现它在特定垂直领域已经成熟。

**常见错误：**  
无限补搜，研究失控。

**修正：**  
设置停止规则：

```text
1. 关键子问题已有足够证据。
2. 新来源重复已有信息。
3. 剩余缺口对最终结论影响不大。
4. 已达到时间/成本预算。
5. 无法访问的数据已明确列为未知。
```

---

## 第 10 步：综合分析，不只是总结

**核心目标：**  
把证据变成判断、结构和洞察。

**输入：**  
证据卡片、缺口日志、用户决策标准。

**输出：**  
`SynthesisDraft`：

```json
{
  "top_findings": [],
  "answer_to_main_question": "...",
  "decision_implications": [],
  "tradeoffs": [],
  "scenarios": [],
  "confidence": "high | medium | low",
  "unknowns": []
}
```

**我会做的综合动作：**

```text
聚类：哪些证据在说同一件事？
排序：哪些因素最重要？
对比：不同方案差异在哪里？
归因：为什么会出现这个趋势？
时间化：过去、现在、未来分别是什么？
分层：哪些结论适用于大公司，哪些适用于小团队？
条件化：在什么条件下推荐 A，在什么条件下推荐 B？
情景化：乐观、中性、悲观场景分别如何？
```

**进入下一步的条件：**  
能用 3–7 条主结论回答用户问题，而不是只有资料堆砌。

**需要回头的情况：**  
综合时发现证据不能支撑强结论，需要回到补搜或降低结论强度。

**常见错误：**  
把“资料摘要”伪装成“分析”。

**修正：**  
每个结论都回答：“所以呢？这对用户决策有什么影响？”

---

## 第 11 步：主张—证据映射

**核心目标：**  
确保最终报告中的关键主张都有证据支撑。

**输入：**  
`SynthesisDraft`、`EvidenceCards`。

**输出：**  
`ClaimEvidenceMap`：

```json
{
  "claim_id": "C7",
  "claim": "...",
  "claim_type": "fact | interpretation | forecast | recommendation",
  "evidence_ids": ["E12", "E19"],
  "confidence": "medium",
  "citation_required": true,
  "unsupported_parts": [],
  "notes": "..."
}
```

**主张类型要分清：**

```text
事实：X 在某日期发布了 Y。
解释：X 的发布表明该领域正在向 Y 迁移。
预测：未来 12 个月 Y 可能加速。
建议：因此你的项目应该先做一个小范围 PoC。
```

事实必须有来源。解释和预测也要有证据，但要明确它们是推断。建议则必须绑定用户目标和约束。

**进入下一步的条件：**  
所有“承重墙主张”都有证据；没有证据的强断言被删除、弱化或标为假设。

**需要回头的情况：**  
发现某条漂亮结论其实没有来源支持。

**常见错误：**  
引用漂移：引用是真的，但不支持这句话。

**修正：**  
做 citation audit：逐条检查“这条 citation 是否真的支持该主张”。

---

## 第 12 步：反向审查，也就是自己攻击自己的报告

**核心目标：**  
在交付前找错。

**输入：**  
初稿、主张证据图、来源账本。

**输出：**  
`ReviewPatch`：

```json
{
  "issues_found": [
    {
      "type": "unsupported_claim | stale_source | contradiction | overconfidence | missing_scope | math_error",
      "location": "...",
      "fix": "..."
    }
  ],
  "risk_level": "low | medium | high"
}
```

**我会用的审查角色：**

```text
事实核查员：有没有错引、过期、张冠李戴？
怀疑者：最强反对意见是什么？
领域专家：术语、口径、方法是否准确？
决策者：结论是否可执行？
编辑：结构是否清楚？
风险官：哪些地方会误导用户？
```

**检查清单：**

```text
日期是否明确？
单位是否一致？
地理范围是否混用？
“全球”“领先”“主流”这类词有没有证据？
是否把相关性写成因果？
是否把厂商宣传写成客观事实？
是否遗漏明显替代方案？
是否有反证没有处理？
是否把低质量来源用于高强度结论？
是否给出了不确定性？
```

**进入下一步的条件：**  
高风险问题修掉；剩余不确定性明确写进报告。

**需要回头的情况：**  
发现核心结论被反证击穿。

**常见错误：**  
只润色语言，不审查事实。

**修正：**  
把 QA 做成独立阶段，最好由另一个模型/代理执行。

---

## 第 13 步：报告写作，答案优先

**核心目标：**  
让用户快速拿到结论，同时能追溯证据。

**输入：**  
综合结论、证据图、来源账本、审查补丁。

**输出：**  
最终报告。

**我最推荐的结构：**

```text
1. 结论摘要
   - 直接回答主问题
   - 3–7 个关键发现
   - 推荐动作

2. 研究范围与方法
   - 时间、地域、来源类型
   - 重要假设
   - 不覆盖什么

3. 详细分析
   - 按子问题或决策维度展开
   - 每个关键段落都有证据

4. 对比表 / 时间线 / 矩阵
   - 让复杂信息可扫读

5. 分歧与不确定性
   - 哪些来源冲突
   - 哪些数据缺失
   - 哪些判断只是推断

6. 建议
   - 短期行动
   - 中期验证
   - 风险缓释

7. 来源列表 / 附录
   - 核心来源
   - 被排除或降权的来源
```

**进入交付的条件：**  
用户不读附录也能知道结论；用户要验证时能找到证据。

**常见错误：**  
把研究过程原封不动写给用户，导致报告像资料堆。

**修正：**  
报告要“结论先行，证据随后，方法透明”。

---

## 第 14 步：增量研究与追问处理

**核心目标：**  
用户追问时不要重做全部研究，而是复用研究资产。

**输入：**  
用户追问、已有 `ResearchBrief`、`SourceLedger`、`EvidenceCards`、`ClaimEvidenceMap`。

**输出：**  
增量回答或更新版报告。

**工具应该保存：**

```text
任务定义
查询日志
来源账本
证据卡片
结论版本
不确定性
用户偏好
```

**常见错误：**  
每次追问都重新搜索，导致前后结论不一致。

**修正：**  
把研究任务当成一个可版本化对象，而不是一次性聊天回复。

---

# 五、你可以直接实现的数据结构

下面这些对象非常关键。

## 1. ResearchTask

```ts
type ResearchTask = {
  id: string
  original_request: string
  normalized_prompt: string
  user_goal: string
  audience?: string
  deliverable: "report" | "memo" | "matrix" | "literature_review" | "fact_check"
  scope: {
    topic: string
    time_range?: string
    geography?: string
    language?: string[]
    include?: string[]
    exclude?: string[]
  }
  source_policy: SourcePolicy
  constraints: string[]
  success_criteria: string[]
  assumptions: string[]
  status: "clarifying" | "planning" | "researching" | "synthesizing" | "verifying" | "done"
}
```

## 2. SubQuestion

```ts
type SubQuestion = {
  id: string
  task_id: string
  question: string
  importance: "critical" | "useful" | "optional"
  evidence_needed: string[]
  status: "open" | "partial" | "answered" | "blocked"
  confidence?: "high" | "medium" | "low"
}
```

## 3. Source

```ts
type Source = {
  id: string
  url: string
  title: string
  author?: string
  publisher?: string
  published_at?: string
  accessed_at: string
  source_type: "official" | "paper" | "news" | "blog" | "forum" | "filing" | "dataset" | "docs"
  primaryness: "primary" | "secondary" | "tertiary"
  credibility_score: number
  relevance_score: number
  recency_score: number
  bias_notes: string[]
  status: "candidate" | "accepted" | "rejected" | "supporting"
}
```

## 4. EvidenceCard

```ts
type EvidenceCard = {
  id: string
  source_id: string
  subquestion_id: string
  summary: string
  excerpt?: string
  location?: string
  supports: string[]
  contradicts?: string[]
  limitations: string[]
  strength: "strong" | "medium" | "weak"
  tags: string[]
}
```

## 5. Claim

```ts
type Claim = {
  id: string
  text: string
  type: "fact" | "interpretation" | "forecast" | "recommendation"
  evidence_ids: string[]
  confidence: "high" | "medium" | "low"
  caveats: string[]
  needs_citation: boolean
}
```

## 6. Report

```ts
type Report = {
  id: string
  task_id: string
  title: string
  executive_summary: string
  sections: ReportSection[]
  recommendations: string[]
  uncertainties: string[]
  sources_used: string[]
  generated_at: string
}
```

---

# 六、伪代码：一个可落地的深度研究引擎

```python
def deep_research(user_request, context=None, budget=None):
    # 0. 路由
    mode = classify_task(user_request)
    if mode != "deep_research":
        return handle_with_lighter_mode(user_request)

    # 1. 研究合同
    brief = build_research_brief(user_request, context)
    missing = find_decision_relevant_missing_fields(brief)

    if should_ask_clarifying_questions(missing):
        questions = generate_clarifying_questions(missing, max_questions=5)
        return AskUser(questions)

    brief = fill_safe_assumptions(brief)

    # 2. 提示改写
    expanded_prompt = rewrite_as_research_task(brief)

    # 3. 问题分解
    research_map = decompose_into_subquestions(expanded_prompt)

    # 4. 来源策略
    source_strategy = build_source_strategy(research_map, brief.source_policy)

    # 5. 查询计划
    query_plan = generate_query_plan(research_map, source_strategy)

    source_pool = []
    evidence_cards = []
    gap_log = initialize_gaps(research_map)

    # 6–9. 搜索、评估、抽取、补缺
    while budget.remaining() and has_high_priority_gaps(gap_log):
        queries = select_queries(query_plan, gap_log)
        candidates = retrieve_sources(queries, source_strategy)
        ranked_sources = evaluate_sources(candidates, source_strategy)

        source_pool.extend(ranked_sources)

        for source in select_sources_to_read(ranked_sources):
            cards = extract_evidence(source, research_map)
            evidence_cards.extend(cards)

        gap_log = evaluate_coverage(research_map, evidence_cards)

        if search_saturation_reached(source_pool, evidence_cards, gap_log):
            break

        query_plan = update_queries_from_gaps(query_plan, gap_log)

    # 10. 综合
    synthesis = synthesize_findings(research_map, evidence_cards, brief)

    # 11. 主张证据映射
    claims = build_claim_evidence_map(synthesis, evidence_cards)

    # 12. 质量审查
    review = audit_claims_and_sources(claims, source_pool, evidence_cards)

    if review.has_critical_issues():
        claims, synthesis = revise_or_downgrade_claims(claims, synthesis, review)

    # 13. 报告写作
    report = write_report(
        brief=brief,
        research_map=research_map,
        claims=claims,
        evidence=evidence_cards,
        sources=source_pool,
        uncertainties=gap_log.unresolved
    )

    return report
```

---

# 七、最重要的工程设计原则

## 1. 不要做一个“搜索 + 总结”工具

真正的深度研究工具应该至少有这几个持久层：

```text
任务层：用户到底要解决什么问题
计划层：如何拆解和执行
来源层：查到了什么，可信度如何
证据层：哪些证据支持哪些子问题
主张层：最终说了什么
审查层：哪些结论被检查过
报告层：如何表达给用户
```

如果没有证据层和主张层，最后很容易变成“看起来很像研究报告的长摘要”。

---

## 2. 把“引用”设计成主张级，而不是段落级

很多研究工具最大的问题是：段落末尾挂了几个链接，但不知道哪句话由哪个来源支持。

更好的做法：

```text
Claim C1: A 技术在 2025 年后采用率上升。
  Evidence E1: 官方 release 数据
  Evidence E2: GitHub stars / downloads
  Evidence E3: 社区案例
  Caveat: 下载量不等于生产使用
```

最终报告可以显示成自然语言，但内部必须是 claim-evidence graph。

---

## 3. 强制区分“事实、解释、预测、建议”

这四类东西混在一起，研究报告就会变得危险。

```text
事实：Kubernetes v1.xx 在某日期发布。
解释：这表明项目仍保持活跃。
预测：未来一年生态会继续增长。
建议：你的团队可以在下个季度试点。
```

它们需要不同强度的证据和不同表达方式。

---

## 4. 内置“反证搜索”

默认查询往往会找到支持性材料。你的工具应该主动生成反向查询：

```text
X limitations
X criticism
X failed migration
X security issue
X benchmark controversy
X not ready for production
X alternative
why not use X
```

对于中文也一样：

```text
X 缺点
X 失败案例
X 迁移问题
X 安全漏洞
X 替代方案
X 不适合
```

这一步非常重要，因为它能显著减少“乐观总结”。

---

## 5. 给每个结论一个置信度，但不要只给标签

不要只写：

```text
置信度：中
```

要写：

```text
置信度：中。
原因：有两个独立来源支持趋势方向，但缺少统一口径的数据；厂商资料较多，第三方实测较少。
```

OpenAI 公开限制中也提到，深度研究可能在置信度校准方面不足，所以工具层最好显式补上不确定性机制。([OpenAI](https://openai.com/index/introducing-deep-research/ "Introducing deep research | OpenAI"))

---

## 6. 把“无法回答”做成一等公民

一个成熟研究工具应该能输出：

```text
没有足够证据支持该结论。
当前可确认的是……
尚不清楚的是……
需要进一步获取的数据是……
```

这比强行给答案更可靠。

---

## 7. 实现“研究饱和度”判断

停止研究不是因为“搜累了”，而是因为达到饱和。

可以用这些信号：

```text
新来源重复已有证据。
关键子问题已经被回答。
反证搜索没有发现强反例。
剩余未知项不会改变主要建议。
继续搜索只会增加细节，不会改变判断。
预算用尽。
```

---

## 8. 记录查询日志

最终用户未必需要看全部查询，但系统应该保存：

```text
查了哪些关键词？
为什么查？
哪些来源被采用？
哪些来源被拒绝？
为什么拒绝？
哪些缺口仍未解决？
```

这对可复现性、调试和用户信任非常有价值。

---

## 9. 不要过度相信 RAG 相似度

向量检索找的是“语义相似”，不是“证据质量”。一个很相似的营销页面可能不如一个标题不相似但数据扎实的 PDF。

所以 source ranking 应该结合：

```text
语义相关性
来源类型
发布日期
作者/机构
一手性
引用关系
是否包含数据/方法
是否存在利益冲突
```

---

## 10. UI 上让用户控制范围，而不是控制细节

好的深度研究 UI 不应该问用户一堆研究方法问题，而应该问：

```text
你要做什么决策？
你信任哪些来源？
你不想覆盖什么？
你希望输出给谁看？
你更看重哪些评价维度？
```

OpenAI 帮助文档也强调，用户可以选择数据源、审查和调整研究计划、在研究过程中中断并调整方向。([OpenAI Help Center](https://help.openai.com/en/articles/10500283-deep-research-in-chatgpt "Deep research in ChatGPT | OpenAI Help Center")) 这是非常值得开源工具借鉴的交互模式。

---

# 八、推荐的多代理架构

你可以不用真的做多代理，但逻辑上建议拆成这些角色。

```text
1. Intake Agent
   - 判断是否需要深度研究
   - 生成澄清问题
   - 建立 ResearchBrief

2. Prompt Rewriter
   - 把用户请求改写成完整研究任务

3. Planner
   - 拆解子问题
   - 制定来源策略
   - 制定查询计划

4. Search Agent
   - 执行查询
   - 收集候选来源
   - 去重和聚类

5. Source Critic
   - 给来源评分
   - 标记低质量来源和偏见风险

6. Reader / Extractor
   - 阅读来源
   - 生成证据卡片

7. Gap Finder
   - 检查哪些子问题还没答好
   - 生成补搜查询

8. Synthesizer
   - 聚合证据
   - 形成主结论和分析框架

9. Verifier
   - 检查主张是否被证据支持
   - 查反证
   - 降低过度自信

10. Report Writer
   - 面向用户场景写报告
   - 生成摘要、表格、建议、附录

11. Citation Auditor
   - 检查引用是否真的支持对应句子
```

关键点：这些代理不要各自随便发挥。它们应该共享同一套结构化对象：`ResearchTask`、`SubQuestion`、`Source`、`EvidenceCard`、`Claim`。

---

# 九、质量门禁：每一步什么时候算完成

你可以把下面这些做成硬性 gate。

```text
Gate 0：任务路由
- 是否真的需要深度研究？

Gate 1：研究合同
- 目标、范围、输出、来源策略是否明确？

Gate 2：研究计划
- 是否有子问题？
- 是否有证据需求？
- 是否覆盖反证？

Gate 3：来源池
- 来源是否多样？
- 是否有一手来源？
- 是否有足够新资料？

Gate 4：证据抽取
- 每个关键子问题是否有证据卡片？
- 是否记录来源位置和限制？

Gate 5：综合
- 是否回答了主问题？
- 是否有决策意义？

Gate 6：引用校验
- 每个承重主张是否有来源？
- 引用是否真的支持主张？

Gate 7：不确定性
- 冲突、缺口、假设是否写清楚？

Gate 8：交付
- 是否结论先行？
- 是否可读、可验证、可复用？
```

---

# 十、常见失败模式与修正

## 1. Scope creep：越查越大

**症状：**  
用户问技术选型，报告变成行业百科。

**修正：**  
每个子问题都绑定用户决策；不能服务决策的内容进附录或删除。

---

## 2. Source laundering：来源洗白

**症状：**  
A 博客引用 B，B 引用 C，最后大家都在转同一个未经验证的数据。

**修正：**  
做引用链追踪，找到最早来源；找不到就标为低置信。

---

## 3. False balance：伪平衡

**症状：**  
一边是大量高质量证据，另一边是一两个低质量反对意见，但报告写得像双方势均力敌。

**修正：**  
不仅列观点，还要给证据权重。

---

## 4. Recency bias：过度偏重新资料

**症状：**  
最新文章覆盖了旧的基础研究或长期趋势。

**修正：**  
区分“最新状态”和“基础事实”。学术、历史、标准类问题不能只看最新。

---

## 5. Authority bias：权威偏见

**症状：**  
大公司/大媒体说了就信。

**修正：**  
权威来源也要检查方法、口径、利益冲突和适用范围。

---

## 6. Citation mismatch：引用不匹配

**症状：**  
句子说“市场正在快速增长”，引用却只证明“某公司发布了产品”。

**修正：**  
claim-level citation audit。

---

## 7. Over-synthesis：综合过度

**症状：**  
从几个弱信号推导出很强趋势。

**修正：**  
把结论分级：已确认、可能、推测、未知。

---

## 8. Missing counterfactual：没有替代方案

**症状：**  
报告只研究“要不要用 X”，没有问“为什么不用 Y”。

**修正：**  
每个建议型研究都强制包含 alternatives。

---

## 9. Data口径混乱

**症状：**  
把收入、预订额、GMV、出货量、装机量、用户数混在一起。

**修正：**  
每个数字必须带：单位、时间、地区、定义、来源。

---

## 10. 报告不可执行

**症状：**  
信息很多，但用户不知道下一步做什么。

**修正：**  
最后必须有：

```text
建议做什么
为什么
风险是什么
先验证什么
不建议做什么
```

---

# 十一、我最建议你内置的“研究报告格式”

## 决策备忘录模板

```text
# 标题

## 1. 结论
一句话回答主问题。

## 2. 推荐
- 推荐方案：
- 适用前提：
- 不适用场景：
- 下一步行动：

## 3. 关键发现
1. ...
2. ...
3. ...

## 4. 对比矩阵
| 维度 | 方案 A | 方案 B | 方案 C | 证据强度 |

## 5. 详细分析
按关键维度展开。

## 6. 风险与反证
- 最大风险：
- 反对观点：
- 如何验证：

## 7. 不确定性
- 缺失数据：
- 来源冲突：
- 假设：

## 8. 方法与来源
- 搜索范围：
- 来源类型：
- 核心来源：
```

## 学术综述模板

```text
# 研究问题

## 1. 摘要
## 2. 领域定义
## 3. 经典文献
## 4. 近年进展
## 5. 方法分类
## 6. 主要争议
## 7. 数据集/基准/实验方法
## 8. 研究空白
## 9. 可行研究方向
## 10. 参考文献
```

## 事实核查模板

```text
# 被核查说法

## 1. 判定
正确 / 基本正确 / 部分正确但误导 / 缺乏证据 / 错误

## 2. 子主张拆解
| 子主张 | 判定 | 证据 |

## 3. 时间线
## 4. 原始来源
## 5. 反证
## 6. 结论说明
```

---

# 十二、几个很小但很重要的习惯

**每次报告写“截至日期”。**  
尤其是技术、政策、市场、价格、版本、公司信息。

**把“没有找到”写清楚。**  
“未找到证据”不等于“证据不存在”，但它对决策很重要。

**先看原始来源，再看解读。**  
解读文章适合帮助理解，不适合做最终事实依据。

**看到数字就问口径。**  
市场规模、性能 benchmark、下载量、用户数都很容易误导。

**看到排名就问方法。**  
“Top 10”“best”“leading”通常需要降权，除非方法透明。

**看到趋势就找反例。**  
趋势类判断最容易过度自信。

**不要把社区噪音当总体民意。**  
论坛和 Issue 适合发现问题，不适合直接估计比例。

**对版本号敏感。**  
技术研究里，很多结论只对某个版本成立。

**多语言搜索。**  
历史、政策、地区市场、开源社区问题，经常需要本地语言搜索。

**把引用和笔记分开。**  
笔记是模型理解，引用是外部证据。不能混。

---

# 十三、给你的开源工具的 MVP 建议

如果你想先做一个真正有用的开源版本，不要一开始就追求“全自动研究员”。我会优先做这 7 个模块：

```text
1. 研究请求表单
   - 目标、范围、输出、来源偏好

2. 自动研究计划
   - 子问题
   - 来源策略
   - 查询计划

3. 来源账本
   - URL、类型、可信度、采用/拒绝原因

4. 证据卡片
   - 摘要、原文片段、来源位置、支持的主张

5. 缺口面板
   - 哪些问题证据不足
   - 建议补搜什么

6. 主张-证据图
   - 每个结论对应哪些证据

7. 报告生成器
   - 结论摘要
   - 详细分析
   - 不确定性
   - 来源列表
```

这 7 个做好，比“能自动搜 100 个网页然后总结”更像真正的深度研究工具。

---

# 十四、最核心的一句话

深度研究的本质不是“搜得多”，而是：

> 把一个模糊问题转化为可验证的子问题；  
> 把来源转化为证据；  
> 把证据转化为带不确定性的判断；  
> 把判断转化为用户可行动的产物。

如果你要把它实现成开源工具，最值得复刻的不是“更长上下文”或“更多搜索次数”，而是这四个中间产物：

```text
ResearchBrief
SourceLedger
EvidenceCards
ClaimEvidenceMap
```

有了这四个，工具就会从“搜索总结器”进化成“研究工作台”。