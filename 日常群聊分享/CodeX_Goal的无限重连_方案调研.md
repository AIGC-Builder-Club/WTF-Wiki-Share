参考资料：
- https://chatgpt.com/share/6a3e1d06-21a8-83ee-9234-711716b7fd36
- 附件包：
	- 见《CodeX_AppServer_Goal_WatchDog》目录。




# 提问1

> [!NOTE]
> 你好，我目前重度使用  macminim4  上面的CodexAPP。并且非常喜欢goal命令模式。
> 
> 
> 现在，有时我的goal，会在【网络相关错误、或者重试超过5次、或者429报错】之后，进入block状态————进而停止后续的重试以及goal的运行。  （哪怕在我的网络恢复后，依然停在block原地）
> 
> 
> 我在想，我有什么方法，能够【让  这种相关网络错误  不会让goal被阻塞；  或者可以反复重试、或者可以让  goal无限的延续下去】吗？
> 
> 互联网上，可能有相关的人研究这方面。  也请你为我广泛的找一下。   如果能解决这个问题，那将对我的帮助很大。





# 回答1


## 结论

**Codex App 目前无法通过一个配置实现真正“无限重试”。**当某一轮遭遇不可恢复错误，或者内部重试耗尽后，Goal 会被明确改成 `blocked`；只有 `active` 状态的 Goal 才会自动启动下一轮。因此网络恢复后，它也不会自行醒来。这个行为是为了避免错误循环持续消耗额度。

你可以用以下三层方案，达到接近“不间断运行”的效果。

## 1. 先提高 Codex 自身的网络容错

Codex 当前默认：

- 流连接中断重试 5 次；
    
- 普通 HTTP 请求重试 4 次；
    
- 用户配置的两种重试都被硬限制为最多 100 次。
    

在 Mac 上编辑：

```bash
mkdir -p ~/.codex
cp ~/.codex/config.toml ~/.codex/config.toml.backup 2>/dev/null || true
open -e ~/.codex/config.toml
```

加入：

```toml
model_provider = "openai_resilient"

[model_providers.openai_resilient]
name = "OpenAI"
wire_api = "responses"
requires_openai_auth = true

# 普通请求：网络、5xx 等
request_max_retries = 20

# 流断开：默认 5，最大 100
stream_max_retries = 100

# 5 分钟无数据才判断流失联
stream_idle_timeout_ms = 300000

# 网络、代理或路由器对 WebSocket 不稳定时，改用 HTTPS/SSE
supports_websockets = false
```

这里故意使用自定义 ID `openai_resilient`，因为内置的 `openai` provider ID 不能直接覆盖。`requires_openai_auth = true` 会继续使用现有的 ChatGPT 登录；省略 `base_url` 时，ChatGPT 登录模式仍会选择 Codex 的 ChatGPT 后端。

保存后：

1. 完全退出 Codex App；
    
2. 重新打开；
    
3. 最好新建一个线程测试；
    
4. 确认模型仍能正常调用。
    

`supports_websockets = false` 对机场、公司代理、透明网关以及经常切换网络的环境通常更稳；代价是可能失去 WebSocket 的部分低延迟优势。若 HTTPS/SSE 反而不稳定，再改回 `true`。

### 这个配置解决不了所有 429

目前 Codex 的底层重试配置对 `429` 明确设置了 `retry_429: false`。某些 429 会被识别为账户用量限制，另一些会成为 `RetryLimit` 错误，所以单纯把 `stream_max_retries` 或 `request_max_retries` 调到 100，**并不能保证 429 自动恢复**。

近期也有多名 Codex App 用户报告完全相同的 `exceeded retry limit, last status: 429 Too Many Requests`，包括 macOS 上的报告，因此这并不像是你机器上的孤立故障。

## 2. Goal 已经 blocked 时，正确恢复方式是重新激活

网络恢复后，在同一个线程中执行：

```text
/goal resume
```

或者点击 Goal 状态栏上的 **Resume**。

这不是重新创建目标，而是把已有 Goal 从 `blocked`、`paused` 或 `usageLimited` 改回 `active`。状态重新变成 `active` 后，Goal runtime 才会再次调用自动续跑逻辑。源码中 `Blocked` 会清除活动状态，而重新设为 `Active` 会立即尝试继续。

如果重新打开线程，Codex 也会识别被暂停、阻塞或用量限制的 Goal，并显示恢复提示。

建议恢复前先判断错误类型：

- `stream disconnected`、DNS、TLS、connection reset：网络恢复后直接 Resume。
    
- `429 Too Many Requests`：先等待几分钟，再 Resume；快速连续点击只会制造更多 429。
    
- `usage limit reached` 并显示重置时间：必须等额度恢复，重试次数设置无效。
    
- `context window exceeded` 或反复 compact 失败：优先处理压缩或迁移线程。
    

## 3. 特别注意远程上下文压缩错误

长时间 Goal 很容易在自动压缩上下文时遇到：

```text
Error running remote compact task:
stream disconnected before completion
```

已有一份与您描述几乎完全一致的 macOS 报告：Goal 运行约一小时，远程压缩网络失败，随后显示 `Goal blocked`；手动点击 Resume 后才继续。

Codex 当前会把名称为 `"OpenAI"` 的 provider 视为支持远程压缩，然后调用远程 compact 路径；其他 provider 则走本地压缩路径。

如果你的日志明确显示失败地址包含 `/responses/compact`，可以尝试一个**非官方但基于当前源码有效的实验方案**：

```toml
[model_providers.openai_resilient]
name = "OpenAI Resilient"
wire_api = "responses"
requires_openai_auth = true
request_max_retries = 20
stream_max_retries = 100
stream_idle_timeout_ms = 300000
supports_websockets = false
```

核心变化只有：

```toml
name = "OpenAI Resilient"
```

这会让当前实现不再把它识别为内置 OpenAI provider，从而可能改走本地 compaction，避开容易断开的远程压缩端点。社区已经请求增加正式的“禁用远程压缩”开关，但目前尚无受支持的配置；有人测试的 `compact_mode = "local"` 也不会影响当前路径。

这属于实现细节，升级后可能失效，也可能影响部分 OpenAI 专属能力。因此建议顺序是：

1. 先保持 `name = "OpenAI"`；
    
2. 增加重试并关闭 WebSocket；
    
3. 只有在确认 `/responses/compact` 是主要故障源时，才改成 `"OpenAI Resilient"`。
    

## 4. 让恢复后的 Goal 不丢进度

在 Goal 指令中加入持久化检查点。示例：

```text
/goal 完成以下目标，持续运行直到所有验收条件满足：

<你的目标和验收条件>

可靠性要求：
1. 每完成一个可验证阶段，更新项目根目录 TASK_STATE.md。
2. TASK_STATE.md 必须记录：
   - 已完成事项
   - 当前进行到哪里
   - 下一步具体操作
   - 最后成功运行的验证命令和结果
   - 当前阻塞原因
3. 每个稳定阶段做一个小粒度 git commit。
4. 遇到网络错误、429、流中断或临时工具错误时，不要把业务目标标记为完成或失败。
5. 恢复运行后，先读取 TASK_STATE.md、git status 和最近提交，再从中断点继续。
```

这不能阻止 Codex 客户端把 Goal 改成 `blocked`，但能保证你按 Resume、迁移到新线程，甚至重启 App 后，模型能够准确接续。

## 5. 真正的“自动无限续跑”需要外层守护程序

Codex 内置 Goal 目前没有“网络恢复后自动唤醒 blocked Goal”的持久调度器。相关的 wait/wake 能力仍是公开的功能请求；当前 `blocked`、`usageLimited`、`budgetLimited` 和 `complete` 都会停止自动续跑。

真正无人值守的方案是使用 `codex app-server` 做一个 watchdog。它监控同一线程的 Goal 状态：

```text
读取 thread/goal/get

active:
    继续监控

blocked:
    指数退避等待
    确认网络恢复
    thread/goal/set(status = "active")

usageLimited:
    长时间等待或等到额度重置
    thread/goal/set(status = "active")

paused / complete / budgetLimited:
    不自动恢复
```

推荐退避策略：

```text
30 秒 → 1 分钟 → 2 分钟 → 4 分钟 → 8 分钟 → 最长 15 分钟
```

一旦成功运行一段时间，就把退避计数清零。对于 429，不要每几秒重新激活，否则可能加重限流。

`app-server` 本身提供持久线程的 `thread/resume`，以及 `thread/goal/get`、`thread/goal/set`、`thread/goal/clear`，所以它能够从外部把 blocked Goal 重新设置为 active。

这才是真正接近“无限延续”的架构，不过建议把桌面 App 和 watchdog 分时使用，避免两个客户端同时操纵同一个活动线程。

## 推荐落地顺序

1. 先备份并加入 `openai_resilient` provider。
    
2. 设置 `stream_max_retries = 100`。
    
3. 首轮使用 `supports_websockets = false`。
    
4. 每个 Goal 强制维护 `TASK_STATE.md` 和 Git 检查点。
    
5. 遇到 block，网络恢复后使用 `/goal resume`。
    
6. 若故障几乎总发生在 `/responses/compact`，再尝试更改 provider 的 `name` 以走本地压缩。
    
7. 对真正无人值守的长任务，使用 app-server watchdog 自动执行退避与重新激活。


# 提问2

> [!NOTE]
> 【codex app-server 做一个 watchdog】这一块我非常感兴趣，能详细展开为我讲一下吗？



# 回答2


可以。核心机制是：**watchdog 不直接发“继续”提示，也不创建新 turn；它只把符合重试条件的现有 Goal 从 `blocked` 改回 `active`。**随后 Codex 自己会在 thread 空闲时继续 Goal。

我已经做成了可运行版本，并附带中文说明、LaunchAgent 安装脚本和离线 smoke test：

[下载 Codex Goal Watchdog 完整包](sandbox:/mnt/data/codex-goal-watchdog.zip)  
[查看中文部署说明](sandbox:/mnt/data/codex-goal-watchdog/README_zh.md)  
[查看主程序](sandbox:/mnt/data/codex-goal-watchdog/codex_goal_watchdog.py)

## 1. Watchdog 实际在做什么

`codex app-server` 是 Codex 的底层控制接口，使用 JSON-RPC 2.0。最简单的 stdio 模式是一行一个 JSON 消息。客户端连接后必须先发送 `initialize`，再发送 `initialized`。

整体结构是：

```text
持久化的 Codex thread / Goal
        存放在 ~/.codex
                │
                ▼
codex_goal_watchdog.py
                │
                ▼
codex app-server --listen stdio://
                │
                ├─ thread/resume
                ├─ thread/goal/get
                ├─ 监听 turn/completed
                ├─ 监听 thread/goal/updated
                └─ thread/goal/set(status="active")
```

具体协议顺序近似于：

```json
{"id":"1","method":"initialize","params":{"clientInfo":{"name":"codex_goal_watchdog"}}}
{"method":"initialized"}

{"id":"2","method":"thread/resume","params":{"threadId":"THREAD_ID"}}
{"id":"3","method":"thread/goal/get","params":{"threadId":"THREAD_ID"}}

{"id":"4","method":"thread/goal/set","params":{
  "threadId":"THREAD_ID",
  "status":"active"
}}
```

app-server 正式提供 `thread/resume`、`thread/goal/get`、`thread/goal/set`、Goal 更新通知和 thread 状态通知。Goal 是持久化状态，不依赖 watchdog 一直记住 objective。

Goal 支持这些状态：

```text
active
paused
blocked
usageLimited
budgetLimited
complete
```

`thread/goal/set` 可以只传 `status`，因此重新激活时不会覆盖原来的 objective、token budget 或进度。

## 2. 为什么不会正常情况下重复启动两轮

当 Goal 被设为 `active` 时，Goal runtime 会调用内部的 `continue_if_idle()`。它首先检查 Goal 是否仍为 active，然后使用 `try_start_turn_if_idle()`；thread 不空闲时，自动启动会被拒绝。

因此 watchdog 可以反复确认：

```text
Goal status = active
```

而不是直接调用：

```text
turn/start
```

这是重要的幂等性设计：

```text
set active
    │
    ├─ thread idle   → Codex 启动下一轮
    └─ thread active → 不再启动第二轮
```

不过这个保护主要是**同一个 app-server runtime 内部**的。它不代表两个独立 app-server 进程可以安全地同时写同一个 thread。

## 3. 为什么 Goal 网络出错后会永远停住

当前 Goal runtime 在 turn 发生最终错误时，会将 Goal：

- 用量限制错误设置为 `usageLimited`；
    
- 其他不可重试错误或内部重试耗尽设置为 `blocked`。
    

源码注释明确说明，这是为了阻止自动 continuation 循环持续耗费 token，尤其是上下文压缩错误。

因此网络恢复后，Codex 并不会自动把：

```text
blocked → active
```

watchdog 补上的正是这个状态转换。

## 4. Watchdog 如何判断“应该重试”

每个失败的 turn 都可以包含：

```text
status
error.message
error.codexErrorInfo
error.additionalDetails
```

`codexErrorInfo` 会区分网络连接失败、响应流断开、内部服务器错误、重试次数耗尽、usage limit、上下文超限、认证失败、bad request、sandbox error 等。

脚本的默认策略是：

|错误类别|行为|
|---|---|
|`httpConnectionFailed`|自动恢复|
|`responseStreamConnectionFailed`|自动恢复|
|`responseStreamDisconnected`|自动恢复|
|`internalServerError`|自动恢复|
|`serverOverloaded`|自动恢复|
|`responseTooManyFailedAttempts`|自动恢复|
|上述错误中的 HTTP 429|使用更长退避|
|`usageLimitExceeded`|默认不自动恢复|
|`contextWindowExceeded`|不自动恢复|
|`unauthorized`|不自动恢复|
|`badRequest`|不自动恢复|
|`sandboxError`|不自动恢复|
|未分类错误|默认不自动恢复|

### 429 需要分成两种

Codex 会把部分 429 识别成真实的账户用量限制，变成 `UsageLimitReached`；其他普通 429 则可能成为 `RetryLimit`，并携带最后的 HTTP 状态。

所以脚本区分：

```text
usageLimitExceeded
```

和：

```text
responseTooManyFailedAttempts {
    httpStatusCode: 429
}
```

前者默认停止，等额度恢复；后者默认按 5 分钟起步进行退避重试。

## 5. 退避，而不是疯狂点击 Resume

默认策略：

```text
普通网络错误：
约 30 秒
→ 60 秒
→ 120 秒
→ 240 秒
→ 480 秒
→ 最长约 15 分钟

429：
约 5 分钟
→ 10 分钟
→ 15 分钟
→ 此后每约 15 分钟
```

每次延迟会加入少量随机抖动，避免多个任务同时醒来。

重激活之前还会执行一次网络探测：

```text
HEAD https://chatgpt.com/
```

只要收到任何 HTTP 响应，即认为 DNS、TCP、TLS 和基本路由已经恢复；不要求返回 200。

成功完成一轮后：

```text
consecutive_failures = 0
```

退避状态持久化到：

```text
~/.codex/watchdogs/<THREAD_ID>.json
```

即使 watchdog 或 Mac 重启，也不会立即重新以高频撞击服务端。

## 6. 最重要的部署约束：不要和 Desktop 并发控制同一 thread

这个包采用的是：

```text
watchdog
   └─ 启动自己的 codex app-server
```

Codex Desktop 通常也有自己的 app-server/runtime。基于当前公开架构，**不应让两个独立 app-server 进程同时执行和写入同一个活动 thread**。这是一个保守但必要的工程判断：内部的 idle 检查解决的是单 runtime 重复启动，不是跨进程的 rollout 和状态写入协调。

推荐使用“所有权交接”：

```text
阶段 A
Codex Desktop 创建 Goal
        │
        ▼
记录 thread ID
        │
        ▼
完全退出 Desktop

阶段 B
启动 watchdog
watchdog 独占该 thread
        │
        ▼
长期自主运行

阶段 C
Ctrl+C 停止 watchdog
确认 app-server 子进程退出
        │
        ▼
重新打开 Desktop
继续查看同一 thread
```

不要长期保持：

```text
Codex Desktop 运行同一 Goal
+
watchdog 运行同一 Goal
```

## 7. 实际部署步骤

解压：

```bash
unzip codex-goal-watchdog.zip
cd codex-goal-watchdog
```

检查环境：

```bash
codex --version
codex login status
python3 --version
```

### 找到 thread ID

```bash
python3 codex_goal_watchdog.py --list --limit 30
```

它会显示：

```text
更新时间
Goal 状态
thread ID
标题
工作目录
```

### 第一次先只读演练

先完全退出 Codex Desktop，然后执行：

```bash
python3 codex_goal_watchdog.py \
  --thread THREAD_ID \
  --dry-run \
  --once \
  --base-delay-seconds 0 \
  --rate-limit-base-seconds 0
```

这会读取 thread、Goal 和最后失败 turn，但不会真正修改 Goal。

### 前台长期运行

```bash
/usr/bin/caffeinate -i python3 codex_goal_watchdog.py \
  --thread THREAD_ID \
  --codex-bin "$(command -v codex)" \
  --approval-policy preserve \
  --sandbox preserve
```

停止：

```text
Ctrl+C
```

`caffeinate -i` 用于避免 Mac mini 因空闲睡眠中断任务。

## 8. 审批和沙箱怎样配置

app-server 的 thread resume 可以覆盖 approval policy 和 sandbox。公开协议支持 `never`、`on-request`、`untrusted` 等审批模式，以及 `read-only`、`workspace-write`、`danger-full-access` 沙箱。

### 保留原设置

```bash
--approval-policy preserve
--sandbox preserve
```

这是默认值。

问题是：无人值守期间一旦出现审批请求，就没有人在 UI 点击。脚本默认会**拒绝**收到的命令执行和文件修改审批，避免自动放权。

### 更适合无人值守的相对安全配置

```bash
--approval-policy never
--sandbox workspace-write
```

完整命令：

```bash
/usr/bin/caffeinate -i python3 codex_goal_watchdog.py \
  --thread THREAD_ID \
  --approval-policy never \
  --sandbox workspace-write
```

这里的 `never` 表示不弹审批，并不代表所有操作获得无限权限。需要越过 workspace 沙箱的行为仍会失败。

### 自动接受审批

```bash
--auto-approve
```

app-server 确实可能向客户端发送命令执行和文件修改审批请求。

启用后，脚本会回应：

```json
{"decision":"accept"}
```

只建议用于：

- 专用代码仓库；
    
- 已使用 Git；
    
- Goal 明确且经过验证；
    
- 仓库中没有私钥、生产凭据或重要个人数据；
    
- 不使用 `danger-full-access`。
    

## 9. 怎样做到“无限继续”

脚本默认：

```text
--max-reactivations 0
```

即没有重激活次数上限。符合自动恢复条件的 Goal 可以持续：

```text
blocked
→ 等待
→ 网络探测
→ active
→ 再次失败
→ 更长等待
→ active
→ …
```

初期建议先增加熔断：

```bash
--max-reactivations 20
```

确认一两天运行稳定后，再恢复为：

```bash
--max-reactivations 0
```

无限指的是**没有人为设定重试次数上限**，不是绕过：

- 账户 usage limit；
    
- 认证失效；
    
- 上下文窗口；
    
- 沙箱限制；
    
- 服务端永久错误；
    
- Goal 自身逻辑死循环。
    

## 10. 开机自动运行

完整包中包含 LaunchAgent 安装器。

仅用于专门交给 watchdog 独占的 thread：

```bash
./install_launchd.sh THREAD_ID
```

安装时会要求确认 Codex Desktop 没有运行该 thread。

日志：

```text
~/.codex/watchdogs/<THREAD_ID>.launchd.out.log
~/.codex/watchdogs/<THREAD_ID>.launchd.err.log
```

停止并卸载：

```bash
./uninstall_launchd.sh THREAD_ID
```

## 11. 更高级的 daemon 共享模式

Codex 提供受管理的 app-server daemon，并在 Unix 平台使用类似以下控制 socket：

```text
$CODEX_HOME/app-server-control/app-server-control.sock
```

CLI 也提供：

```bash
codex app-server daemon start
codex app-server daemon restart
codex app-server proxy
```

理想结构是：

```text
Desktop / 控制客户端
              \
               → 单一 app-server daemon → 单一 thread runtime
              /
watchdog
```

但当前有三个现实限制：

1. Unix socket 上传输的是 WebSocket 帧，而不是本脚本使用的 JSONL。
    
2. `codex app-server proxy` 是原始 WebSocket 字节代理，不负责把它转换成逐行 JSON。
    
3. TCP WebSocket transport 在公开文档中仍标记为 experimental/unsupported。
    

更重要的是，目前公开文档没有稳定说明 Codex Desktop 可以被配置为连接用户自行启动的 daemon。因此现阶段最可靠的是：**让 watchdog 独占该 thread，而不是试图附着到 Desktop 的内部进程。**

## 12. 包内验证

我已通过本地 mock app-server 测试以下流程：

```text
Goal = blocked
最后错误 = HTTP 429 / responseTooManyFailedAttempts
网络探测 = 成功
watchdog 调用 thread/goal/set
返回 Goal = active
```

你也可以执行：

```bash
./smoke_test.sh
```

此外，每次 Codex 升级后，可以先验证协议并运行一次 dry-run：

```bash
codex app-server generate-json-schema --out /tmp/codex-schema

python3 codex_goal_watchdog.py \
  --thread THREAD_ID \
  --dry-run \
  --once
```

app-server 可以生成与当前安装版本完全对应的 TypeScript 或 JSON Schema。


# 提问3



# 回答3



