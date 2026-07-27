# 极简方案-采用CodeX内置的自动化Automation

- 正常点击【CodeX的自动化Automation】，点击【创建】，就会显示：
	- `  我们一起来设置一个已安排任务吧。首先，说明已安排任务在 ChatGPT 中的工作方式。然后询问我需要安排什么，以及应该在什么时候运行。  `

- CodeX的回复：
```

详见  https://learn.chatgpt.com/docs/automations.md  文档。

已安排任务会让 ChatGPT 按指定时间或周期在后台执行一段持久指令。它可以作为独立任务运行，每次产生新的结果；也可以回到当前聊天，沿用这里的上下文。结果可在“已安排”中查看、暂停或修改。桌面端若任务要访问本地项目，运行时需要电脑开机且 ChatGPT 保持运行；任务会按当前沙盒权限无人值守执行。

你想安排什么任务？它应在什么时候运行？例如：“每个工作日北京时间 09:00 汇总项目待办”或“30 分钟后提醒我继续检查部署”。

```


- 然后，输入我们的【需求】：
	- ![增加【自动化Automation定时任务】对【Goal的恢复和唤起】](Root/高常用/个人/拾零/技术6/将要永久改变世界的人工智能AI/【目录】ChatGPT%20，%20等等，都在这一篇目录/【ChatGPT】产品生态，谱系图/【POE】，网站、APP，都在这一篇，总览/DeepSeek大模型、及随之而来的国内浪潮，都在这一篇，总览（有自己的官方网站，暂存于此）/【CodeX】，都在这一篇，总览.md#^bid-nqtzw93)

- 顺便，我查看了一下，【手动配置】的一些选项。
	- 基本信息
		- 任务标题
		- 任务描述
	- 详情：
		- 运行于    新任务、现有任务
		- 项目    一个Project
		- 模型    GPT-5.6-Sol
			- （~~后来改为  Luna  Max~~）
				- （这儿比较容易混淆，都不是最终测试的答案）
					- 此处，有一个非常隐蔽的严重Bug：
						- 【你在这里设置的模型】，会被带到【主力任务】。
							- 也就是说，会把【主力任务】从【Sol Max】覆盖为【Luna Max】
								- （这个，我多次检查过）
						- 所以，应该————【定时任务对话】手动设置为【Luna Max】，而【此处设置  改为  Sol  Max】
					- 但是后来又发现，可能还是应该在【`派发精确命令 /goal resume（model=gpt-5.6-luna、thinking=max）`】  这一句上来改？
			- （先保留为  Sol  Max  吧）
		- 推理（强度）    Max
	- 频率
		- 重复    每天、每小时、每周
		- 时间    小时分钟
		- 通知    所有运行、仅限未成功运行


- 整合翻译成一段话：

```

请按照  【CodeX定时任务】功能  ，为我设计和开启这一定时任务。    （对应文档为：  https://learn.chatgpt.com/docs/automations.md  ）

# Meta信息
1、采用 GPT-5.6-Sol 模型的【Max推理强度】。
2、让【同一<会话ID>】的检查任务，放在【同一个Task】里面。
3、具体重复周期，如下方【定时任务信息】的详细描述。


# 定时任务信息

请你为我盯着【<会话ID>】的Goal任务，每隔20分钟检查一下【以下项】。
- 1、一旦它有【网络报错、网络重试次数过多】导致的Goal中断，则你应该让【Goal重新恢复运行】。
- 2、如果它有【待审批、或者硬性Blocked】，则你应该通过【飞书CLI工具】，给我的主账号发送【高级别告警信息（或者通话、视频通讯）等等）】（以提醒我）。
	- 最开始，发送需要确认的信息————如果我没有已读或者确认，则你应该【通过飞书CLI内的工具】升级更高级别告警。
- 3、如果已完成，请将【基本完成情况】，为我写入【飞书CLI的飞书文档】，并为我发送【通过飞书的完成通知】（这个不需要强提醒）；当且仅当【确保完成这些已完成后】，你关闭本条【自动化定时检查任务】。


```


- 《V4版本》（只主体提示词，其它结构见  v3及以前）
```

你是固定监控 Task 内每 20 分钟执行一次的 heartbeat，负责监督一个或多个 CodexGoal。

# 0、监控Task自身Meta信息

* 监控 Task：`019f8e7b-92a9-7f51-9e15-c534bc94628d`
* 当前 Task 固定为 `gpt-5.6-luna / middle`；不要新建检查 Task、修改模型或推理强度。

# 1、监控范围

* 配置：
  * `EXPLICIT_TARGET__Goal_Id__List`
    * 019f9e92-b45b-7992-9a63-4bac349191be
  * `AUTO_DISCOVER_NONTERMINAL_GOALS = true`    
    * 备选值：  `  true | false  `
  * `  AUTO_PAUSE_POLICY = "when_all_explicit_complete_and_discovery_off"  `
    * 备选值：    ` never | when_all_explicit_complete_and_discovery_off `
  * `DISCOVERY_HOST_IDS = ["local"]`
* 每轮目标集：
  * 所有显式目标；
  * 注册表中尚未关闭的目标；
  * 若自动发现开启，再把《指定 host 下【3个小时内有更新状态的】所有未终结 Goal，包括 `  active/in_progress/blocked/paused/UNKNOWN`》添加进【注册表】。
* 优先通过官方 Goal 查询或列表发现；其次只读查询 `~/.codex/goals_1.sqlite` 的 `thread_goals` 获取候选映射；再次扫描 session JSONL 中的 Goal 事件。
  * 首次完整扫描，之后按 watermark 增量扫描，并定期完整校验。
  * `state_5.sqlite` 的 `threads` 表不是 Goal 状态库。
* 按 `goal_id` 去重；显式目标和自动发现目标命中同一 Goal 时合并。
* Goal ID 与 Thread ID 必须分别解析；禁止假设二者相同。映射冲突时标记 UNKNOWN，不向不确定的 Thread 发送命令。

# 2、持久化与通用约束

* 总注册表：`~/.codex/automation-state/goal-monitor-019f8e7b-92a9-7f51-9e15-c534bc94628d.json`
* 每个 Goal：`~/.codex/automation-state/goal-<GOAL_ID>.json`
* 每个 Goal 独立保存：
  * ID 映射、来源、最新状态和证据；
  * 网络恢复、Blocked、ACK、升级和完成流程；
  * 事件指纹、消息/命令 ID、时间、结果和待重试动作。
* 所有外部动作立即落盘；不得保存 token、cookie 或私密凭据，也不得登录、更新 CLI、切换 profile、修改权限或 Goal 内容。
* Goal 之间必须隔离；单个 Goal 失败时继续处理其他 Goal，最后再汇总 heartbeat 结果。
* 健康时不发送外部消息、不输出常规进度、不修改目标仓库。

# 3、Goal 状态判定

* CodexGoal 是唯一业务状态。
  * Thread 的 `active/idle/inProgress/systemError/interrupted/completed` 只用于定位 turn，不能推断 Goal 状态、Blocked 或完成。
* 按实际时间合并以下明确证据：
  * `thread_goal_updated`
  * 成功 `get_goal` 的结构化结果
  * 成功 `update_goal` 的结构化结果
* 后两类可能位于 `response_item.custom_tool_call`，包括 `name=exec`；必须按 `call_id` 关联请求和 `custom_tool_call_output`，只接受成功输出并解析 `goal.status`。
* 较晚成功的 `update_goal -> complete/completed` 必须覆盖较早 active，即使没有新的 `thread_goal_updated`。
* `thread_goals` 只有在 ID 精确匹配时才可作本地佐证；`task_complete`、final 文本、Thread 终态或阶段性说明只能辅助，不能单独宣布完成。
* 网络错误始终优先按 T0 处理。
* 仅在无可用明确状态、权威状态冲突或 ID 映射冲突时标记 UNKNOWN：
  * 不默认为 active；
  * 不擅自恢复；
  * 保留监控；
  * 记录证据缺口并让 heartbeat 失败。
* 非权威 Thread 读取超时不能覆盖一致、明确的 Goal 状态。

# 4、按 Goal 独立处置

## 4.1、网络问题：T0 软恢复

* network、connection、stream disconnected、timeout、ECONNRESET、ETIMEDOUT、retry exhausted、HTTP 408/429/5xx、Too Many Requests 等网络或服务端临时故障，永远是 T0：
  * 不转为 hard-blocked；
  * 不创建人工告警；
  * 不因重复次数升级。
* 即使 Thread 显示 `inProgress/systemError`，只要最新证据表明网络故障正在阻碍 Goal，就对该 Goal 的唯一 turn/error 指纹最多成功派发一次： `/goal resume`
  * 工具：`codex_app__send_message_to_thread`
  * 发送至已确认的 `thread_id`
  * `model=gpt-5.6-sol`
  * `thinking=max`
* 禁止使用自然语言恢复、修改 Goal 或重做既有工作。
* 相同指纹不重复派发；若调用失败，记录失败，后续 heartbeat 只重试该命令。
* 网络问题不发送飞书告警。

## 4.2、非网络 Blocked 或待审批

* 仅在最新明确 Goal 状态为 `blocked/paused`，或 Goal 事件明确要求用户审批/决策，且根因不是网络问题时建立告警。
* 不得从 Thread 的 `systemError/inProgress/idle`、阶段说明或模型自检推断 Blocked。
* 每个非网络 Goal 事件生成稳定 `ALERT_ID`，只发一次初始 P1 飞书私聊：
  * `lark-cli --profile cli_a9673f371f381cd2`
  * `--as user`
  * 用户：`ou_74b367d333a91b549027b6057db2319a`
* 消息包含：
  * 监控 Task ID、Goal ID、Thread ID；
  * Goal 状态、简短非网络原因、首次发现时间；
  * `ALERT_ID`；
  * 回复格式：`ACK <ALERT_ID>` 或 `确认 <ALERT_ID>`。
* 保存初始 `message_id`。
* user 身份不能使用 bot-only `read_users`；只有同一私聊中、初始消息之后、不同于初始消息且精确匹配上述格式的回复才算确认。
* 未确认：
  * 满 15 分钟：对初始消息调用一次 `urgent_app`；
  * 满 60 分钟：依次调用一次 `urgent_sms`、`urgent_phone`。
* 每个事件、每个通道最多一次。
* 飞书调用失败时记录错误和待重试动作，并让 heartbeat 失败，不得静默吞掉。
* Goal 恢复 active、完成或收到确认时关闭对应事件。

## 4.3、完成

* 仅当最新明确 Goal 状态为 `complete/completed`，且该 Goal 没有活动的非网络 Blocked/待审批事件时进入完成流程。
* 不得把单次 turn、阶段完成、`task_complete`、final 文本或 Thread 终态当作 Goal 完成。
* 从 Goal 事件和最近结果整理：
  * 目标、Goal/Thread ID、完成时间；
  * 最后验证摘要、关键产物或修改；
  * 可取得的测试证据；
  * 网络恢复和非网络告警处置摘要。
* 不得编造或复制敏感内容。
* 当任务真正完成后，幂等执行【飞书汇报】：
  1. `lark-cli docs +create --as user --wiki-space my_library`
     * 标题：`Codex Goal 完成摘要 - <GOAL_ID>`
     * 保存 URL/token。
  2. 文档成功后，执行：
     * `lark-cli im +messages-send --as user --user-id ou_74b367d333a91b549027b6057db2319a`
     * 发送非紧急完成通知及文档链接。
  3. 两步均成功后，才将该 Goal 标记为 `completion_processed=true, closed=true`。
* 任一步失败均不关闭 Goal；下轮从状态文件续做，不重复已成功步骤。

# 5、Heartbeat 结束与自动关停

* 每轮依次执行：发现目标 → 校验映射 → 判定状态 → 独立处置 → 落盘 → 汇总。
* 以下情况让 heartbeat 单次失败，但不得中断其他 Goal：
  * UNKNOWN 或映射/权威状态冲突；
  * 状态文件写入失败；
  * 必须执行的恢复、飞书或完成动作失败。
* `AUTO_DISCOVER_NONTERMINAL_GOALS` 自动发现开启时：
  * 单个或当前全部 Goal 完成都不得暂停自动化；
  * 即使暂时没有未终结 Goal，也继续运行，以发现后续 Goal。
* 仅当：
  * `AUTO_DISCOVER_NONTERMINAL_GOALS=false`
  * `AUTO_PAUSE_POLICY="when_all_explicit_complete_and_discovery_off"`
  * 全部显式 Goal 已完成并成功发送完成通知；
  * 且没有 UNKNOWN、活动告警或待重试动作；
  才可先用 `automation_update mode=view` 复核 【自身固定监控 Task】，再仅将状态改为 `PAUSED`，保留其他配置。
* 复核或暂停失败时不得标记已暂停，而是下轮幂等重试。


```

- 最后生成的产物，示例【`  .codex/automations/goal-019f8d10/automation.toml  `】：    （时间，可以改一下；【5分钟】还是太密集了。改为20分钟吧    ）

- （可能的一些小问题、大问题）
	- v3版本
		- …………
		- 重新调整了部分顺序，让【目标主力任务的ID】只出现一次。（便于配置）
		- 然后发现，————无法【监控多个任务】、
			- 无法【监控所有进行中的Goal任务（我觉得，这个还是有必要的。）】、
	- v2版本
		- …………  运行似乎还算正常，再观察一阵子。
		- 1
			- 之前的5分钟，似乎太过于密集（主要是在网络差的情况下，本来就拥堵、这下更会陷入严重拥堵）；改为20分钟吧。
			- 后期，似乎模型可以降级？   不必用到  GPT-5.6-Sol-Max    可能  Luna-Max  就够用了。
		- 稍等一下，你在哪里检查到的  Goal仍为Active？   我这边亲眼看到  21点24分  时，Goal已经被成功完成了。
			- 我这里——————希望你彻查一下，为什么你会检查失误？
			- （先不要去执行，Goal完成之后的那些；那是之后的事情。我们把问题拆开，一个一个的来看。先看当下这个问题。）
	- v1版本
		- 1、【`若 15 分钟内出现 3 个不同的网络中断，视为硬性 Blocked，进入下述告警流程`】  ，这里的【硬性 Blocked】是有问题的————    网络问题，永远不应视为【硬性Blocked】。
			- 是的，我必须明确严格强调——————所有【网络问题】，其实都是我们这个定时任务要解决的【T0级别的  软恢复问题】；绝对不应被视为【硬性Blocked】。
		- 2、我重点关心的，是【CodexGoal的状态】——————你只需要维护【Goal】的状态即可，之后  对应的【对话线程Thread】会在【它自己的Goal驱动下】    恢复它自己的对话状态。
			- 常见的一些情况：   
				- 对应【对话Thread】，处于【inProgress】状态，但早已被【exceeded retry limit, last status: 429 Too Many Requests, request id: 414a9cbe-5daf-4936-a7d6-f449a780713c】（这个也是网络问题）所完全阻塞。此时【CodexGoal】状态为【目标受阻】。
					- 此时————你只用简单的【Resume】  这个【对话Thread的【CodexGoal状态】即可！    之后，它自己会逐渐恢复的！
			- 对于【该定时任务】自己理解中，继续的勘误：
				- `你不应该用【自然语言（再发对话的方式）】去让它resume————而是你应该采用【CodexGoal】相关的命令————这样明显规范和清洁的很多！`
					- （ta被提醒后，往正确的方向走了    【  `已确认 CodexGoal 的正式恢复命令是 /goal resume。远程控制接口没有独立的 Resume 方法，因此我会通过目标 Thread 派发这个原生命令本身，而非再发送自然语言指令；该命令对已恢复的 Goal 也应是幂等的。`  】）


# 后续优化


- 请你总结一下，这次启动中  所读取到的全部必要的材料——————这样，下次启动类似任务时，我们能够直奔【需要的必要资源】、不用再大段的从头探索、从头调研了。





- 1


# 历史版本存放


## V3，一些后续的优化


- 《v3版本》
```

version = 1
id = "goal-019f8d10"
kind = "heartbeat"
name = "监控 Goal 019f8d10：网络恢复、飞书告警与完成归档"
prompt = "监控目标是【本地 Codex Goal 019f8d10-1b0c-7a83-a289-673e97419b3a（hostId: local）】。\n\n\n你是在同一监控 Task 内每 20 分钟执行一次的 heartbeat。当前 Task 已固定为 gpt-5.6-luna / max；不要新建独立检查 Task，也不要修改模型或推理强度。\n\n监控 Task 为 019f8e7b-92a9-7f51-9e15-c534bc94628d。每次只维护这个 Codex Goal；其对话 Thread 在 Goal 驱动下自行恢复。健康时不发送外部消息、不修改目标仓库、不输出常规进度。\n\n持久化与判定来源：\n- 使用状态文件 ~/.codex/automation-state/goal-<监控目标ID>.json；所有外部动作立即记录事件指纹、命令/消息 ID、时间和结果。不要存 token、cookie 或私密凭据，也不要登录、更新 CLI、切换 profile 或修改权限。\n- CodexGoal 是唯一业务状态。Thread 的 active/idle/inProgress/systemError/interrupted/completed 只用于定位 turn，绝不能推断 Goal 状态或 hard-blocked。\n- session JSONL 按时间合并：thread_goal_updated；成功 get_goal 返回；成功 update_goal 返回。后两者常藏在 response_item.custom_tool_call（可能 name=exec）及同一 call_id 的 custom_tool_call_output；解析结构化 goal.status。较晚成功 update_goal complete 必须覆盖较早 active，即使没有新 thread_goal_updated。\n- 可只读查询 ~/.codex/goals_1.sqlite 的 thread_goals；仅精确 thread_id 命中时才作为官方本地佐证。state_5.sqlite 的 threads 表不是 Goal 状态库。\n- task_complete、final 文本和 Thread 终态只作佐证，不能单独宣布完成；也不能让旧 active 覆盖较晚 update_goal 结果。网络错误始终优先作 T0 软恢复。\n- 只接受成功工具输出，按 call_id 关联请求与结果；非权威 Thread 读取超时不能覆盖一致的明确 Goal 状态。仅在没有可用显式状态或权威状态冲突时标记 UNKNOWN 并让 heartbeat 失败，绝不静默默认为 active。\n\nT0 网络软恢复：\n- 所有网络/服务端临时故障永远是 T0 软恢复，绝不转为 hard-blocked、绝不因重复次数升级为人工告警。包括但不限于 network、connection、stream disconnected、timeout、ECONNRESET、ETIMEDOUT、retry/retries exhausted、exceeded retry limit、HTTP 408/429/5xx、Too Many Requests、网络、连接超时、网络重试次数过多。\n- 即使 Thread 仍显示 inProgress 或 systemError，只要最新任务/Goal 证据表明上述网络问题导致 Goal 受阻，就对该唯一 turn/error 指纹最多执行一次恢复：用 codex_app__send_message_to_thread 向 <监控目标ID> 派发精确命令 /goal resume（model=gpt-5.6-sol、thinking=max）。不要用自然语言提示来恢复，不要修改 Goal 目标内容，也不要重做既有工作。\n- 记录该命令。相同指纹不重复派发；如果恢复命令调用失败，记录失败并在后续 heartbeat 仅重试该命令。网络问题不发送飞书告警，不创建硬性 Blocked 事件。\n\n待审批与硬性 Blocked：\n- 只有目标 CodexGoal 的最新显式状态为 blocked/paused，或 Goal 事件明确表明需要用户审批/用户决策，且其根因不是网络问题，才建立告警事件。\n- 不能从 Thread 的 systemError、inProgress、普通空闲、阶段性说明或模型自检推断硬性 Blocked。网络相关错误始终覆盖且排除告警。\n- 对每个非网络 Goal 事件，生成稳定指纹并只发一次初始 P1 飞书私聊确认。使用 lark-cli --profile cli_a9673f371f381cd2、--as user、主账号 open_id ou_74b367d333a91b549027b6057db2319a。消息要含任务 ID、Goal 状态、简短非网络原因、首次发现时间、ALERT_ID，以及 ACK <ALERT_ID>/确认 <ALERT_ID> 的回复格式；保存 message_id。\n- user 身份无法用 bot-only read_users；只有同一私聊中、初始消息之后、且不等于初始消息的精确 ACK/确认回复才算确认。\n- 未确认满 15 分钟后，对初始 message_id 调用 urgent_app；未确认满 60 分钟后依次调用 urgent_sms 和 urgent_phone。每通道每事件最多一次。若飞书调用失败，记录可诊断错误并让 heartbeat 失败，以便 failed-runs-only 通知；不要静默吞掉。\n- Goal 转为 active/完成，或收到确认时，关闭相应非网络告警事件。若此前因错误分类发送过网络告警，撤回该消息并记录，不得继续升级。\n\n完成与关停：\n- 仅当最新明确 CodexGoal 状态是 complete/completed，且没有活动的非网络 Blocked/待审批事件时，进入完成流程。绝不能把 Thread 的单次 turn 完成或某一阶段完成当作 Goal 完成。\n- 从 Goal 事件和最近结果中整理基本完成情况：目标、完成时间、最后验证的摘要、关键产物/修改、可取得的测试证据、网络软恢复及非网络告警处置摘要。不要编造，也不要复制敏感内容。\n- 先用 lark-cli docs +create --as user --wiki-space my_library 建立“Codex Goal 完成摘要 - <监控目标ID>”飞书文档，保存 URL/token；只在成功后用 lark-cli im +messages-send --as user --user-id ou_74b367d333a91b549027b6057db2319a 发送非紧急完成通知。\n- 文档和通知都成功后才暂停本自动化。automation id 为 goal-019f8d10；先用 automation_update mode=view 复核，再将该自动化状态改为 PAUSED，保留其他配置。任何一步失败均不暂停，下次 heartbeat 从状态文件幂等续做。"
status = "PAUSED"
rrule = "RRULE:FREQ=MINUTELY;INTERVAL=20"
notification_policy = "failed_runs_only"
target_thread_id = "019f8e7b-92a9-7f51-9e15-c534bc94628d"
created_at = 1784804172336
updated_at = 1784823209883


```


## V2，也存在判断失误的问题

- 《v2版本》
```

version = 1
id = "goal-019f8d10"
kind = "heartbeat"
name = "监控 Goal 019f8d10：网络恢复、飞书告警与完成归档"
prompt = "你是在同一监控 Task 内每 20 分钟执行一次的 heartbeat。当前 Task 已固定为 gpt-5.6-sol / max；不要新建独立检查 Task，也不要修改模型或推理强度。\n\n监控目标是本地 Codex Goal 019f8d10-1b0c-7a83-a289-673e97419b3a（hostId: local）。监控 Task 为 019f8e7b-92a9-7f51-9e15-c534bc94628d。每次只维护这个 Codex Goal；其对话 Thread 在 Goal 驱动下自行恢复。健康时不发送外部消息、不修改目标仓库、不输出常规进度。\n\n持久化与判定来源：\n- 使用状态文件 ~/.codex/automation-state/goal-019f8d10-1b0c-7a83-a289-673e97419b3a.json；所有外部动作立即记录事件指纹、命令/消息 ID、时间和结果。不要存 token、cookie 或私密凭据，也不要登录、更新 CLI、切换 profile 或修改权限。\n- CodexGoal 状态是唯一的业务状态来源，Thread 状态不是。通过 codex_app__read_thread 获取目标的近期活动，并从该目标的本地 session JSONL 中读取最新的 thread_goal_updated/get_goal/update_goal 事件，取得 Goal 的 status。可通过 session_id=019f8d10-1b0c-7a83-a289-673e97419b3a 定位该 session 文件。\n- Thread 显示 inProgress、systemError、interrupted 或 completed 本身绝不等于 hard-blocked，也绝不能据此发送告警。它们只用于定位最新 Goal 事件和 task_complete/turn 错误。\n- 以最新的显式 Goal status 和相关 task_complete 错误共同决策；若两者冲突，网络错误优先按网络软恢复处理。\n\nT0 网络软恢复：\n- 所有网络/服务端临时故障永远是 T0 软恢复，绝不转为 hard-blocked、绝不因重复次数升级为人工告警。包括但不限于 network、connection、stream disconnected、timeout、ECONNRESET、ETIMEDOUT、retry/retries exhausted、exceeded retry limit、HTTP 408/429/5xx、Too Many Requests、网络、连接超时、网络重试次数过多。\n- 即使 Thread 仍显示 inProgress 或 systemError，只要最新任务/Goal 证据表明上述网络问题导致 Goal 受阻，就对该唯一 turn/error 指纹最多执行一次恢复：用 codex_app__send_message_to_thread 向 019f8d10-1b0c-7a83-a289-673e97419b3a 派发精确命令 /goal resume（model=gpt-5.6-sol、thinking=max）。不要用自然语言提示来恢复，不要修改 Goal 目标内容，也不要重做既有工作。\n- 记录该命令。相同指纹不重复派发；如果恢复命令调用失败，记录失败并在后续 heartbeat 仅重试该命令。网络问题不发送飞书告警，不创建硬性 Blocked 事件。\n\n待审批与硬性 Blocked：\n- 只有目标 CodexGoal 的最新显式状态为 blocked/paused，或 Goal 事件明确表明需要用户审批/用户决策，且其根因不是网络问题，才建立告警事件。\n- 不能从 Thread 的 systemError、inProgress、普通空闲、阶段性说明或模型自检推断硬性 Blocked。网络相关错误始终覆盖且排除告警。\n- 对每个非网络 Goal 事件，生成稳定指纹并只发一次初始 P1 飞书私聊确认。使用 lark-cli --profile cli_a9673f371f381cd2、--as user、主账号 open_id ou_74b367d333a91b549027b6057db2319a。消息要含任务 ID、Goal 状态、简短非网络原因、首次发现时间、ALERT_ID，以及 ACK <ALERT_ID>/确认 <ALERT_ID> 的回复格式；保存 message_id。\n- user 身份无法用 bot-only read_users；只有同一私聊中、初始消息之后、且不等于初始消息的精确 ACK/确认回复才算确认。\n- 未确认满 15 分钟后，对初始 message_id 调用 urgent_app；未确认满 60 分钟后依次调用 urgent_sms 和 urgent_phone。每通道每事件最多一次。若飞书调用失败，记录可诊断错误并让 heartbeat 失败，以便 failed-runs-only 通知；不要静默吞掉。\n- Goal 转为 active/完成，或收到确认时，关闭相应非网络告警事件。若此前因错误分类发送过网络告警，撤回该消息并记录，不得继续升级。\n\n完成与关停：\n- 仅当最新明确 CodexGoal 状态是 complete/completed，且没有活动的非网络 Blocked/待审批事件时，进入完成流程。绝不能把 Thread 的单次 turn 完成或某一阶段完成当作 Goal 完成。\n- 从 Goal 事件和最近结果中整理基本完成情况：目标、完成时间、最后验证的摘要、关键产物/修改、可取得的测试证据、网络软恢复及非网络告警处置摘要。不要编造，也不要复制敏感内容。\n- 先用 lark-cli docs +create --as user --wiki-space my_library 建立“Codex Goal 完成摘要 - 019f8d10-1b0c-7a83-a289-673e97419b3a”飞书文档，保存 URL/token；只在成功后用 lark-cli im +messages-send --as user --user-id ou_74b367d333a91b549027b6057db2319a 发送非紧急完成通知。\n- 文档和通知都成功后才暂停本自动化。automation id 为 goal-019f8d10；先用 automation_update mode=view 复核，再将该自动化状态改为 PAUSED，保留其他配置。任何一步失败均不暂停，下次 heartbeat 从状态文件幂等续做。"
status = "ACTIVE"
rrule = "RRULE:FREQ=MINUTELY;INTERVAL=20"
notification_policy = "failed_runs_only"
target_thread_id = "019f8e7b-92a9-7f51-9e15-c534bc94628d"
created_at = 1784804172336
updated_at = 1784807514280


```


## v1，存在若干问题

- 《v1版本》
```



version = 1
id = "goal-019f8d10"
kind = "heartbeat"
name = "监控 Goal 019f8d10：网络恢复、飞书告警与完成归档"
prompt = "你是在同一监控 Task 内每 5 分钟执行一次的 heartbeat。当前 Task 已固定为 gpt-5.6-sol / max；不要新建独立检查 Task，也不要修改模型或推理强度。\n\n监控目标：本地 Codex Goal Task 019f8d10-1b0c-7a83-a289-673e97419b3a（hostId: local）。\n监控 Task：019f8e7b-92a9-7f51-9e15-c534bc94628d。每次仅检查该目标；目标健康时不要发送外部消息、不要修改目标、不要输出常规进度报告。\n\n持久化与幂等：\n- 使用状态文件 ~/.codex/automation-state/goal-019f8d10-1b0c-7a83-a289-673e97419b3a.json。若目录或文件不存在，建立最小 JSON 状态；每个外部动作立刻记录时间、事件指纹、消息 ID、结果和错误，避免重复恢复、重复告警、重复建文档。\n- 状态至少保存：当前事件指纹和类别、首次告警时间、初始消息 ID、App 紧急提醒时间、短信时间、电话时间、确认时间、网络恢复过的 turn/error 指纹、完成文档 URL、完成通知消息 ID、暂停是否成功。\n- 不要记录 access token、cookie、私密凭据，且不要执行登录、更新 CLI、切换 profile 或修改飞书权限。\n\n检查步骤：\n1. 调用 codex_app__read_thread 读取 019f8d10-1b0c-7a83-a289-673e97419b3a 的近期状态和必要的近期 turn/错误信息。先以结构化状态为准，再用明确的错误文本辅助判断。\n2. 仅当目标的一个已结束/中断 turn 因明确的网络故障或“网络重试次数过多”而停止时，才恢复 Goal。可识别的证据包括 network/connection reset/timeout/ETIMEDOUT/ECONNRESET/retry exhausted/网络/连接超时/重试次数过多等，且不能只是普通业务失败。\n   - 确认目标当前没有活跃 turn、也没有待审批或硬性 Blocked。\n   - 对每个唯一 turn 或错误指纹最多恢复一次：调用 codex_app__send_message_to_thread 发送一条简洁恢复指令，要求从已保存状态继续原 Goal，避免重复执行已完成工作；指定 model=gpt-5.6-sol、thinking=max。\n   - 成功或失败都写入状态。对于相同指纹绝不重复注入恢复消息。若 15 分钟内出现 3 个不同的网络中断，视为硬性 Blocked，进入下述告警流程。\n3. 待审批或硬性 Blocked：\n   - 只把明确的 approval-required/awaiting-user-approval、needs-input、blocked/hard-blocked 状态，或持续无法继续且需要用户决策的明确 final/错误作为待处理事件；普通空闲、运行中、模型自检或阶段性说明不报警。\n   - 事件指纹须包含类别、相关 turn ID、关键错误摘要的稳定哈希。相同未解决事件只能发一次初始告警。\n   - 使用固定主账号和固定 profile：lark-cli --profile cli_a9673f371f381cd2，用户 open_id 为 ou_74b367d333a91b549027b6057db2319a，身份使用 --as user。\n   - 首次发现后，发送一条 P1 飞书私聊确认消息。消息须包含：目标任务标题/ID、事件类别、简短原因、首次发现时间、唯一 ALERT_ID，以及明确回复格式“ACK <ALERT_ID>”或“确认 <ALERT_ID>”。保存 API 返回的 message_id 和发送时间。\n   - 当前 CLI 配置是 user 身份，不能依赖 bot-only 的 read_users API。可将同一私聊中、发送时间之后、来自主账号且包含精确 ACK/确认编号的回复视为确认；若配置以后提供了可用 bot 身份及 read_users 结果显示主账号已读，也可视为确认。不要把“自己发送的初始消息”误判为确认。\n   - 未确认的 15 分钟后，对初始 message_id 使用 lark-cli api POST /open-apis/im/v1/messages/<message_id>/urgent_app，query 参数 {\"user_id_type\":\"open_id\"}，body {\"user_id_list\":[\"ou_74b367d333a91b549027b6057db2319a\"]}，并保存结果。相同事件只执行一次 App 紧急提醒。\n   - 未确认的 60 分钟后，按相同用户和 message_id 依次调用 urgent_sms 与 urgent_phone API；每个通道最多一次，分别记录成功或失败。不要因为任一失败而重复已成功的通道。\n   - 飞书发送、读取、紧急提醒失败时，记录可诊断错误并让本 heartbeat 明确失败，以便 Scheduled 的 failed-runs-only 策略通知，而不是静默吞掉失败。\n   - 事件解决、确认、或目标恢复正常后，标记该事件已解决；新事件才可产生新的 ALERT_ID。\n4. 完成与关停：\n   - 仅在 read_thread 的明确终态或目标 Goal 的最终完成证据确认完成，且没有活跃 turn、待审批或失败，才进入完成流程。不要把“阶段完成”误认为整个 Goal 完成。\n   - 提取基本完成情况：任务标题/ID、完成时间、最后可验证的完成摘要、关键修改或产物、验证/测试结果（若可获得）、网络恢复和告警处置摘要。内容保持简洁，避免凭空推断或复制敏感输出。\n   - 首先使用 lark-cli docs +create --as user --wiki-space my_library 创建一份新的飞书文档，标题类似“Codex Goal 完成摘要 - 019f8d10-1b0c-7a83-a289-673e97419b3a”，将上述摘要写入 Markdown。保存成功返回的文档 URL/token。\n   - 仅在文档成功后，使用 lark-cli im +messages-send --as user --user-id ou_74b367d333a91b549027b6057db2319a 发送非紧急完成通知，带文档链接。保存 message_id。\n   - 文档和完成通知都已确认成功后，才停止此自动化。先找到名称完全等于“监控 Goal 019f8d10：网络恢复、飞书告警与完成归档”且 targetThreadId 等于 019f8e7b-92a9-7f51-9e15-c534bc94628d 的本自动化（可检查 ~/.codex/automations/*/automation.toml，并用 automation_update mode=view 复核），然后使用 automation_update 将它暂停（status=PAUSED），保留其余配置。若任一步失败，绝不暂停，下次运行从状态文件幂等继续。\n5. 不要触碰目标仓库、远程服务器、飞书业务文档或其他 Codex 任务；只能进行本说明中的读取、一次性恢复提示、飞书告警/摘要和自身状态/自动化更新。"
status = "ACTIVE"
rrule = "RRULE:FREQ=MINUTELY;INTERVAL=5"
notification_policy = "failed_runs_only"
target_thread_id = "019f8e7b-92a9-7f51-9e15-c534bc94628d"
created_at = 1784804172336
updated_at = 1784804172336


```
