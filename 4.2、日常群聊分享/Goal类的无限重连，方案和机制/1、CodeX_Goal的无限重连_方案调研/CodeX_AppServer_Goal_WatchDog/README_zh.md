# Codex Goal Watchdog（macOS / Mac mini）

这个 watchdog 的职责很窄：**观察一个已经持久化的 Codex thread；当其 Goal 因可重试的网络、流连接、服务端或 429 错误进入 `blocked` 后，按退避策略把同一个 Goal 的状态重新设置为 `active`。**

它不会重写 Goal objective，不会新建 Goal，也不会不断补发“继续”提示词。

> 当前脚本使用 `codex app-server --listen stdio://`，只依赖 Python 标准库。

## 一、工作原理

```text
持久化 thread / Goal（~/.codex）
              │
              ▼
watchdog.py 启动 codex app-server（stdio + JSONL）
              │
              ├─ initialize → initialized
              ├─ thread/resume（加载并订阅线程）
              ├─ thread/goal/get（读取 Goal 状态）
              ├─ 监听 turn/completed、thread/goal/updated、thread/status/changed
              └─ thread/goal/set { status: "active" }（满足重试策略时）
```

Goal 被重新设置为 `active` 后，Codex 自己的 Goal runtime 会在 thread 空闲时发起下一轮。watchdog 不直接调用 `turn/start`。

## 二、默认状态策略

| Goal 状态 | 默认动作 |
|---|---|
| `active` | 只观察；若长时间显示 active 但 thread 一直 idle，则重新确认一次 active |
| `blocked` + 网络/流断开/服务端错误 | 指数退避后重新激活 |
| `blocked` + 429 / 内部重试耗尽 | 以 5 分钟为初始退避重新激活 |
| `usageLimited` | 默认不自动恢复，避免反复撞账户额度；可显式开启低频探测 |
| `paused` | 不动，视为用户主动暂停 |
| `budgetLimited` | 不动，视为预算保护 |
| `complete` | 不动 |
| 上下文超限、认证失败、bad request、沙箱错误等 | 不自动恢复 |

默认退避：

```text
普通网络错误：约 30 秒 → 60 秒 → 120 秒 → 240 秒 → ... → 最长 15 分钟
429：约 5 分钟 → 10 分钟 → 15 分钟（达到上限后持续 15 分钟）
```

每次成功完成一轮后，连续失败计数清零。退避状态保存在：

```text
~/.codex/watchdogs/<THREAD_ID>.json
```

## 三、非常重要：与 Codex Desktop 的线程所有权

这个版本会启动一个**独立的 app-server 进程**。不要让 Codex Desktop 和 watchdog 同时对同一个 thread 执行、写文件或追加 rollout。

推荐的交接流程：

1. 在 Codex Desktop 中创建并确认 Goal。
2. 记下 thread ID。
3. 完全退出 Codex Desktop，或至少确保该 thread 不再由 Desktop 运行。
4. 启动 watchdog，让它独占该 thread 的执行期。
5. 需要回到 Desktop 时，先 `Ctrl+C` 停止 watchdog，确认子进程退出，再打开 Desktop。

**不要把“Desktop 正在运行同一 Goal”与“本脚本正在运行同一 Goal”作为常态并行使用。** 当前公开接口没有承诺两个独立 app-server 进程可以安全地共同写同一活动线程。

## 四、前置检查

```bash
codex --version
codex login status
python3 --version
```

Python 建议 3.10 或更高版本。脚本复用 `~/.codex` 中已有的 Codex 登录状态。

Codex CLI 不在 PATH 时，通过 `--codex-bin` 传绝对路径：

```bash
which codex
```

## 五、找到 thread ID

在本目录执行：

```bash
python3 codex_goal_watchdog.py --list --limit 30
```

输出包括最近 thread 的更新时间、Goal 状态、thread ID、标题和工作目录。

也可以先限定使用某个 Codex 二进制：

```bash
python3 codex_goal_watchdog.py \
  --list \
  --codex-bin "$(command -v codex)"
```

## 六、先做一次只读演练

将 `THREAD_ID` 替换为实际 UUID：

```bash
python3 codex_goal_watchdog.py \
  --thread THREAD_ID \
  --dry-run \
  --once \
  --base-delay-seconds 0 \
  --rate-limit-base-seconds 0
```

`--dry-run` 不会真正执行 `thread/goal/set`。若 Goal 当前为 blocked，日志应显示它是否被判定为可重试。

## 七、前台长期运行

稳妥配置：保留 thread 原有审批与沙箱设置。

```bash
/usr/bin/caffeinate -i python3 codex_goal_watchdog.py \
  --thread THREAD_ID \
  --codex-bin "$(command -v codex)" \
  --approval-policy preserve \
  --sandbox preserve
```

`caffeinate -i` 避免 macOS 因空闲睡眠中止长时间任务。停止时按 `Ctrl+C`。

### 无人值守但仍保持 workspace 沙箱

```bash
/usr/bin/caffeinate -i python3 codex_goal_watchdog.py \
  --thread THREAD_ID \
  --codex-bin "$(command -v codex)" \
  --approval-policy never \
  --sandbox workspace-write
```

`approval-policy never` 的含义是“不弹审批”，不是“自动赋予所有权限”。需要越过沙箱的动作仍会被拒绝，适合大多数代码仓库。

### 自动接受命令和文件修改审批（高风险）

```bash
/usr/bin/caffeinate -i python3 codex_goal_watchdog.py \
  --thread THREAD_ID \
  --auto-approve
```

该参数会接受 watchdog 客户端收到的命令执行和文件修改审批。只应在专用仓库、可靠的 Goal、已启用 Git 检查点且不含敏感凭据的环境使用。默认不启用。

## 八、重要参数

```text
--poll-seconds 15                 状态轮询周期
--base-delay-seconds 30           普通可重试错误的初始退避
--rate-limit-base-seconds 300     429 的初始退避
--max-delay-seconds 900           普通/429 退避上限
--max-reactivations 0             连续重激活熔断次数；0 表示不设上限
--probe-url https://chatgpt.com/  重激活前的网络连通探针
--active-stall-seconds 300        active + idle 多久后重新确认 active
--auto-resume-usage-limited       低频尝试恢复 usageLimited
--allow-unknown-errors            未分类错误也允许恢复；不建议默认开启
--state-file PATH                 指定退避状态文件
--once                            判断/执行一次后退出
--dry-run                         不写 Goal 状态
```

建议长期无人值守时先使用有限熔断：

```bash
--max-reactivations 20
```

确认策略稳定后，再改回 `0` 实现无限循环。

## 九、作为 LaunchAgent 运行

只建议用于**专门交给 watchdog 独占的 thread**。

安装并立即启动：

```bash
./install_launchd.sh THREAD_ID
```

日志位于：

```text
~/.codex/watchdogs/<THREAD_ID>.launchd.out.log
~/.codex/watchdogs/<THREAD_ID>.launchd.err.log
```

停止并卸载：

```bash
./uninstall_launchd.sh THREAD_ID
```

LaunchAgent 会继承安装时的 PATH，并使用 `command -v python3` 和 `command -v codex` 得到的绝对路径。

## 十、测试与诊断

运行离线 mock smoke test：

```bash
./smoke_test.sh
```

打开 app-server stderr 调试日志：

```bash
CODEX_WATCHDOG_DEBUG_APP_SERVER=1 \
python3 codex_goal_watchdog.py --thread THREAD_ID
```

验证当前安装版本的协议结构：

```bash
mkdir -p /tmp/codex-schema
codex app-server generate-json-schema --out /tmp/codex-schema
```

app-server 协议仍在快速演进；脚本对较旧版本的 `thread/resume` 分页字段提供了回退，但升级 Codex 后仍应先执行一次 `--dry-run --once`。

## 十一、关于 daemon / Unix socket 的高级模式

Codex 也支持受管理的 app-server daemon 和 Unix socket。理想拓扑是：

```text
多个控制客户端 ──WebSocket over Unix socket──> 单一 app-server daemon ──> 单一 thread runtime
```

这比“多个独立 app-server 进程读写同一 thread”更合理。不过：

1. Unix socket 上承载的是 WebSocket 帧，不是本脚本使用的逐行 JSONL。
2. `codex app-server proxy` 是原始字节代理，不会把 WebSocket 转成 JSONL。
3. 公开文档将 TCP WebSocket transport 标记为 experimental/unsupported。
4. Codex Desktop 是否会接入你自行启动的 daemon，目前没有公开的稳定契约。

因此，本包先实现可审计、依赖最少的“watchdog 独占 thread”模式。要做真正的共享 daemon 客户端，需要 WebSocket-over-UDS 客户端、连接恢复、订阅恢复和多客户端所有权协调，复杂度明显更高。

## 十二、它不能解决什么

- 真实的账户额度耗尽或需要等重置的 usage limit。
- 登录过期、权限策略错误、沙箱拒绝、无效请求。
- 上下文结构已经无法压缩的错误。
- Goal 本身进入死循环或持续制造相同业务错误。
- 两个独立 Codex 进程同时执行同一 thread 的一致性问题。

watchdog 的正确定位是“故障恢复控制器”，不是绕过额度、权限或上下文约束的工具。
