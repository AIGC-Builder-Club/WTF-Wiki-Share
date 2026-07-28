# Codex Goal 历史阻塞原因审计

生成时间（UTC）：`2026-07-28T06:40:52.280555Z`  
口径：本机规范存储中的可恢复 Codex Goal 历史；`blocked` 与 `paused` 分开统计。

## 结论

- 确认 **10 个有序列化权威 Goal 状态的 blocked 事件**；另有 1 个 SQLite 当前快照与同一毫秒 HTTP 429 的高置信候选，单列且不计入确认事件。
- 10 个确认事件的根因分布：**5 个用户审批/评审门禁**、**1 个生产密钥配置缺失**、**1 个目标主机/配置问题**、**3 个上游 T0 事件**。
- 3 个确认 T0 分别是：2 个 HTTP 503、1 个经用户确认的上游模型部署/路由 404；另有 1 个仅由 SQLite 当前快照关联的 HTTP 429 T0 候选。
- 确认 **11 个有序列化权威状态的 paused 事件**；另有 1 个 SQLite 当前快照与明确 `turn_aborted(interrupted)` 的关联候选，单列且不计入确认事件。全部属于用户/turn 中断，不是上游网络阻塞。
- 未发现 `usage_limited` 或 `budget_limited` episode。

## Blocked 完整清单

| ID          | 上海时间                          | Goal ID                                | Thread ID                              | 分类                               | 原因                                                                    | 最新状态       |
| ----------- | ----------------------------- | -------------------------------------- | -------------------------------------- | -------------------------------- | --------------------------------------------------------------------- | ---------- |
| BLOCKED-001 | 2026-05-23T22:17:09+08:00     | 未序列化                                   | `019e546b-8491-72b3-8722-4ebb11539219` | user_approval_review             | 修订后的设计规格已经完成，但工作流要求先由用户评审或明确授权，之后才能进入实施计划。                            | `complete` |
| BLOCKED-002 | 2026-06-06T23:23:39+08:00     | `9c3b397b-274c-4760-b3a3-ef21e53f3024` | `019e9bed-4d4a-7710-88c1-4d3ca5f5b073` | missing_external_configuration   | Vercel Production 缺少已部署 demo 所需的真实 provider secrets；所有不依赖这些密钥的工作均已完成。 | `complete` |
| BLOCKED-003 | 2026-06-26T01:06:10+08:00     | 未序列化                                   | `019eef37-7358-7ad2-86d7-0e84a5c9749c` | user_approval_destructive_action | 把残留应用移入废纸篓属于 Finder 删除动作；Computer Use 审批被拒，需要用户明确授权。                  | `complete` |
| BLOCKED-004 | 2026-07-06T12:16:06+08:00     | 未序列化                                   | `019ef259-319e-7473-8e8d-86d12c529a6e` | external_target_configuration    | VPN 与目标子网可达，但文档中的目标主机不可达；需要确认正确且已授权的部署目标。                             | `complete` |
| BLOCKED-005 | 2026-07-23T11:55:42+08:00     | 未序列化                                   | `019f8d10-1b0c-7a83-a289-673e97419b3a` | user_approval_design_decision    | 只读调查已经完成，实施工作等待用户明确批准推荐的方案 2。                                         | `complete` |
| BLOCKED-006 | 2026-07-23T12:04:21+08:00     | 未序列化                                   | `019f8d10-1b0c-7a83-a289-673e97419b3a` | user_approval_review             | 设计已经写完，但工作流仍要求在代码实施前完成明确的书面规格评审。                                      | `complete` |
| BLOCKED-007 | 2026-07-23T14:30:56.331+08:00 | `5a0f6d10-9fbb-4849-8134-505e8ec8d1e6` | `019f8d5e-1f7f-7e32-809a-df43004a6653` | upstream_api_transient / T0      | 上游 API 返回 HTTP 429 Too Many Requests，并最终超过重试上限。                       | `blocked`  |
| BLOCKED-008 | 2026-07-24T19:19:01+08:00     | 未序列化                                   | `019f92c7-ccc0-7f91-b6a6-ac755537051d` | upstream_api_transient / T0      | 上游 API 返回 HTTP 503 Service Unavailable。                               | `complete` |
| BLOCKED-009 | 2026-07-26T17:01:39.077+08:00 | `c503bc27-2309-44cb-aa6a-c638fb98ee6e` | `019f9da3-9ac7-7f32-9a3f-338996061476` | user_approval_design_decision    | 所选工作流禁止在设计批准前实施；当时尚未收到对方案 A 的明确批准。                                    | `blocked`  |
| BLOCKED-010 | 2026-07-28T02:22:04+08:00     | `1eeb68c4-ef03-4284-b3b4-f40e66102502` | `019fa387-e90e-76b0-bdc0-5c05288102e4` | upstream_model_routing / T0      | 上游模型路由层返回 HTTP 404：请求模型当时不受该组任何已配置账户支持。                               | `active`   |
| BLOCKED-011 | 2026-07-28T11:19:52+08:00     | `1eeb68c4-ef03-4284-b3b4-f40e66102502` | `019fa387-e90e-76b0-bdc0-5c05288102e4` | upstream_api_transient / T0      | 上游 API 返回 HTTP 503 Service Unavailable。                               | `active`   |

### Blocked 证据与结局

#### BLOCKED-001

- 根因证据：[rollout-2026-05-23T18-39-52-019e546b-8491-72b3-8722-4ebb11539219.jsonl:6722](/Users/ycw/.codex/sessions/2026/05/23/rollout-2026-05-23T18-39-52-019e546b-8491-72b3-8722-4ebb11539219.jsonl:6722)
- Goal 状态证据：[rollout-2026-05-23T18-39-52-019e546b-8491-72b3-8722-4ebb11539219.jsonl:6726](/Users/ycw/.codex/sessions/2026/05/23/rollout-2026-05-23T18-39-52-019e546b-8491-72b3-8722-4ebb11539219.jsonl:6726), [rollout-2026-05-23T18-39-52-019e546b-8491-72b3-8722-4ebb11539219.jsonl:6727](/Users/ycw/.codex/sessions/2026/05/23/rollout-2026-05-23T18-39-52-019e546b-8491-72b3-8722-4ebb11539219.jsonl:6727)
- 证据等级：`authoritative_serialized_goal_state`；Goal ID 可用性：`not_serialized`。
- 结局：后续权威 Goal 状态为 complete（2026-05-24T07:36:46Z）。
- 结局证据：[rollout-2026-05-23T18-39-52-019e546b-8491-72b3-8722-4ebb11539219.jsonl:8576](/Users/ycw/.codex/sessions/2026/05/23/rollout-2026-05-23T18-39-52-019e546b-8491-72b3-8722-4ebb11539219.jsonl:8576)

#### BLOCKED-002

- 根因证据：[rollout-2026-06-06T15-54-40-019e9bed-4d4a-7710-88c1-4d3ca5f5b073.jsonl:4924](/Users/ycw/.codex/sessions/2026/06/06/rollout-2026-06-06T15-54-40-019e9bed-4d4a-7710-88c1-4d3ca5f5b073.jsonl:4924)
- Goal 状态证据：[rollout-2026-06-06T15-54-40-019e9bed-4d4a-7710-88c1-4d3ca5f5b073.jsonl:4928](/Users/ycw/.codex/sessions/2026/06/06/rollout-2026-06-06T15-54-40-019e9bed-4d4a-7710-88c1-4d3ca5f5b073.jsonl:4928), [rollout-2026-06-06T15-54-40-019e9bed-4d4a-7710-88c1-4d3ca5f5b073.jsonl:4929](/Users/ycw/.codex/sessions/2026/06/06/rollout-2026-06-06T15-54-40-019e9bed-4d4a-7710-88c1-4d3ca5f5b073.jsonl:4929)
- 证据等级：`authoritative_serialized_goal_state`；Goal ID 可用性：`exact_current_sqlite_mapping`。
- 结局：后续权威 Goal 状态为 complete（2026-06-08T06:26:58.414Z）。
- 结局证据：[rollout-2026-06-06T15-54-40-019e9bed-4d4a-7710-88c1-4d3ca5f5b073.jsonl:6744](/Users/ycw/.codex/sessions/2026/06/06/rollout-2026-06-06T15-54-40-019e9bed-4d4a-7710-88c1-4d3ca5f5b073.jsonl:6744)

#### BLOCKED-003

- 根因证据：[rollout-2026-06-22T20-04-09-019eef37-7358-7ad2-86d7-0e84a5c9749c.jsonl:2081](/Users/ycw/.codex/sessions/2026/06/22/rollout-2026-06-22T20-04-09-019eef37-7358-7ad2-86d7-0e84a5c9749c.jsonl:2081), [rollout-2026-06-22T20-04-09-019eef37-7358-7ad2-86d7-0e84a5c9749c.jsonl:2104](/Users/ycw/.codex/sessions/2026/06/22/rollout-2026-06-22T20-04-09-019eef37-7358-7ad2-86d7-0e84a5c9749c.jsonl:2104)
- Goal 状态证据：[rollout-2026-06-22T20-04-09-019eef37-7358-7ad2-86d7-0e84a5c9749c.jsonl:2107](/Users/ycw/.codex/sessions/2026/06/22/rollout-2026-06-22T20-04-09-019eef37-7358-7ad2-86d7-0e84a5c9749c.jsonl:2107)
- 证据等级：`authoritative_serialized_goal_state`；Goal ID 可用性：`not_serialized`。
- 结局：后续权威 Goal 状态为 complete（2026-06-25T17:13:12Z）。
- 结局证据：[rollout-2026-06-22T20-04-09-019eef37-7358-7ad2-86d7-0e84a5c9749c.jsonl:2265](/Users/ycw/.codex/sessions/2026/06/22/rollout-2026-06-22T20-04-09-019eef37-7358-7ad2-86d7-0e84a5c9749c.jsonl:2265)

#### BLOCKED-004

- 根因证据：[rollout-2026-06-23T10-39-52-019ef259-319e-7473-8e8d-86d12c529a6e.jsonl:454](/Users/ycw/.codex/sessions/2026/06/23/rollout-2026-06-23T10-39-52-019ef259-319e-7473-8e8d-86d12c529a6e.jsonl:454)
- Goal 状态证据：[rollout-2026-06-23T10-39-52-019ef259-319e-7473-8e8d-86d12c529a6e.jsonl:457](/Users/ycw/.codex/sessions/2026/06/23/rollout-2026-06-23T10-39-52-019ef259-319e-7473-8e8d-86d12c529a6e.jsonl:457)
- 证据等级：`authoritative_serialized_goal_state`；Goal ID 可用性：`not_serialized`。
- 结局：后续权威 Goal 状态为 complete（2026-07-06T07:21:52Z）。
- 结局证据：[rollout-2026-06-23T10-39-52-019ef259-319e-7473-8e8d-86d12c529a6e.jsonl:798](/Users/ycw/.codex/sessions/2026/06/23/rollout-2026-06-23T10-39-52-019ef259-319e-7473-8e8d-86d12c529a6e.jsonl:798)

#### BLOCKED-005

- 根因证据：[rollout-2026-07-23T11-41-10-019f8d10-1b0c-7a83-a289-673e97419b3a.jsonl:260](/Users/ycw/.codex/sessions/2026/07/23/rollout-2026-07-23T11-41-10-019f8d10-1b0c-7a83-a289-673e97419b3a.jsonl:260)
- Goal 状态证据：[rollout-2026-07-23T11-41-10-019f8d10-1b0c-7a83-a289-673e97419b3a.jsonl:273](/Users/ycw/.codex/sessions/2026/07/23/rollout-2026-07-23T11-41-10-019f8d10-1b0c-7a83-a289-673e97419b3a.jsonl:273)
- 证据等级：`authoritative_serialized_goal_state`；Goal ID 可用性：`not_serialized`。
- 结局：同一 Goal 实例后续达到 complete（2026-07-23T13:24:07Z）。
- 结局证据：[rollout-2026-07-23T11-41-10-019f8d10-1b0c-7a83-a289-673e97419b3a.jsonl:3514](/Users/ycw/.codex/sessions/2026/07/23/rollout-2026-07-23T11-41-10-019f8d10-1b0c-7a83-a289-673e97419b3a.jsonl:3514)

#### BLOCKED-006

- 根因证据：[rollout-2026-07-23T11-41-10-019f8d10-1b0c-7a83-a289-673e97419b3a.jsonl:412](/Users/ycw/.codex/sessions/2026/07/23/rollout-2026-07-23T11-41-10-019f8d10-1b0c-7a83-a289-673e97419b3a.jsonl:412)
- Goal 状态证据：[rollout-2026-07-23T11-41-10-019f8d10-1b0c-7a83-a289-673e97419b3a.jsonl:415](/Users/ycw/.codex/sessions/2026/07/23/rollout-2026-07-23T11-41-10-019f8d10-1b0c-7a83-a289-673e97419b3a.jsonl:415)
- 证据等级：`authoritative_serialized_goal_state`；Goal ID 可用性：`not_serialized`。
- 结局：同一 Goal 实例后续达到 complete（2026-07-23T13:24:07Z）。
- 结局证据：[rollout-2026-07-23T11-41-10-019f8d10-1b0c-7a83-a289-673e97419b3a.jsonl:3514](/Users/ycw/.codex/sessions/2026/07/23/rollout-2026-07-23T11-41-10-019f8d10-1b0c-7a83-a289-673e97419b3a.jsonl:3514)

#### BLOCKED-007

- 根因证据：[rollout-2026-07-23T13-06-23-019f8d5e-1f7f-7e32-809a-df43004a6653.jsonl:1447](/Users/ycw/.codex/sessions/2026/07/23/rollout-2026-07-23T13-06-23-019f8d5e-1f7f-7e32-809a-df43004a6653.jsonl:1447)
- Goal 状态证据：[goals_1.sqlite](/Users/ycw/.codex/goals_1.sqlite)
- 证据等级：`current_sqlite_snapshot_correlated`；Goal ID 可用性：`exact_current_sqlite_mapping`。
- 结局：当前 SQLite 精确行仍为 blocked；该 episode 未找到序列化的 blocked 转换事件。
- 请求 ID：`5fffeacf-5ce3-4276-bd34-ecfc5a7cd54e`

#### BLOCKED-008

- 根因证据：[rollout-2026-07-24T14-19-55-019f92c7-ccc0-7f91-b6a6-ac755537051d.jsonl:1329](/Users/ycw/.codex/sessions/2026/07/24/rollout-2026-07-24T14-19-55-019f92c7-ccc0-7f91-b6a6-ac755537051d.jsonl:1329)
- Goal 状态证据：[rollout-2026-07-24T14-19-55-019f92c7-ccc0-7f91-b6a6-ac755537051d.jsonl:1524](/Users/ycw/.codex/sessions/2026/07/24/rollout-2026-07-24T14-19-55-019f92c7-ccc0-7f91-b6a6-ac755537051d.jsonl:1524)
- 证据等级：`authoritative_serialized_goal_state`；Goal ID 可用性：`not_serialized`。
- 结局：后续权威 Goal 状态为 complete（2026-07-24T13:46:55Z）。
- 请求 ID：`a7a2c780-32e0-419e-9b48-541a3c64c242`
- 结局证据：[rollout-2026-07-24T14-19-55-019f92c7-ccc0-7f91-b6a6-ac755537051d.jsonl:1648](/Users/ycw/.codex/sessions/2026/07/24/rollout-2026-07-24T14-19-55-019f92c7-ccc0-7f91-b6a6-ac755537051d.jsonl:1648)

#### BLOCKED-009

- 根因证据：[rollout-2026-07-26T16-56-12-019f9da3-9ac7-7f32-9a3f-338996061476.jsonl:118](/Users/ycw/.codex/archived_sessions/rollout-2026-07-26T16-56-12-019f9da3-9ac7-7f32-9a3f-338996061476.jsonl:118)
- Goal 状态证据：[rollout-2026-07-26T16-56-12-019f9da3-9ac7-7f32-9a3f-338996061476.jsonl:121](/Users/ycw/.codex/archived_sessions/rollout-2026-07-26T16-56-12-019f9da3-9ac7-7f32-9a3f-338996061476.jsonl:121), [goals_1.sqlite](/Users/ycw/.codex/goals_1.sqlite)
- 证据等级：`authoritative_serialized_goal_state`；Goal ID 可用性：`exact_current_sqlite_mapping`。
- 结局：当前 SQLite 精确行仍为 blocked。

#### BLOCKED-010

- 根因证据：[rollout-2026-07-27T20-23-41-019fa387-e90e-76b0-bdc0-5c05288102e4.jsonl:5181](/Users/ycw/.codex/sessions/2026/07/27/rollout-2026-07-27T20-23-41-019fa387-e90e-76b0-bdc0-5c05288102e4.jsonl:5181)
- Goal 状态证据：[rollout-2026-07-27T20-23-41-019fa387-e90e-76b0-bdc0-5c05288102e4.jsonl:5197](/Users/ycw/.codex/sessions/2026/07/27/rollout-2026-07-27T20-23-41-019fa387-e90e-76b0-bdc0-5c05288102e4.jsonl:5197), [goals_1.sqlite](/Users/ycw/.codex/goals_1.sqlite)
- 证据等级：`authoritative_serialized_goal_state`；Goal ID 可用性：`exact_current_sqlite_mapping`。
- 结局：用户确认这是上游部署/路由故障；监控将其重分类为 T0，成功发送一次 /goal resume，最新 SQLite 精确状态为 active。
- 请求 ID：`8be5affb-5009-406a-b652-18b69a15ba5d`
- 结局证据：[goal-monitor-019f8e7b-92a9-7f51-9e15-c534bc94628d.json](/Users/ycw/.codex/automation-state/goal-monitor-019f8e7b-92a9-7f51-9e15-c534bc94628d.json)

#### BLOCKED-011

- 根因证据：[rollout-2026-07-27T20-23-41-019fa387-e90e-76b0-bdc0-5c05288102e4.jsonl:5779](/Users/ycw/.codex/sessions/2026/07/27/rollout-2026-07-27T20-23-41-019fa387-e90e-76b0-bdc0-5c05288102e4.jsonl:5779)
- Goal 状态证据：[rollout-2026-07-27T20-23-41-019fa387-e90e-76b0-bdc0-5c05288102e4.jsonl:6432](/Users/ycw/.codex/sessions/2026/07/27/rollout-2026-07-27T20-23-41-019fa387-e90e-76b0-bdc0-5c05288102e4.jsonl:6432), [rollout-2026-07-27T20-23-41-019fa387-e90e-76b0-bdc0-5c05288102e4.jsonl:7197](/Users/ycw/.codex/sessions/2026/07/27/rollout-2026-07-27T20-23-41-019fa387-e90e-76b0-bdc0-5c05288102e4.jsonl:7197), [goals_1.sqlite](/Users/ycw/.codex/goals_1.sqlite)
- 证据等级：`authoritative_serialized_goal_state`；Goal ID 可用性：`exact_current_sqlite_mapping`。
- 结局：监控针对该 request ID 成功发送一次 /goal resume；最新 SQLite 精确状态为 active。
- 请求 ID：`fe4e1b4c-a49c-406e-bc42-940973646512`
- 结局证据：[goal-monitor-019f8e7b-92a9-7f51-9e15-c534bc94628d.json](/Users/ycw/.codex/automation-state/goal-monitor-019f8e7b-92a9-7f51-9e15-c534bc94628d.json)

## Paused 附录

`paused` 只表示 Goal 实例因 turn 中断而暂停，不能自动解释为业务 blocker。以下 12 条不计入 11 个 blocked episode。

| ID | 上海时间 | Goal ID | Thread ID | 分类 | 原因 | 最新状态 |
|---|---|---|---|---|---|---|
| PAUSED-001 | 2026-05-18T15:38:43+08:00 | 未序列化 | `019e2eb5-b664-7c43-b7dd-96a9c6cd05b6` | user_interruption | 用户在残留进程检查尚未结束时中断 turn；紧邻的上一条命令以 code 1 退出。 | `active` |
| PAUSED-002 | 2026-05-21T07:27:55+08:00 | 未序列化 | `019e40fd-669d-7592-b730-e9be6518f76e` | user_interruption_after_permission_wait | 一个需要额外文件系统权限的本地 pullback 操作悬置约 31 小时，随后被用户中断。 | `paused` |
| PAUSED-003 | 2026-05-21T07:27:55+08:00 | 未序列化 | `019e4384-eb39-7031-a8c2-4ae8f8515fc9` | user_interruption_after_permission_wait | 首次 pullback 因无法创建 Git index lock 而失败；提权重试继续悬置，之后被用户中断。 | `paused` |
| PAUSED-004 | 2026-05-22T05:00:36+08:00 | 未序列化 | `019e4571-f84a-7231-ac78-12f286522647` | user_interruption | 用户中断了一个包含三个长期工具调用的旧 turn；临近的平台刷新返回 HTTP 200，因此不是网络故障。 | `active` |
| PAUSED-005 | 2026-05-26T21:00:30.332+08:00 | `737665f1-3588-4daa-98be-310a0bdbe2e6` | `019e4571-f84a-7231-ac78-12f286522647` | user_interruption | 用户中断该 Goal 实例；当前 SQLite 精确行保存了 paused，而会话在中断前序列化的是 active，没有留下 paused 转换。 | `paused` |
| PAUSED-006 | 2026-06-26T01:11:57+08:00 | 未序列化 | `019eef37-7358-7ad2-86d7-0e84a5c9749c` | user_interruption | 用户在前述删除动作审批门禁之后中断 turn。 | `complete` |
| PAUSED-007 | 2026-07-06T12:00:20+08:00 | 未序列化 | `019ef259-319e-7473-8e8d-86d12c529a6e` | user_interruption | 用户在工具调用运行期间中断了初始 turn。 | `paused` |
| PAUSED-008 | 2026-07-23T18:01:17+08:00 | 未序列化 | `019f8d10-1b0c-7a83-a289-673e97419b3a` | user_interruption | 用户明确中断了恢复后的 turn。 | `complete` |
| PAUSED-009 | 2026-07-26T17:05:37+08:00 | 未序列化 | `019f9dab-b83c-76c1-ba56-6bd9a7d3dd9e` | user_interruption | skill 获取规划开始后不久，用户中断了 turn。 | `paused` |
| PAUSED-010 | 2026-07-26T17:36:18+08:00 | 未序列化 | `019f9dac-7147-7463-8243-38b9e2154a6b` | user_interruption | 读取 skill 模板期间，用户中断了 turn。 | `paused` |
| PAUSED-011 | 2026-07-26T23:51:01+08:00 | 未序列化 | `019f9ef5-9ddc-7fc1-9ebc-fcef8e5c79a1` | user_interruption | 正常检查源码期间，用户中断了 turn。 | `complete` |
| PAUSED-012 | 2026-07-27T23:25:38+08:00 | `1eeb68c4-ef03-4284-b3b4-f40e66102502` | `019fa387-e90e-76b0-bdc0-5c05288102e4` | user_interruption | 读取 skill 文档期间，用户中断了初始 turn。 | `active` |

### Paused 证据

- **PAUSED-001**：根因 [rollout-2026-05-16T10-55-21-019e2eb5-b664-7c43-b7dd-96a9c6cd05b6.jsonl:32255](/Users/ycw/.codex/sessions/2026/05/16/rollout-2026-05-16T10-55-21-019e2eb5-b664-7c43-b7dd-96a9c6cd05b6.jsonl:32255), [rollout-2026-05-16T10-55-21-019e2eb5-b664-7c43-b7dd-96a9c6cd05b6.jsonl:32253](/Users/ycw/.codex/sessions/2026/05/16/rollout-2026-05-16T10-55-21-019e2eb5-b664-7c43-b7dd-96a9c6cd05b6.jsonl:32253)；状态 [rollout-2026-05-16T10-55-21-019e2eb5-b664-7c43-b7dd-96a9c6cd05b6.jsonl:32257](/Users/ycw/.codex/sessions/2026/05/16/rollout-2026-05-16T10-55-21-019e2eb5-b664-7c43-b7dd-96a9c6cd05b6.jsonl:32257)；证据等级 `authoritative_serialized_goal_state`。
- **PAUSED-002**：根因 [rollout-2026-05-20T00-06-49-019e40fd-669d-7592-b730-e9be6518f76e.jsonl:457](/Users/ycw/.codex/sessions/2026/05/20/rollout-2026-05-20T00-06-49-019e40fd-669d-7592-b730-e9be6518f76e.jsonl:457), [rollout-2026-05-20T00-06-49-019e40fd-669d-7592-b730-e9be6518f76e.jsonl:459](/Users/ycw/.codex/sessions/2026/05/20/rollout-2026-05-20T00-06-49-019e40fd-669d-7592-b730-e9be6518f76e.jsonl:459)；状态 [rollout-2026-05-20T00-06-49-019e40fd-669d-7592-b730-e9be6518f76e.jsonl:461](/Users/ycw/.codex/sessions/2026/05/20/rollout-2026-05-20T00-06-49-019e40fd-669d-7592-b730-e9be6518f76e.jsonl:461)；证据等级 `authoritative_serialized_goal_state`。
- **PAUSED-003**：根因 [rollout-2026-05-20T11-54-04-019e4384-eb39-7031-a8c2-4ae8f8515fc9.jsonl:565](/Users/ycw/.codex/sessions/2026/05/20/rollout-2026-05-20T11-54-04-019e4384-eb39-7031-a8c2-4ae8f8515fc9.jsonl:565), [rollout-2026-05-20T11-54-04-019e4384-eb39-7031-a8c2-4ae8f8515fc9.jsonl:569](/Users/ycw/.codex/sessions/2026/05/20/rollout-2026-05-20T11-54-04-019e4384-eb39-7031-a8c2-4ae8f8515fc9.jsonl:569), [rollout-2026-05-20T11-54-04-019e4384-eb39-7031-a8c2-4ae8f8515fc9.jsonl:571](/Users/ycw/.codex/sessions/2026/05/20/rollout-2026-05-20T11-54-04-019e4384-eb39-7031-a8c2-4ae8f8515fc9.jsonl:571)；状态 [rollout-2026-05-20T11-54-04-019e4384-eb39-7031-a8c2-4ae8f8515fc9.jsonl:573](/Users/ycw/.codex/sessions/2026/05/20/rollout-2026-05-20T11-54-04-019e4384-eb39-7031-a8c2-4ae8f8515fc9.jsonl:573)；证据等级 `authoritative_serialized_goal_state`。
- **PAUSED-004**：根因 [rollout-2026-05-20T20-52-37-019e4571-f84a-7231-ac78-12f286522647.jsonl:37903](/Users/ycw/.codex/sessions/2026/05/20/rollout-2026-05-20T20-52-37-019e4571-f84a-7231-ac78-12f286522647.jsonl:37903), [rollout-2026-05-20T20-52-37-019e4571-f84a-7231-ac78-12f286522647.jsonl:37907](/Users/ycw/.codex/sessions/2026/05/20/rollout-2026-05-20T20-52-37-019e4571-f84a-7231-ac78-12f286522647.jsonl:37907), [rollout-2026-05-20T20-52-37-019e4571-f84a-7231-ac78-12f286522647.jsonl:37901](/Users/ycw/.codex/sessions/2026/05/20/rollout-2026-05-20T20-52-37-019e4571-f84a-7231-ac78-12f286522647.jsonl:37901)；状态 [rollout-2026-05-20T20-52-37-019e4571-f84a-7231-ac78-12f286522647.jsonl:37909](/Users/ycw/.codex/sessions/2026/05/20/rollout-2026-05-20T20-52-37-019e4571-f84a-7231-ac78-12f286522647.jsonl:37909)；证据等级 `authoritative_serialized_goal_state`。
- **PAUSED-005**：根因 [rollout-2026-05-20T20-52-37-019e4571-f84a-7231-ac78-12f286522647.jsonl:82982](/Users/ycw/.codex/sessions/2026/05/20/rollout-2026-05-20T20-52-37-019e4571-f84a-7231-ac78-12f286522647.jsonl:82982)；状态 [goals_1.sqlite](/Users/ycw/.codex/goals_1.sqlite), [rollout-2026-05-20T20-52-37-019e4571-f84a-7231-ac78-12f286522647.jsonl:82980](/Users/ycw/.codex/sessions/2026/05/20/rollout-2026-05-20T20-52-37-019e4571-f84a-7231-ac78-12f286522647.jsonl:82980)；证据等级 `current_sqlite_snapshot_correlated`。
- **PAUSED-006**：根因 [rollout-2026-06-22T20-04-09-019eef37-7358-7ad2-86d7-0e84a5c9749c.jsonl:2243](/Users/ycw/.codex/sessions/2026/06/22/rollout-2026-06-22T20-04-09-019eef37-7358-7ad2-86d7-0e84a5c9749c.jsonl:2243)；状态 [rollout-2026-06-22T20-04-09-019eef37-7358-7ad2-86d7-0e84a5c9749c.jsonl:2240](/Users/ycw/.codex/sessions/2026/06/22/rollout-2026-06-22T20-04-09-019eef37-7358-7ad2-86d7-0e84a5c9749c.jsonl:2240)；证据等级 `authoritative_serialized_goal_state`。
- **PAUSED-007**：根因 [rollout-2026-06-23T10-39-52-019ef259-319e-7473-8e8d-86d12c529a6e.jsonl:226](/Users/ycw/.codex/sessions/2026/06/23/rollout-2026-06-23T10-39-52-019ef259-319e-7473-8e8d-86d12c529a6e.jsonl:226), [rollout-2026-06-23T10-39-52-019ef259-319e-7473-8e8d-86d12c529a6e.jsonl:230](/Users/ycw/.codex/sessions/2026/06/23/rollout-2026-06-23T10-39-52-019ef259-319e-7473-8e8d-86d12c529a6e.jsonl:230)；状态 [rollout-2026-06-23T10-39-52-019ef259-319e-7473-8e8d-86d12c529a6e.jsonl:225](/Users/ycw/.codex/sessions/2026/06/23/rollout-2026-06-23T10-39-52-019ef259-319e-7473-8e8d-86d12c529a6e.jsonl:225)；证据等级 `authoritative_serialized_goal_state`。
- **PAUSED-008**：根因 [rollout-2026-07-23T11-41-10-019f8d10-1b0c-7a83-a289-673e97419b3a.jsonl:2026](/Users/ycw/.codex/sessions/2026/07/23/rollout-2026-07-23T11-41-10-019f8d10-1b0c-7a83-a289-673e97419b3a.jsonl:2026)；状态 [rollout-2026-07-23T11-41-10-019f8d10-1b0c-7a83-a289-673e97419b3a.jsonl:2024](/Users/ycw/.codex/sessions/2026/07/23/rollout-2026-07-23T11-41-10-019f8d10-1b0c-7a83-a289-673e97419b3a.jsonl:2024)；证据等级 `authoritative_serialized_goal_state`。
- **PAUSED-009**：根因 [rollout-2026-07-26T17-05-04-019f9dab-b83c-76c1-ba56-6bd9a7d3dd9e.jsonl:32](/Users/ycw/.codex/archived_sessions/rollout-2026-07-26T17-05-04-019f9dab-b83c-76c1-ba56-6bd9a7d3dd9e.jsonl:32)；状态 [rollout-2026-07-26T17-05-04-019f9dab-b83c-76c1-ba56-6bd9a7d3dd9e.jsonl:33](/Users/ycw/.codex/archived_sessions/rollout-2026-07-26T17-05-04-019f9dab-b83c-76c1-ba56-6bd9a7d3dd9e.jsonl:33)；证据等级 `authoritative_serialized_goal_state`。
- **PAUSED-010**：根因 [rollout-2026-07-26T17-05-51-019f9dac-7147-7463-8243-38b9e2154a6b.jsonl:284](/Users/ycw/.codex/archived_sessions/rollout-2026-07-26T17-05-51-019f9dac-7147-7463-8243-38b9e2154a6b.jsonl:284)；状态 [rollout-2026-07-26T17-05-51-019f9dac-7147-7463-8243-38b9e2154a6b.jsonl:285](/Users/ycw/.codex/archived_sessions/rollout-2026-07-26T17-05-51-019f9dac-7147-7463-8243-38b9e2154a6b.jsonl:285)；证据等级 `authoritative_serialized_goal_state`。
- **PAUSED-011**：根因 [rollout-2026-07-26T23-05-24-019f9ef5-9ddc-7fc1-9ebc-fcef8e5c79a1.jsonl:5421](/Users/ycw/.codex/sessions/2026/07/26/rollout-2026-07-26T23-05-24-019f9ef5-9ddc-7fc1-9ebc-fcef8e5c79a1.jsonl:5421)；状态 [rollout-2026-07-26T23-05-24-019f9ef5-9ddc-7fc1-9ebc-fcef8e5c79a1.jsonl:5422](/Users/ycw/.codex/sessions/2026/07/26/rollout-2026-07-26T23-05-24-019f9ef5-9ddc-7fc1-9ebc-fcef8e5c79a1.jsonl:5422)；证据等级 `authoritative_serialized_goal_state`。
- **PAUSED-012**：根因 [rollout-2026-07-27T20-23-41-019fa387-e90e-76b0-bdc0-5c05288102e4.jsonl:2014](/Users/ycw/.codex/sessions/2026/07/27/rollout-2026-07-27T20-23-41-019fa387-e90e-76b0-bdc0-5c05288102e4.jsonl:2014)；状态 [rollout-2026-07-27T20-23-41-019fa387-e90e-76b0-bdc0-5c05288102e4.jsonl:2015](/Users/ycw/.codex/sessions/2026/07/27/rollout-2026-07-27T20-23-41-019fa387-e90e-76b0-bdc0-5c05288102e4.jsonl:2015), [goals_1.sqlite](/Users/ycw/.codex/goals_1.sqlite)；证据等级 `authoritative_serialized_goal_state`。

## 方法与边界

- 扫描 `429` 个规范 session/archived-session JSONL，共 `486683` 条有效 JSONL 记录，解析错误 `0`。
- 发现 `440` 个 Goal 工具调用，按 `call_id` 成功配对 `440` 个；只有成功输出才用于状态判定。
- 状态证据仅接受 `thread_goal_updated`、成功 `get_goal/update_goal` 结构化输出，以及当前 `goals_1.sqlite.thread_goals` 的精确行。
- `task_complete`、final 文本或 Thread 终态不能单独证明 Goal 状态；但可作为已确认 Goal 状态的根因上下文。
- Goal ID 与 Thread ID 是不同标识。旧事件只序列化 `goal.threadId` 时，Goal ID 保持 `null / 未序列化`，绝不把 Thread ID 冒充 Goal ID。
- “所有”限定为本机规范存储中仍可恢复的记录；已经永久删除且未留存于规范 session、archived session 或当前 Goal SQLite 的事件无法从本机证明。
- 备份目录中的重复 rollout 不计入覆盖数量，以免重复计算同一事件；规范 session 与 archived session 是统计基准。
- 已按 rollout 文件名核对备份目录，备份中独有而规范存储缺失的 JSONL 数量为 `0`。

## 数据文件

- `blocked_goal_episodes.json`：完整结构化 blocked 数据与元信息。
- `blocked_goal_episodes.csv`：便于表格分析的扁平 blocked 数据。
- `paused_goal_episodes.json` / `paused_goal_episodes.csv`：单独的 paused 附录。
- `coverage_manifest.json`：扫描覆盖与解析统计。
- `raw_blocked_entries.json` / `raw_paused_entries.json`：未经人工根因归类的状态条目。
- `independent_audit_memo.md`：对状态计数、T0 分类和 Keychain 因果链的独立只读复核。
