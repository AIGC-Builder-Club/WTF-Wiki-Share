
# 《第一篇》（裁剪版）《🚀开发者必看！Codex /goal命令高级技巧保姆级教程：Plan模式\+Spec\-Driven\+自研Skill 三大技巧组合让效率倍增》



原文资料：

- 🚀开发者必看！Codex /goal命令高级技巧保姆级教程：Plan模式\+Spec\-Driven\+自研Skill 三大技巧组合让效率倍增 \- 知乎    https://zhuanlan\.zhihu\.com/p/2035288538678288989



`/goal` 是 OpenAI 在 [Codex CLI](https://zhida.zhihu.com/search?content_id=274291716&content_type=Article&match_order=1&q=Codex+CLI&zhida_source=entity) 0\.128\.0（2026 年 4 月 30 日发布）中新增的一条命令。它不是又一个普通的提示词模板，而是 Codex 内部新增了一整套目标生命周期管理机制——给一个目标，Codex 会自己一轮接一轮往下推进，真正实现无人值守。社区里已经出现连续运行 21 小时、烧掉 9 亿 token 的案例。这篇笔记把我自己踩过的坑、固定下来的工作流、配套的 Skill 全都整理成保姆级教程。



### 一、`/goal` 是什么，以及它为什么重要

`/goal` 是 OpenAI 在 Codex CLI 0\.128\.0（2026 年 4 月 30 日发布）中新增的一条命令。官方更新日志的原话是：

> *Added persisted /goal workflows with app\-server APIs, model tools, runtime continuation, and TUI controls for create, pause, resume, and clear\.*
> 
> 

翻译成大白话就是：`/goal` 不是又一个普通的提示词模板，而是 Codex 内部新增了一整套目标生命周期管理机制。它由四个层面共同构成：

1. 持久化层 — 把目标作为一个独立于对话历史的状态存起来，带状态机（`active` / `paused` / `achieved` / `unmet` / `budget_limited`）

2. App\-server RPC — `thread/goal/{get, set, clear}` 三个接口，让客户端可以读写目标状态

3. 模型工具 — `get_goal`、`create_goal`、`update_goal` 三个工具，让模型可以查询和声明完成，但不能自己暂停/清空/篡改

4. 运行时延续（continuation）\+ TUI — 每一轮空闲时，Codex 会自动注入一段”延续提示词”让模型决定下一步，直到目标达成、被暂停、被清空或者烧到 token 上限才停

这套机制最直观的效果就是：给一个目标，Codex 会自己一轮接一轮往下推进，真正实现无人值守。社区里已经出现连续运行 21 小时、烧掉 9 亿 token 的案例；我自己测试中也跑过几个小时不间断的批量重构任务。

如果你之前听说过 [Ralph Loop](https://zhida.zhihu.com/search?content_id=274291716&content_type=Article&match_order=1&q=Ralph+Loop&zhida_source=entity)（用脚本反复让 agent 跑同一个目标的工作流），`/goal` 就是 OpenAI 把它做进了 Codex 内核里。OpenAI 总裁 [Greg Brockman](https://zhida.zhihu.com/search?content_id=274291716&content_type=Article&match_order=1&q=Greg+Brockman&zhida_source=entity) 在 X 上的原话是：*“codex now has a built in Ralph loop\+\+”*。比起外部脚本驱动的 Ralph Loop，内置版本的优势在于：目标可以跨会话恢复、token 预算是一等公民、暂停/恢复是原生命令，而且不需要每轮重建上下文，产出质量明显更稳。

---

### 二、`/goal` 解决了哪些以前解决不了的问题

理解 `/goal` 价值的关键，是它到底解决了什么以前没办法解决的问题。我归纳为四点：

#### 目标本身的持久化

普通 prompt 是写在 Codex 的对话流里的。一旦上下文超过阈值触发 `/compact`，或者你切换会话，prompt 就可能被压缩、被覆盖、被丢失。`/goal` 不一样，它把”目标”作为独立的 thread 状态存起来，跟对话历史是两回事。所以：

- `/compact` 压缩对话历史，不会破坏 goal 状态

- 关掉终端，下次 `codex resume <id>` 还能续上之前的 goal

- 多天跨度的长任务也能撑住

> 注意一个已知问题：Issue \#19910 报告，如果 `/compact` 发生在一轮模型调用执行的中间，延续提示词不会被重新注入，下一个 agent 可能丢掉目标和审计要求。如果你计划做超长任务，尽量让自动 compaction 落在轮次边界而不是手动压缩。
> 
> 

#### 内置的”完成审计”

这是 `/goal` 最低估的部分，但也是最关键的部分。

每一轮空闲后，Codex 会自动向模型注入一段叫 `continuation.md` 的提示词（源码在 `codex-rs/core/templates/goals/continuation.md`）。这段提示词的核心要求是这样的（直译关键段落）：

> 在判定目标已达成之前，执行一次”完成审计”：
> 
> 

- 把目标重述为具体的交付物或成功标准

- 构建一份提示词到产物的清单，把每一条显式要求、每一个编号项、每一个具名文件、命令、测试、门禁、交付物映射到具体证据

- 检查相关文件、命令输出、测试结果、PR 状态等真实证据

- 不要把代理信号当成完成证据：测试通过、清单填满、verifier 跑成功、写了大量代码 —— 这些只是辅助信号，不能单独作为完成依据

- 把不确定视作未达成；继续验证或继续工作



以及一段非常关键的反偷懒规则：

> 不要依赖你的意图、阶段性进度、已耗费精力、对早前工作的记忆、或一个看上去合理的最终答案，作为完成的证明。只有审计显示目标确实已达成、且没有遗留必需工作时，才能调用 `update_goal` 标记完成。
> 
> 

这套机制是在解决一个具体的痛点：模型在长任务中习惯”sandbag”（早早声称做完然后偷懒）。`/goal` 把这种倾向用机制压住了 —— 但前提是你给的目标必须能被映射成一份清单。

#### Token 预算的软停止

`/goal` 支持设置 token 预算上限。一旦烧到上限，Codex 不会粗暴中断当前轮次，而是注入另一段提示词 `budget_limit.md`，让模型把当前任务收尾：总结已完成的进度、列出剩余工作、给出下一步建议，然后停下。

对于无人值守场景，这意味着即使你设错了预期或者目标比想象中复杂，你也能在第二天打开终端时拿到一份能看懂的进度报告，而不是一堆半成品和没了的 token。

#### 完整的生命周期控制

`/goal` 提供四条 TUI 命令：

注意：暂停/恢复/清空/预算限制状态的转换，模型自己改不了，只能由用户或运行时触发。这是设计上的安全边界 —— 模型唯一能自己做的状态变更是”标记完成”，而且这个动作还得通过完成审计。



---

### 五、`/goal` 提示词的核心心法

我在最初使用 `/goal` 的时候，踩过一个最典型的坑：直接 `/goal` 加一句简短描述就回车走人。结果几个小时回来一看，Codex 跑了一堆事情，但跑的根本不是我要的；甚至有时候会陷入静默卡死状态。

后来我把这个事情想清楚了：`/goal` 对提示词的要求，比普通对话高一个数量级。原因是它的内置审计机制 —— `continuation.md` 要把你的目标映射成一份”提示词到产物”的清单，如果你用的是模糊词（”全部”、”所有”、”彻底”、”清理一下”、”提升一下”），清单根本建不起来，审计就会退化成”测试跑过了就算完成”这种代理信号 —— 然后你就得到一个声称完成、实际跑偏的结果。

所以 `/goal` 真正发挥威力的前提，是你要能写出可被映射成清单的目标。

#### 五段式黄金模板

经过这段时间的实践，我固定下来一套五段式模板，几乎所有 `/goal` 我都按这个写：

```Plain Text
/goal <一句话描述目标>

Scope: <作用范围 — 改哪些文件/子系统/feature 区域，其他不要碰>

Constraints:
- <硬性约束 1 — 比如"不要修改数据库 schema">
- <硬性约束 2 — 比如"保持现有公开 API 不变">
- <硬性约束 3 — 项目类型相关的默认规则>

Done when:
1. <可验证的产物 1 — 引用具体文件名或命令>
2. <可验证的产物 2>
3. <可验证的产物 3>
...

Stop if:
- <机械可识别的停止条件 1 — 比如"需要新依赖">
- <机械可识别的停止条件 2 — 比如"需要修改 MUST NOT 列表中的文件">

Use a token budget of <N> tokens for this goal.
```

每一段的要点：

- Objective：一句话说清要做什么。避开虚词：全部、所有、彻底、improve、optimize、clean up —— 这些词无法映射成清单，会让审计失效。

- Scope：画一条边界。Codex 是会扩散的，你不画它就乱跑。

- Constraints：硬性规则，违反就停。约束一定要”可机械识别”，比如”不动 `project.pbxproj`“就比”不要破坏现有结构”好。

- Done when：验收清单。每一条最好引用一个具体文件路径或者一个具体命令（`npm test`、`pytest -q`、`tsc --noEmit` 都比”测试通过”明确）。

- Stop if：停止条件。这个比 Done when 更重要，它防止 Codex 钻牛角尖或越界。

- Token budget：必给。这是 Codex 唯一一个一等公民的成本治理机制 —— 没设预算 = 没有软停止 = 万一跑飞就只能眼睁睁看着烧 token。

#### 一个具体例子

```Plain Text
/goal 把 src/data/words.json 里的词库扩展到 1000 个唯一词条。

Scope: 只改 src/data/words.json，其他文件不要动。

Constraints:
- 词条 schema 保持不变（id / word / phonetic / meaning / example）
- 不允许重复词条（以 word 字段为准去重）
- 只能用真实的、常见的英语单词，不要生造

Done when:
1. words.json 包含恰好 1000 个唯一词条
2. 所有词条 schema 校验通过（用 tools/validate.js 跑一遍）
3. 在终端输出最终词条数和文件大小

Stop if:
- 需要修改 words.json 以外的任何文件
- 需要新增 npm 依赖
- 出现 schema 校验失败超过 3 次

Use a token budget of 80000 tokens.
```

这个目标可以被审计 —— 每一条 Done when 都对应一个能跑的检查；每一条 Stop if 都是机械可识别的；Scope 把作用面锁死了。这种 goal Codex 跑起来准确率明显不一样。

---

### 六、三种典型工作流

下面是我目前固定下来的三种 `/goal` 用法。从简单到复杂，按任务规模选用。



#### 工作流 C：OpenSpec \+ `/goal` — 适合规格驱动开发

这是最适合 `/goal` 的工作流之一。Spec\-Driven Development（SDD） 的思路是：先把需求写成规格文档（包含 proposal、specs、design、tasks），然后让 AI 严格按规格实现。规格文档天然就是一份审计清单 —— 把它喂给 `/goal`，完成审计能精准地工作。

OpenSpec 是 Fission\-AI 团队开发的开源 SDD 工具（MIT 协议，GitHub 上 37k stars），它的工作方式是这样的：

```Plain Text
You: /opsx:propose add-dark-mode
AI:  Created openspec/changes/add-dark-mode/
     ✓ proposal.md — 为什么要做、改了什么
     ✓ specs/      — 需求和场景
     ✓ design.md   — 技术方案
     ✓ tasks.md    — 实现清单
     Ready for implementation!
```

完整工作流：

##### （此处，我将OpenSpec  换成了  【Kiro单文件版\.md】  的方式）



（是为了GptPro方便进行引用，因为OpenSpec需要命令行交互、而我抽取出来的【Kiro单文件版\.md】  类似于Skill直接读取  即可。）



##### 用 `/goal` 执行规格

规格文档生成完后，在 Codex 里：

```Plain Text
/goal 严格实现 openspec/changes/add-cohere-rerank/ 中描述的变更。

First action: 先读 proposal.md / specs/ / design.md / tasks.md / AGENTS.md 这五个文件，
报告每个文件的字数和关键章节标题，等我确认后再开始实现。

Scope: design.md 里的 "MUST NOT modify" 列表严格遵守。

Constraints:
- AGENTS.md 中的所有 iron rules 不可违反
- 不允许新增 npm 依赖
- 镜像现有 4 个 Rerank provider 的代码风格

Done when:
1. tasks.md 中的每一项都打勾，引用对应文件路径
2. 每条 SHALL 都有对应的通过测试，引用测试名
3. 每个 GIVEN/WHEN/THEN 场景都有集成测试覆盖
4. `npx tsc --noEmit` 退出码 0
5. `npm test` 退出码 0，粘贴汇总输出
6. README.md 在 provider 表格里加上新一行
7. CHANGELOG.md 在 Unreleased 段加条目

Stop if:
- 任何任务需要修改 MUST NOT 列表中的文件
- SHALL 之间出现冲突（暂停，让我决定）
- 需要 npm install 新依赖
- 现有 Rerank provider 测试出现失败

Use a token budget of 120000 tokens.
```

注意第二行的 First action：这是个非常关键的小技巧。它强制 Codex 在动手前先把规格文件全部读一遍并向你报告确认 —— 防止 Codex 用 `@filename` 等不可靠引用方式假装”知道”了规格，实际上没读全。

这种工作流跑出来的产物质量最稳。我自己测试中，中等规模的 feature（类似新增一个 provider 这种 200\~400 行的改动）基本都能一次跑通，跑完直接是个能 review 的 PR。



---

### 八、几个非常容易踩的坑

这些是我自己踩过、或者社区在 GitHub Issue 里报告过的坑。直接列出来，贴在显示器旁边比什么都管用。

#### 坑 1：Plan 模式下 `/goal` 不延续

现象：UI 上显示 “Goal active”，但 Codex 不会自己往下推进，看上去像卡死了。

原因：Issue \#20656。源码里 `should_ignore_goal_for_mode(mode) -> mode == ModeKind::Plan`。Plan 模式下 goal 延续被静默跳过。

对策：用 `/plan` 做规划时不要同时启动 `/goal`。规划完先退出 Plan 模式（`Shift+Tab`），再下 `/goal`。

#### 坑 2：中途 `/compact` 把 goal 上下文搞丢

现象：跑了一段时间，模型突然好像”忘了”目标的细节，开始做不相关的事，或者过早声称完成。

原因：Issue \#19910。如果 `/compact` 发生在一轮模型调用执行的中间，延续提示词不会被重新注入，后续 agent 丢掉目标和审计要求。

对策：长任务不要手动 `/compact`。设一个相对宽松的 token 预算，让自动 compaction 落在轮次边界上。

#### 坑 3：第一条消息就发 `/goal`，之后 resume 列表里找不到这个会话

现象：`codex resume` 列表、Codex Desktop 的 recents 里都看不到这个 thread，但 thread 本身没丢，知道 ID 还能打开。

原因：Issue \#20792。`/goal`\-first 的 thread 在列表里被遗漏了。

对策：新 thread 第一条消息别用 `/goal`。先随便发一句话，比如 “Working on the OAuth migration goal”，再用 `/goal`。

#### 坑 4：目标里出现”全部 / 所有 / 彻底 / improve”

现象：跑了几个小时回来，声称做完了，但你一看实际改动只是边边角角，核心问题没动。

原因：这些词没法被 `continuation.md` 映射成清单，审计退化成”测试跑过 = 完成”。

对策：换具体的数字或可验证的状态。”修 5 个真实可复现的 bug”、”覆盖 README 列出的 3 条用户路径”、”`pytest` 0 失败 0 跳过” —— 这些都比”修复所有 bug”强一万倍。

#### 坑 5：不设 token 预算

现象：任务跑飞，token 烧光也没人提醒，等回来一看账单不对劲。

对策：永远设 token budget。`Use a token budget of <N> tokens for this goal.`。烧到上限会触发软停止，让模型把工作收尾，而不是裸停。

#### 坑 6：破坏性操作不加保护

现象：让 Codex 做迁移，跑着跑着把数据库 schema 改了 / 把不该删的文件删了。

对策：破坏性操作不要用 `/goal`。必须用的话，Constraints 里明确写”不要执行 `rm -rf`“、”不要修改数据库 schema”、”任何 destructive migration 暂停问我”，并且把对应内容也写进 Stop if。

---

### 九、控制命令速查

状态标识：

- `pursuing` / `active` — 正在自主推进

- `paused` — 被手动暂停

- `achieved` / `complete` — 完成审计通过，目标达成

- `unmet` — 未达成

- `budget_limited` — token 预算耗尽，软停止中

---

### 十、启动前 checklist

每次发 `/goal` 之前，过一遍这个清单：

* [ ] 对项目的上下文我先聊过一轮了吗？（背景、关心的模块、已排除的方向、AGENTS\.md / CLAUDE\.md 是否已读）

* [ ] 我的目标可以被映射成一份清单吗？

* [ ] 验收标准是具体数字 / 可验证状态，还是”全部 / 所有 / 彻底”这种虚词？

* [ ] Stop if 段写了吗？它能不能机械可识别？

* [ ] Token budget 设了吗？

* [ ] 这个任务真的需要 `/goal` 吗？（单轮能干完的别用）

* [ ] 我现在不在 Plan 模式吧？

* [ ] 这是 thread 的第一条消息吗？如果是，先发一条非 `/goal` 消息再说

跑起来之后：

* [ ] 第一轮输出对得上我的目标吗？对不上立刻 `/goal pause`，补上下文，再 `/goal resume`

* [ ] 中间需要的话用 `/goal` 查进度

* [ ] 长任务不要手动 `/compact`

* [ ] 重要节点考虑挂 hook（自动 commit、自动跑测试）

---

### 十一、一些更宏观的观察

最近半年，prompt 写法明显在变化：

- 以前 —— 一步一步指挥（”先做 A，再做 B，然后 C”）

- 现在 —— 声明结果（”我要这个，完成标准是 X、Y、Z，达到 X / Y / Z 才算完成”），然后让 Agent 自己规划

`/goal` 是这个方向走得最远的产物之一。它把”过程指挥”压到最低、把”结果声明”提到最高，然后用一套内置审计机制保证模型不偷懒。

但反过来，这也提高了对”会写需求”的要求。模型越来越能干，但它干得好不好，反过来更依赖你能不能把”到底要啥”说清楚。会写需求这件事，正在重新变成稀缺技能。

以前 prompt 糊一点没事，反正它也只跑几秒钟；现在它能跑一整天，你那条糊掉的 goal，换来的就是一整天的糊产出。

`/goal` 的真正价值不在于”它能跑一整天”，而在于它把”AI 真的能替你跑一整天”这件事，从一个需要外部脚本 \+ 反复试错的工程，变成了一条可以直接在终端里下的命令。剩下的事，是把目标写清楚。

---

Tags: AGI · AIGC · AI 编程 · Claude · Claude Code · Codex · goal · OpenAI · OpenSpec · Ralph Loop · Spec\-Driven

Categories: LLMs



