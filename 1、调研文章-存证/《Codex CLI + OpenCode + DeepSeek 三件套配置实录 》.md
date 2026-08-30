# Codex CLI + OpenCode + DeepSeek 三件套配置实录

# 我的 AI 编程搭档：Codex CLI + OpenCode + DeepSeek 三件套配置实录



> 花了一周时间折腾 AI 编程工具，终于搭出一套好用、省钱、数据还安全的组合，分享一下踩坑过程和最终方案。



------



## 为什么折腾这个



今年 AI 编程工具爆发式增长，Cursor、GitHub Copilot、Windsurf……选哪个都纠结。



我的核心诉求很明确：



• **模型灵活**——不想被绑定在某一家

• **费用可控**——月费不能超标

• **数据安全**——代码不喂给模型训练

• **开源透明**——底层能看能改



试了一圈，最终方案是：**Codex CLI + OpenCode Go + DeepSeek V4 Flash** 三件套。用了两周，体验相当不错。



------



## 整体架构



```
Codex CLI → Responses API → codex-proxy → OpenCode Go → DeepSeek V4 Flash
```



你可能好奇：为什么中间要加一层代理？



Codex CLI 是 OpenAI 开源的终端编程代理，但它只支持 OpenAI 新版的 Responses API。而 DeepSeek 走的是标准 Chat Completions API，接口格式不一样。



所以需要一个「翻译层」——codex-proxy 就是干这个的：把 Responses API 请求转成 Chat Completions API，让 DeepSeek 能听懂。



## 第一步：安装 Codex CLI



有两种方式：



```
# macOS Homebrew
brew install codex-cli

# 或通过 npm
npm install -g @openai/codex
```



推荐用 Homebrew，环境隔离更干净。



## 第二步：注册 OpenCode 并订阅 Go 计划



访问 [opencode.ai/auth](https://opencode.ai/auth) 注册账号，然后订阅 **Go 计划**。



价格方面：

• 首月优惠 $5，之后 $10/月

• 用量封顶 $60/月

• 包含 DeepSeek V4 Flash 在内的多个开源编程模型



对于个人开发者来说性价比很高——一个月的费用还不到一杯精品咖啡的价格。



## 第三步：安装配置 codex-proxy



```
npm install -g codex-proxy
```



然后在 `~/.codex-proxy/config.yaml` 写入配置：



```
server:
  port: 10204
  host: "127.0.0.1"

channels:
  deepseek-opencode:
    base_url: "https://opencode.ai/zen/go"
    api_key: "你的 OpenCode API Key"
    timeout: 300

model_routing:
  _default:
    channel: deepseek-opencode
    model: deepseek-v4-flash
```



唯一需要替换的就是 `api_key`，去 OpenCode 后台复制就行。



## 第四步：配置 Codex CLI



编辑 `~/.codex/config.toml`：



```
model_provider = "custom"
model = "deepseek-v4-flash"
sandbox_mode = "workspace-write"
personality = "pragmatic"

[model_providers.custom]
name = "custom"
base_url = "http://127.0.0.1:10204/v1"
wire_api = "responses"
```



关键点：`wire_api = "responses"`——告诉 Codex CLI 用 Responses API 协议，这样它才会和 codex-proxy 正确握手。



最后把 API Key 写入环境变量：



```
export OPENAI_API_KEY="你的 OpenCode API Key"
```



## 开机自启（macOS 用户）



手动启动代理每次都要敲命令，太烦。配个 LaunchAgent 实现开机自启：



编辑 `~/Library/LaunchAgents/ai.opencode.codex-proxy.plist`，把 `/path/to/codex-proxy` 替换成实际路径，然后：



```
launchctl load ~/Library/LaunchAgents/ai.opencode.codex-proxy.plist
```



之后就再也不用管它了，重启也自动运行。



## 使用体验



直接在终端输入 `codex` 就能进入交互界面。看到模型名显示为 `deepseek-v4-flash` 就说明成功了。



日常使用感受：



• **响应速度**：DeepSeek V4 Flash 名不虚传，代码补全和对话基本秒回

• **代码质量**：在 Python 项目中的表现出乎意料地好，比预期强不少

• **上下文长度**：完全够用，整文件分析和跨文件重构都没问题

• **费用情况**：按我的使用强度（每天 3-5 小时），一个月 $10 完全够，根本触发不到 $60 的封顶



### 踩坑记录



遇到 `stream disconnected` 错误怎么办？大概率是代理没跑起来：



```
lsof -i :10204
```



如果端口没监听，手动启动一下：



```
codex-proxy
```



检查日志看看有没有报错。我遇到过一次是因为 Node.js 版本太旧，升级就好了。



## 费用总结



项目费用

|------|------|

OpenCode Go 订阅$10/月（首月 $5） DeepSeek V4 Flash包含在订阅内 用量上限$12/5小时，$30/周，$60/月 每天重度使用约 $0.3-0.5/天



对于个人开发者来说，一个月的费用还不到一顿外卖钱，比自己调 DeepSeek API 用多少付多少的模式省心太多——不用担心跑脚本跑超了账单。



## 这套方案好在哪



• **模型灵活**：不想用 DeepSeek 了？改一行配置文件就能换成别的模型

• **费用封顶**：$10/月的用量上限，不怕跑超，用着安心

• **数据安全**：通过 OpenCode Go 调用，数据不用于模型训练，可以放心把代码交给它

• **开源透明**：Codex CLI 和 codex-proxy 都是开源的，底层逻辑一清二楚

• **终端原生**：不需要 IDE 插件，终端里就能用，和 Vim/Neovim/SSH 远程开发天然契合



## 结语



如果你也在找 AI 编程工具，或者已经在用 Codex CLI 想换个模型，强烈推荐试试这个组合。配置过程有点小门槛，但一劳永逸——配好之后每天就是打开终端直接干活。
