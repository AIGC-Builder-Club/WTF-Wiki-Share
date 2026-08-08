

# 《第二篇》KiroFold Single Spec，Kiro单文件版.md



参考资料：

- OpenSpec 和 KeroSpec 的单文件版本。 https://chatgpt\.com/share/6a30aaa7\-3364\-83ee\-85c2\-a26aca076abe \| Notion    https://app\.notion\.com/p/OpenSpec\-KeroSpec\-https\-chatgpt\-com\-share\-6a30aaa7\-3364\-83ee\-85c2\-a26aca076abe\-643b981cd08a4f3f95646172e0232020



`````````Plain Text
# KiroFold Goal Spec: <Goal Name>

Goal编号: <kebab-case-goal-name>  
Status: Draft | Ready | Running | Paused | Done | Budget-Limited | Failed  
最近更新时间: <YYYY-MM-DD>  

---

## 0. Goal Contract

### 0.1 Goal

<用一段话说明本次目标。必须是结果声明，不能只是过程指令。>

Example:

实现 <某一capability> so that <user/system> can <有某些输出或结果>, while preserving <important existing behavior>.

### 0.2 最终交付物

仅当以下交付物全部存在时，此目标才算完成：

- De1: <具体产物，例如某个功能、接口、页面、测试、文档>
- De2: <具体产物>
- De3: <具体产物>

### 0.3 成功标准 Success Criteria

当满足以下条件时，目标视为成功：

- SC1: <可验证成功标准>
- SC2: <可验证成功标准>
- SC3: <可验证成功标准>

避免使用模糊的成功标准，例如：

- 改进 improve
- 优化 optimize
- 做得更好 clean up
- 做得更好 make it better
- 处理所有情况 handle everything

应该改用可观察、可验证的标准，例如：

- 命令 X 通过 ； command X passes
- 文件 Y 包含行为 Z ； file Y contains behavior Z
- API A 在条件 C 下返回 B ；API A returns B under condition C
- 测试 T 覆盖需求 R ； test T covers requirement R
- 旧行为 O 仍然正常工作 ； old behavior O still works

### 0.4 不纳入目标的 Non-Goals

本次目标明确不包括：

- NG1: <明确不做什么>
- NG2: <明确不做什么>
- NG3: <明确不做什么>

### 0.5 停止条件 Stop If

遇到以下情况时应停止并汇报，而不是继续执行：

- (仅为个例举例)STOP1: <机械可识别的停止条件>
- (仅为个例举例)STOP2: <缺少权限 / 缺少文件 / 测试环境不可用 / 需求冲突>
- (仅为个例举例)STOP3: <继续会导致大范围重构、破坏兼容性、删除数据、修改公共 API>

停止后应汇报：

- 已完成的内容 what was completed
- 被阻塞的内容 what is blocked
- 具体证据 exact evidence
- 最安全的下一步行动 safest next action

### 0.6 预算** **Budget

软预算 Soft budget:

- Token / time / iteration budget: <budget>
- Maximum scope expansion: <none / limited to X>
- Maximum risk allowed: Low | Medium | High

当预算即将耗尽时，应输出交接摘要，而不是开始新的高风险工作。

---

## 1. Context

### 1.1 背景说明

<说明为什么要做这个 goal。只写和本次目标直接相关的信息。>

### 1.2 相关 Relevant Files / Areas

| Path / Area | Why It Matters | Expected Change |
|---|---|---|
| `<path>` | <作用> | read / modify / add / avoid |
| `<path>` | <作用> | read / modify / add / avoid |
| `<path>` | <作用> | read / modify / add / avoid |

### 1.3 需要保留的现有行为

以下行为必须保持不变：

- INV1: <不能破坏的行为>
- INV2: <不能破坏的行为>
- INV3: <不能破坏的行为>

### 1.4 Known Constraints约束

- CON1: <技术约束，例如不能引入新框架>
- CON2: <兼容性约束，例如不能改 public API>
- CON3: <测试 / 部署 / 数据 / 性能约束>

---

## 2. 需求

保持需求【清晰、可拆分】、稳定且可测试。

### Rqmt1 — <需求名称>

The system shall <required behavior>.

验收标准 Acceptance Criteria:

- AC1.1: WHEN <event>, THE SYSTEM SHALL <response>.
- AC1.2: IF <condition>, THE SYSTEM SHALL <behavior>.
- AC1.3: WHILE <state>, THE SYSTEM SHALL <guarantee>.

所需证据：

- <test / command / file / manual check>

优先级Priority: Must | Should | Could

---

### Rqmt2 — <需求名称>

The system shall <required behavior>.

验收标准：

- AC2.1: WHEN <event>, THE SYSTEM SHALL <response>.
- AC2.2: IF <condition>, THE SYSTEM SHALL <behavior>.

Evidence Required:

- <test / command / file / manual check>

优先级Priority: Must | Should | Could

---

### Rqmt3 — 【兼容性/回归】需求

The system shall preserve <existing behavior>.

（注意：这里的回归，不是指【量化回测】。）

验收标准 Acceptance Criteria:

- AC3.1: WHEN <old supported scenario>, THE SYSTEM SHALL <old expected result>.
- AC3.2: IF <existing input/config>, THE SYSTEM SHALL NOT <forbidden regression>.

所需证据：

- <regression test / manual check / command>

优先级Priority: Must

---

## 3. Design设计

Design to prevent the agent from guessing wrong.

### 3.1 实现策略

The implementation should:

- <main approach>
- <主要方式>
- <main approach>

The implementation should avoid:

- <unwanted approach>
- <不想要的方式>
- <unwanted approach>

### 3.2 计划中的变更范围

| Area | Planned Change | Related Requirement |
|---|---|---|
| `<path/module>` | <change> | R1 |
| `<path/module>` | <change> | R2 |
| `<test path>` | <test change> | R1, R3 |

### 3.3 Data / API / Interface 说明

Fill what matters.

Data changes:
- <none / describe>
API changes:
- <none / describe>
UI changes:
- <none / describe>
Config / env changes:
- <none / describe>
Migration required:
- No
- Yes: <migration notes>

### 3.4 Error&Edge Case 错误与边界情况处理 

系统必须处理：

- Eec1: IF <failure condition>, THEN <safe behavior>.
- Eec2: IF <invalid input>, THEN <error / fallback / no-op>.
- Eec3: IF <external dependency unavailable>, THEN <safe behavior>.

### 3.5 【回滚/恢复】路径

应能够通过以下方式回滚：

- <revert commit / disable flag / restore file / remove adapter>
- <data rollback note, if any>

---

## 4. 任务计划 Task Plan

The agent should execute tasks in order unless a task is blocked.

只有在填写完其 Evidence证据 部分后，任务才能被勾选完成。

---

以下均为样例的【个例示例】，非固定流程。
但需要遵从以下格式：
- 1、特别是【CheckBox】的未开始、进行中、已完成，这样的形式。

### [ ] Task1 — 检查当前行为

状态Status: [ ] Todo  
覆盖范围Covers: Context, Rqmt3  
依赖项Depends On: none  

执行Do:

- [ ] 检查相关文件
- [*] 识别当前入口点
- [-] 识别现有测试
- [x] 确认不变条件

证据Evidence:

- Files inspected:
  - `<path>`
- Findings:
  - <finding>
- Existing tests:
  - <test or none>
- Risk:
  - <risk or none>

---

### [ ] Task2 — 实现CoreChange

Status: [ ] Todo  
Covers: Rqmt1  
Depends On: Task1  

Do:

- [ ] implement the smallest core behavior for Rqmt1
- [ ] keep compatibility intact
- [ ] avoid unrelated refactors

Evidence:

- Files changed:
  - `<path>`
- Behavior implemented:
  - <behavior>
- Validation:
  - <test / command / manual check>
- Risk:
  - <risk or none>

---

### [ ] Task3 — Implement Secondary / Edge Behavior

Status: [ ] Todo  
Covers: Rqmt2, error behavior  
Depends On: Task2  

Do:

- [ ] implement secondary behavior
- [ ] implement edge cases
- [ ] implement failure behavior

Evidence:

- Files changed:
  - `<path>`
- Behavior implemented:
  - <behavior>
- Validation:
  - <test / command / manual check>
- Risk:
  - <risk or none>

---

### [ ] Task4 — Add or Update Tests

Status: [ ] Todo  
Covers: Rqmt1, Rqmt2, Rqmt3  
Depends On: Task2, Task3  

Do:

- [ ] add tests for new behavior
- [ ] add regression checks for preserved behavior
- [ ] add failure / edge checks where practical

Evidence:

- Test files:
  - `<path>`
- Commands run:
  - `<command>`
- Result:
  - <pass / fail / partial>
- Gaps:
  - <gap or none>

---

### [ ] Task5 — Documentation / Notes

Status: [ ] Todo  
Covers: final deliverables  
Depends On: Task4  

Do:

- [ ] update docs only where useful
- [ ] add inline comments only where they prevent future mistakes
- [ ] update this spec’s Final Audit section

Evidence:

- Files changed:
  - `<path>`
- Notes:
  - <summary>

---

## 5. 完成情况审计 Completion Audit

在将目标标记为完成之前，执行此审计。

Do not mark complete based only on:

- 意图 intent
- 已投入的努力 effort spent
- 已修改文件的数量 number of files changed
- 测试通过但未映射到需求 tests passing without requirement mapping
- 对先前工作的记忆 memory of earlier work
- 一个看似合理的最终答案 a plausible final answer

完成必须有与【每项交付物和成功标准】映射对应的证据。

---

### 5.1 交付物审计 Deliverable Audit


| 交付物 | 证据 | 状态 |
|---|---|---|
| De1 | <file / command / test / behavior> | Pending |
| De2 | <file / command / test / behavior> | Pending |
| De3 | <file / command / test / behavior> | Pending |

### 5.2 需求审计 Requirement Audit

| 需求 Requirement | 验收标准 Acceptance Criteria | 证据 Evidence | Status |
|---|---|---|---|
| Rqmt1 | AC1.1, AC1.2 | <test / command / file> | Pending |
| Rqmt2 | AC2.1, AC2.2 | <test / command / file> | Pending |
| Rqmt3 | AC3.1, AC3.2 | <regression evidence> | Pending |

### 5.3 回归审计 Regression Audit

（注意：这里的回归，不是指【量化回测】。）

受保护的行为仍然正常工作：

- [ ] INV1 已通过 <证据> 验证
- [ ] INV2 已通过 <证据> 验证
- [ ] INV3 已通过 <证据> 验证

### 5.4 最终完成标准 Final Done Criteria

This goal is Done only when:

- [ ] 所有 Must（必须）需求均已实现
- [ ] all Must acceptance criteria have evidence
- [ ] 所有交付物均已存在
- [ ] all preserved behaviors are verified
- [ ] 没有未解决的“Stop If”条件
- [ ] 不需要任何【仅存在于聊天中的隐藏假设】即可理解结果
- [ ] this file contains 【足够的说明】 for another agent to 【继续工作或进行审查】

最终结果 Final Result:

Done | Done with Accepted Risks | Budget-Limited | Failed

Accepted Risks:

- <risk or none>

---

## 6. 运行备注 Run Notes

使用此部分在长时间运行、`/compact`、恢复会话或由其他代理接手时保留状态。
Use this section to preserve state across 【long runs, `/compact`, resume, or another agent taking over】.

### RUN-001 — <YYYY-MM-DD> — <short title>

Status:
Done | Partial | Blocked | Reverted

涉及的任务 Tasks touched:
- <Task1/Task2/Task3/Task4/Task5>

Files inspected:
- `<path>`

Files changed:
- `<path>`

What changed:
- <change>
- <change>

Validation:
- <command / test / manual check>
- Result: <result>

Blocked by:
- <none / blocker>

Next safe action:
- <next task>

Notes:
- <important context for resume>

---

## 7. 交接摘要 Handoff Summary

在【暂停、达到预算上限或提前停止】时填写此部分。

当前状态 Current state:
- <what is complete>
- <what is partial>
- <what is not started>

目前的证据 Evidence so far:
- <evidence>
- <evidence>

Known risks:

- <risk>
- <risk>

Recommended next action:

- <specific next task>

Do not continue until:

- <condition, if any> 
`````````



