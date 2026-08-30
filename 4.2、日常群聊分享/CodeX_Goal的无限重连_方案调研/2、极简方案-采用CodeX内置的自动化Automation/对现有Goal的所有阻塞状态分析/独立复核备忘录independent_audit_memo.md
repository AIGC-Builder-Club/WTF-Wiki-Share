# Codex Goal blocked / paused 独立复核备忘录

复核日期：`2026-07-28`  
复核对象：本机 Codex 会话日志、Goal 工具结构化结果、`goals_1.sqlite` 当前快照，以及监控侧 `lark-cli` 认证日志。  
目的：严格区分 Goal 的业务状态、上游 T0 故障、Thread 中断，以及监控侧通知故障。

## 一、结论

1. 在允许作为权威状态证据的序列化记录中，确认 **21 个状态事件，分布于 15 个 Thread：10 个 `blocked`，11 个 `paused`**。
2. 另有 **2 个 SQLite 当前快照关联事件**：1 个 `blocked` 与同毫秒 HTTP 429 高置信关联，1 个 `paused` 与明确中断关联。二者没有序列化的目标状态转换，必须单列，不能加入上述 21 个确认事件。
3. 10 个确认 `blocked` 中，3 个是 T0：2 个 HTTP 503，以及 1 个经用户明确确认的上游模型部署/路由 HTTP 404。其余 7 个是审批、配置或目标地址问题。
4. `Model ... is not supported by any configured account in this group` 这次 404 已由用户确认属于上游部署/路由故障，因此应按 T0 执行 `/goal resume`，不应建立 P1 人工告警。
5. `keychain not initialized` 不是任何 Goal 的根因。它发生在监控把上述 404 错误误分类后尝试发送飞书告警时，是第二层、监控侧的凭据读取故障。
6. “环境恢复后发送成功”这一旧表述不成立。证据只支持：`04:56:58+08:00` 那一次进程成功读取凭据并取得 HTTP 200；约 20 分钟后同类读取再次失败，因此不存在已被证明的持续恢复。

## 二、复核口径与覆盖

- 扫描 363 个 live session JSONL、66 个 archived JSONL，共 429 个文件；全部可解析。
- 共读取 16,754 条顶层 `thread_goal_updated`：`active=16,720`、`complete=12`、`paused=20`、`blocked=2`。
- 核对 360 次直接 `get_goal` / `update_goal` 调用，其中 356 次存在成功且可解析的结构化输出；另核对 75 次由 `exec` 包装的 Goal 调用，并按 `call_id` 关联请求与输出。
- 只接受以下权威证据：顶层 `thread_goal_updated`；成功的结构化 `get_goal` / `update_goal` 输出；以及按 `call_id` 配对且执行成功的 `exec` 包装输出。
- 去重键为 `thread_id + status + goal.updatedAt`。Thread 的 `idle`、`inProgress`、`systemError`、`completed`，以及 `task_complete`、final 文本，均不作为 Goal 状态证据。
- `goals_1.sqlite.thread_goals` 只表示当前快照。它可精确佐证当前映射，但不能独自证明历史状态转换。
- Goal ID 与 Thread ID 分开处理。旧事件未序列化 Goal ID、且没有精确映射时，以下表格标为 `UNKNOWN`，绝不假设两者相同。

## 三、确认的 10 个 blocked 事件

以下 10 条均有允许口径内的权威 Goal 状态证据。

| #   | 时间（UTC）                | Goal ID                                | Thread ID                              | 根因与判定                                | 一手证据                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| --- | ---------------------- | -------------------------------------- | -------------------------------------- | ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| B01 | `2026-05-23T14:17:09Z` | `UNKNOWN`                              | `019e546b-8491-72b3-8722-4ebb11539219` | 等待规格评审或明确授权；非网络业务门禁。                 | [原因](/Users/ycw/.codex/sessions/2026/05/23/rollout-2026-05-23T18-39-52-019e546b-8491-72b3-8722-4ebb11539219.jsonl:6722) [状态调用](/Users/ycw/.codex/sessions/2026/05/23/rollout-2026-05-23T18-39-52-019e546b-8491-72b3-8722-4ebb11539219.jsonl:6726) [成功输出](/Users/ycw/.codex/sessions/2026/05/23/rollout-2026-05-23T18-39-52-019e546b-8491-72b3-8722-4ebb11539219.jsonl:6727)                                                                                                                            |
| B02 | `2026-06-06T15:23:39Z` | `9c3b397b-274c-4760-b3a3-ef21e53f3024` | `019e9bed-4d4a-7710-88c1-4d3ca5f5b073` | 缺少生产环境所需的真实 provider secrets；外部配置缺失。 | [原因](/Users/ycw/.codex/sessions/2026/06/06/rollout-2026-06-06T15-54-40-019e9bed-4d4a-7710-88c1-4d3ca5f5b073.jsonl:4924) [状态调用](/Users/ycw/.codex/sessions/2026/06/06/rollout-2026-06-06T15-54-40-019e9bed-4d4a-7710-88c1-4d3ca5f5b073.jsonl:4928) [成功输出](/Users/ycw/.codex/sessions/2026/06/06/rollout-2026-06-06T15-54-40-019e9bed-4d4a-7710-88c1-4d3ca5f5b073.jsonl:4929)                                                                                                                            |
| B03 | `2026-06-25T17:06:10Z` | `UNKNOWN`                              | `019eef37-7358-7ad2-86d7-0e84a5c9749c` | 删除应用属于破坏性动作，等待用户明确审批。                | [原因](/Users/ycw/.codex/sessions/2026/06/22/rollout-2026-06-22T20-04-09-019eef37-7358-7ad2-86d7-0e84a5c9749c.jsonl:2081) [审批结果](/Users/ycw/.codex/sessions/2026/06/22/rollout-2026-06-22T20-04-09-019eef37-7358-7ad2-86d7-0e84a5c9749c.jsonl:2104) [状态](/Users/ycw/.codex/sessions/2026/06/22/rollout-2026-06-22T20-04-09-019eef37-7358-7ad2-86d7-0e84a5c9749c.jsonl:2107)                                                                                                                              |
| B04 | `2026-07-06T04:16:06Z` | `UNKNOWN`                              | `019ef259-319e-7473-8e8d-86d12c529a6e` | 指定目标主机不可达，需要确认正确且已授权的地址；目标配置问题。      | [原因](/Users/ycw/.codex/sessions/2026/06/23/rollout-2026-06-23T10-39-52-019ef259-319e-7473-8e8d-86d12c529a6e.jsonl:454) [状态](/Users/ycw/.codex/sessions/2026/06/23/rollout-2026-06-23T10-39-52-019ef259-319e-7473-8e8d-86d12c529a6e.jsonl:457)                                                                                                                                                                                                                                                          |
| B05 | `2026-07-23T03:55:42Z` | `UNKNOWN`                              | `019f8d10-1b0c-7a83-a289-673e97419b3a` | 等待实施方案批准；非网络审批门禁。                    | [原因](/Users/ycw/.codex/sessions/2026/07/23/rollout-2026-07-23T11-41-10-019f8d10-1b0c-7a83-a289-673e97419b3a.jsonl:260) [状态](/Users/ycw/.codex/sessions/2026/07/23/rollout-2026-07-23T11-41-10-019f8d10-1b0c-7a83-a289-673e97419b3a.jsonl:273)                                                                                                                                                                                                                                                          |
| B06 | `2026-07-23T04:04:21Z` | `UNKNOWN`                              | `019f8d10-1b0c-7a83-a289-673e97419b3a` | 等待书面设计评审；非网络审批门禁。                    | [原因](/Users/ycw/.codex/sessions/2026/07/23/rollout-2026-07-23T11-41-10-019f8d10-1b0c-7a83-a289-673e97419b3a.jsonl:412) [状态](/Users/ycw/.codex/sessions/2026/07/23/rollout-2026-07-23T11-41-10-019f8d10-1b0c-7a83-a289-673e97419b3a.jsonl:415)                                                                                                                                                                                                                                                          |
| B07 | `2026-07-24T11:19:01Z` | `UNKNOWN`                              | `019f92c7-ccc0-7f91-b6a6-ac755537051d` | HTTP 503 Service Unavailable；**T0**。 | [503](/Users/ycw/.codex/sessions/2026/07/24/rollout-2026-07-24T14-19-55-019f92c7-ccc0-7f91-b6a6-ac755537051d.jsonl:1329) [状态调用](/Users/ycw/.codex/sessions/2026/07/24/rollout-2026-07-24T14-19-55-019f92c7-ccc0-7f91-b6a6-ac755537051d.jsonl:1523) [成功输出](/Users/ycw/.codex/sessions/2026/07/24/rollout-2026-07-24T14-19-55-019f92c7-ccc0-7f91-b6a6-ac755537051d.jsonl:1524)                                                                                                                           |
| B08 | `2026-07-26T09:01:39Z` | `c503bc27-2309-44cb-aa6a-c638fb98ee6e` | `019f9da3-9ac7-7f32-9a3f-338996061476` | 等待方案 A 批准；非网络审批门禁。                   | [原因](/Users/ycw/.codex/archived_sessions/rollout-2026-07-26T16-56-12-019f9da3-9ac7-7f32-9a3f-338996061476.jsonl:118) [状态调用](/Users/ycw/.codex/archived_sessions/rollout-2026-07-26T16-56-12-019f9da3-9ac7-7f32-9a3f-338996061476.jsonl:120) [成功输出](/Users/ycw/.codex/archived_sessions/rollout-2026-07-26T16-56-12-019f9da3-9ac7-7f32-9a3f-338996061476.jsonl:121)                                                                                                                                     |
| B09 | `2026-07-27T18:22:04Z` | `1eeb68c4-ef03-4284-b3b4-f40e66102502` | `019fa387-e90e-76b0-bdc0-5c05288102e4` | 上游模型部署/路由返回 404；用户已确认属于 **T0**。      | [404](/Users/ycw/.codex/sessions/2026/07/27/rollout-2026-07-27T20-23-41-019fa387-e90e-76b0-bdc0-5c05288102e4.jsonl:5181) [状态调用](/Users/ycw/.codex/sessions/2026/07/27/rollout-2026-07-27T20-23-41-019fa387-e90e-76b0-bdc0-5c05288102e4.jsonl:5196) [成功输出](/Users/ycw/.codex/sessions/2026/07/27/rollout-2026-07-27T20-23-41-019fa387-e90e-76b0-bdc0-5c05288102e4.jsonl:5197) [用户确认](/Users/ycw/.codex/sessions/2026/07/23/rollout-2026-07-23T18-18-10-019f8e7b-92a9-7f51-9e15-c534bc94628d.jsonl:4667) |
| B10 | `2026-07-28T03:19:52Z` | `1eeb68c4-ef03-4284-b3b4-f40e66102502` | `019fa387-e90e-76b0-bdc0-5c05288102e4` | HTTP 503 Service Unavailable；**T0**。 | [503](/Users/ycw/.codex/sessions/2026/07/27/rollout-2026-07-27T20-23-41-019fa387-e90e-76b0-bdc0-5c05288102e4.jsonl:5779) [状态调用](/Users/ycw/.codex/sessions/2026/07/27/rollout-2026-07-27T20-23-41-019fa387-e90e-76b0-bdc0-5c05288102e4.jsonl:6431) [成功输出](/Users/ycw/.codex/sessions/2026/07/27/rollout-2026-07-27T20-23-41-019fa387-e90e-76b0-bdc0-5c05288102e4.jsonl:6432)                                                                                                                           |

## 四、确认的 11 个 paused 事件

这 11 条均紧邻明确的 `turn_aborted` / `interrupted`，表示 Goal 因 turn 中断而暂停；没有一条可仅凭 `paused` 推断为业务 Blocked。

| # | 时间（UTC） | Goal ID | Thread ID | 判定 | 一手证据 |
|---|---|---|---|---|---|
| P01 | `2026-05-18T07:38:43Z` | `UNKNOWN` | `019e2eb5-b664-7c43-b7dd-96a9c6cd05b6` | 用户中断。 | [中断](/Users/ycw/.codex/sessions/2026/05/16/rollout-2026-05-16T10-55-21-019e2eb5-b664-7c43-b7dd-96a9c6cd05b6.jsonl:32255) [状态](/Users/ycw/.codex/sessions/2026/05/16/rollout-2026-05-16T10-55-21-019e2eb5-b664-7c43-b7dd-96a9c6cd05b6.jsonl:32257) |
| P02 | `2026-05-20T23:27:55Z` | `UNKNOWN` | `019e40fd-669d-7592-b730-e9be6518f76e` | 权限等待后被用户中断。 | [上下文](/Users/ycw/.codex/sessions/2026/05/20/rollout-2026-05-20T00-06-49-019e40fd-669d-7592-b730-e9be6518f76e.jsonl:457) [中断](/Users/ycw/.codex/sessions/2026/05/20/rollout-2026-05-20T00-06-49-019e40fd-669d-7592-b730-e9be6518f76e.jsonl:459) [状态](/Users/ycw/.codex/sessions/2026/05/20/rollout-2026-05-20T00-06-49-019e40fd-669d-7592-b730-e9be6518f76e.jsonl:461) |
| P03 | `2026-05-20T23:27:55Z` | `UNKNOWN` | `019e4384-eb39-7031-a8c2-4ae8f8515fc9` | 权限等待后被用户中断。 | [上下文](/Users/ycw/.codex/sessions/2026/05/20/rollout-2026-05-20T11-54-04-019e4384-eb39-7031-a8c2-4ae8f8515fc9.jsonl:565) [中断](/Users/ycw/.codex/sessions/2026/05/20/rollout-2026-05-20T11-54-04-019e4384-eb39-7031-a8c2-4ae8f8515fc9.jsonl:571) [状态](/Users/ycw/.codex/sessions/2026/05/20/rollout-2026-05-20T11-54-04-019e4384-eb39-7031-a8c2-4ae8f8515fc9.jsonl:573) |
| P04 | `2026-05-21T21:00:36Z` | `UNKNOWN` | `019e4571-f84a-7231-ac78-12f286522647` | 用户中断长期工具调用；邻近平台请求为 HTTP 200，不是网络故障。 | [上下文](/Users/ycw/.codex/sessions/2026/05/20/rollout-2026-05-20T20-52-37-019e4571-f84a-7231-ac78-12f286522647.jsonl:37903) [中断](/Users/ycw/.codex/sessions/2026/05/20/rollout-2026-05-20T20-52-37-019e4571-f84a-7231-ac78-12f286522647.jsonl:37907) [状态](/Users/ycw/.codex/sessions/2026/05/20/rollout-2026-05-20T20-52-37-019e4571-f84a-7231-ac78-12f286522647.jsonl:37909) |
| P05 | `2026-06-25T17:11:57Z` | `UNKNOWN` | `019eef37-7358-7ad2-86d7-0e84a5c9749c` | 用户在审批门禁后中断。 | [状态](/Users/ycw/.codex/sessions/2026/06/22/rollout-2026-06-22T20-04-09-019eef37-7358-7ad2-86d7-0e84a5c9749c.jsonl:2240) [中断](/Users/ycw/.codex/sessions/2026/06/22/rollout-2026-06-22T20-04-09-019eef37-7358-7ad2-86d7-0e84a5c9749c.jsonl:2243) |
| P06 | `2026-07-06T04:00:20Z` | `UNKNOWN` | `019ef259-319e-7473-8e8d-86d12c529a6e` | 用户在工具调用期间中断。 | [状态](/Users/ycw/.codex/sessions/2026/06/23/rollout-2026-06-23T10-39-52-019ef259-319e-7473-8e8d-86d12c529a6e.jsonl:225) [中断](/Users/ycw/.codex/sessions/2026/06/23/rollout-2026-06-23T10-39-52-019ef259-319e-7473-8e8d-86d12c529a6e.jsonl:230) |
| P07 | `2026-07-23T10:01:17Z` | `UNKNOWN` | `019f8d10-1b0c-7a83-a289-673e97419b3a` | 用户明确中断恢复后的 turn。 | [状态](/Users/ycw/.codex/sessions/2026/07/23/rollout-2026-07-23T11-41-10-019f8d10-1b0c-7a83-a289-673e97419b3a.jsonl:2024) [中断](/Users/ycw/.codex/sessions/2026/07/23/rollout-2026-07-23T11-41-10-019f8d10-1b0c-7a83-a289-673e97419b3a.jsonl:2026) |
| P08 | `2026-07-26T09:05:37Z` | `UNKNOWN` | `019f9dab-b83c-76c1-ba56-6bd9a7d3dd9e` | 用户中断。 | [上下文](/Users/ycw/.codex/archived_sessions/rollout-2026-07-26T17-05-04-019f9dab-b83c-76c1-ba56-6bd9a7d3dd9e.jsonl:32) [状态](/Users/ycw/.codex/archived_sessions/rollout-2026-07-26T17-05-04-019f9dab-b83c-76c1-ba56-6bd9a7d3dd9e.jsonl:33) |
| P09 | `2026-07-26T09:36:18Z` | `UNKNOWN` | `019f9dac-7147-7463-8243-38b9e2154a6b` | 用户中断。 | [中断](/Users/ycw/.codex/archived_sessions/rollout-2026-07-26T17-05-51-019f9dac-7147-7463-8243-38b9e2154a6b.jsonl:284) [状态](/Users/ycw/.codex/archived_sessions/rollout-2026-07-26T17-05-51-019f9dac-7147-7463-8243-38b9e2154a6b.jsonl:285) |
| P10 | `2026-07-26T15:51:01Z` | `UNKNOWN` | `019f9ef5-9ddc-7fc1-9ebc-fcef8e5c79a1` | 用户在正常源码检查期间中断。 | [中断](/Users/ycw/.codex/sessions/2026/07/26/rollout-2026-07-26T23-05-24-019f9ef5-9ddc-7fc1-9ebc-fcef8e5c79a1.jsonl:5421) [状态](/Users/ycw/.codex/sessions/2026/07/26/rollout-2026-07-26T23-05-24-019f9ef5-9ddc-7fc1-9ebc-fcef8e5c79a1.jsonl:5422) |
| P11 | `2026-07-27T15:25:38Z` | `1eeb68c4-ef03-4284-b3b4-f40e66102502` | `019fa387-e90e-76b0-bdc0-5c05288102e4` | 用户在读取 skill 文档期间中断，随后恢复。 | [中断](/Users/ycw/.codex/sessions/2026/07/27/rollout-2026-07-27T20-23-41-019fa387-e90e-76b0-bdc0-5c05288102e4.jsonl:2014) [状态](/Users/ycw/.codex/sessions/2026/07/27/rollout-2026-07-27T20-23-41-019fa387-e90e-76b0-bdc0-5c05288102e4.jsonl:2015) |

## 五、仅快照关联的 2 个候选事件

| # | SQLite 当前映射 / 状态 | 关联事实 | 结论 |
|---|---|---|---|
| S01 | Goal `5a0f6d10-9fbb-4849-8134-505e8ec8d1e6` -> Thread `019f8d5e-1f7f-7e32-809a-df43004a6653`；`blocked`；`updated_at_ms=1784788256331` | 同毫秒出现 HTTP 429 Too Many Requests 并超过重试上限：[JSONL](/Users/ycw/.codex/sessions/2026/07/23/rollout-2026-07-23T13-06-23-019f8d5e-1f7f-7e32-809a-df43004a6653.jsonl:1447)；快照源：[goals_1.sqlite](/Users/ycw/.codex/goals_1.sqlite) | 高置信 T0 关联，但缺少允许口径内的序列化 `blocked` 转换；不计入确认的 10 条。 |
| S02 | Goal `737665f1-3588-4daa-98be-310a0bdbe2e6` -> Thread `019e4571-f84a-7231-ac78-12f286522647`；`paused`；`updated_at_ms=1779800430332` | 会话最后序列化状态仍为 `active`：[状态](/Users/ycw/.codex/sessions/2026/05/20/rollout-2026-05-20T20-52-37-019e4571-f84a-7231-ac78-12f286522647.jsonl:82980)，随后明确中断：[事件](/Users/ycw/.codex/sessions/2026/05/20/rollout-2026-05-20T20-52-37-019e4571-f84a-7231-ac78-12f286522647.jsonl:82981) [原因](/Users/ycw/.codex/sessions/2026/05/20/rollout-2026-05-20T20-52-37-019e4571-f84a-7231-ac78-12f286522647.jsonl:82982) | 高置信中断关联，但缺少序列化 `paused` 转换；不计入确认的 11 条。 |

## 六、404 误分类

正确的先后关系如下：

1. `2026-07-27T18:22:04Z`：目标 Thread 收到模型路由 404；后续成功 `get_goal` 返回 `blocked`，且 `updatedAt` 匹配。
2. 监控没有把相邻的 404 错误与该 `blocked` 状态合并为 T0，而把“权威状态为 blocked、未读到非网络原因”当成了非网络 Blocked，因而错误进入 P1 告警流程。
3. 用户随后明确确认 404 是上游部署/路由故障。正确处置是按唯一错误指纹执行一次 `/goal resume`，不发飞书告警。


## 八、现有报告需要替换的具体句子

为避免把 SQLite 当前快照候选混入权威历史事件，建议对 [blocked_goal_report.md](/Users/ycw/codex-goal-blocked-audit-2026-07-28/blocked_goal_report.md) 作以下口径替换；本备忘录不直接修改该报告。

| 位置 | 现有句子 | 应替换为 |
|---|---|---|
| 结论第 1 条 | “共识别 **11 个 blocked episode**：其中 10 个有会话中序列化的权威 Goal 状态，1 个是当前 SQLite 精确 blocked 快照……” | “确认 **10 个有序列化权威 Goal 状态的 blocked 事件**；另有 1 个 SQLite 当前快照与 HTTP 429 的高置信候选，单列且不计入确认事件。” |
| 结论第 2、3 条 | “根因分布……**4 个上游 T0 事件**。4 个 T0 分别是：1 个 HTTP 429、2 个 HTTP 503、1 个……404。” | “10 个确认事件中有 **3 个 T0**：2 个 HTTP 503、1 个用户确认的上游模型路由 404；另有 1 个仅由 SQLite 快照关联的 HTTP 429 T0 候选。” |
| 结论第 4 条 | “另有 **12 个 paused episode**：11 个有序列化 paused 状态，1 个是当前 SQLite……” | “确认 **11 个有序列化权威状态的 paused 事件**；另有 1 个 SQLite 当前快照与明确中断的关联候选，单列且不计入确认事件。” |

旧沟通中的“环境恢复后初始 P1 消息已成功发送”应统一替换为：

> `04:56:58+08:00` 的一次 `lark-cli` 调用在已解锁的 Keychain 中成功读取凭据并取得 HTTP 200；`05:16:38+08:00` 同类读取再次失败，因此这只是单次成功，不能称为“环境恢复”。

## 九、最终审计判断

- Goal 404：**上游 T0，应该恢复 Goal，不应该发 P1。**
- 监控误动作根因：**没有把已确认的模型路由 404 指纹优先归入 T0，并在仅看到 `blocked` 状态时过早进入 P1。**
- 当前证据没有映射冲突；唯一需要保持 UNKNOWN 的是未序列化且无精确历史映射的 Goal ID。
- 没有证据支持把 11 个 `paused` 事件升级为非网络业务 Blocked。
- 阻断项：**无**。21 条权威事件与 2 条 SQLite 候选均已按证据等级分离，现有证据足以形成上述审计结论。
