# 【讨论和回答环节】GptPro的《分形上下文系统调研》最终方案


# 提问1



## 用于调研的直接提问，提示词


> [!NOTE]
> 
> 你好，我这边想要研究一个【用于  VibeCoding类项目/也包括其它知识管理类项目、通用文件目录  的分形上下文系统】。
> 
> 我前期做了一些调研，相关做的笔记和链接，放在了：
> - 《  分形上下文系统.md  https://github.com/hanshou101/Obsidian_PublicGitHubShare_InsteadOf_FeiShu/raw/refs/heads/main/3%E3%80%81%E5%90%84%E7%A7%8DSkill%EF%BC%88%E5%BF%AB%E9%80%9F%E5%88%86%E4%BA%AB%EF%BC%89/%E5%88%86%E5%BD%A2%E4%B8%8A%E4%B8%8B%E6%96%87%E7%B3%BB%E7%BB%9F.md  》
> 
> 然后，我强调一下我自己的想法：
> - 豆包，给出的只是一个  仅供参考、需要你进行扬弃    的一些试验性探索。
>   - 更多的，是你要有自己独立的判断、独立的思考，给出自己真正认为正确的调研方案。
> 
> 补充：
> - 1、不许你做成一个【面面俱到、庞大臃肿、充斥着各种冗余】功能的超大系统。
>   - 反面例子，比如：
>     - “代码库认知层 / Repo Cognition Layer”
>       - 评价：远远超出了必要的范围。而且有点越俎代庖。
>     - 而是每次推理时精心选择、维护、压缩哪些 token 进入模型上下文；上下文是有限资源，需要追求“最小高信号 token 集”。
>       - 评价：极大增加了【认知精力成本】————而且效果还不如  “简单粗暴直接”的方式有效。
>     - “代码库的可查询认知缓存”
>       - 远远超出了我的本意，而且会增加无穷无尽的    适配和维护成本。
>       - 而且————和我自己做的【MD笔记】中的初衷，偏离较远。
>     - “Fractal Context System, FCS：一个以代码库结构为骨架、以静态分析和 Git 变更为事实基础、以 LLM 摘要为压缩层、以证据链和校验机制防漂移、面向 AI Coding Agent 动态供给上下文的多粒度认知系统。   输入层：事实来源   节点层：统一数据模型   节点层：统一数据模型   节点层：统一数据模型  节点层：统一数据模型   更新层：增量传导  供给层：Context Pack   接入层：兼容现有 Agent 生态”
>       - 设计的太大了、野心跟不上实际能力：
>         - 成本极高，和现有的很多工具相冲突、后续维护成本高；产出效果不稳定（因为不够简单）。
>       - ROI很低，效果比【简单的实现机制】没有任何明显优势。
> - 2、一些其它，仅供借鉴、部分参考、而需要扬弃的思路和想法：
>   - .frac.md 本身应该是一棵递归摘要树。   
>     - 不是 pack 系统。 不是索引系统。 不是图谱系统。 不是文档系统。 而是： 父 frac = 自己直属内容 + 子 frac 的总结与导航
>     - 然后： 任何底层文件变化 -> 最近的 frac 失效 -> 更新这个 frac -> 它的父 frac 失效 -> 再更新父 frac -> 一直链式更新到根 frac
>     - 正确的核心公式
>       - Frac(D) = Summary( OwnFiles(D), ChildFracs(D) )   也就是： 一个目录下的 .frac.md 只总结两类东西： 1. 这个 frac 自己直接管辖的文件 2. 它下面直属子 frac 的摘要 它不直接总结孙子目录。 它不跨层读取深层代码。 它不试图理解整个仓库。 父级只相信子级 .frac.md。 这就是分形。
>     - 真正的系统不变量 
>       - 这个系统只有一个核心不变量： 每个 .frac.md 的修改时间，必须晚于它的所有输入。
>       - 判断是否过期非常简单： 如果 max(直属文件 mtime, 子 frac mtime) > 当前 .frac.md mtime 则当前 .frac.md stale 。 这就够了。 不需要数据库。 不需要 hash。 不需要 embedding。 不需要 graph。 不需要 RAG。 不需要复杂 schema。 文件系统的 mtime 本身就是状态。
>     - 更新规则：bottom-up 链式更新 更新必须从最深处开始。
>       - 递归摘要。
>     - Python经常要做的事情：
>       - 1. 找 frac 树 2. 判断 stale 3. 给出 bottom-up 更新顺序
>       - status 扫描所有 .frac.md，判断哪些过期。
>       - chain 查看某个文件会影响哪条 frac 链。
>       - frac-inputs 告诉 Agent：更新某个 frac 时应该看什么。
> 
> 请你为我进行专业化的调研，和一个比较合适的方案。
> 


# 回答1


## 结论：我建议做“FCS-Lite”，不是“上下文平台”

你这个想法最有价值的内核是：

> **用文件目录树本身作为认知骨架；每个目录只维护一个 `.frac.md`；父级只读取直属文件和直属子目录的 `.frac.md`；状态由文件系统时间戳决定；更新永远自底向上。**

我不建议把它做成 RAG、索引系统、代码认知缓存、知识图谱、Repo Cognition Layer，也不建议搞复杂的 Context Pack 分级供给。豆包版里“初始化、维护、检查、提炼、按需供给”这些词看起来完整，但已经开始滑向一个大系统：例如它引入了 `.fractal-index.json`、L1-L4 供给流程、`project-vibe.md`、结构真实性校验、提炼升华流程等模块，这些都容易让最初那个漂亮的递归不变量被工程噪声淹没。([GitHub](https://github.com/hanshou101/Obsidian_PublicGitHubShare_InsteadOf_FeiShu/blob/main/3、各种Skill（快速分享）/分形上下文系统/豆包调研，及对话信息.md))

我认为正确方向是：

> **一个文件约定 + 一个 Python 小工具 + 一个 Agent Skill。**
> 文件约定解决“是什么”；Python 工具解决“哪些过期、按什么顺序更新、更新时应该看什么”；Agent Skill 解决“让 Claude Code / Cursor Agent 按这个规矩做事”。

------

## 1. 调研后的取舍判断

### 1.1 你的方案和 GEB 类方案的区别

GEB 的思路也使用“每个目录都有文档”，但它要求在根目录 `AGENTS.md` 写管理方法、每个子目录建 `AGENTS.md`，甚至要求在代码文件头部写 input/output/pos 注释，并在功能更新后同步更新子文档。这个方案的优点是直观，缺点是**侵入代码文件、维护面太大、容易变成纪律系统**。([IIMT](https://www.iimt.me/技术/AI/vibe-coding/GEB-代码管理))

你的方案更好的地方在于：**不碰业务文件，不要求每个代码文件加注释，不要求文档与代码严格同构；只在目录层生成一个可重建的递归摘要。** 这比 GEB 更轻，也更接近你说的“简单粗暴直接”。

### 1.2 和 Repomix / Aider / Cursor Index 的区别

Repomix 的方向是把整个代码库打包成一个 AI-friendly 文件，适合一次性喂给模型做 review、重构或理解，但它本质是“pack”，不是递归上下文系统。([Repomix](https://repomix.com/))

Aider 的 repo map 很成熟：它会把 Git 仓库压成一个包含关键类、函数、签名的简洁地图，并在大仓库中用图排序和 token budget 选择最相关部分。这个方向对代码编辑很有用，但它引入了 AST、图排名、token budget、动态选择，这正是你不想要的“上下文调度系统”。([Aider](https://aider.chat/docs/repomap.html))

Cursor 的 Codebase Indexing 属于“索引 + 搜索 + AI 上下文”的路线，适合 IDE 内检索和语义召回，但它不是一个可用纯文件系统解释的递归摘要树。([Cursor](https://cursor.com/help/customization/indexing?utm_source=chatgpt.com))

所以我的判断是：**这些工具证明了“大项目上下文”确实是痛点，但它们不是你的目标形态。你的目标应该是低技术含量、低维护成本、高可解释性的目录递归摘要。**

------

## 2. 核心定义：`.frac.md` 是递归摘要树，不是索引

我建议把系统正式定义为：

```text
Frac(D) = Summary( OwnFiles(D), ChildFracs(D) )
```

其中：

```text
OwnFiles(D)   = D 目录下的直属有效文件，不含 .frac.md，不含被忽略文件
ChildFracs(D) = D 的直属子目录中的 .frac.md
```

严格禁止：

```text
父级 .frac.md 直接读取孙目录文件
父级 .frac.md 跨层总结深层代码
父级 .frac.md 通过搜索、embedding、RAG 找材料
```

这条规则非常关键。它让系统保持“分形”而不是“全局总结器”。

更完整一点，建议把输入定义为：

```text
Inputs(D) = DirEntryMTime(D) + OwnFiles(D) + ChildFracs(D)
```

这里多加一个 `DirEntryMTime(D)`，是为了捕捉**直属文件新增、删除、重命名**。只看文件 mtime 会漏掉“文件被删除”这种情况，因为被删除的文件已经没有 mtime 可读。

------

## 3. Fresh / Stale 不变量

你原来的不变量是对的，但我建议工程表达稍微调整：

```text
fresh(D)  ⇔  .frac.md 存在，且 frac_mtime_ns >= max(input_mtime_ns)
stale(D)  ⇔  .frac.md 不存在，或 max(input_mtime_ns) > frac_mtime_ns
```

用 `>=` 而不是强制 `>`，是为了避免文件系统时间戳精度导致“刚生成就仍然 stale”的循环。Python 的 `Path.stat()` 可以读取文件状态，`st_mtime` 表示最近内容修改时间，官方也提供 `st_mtime_ns` 作为纳秒整数；同时 Python 文档提醒，不同操作系统和文件系统的时间戳精度不同，所以这里应优先使用 `st_mtime_ns`。([Python documentation](https://docs.python.org/3/library/pathlib.html))

这个系统只承认一个事实：

> **如果输入比 `.frac.md` 新，`.frac.md` 就过期。**

它不判断“摘要语义是否完美”，也不试图用模型校验每句话。这一点要坚持住。语义校验可以人工抽查，但不能成为 MVP 的核心机制。

------

## 4. `.frac.md` 最小模板

我建议模板控制在 5 个区块，不要引入大 schema。

```markdown
# .frac.md — <relative/path>

> 生成规则：本文件只总结当前目录的直属文件，以及直属子目录的 .frac.md。
> 最近更新：YYYY-MM-DD HH:MM
> 输入范围：direct-files + child-fracs only

## 1. 本目录是什么

用 3-8 行说明这个目录的职责、边界、在上级中的位置。

## 2. 直属文件

- `file_a.py`：做什么；对外暴露什么；需要注意什么。
- `config.yaml`：配置什么；谁会读取它。

## 3. 子目录导航

- `api/`：见 `api/.frac.md`；一句话说明子模块职责。
- `ui/`：见 `ui/.frac.md`；一句话说明子模块职责。

## 4. 本层约束 / 约定 / 禁忌

- 本目录内必须遵守的命名、架构、数据流、风格约束。
- 不要写泛泛而谈的“保持简洁”“注意安全”。

## 5. 什么时候需要下钻

- 修改 X 时，先读 `api/.frac.md`。
- 改 Y 时，必须同时看 `schema.ts` 和 `ui/.frac.md`。
```

我建议**不放变更记录**。变更记录应该交给 Git，不要让每个 `.frac.md` 越写越长。

我也建议**不在 `.frac.md` 中保留人工区块**。如果有人工长期规则，放到直属的 `README.md`、`CLAUDE.md`、`AGENTS.md` 或 `notes.md`，然后由 `.frac.md` 总结它。这样 `.frac.md` 始终是可重建产物，而不是半生成、半手写的混合文件。

------

## 5. Python 工具只做 5 件事

工具不要叫“平台”，也不要做 Agent。它只负责确定性工作。

建议命令：

```bash
frac init [path]
frac status [path]
frac plan [path]
frac inputs <dir>
frac chain <file-or-dir>
frac stamp [path]
```

含义如下：

| 命令                       | 作用                                                         |
| -------------------------- | ------------------------------------------------------------ |
| `frac init`                | 按忽略规则扫描目录，为需要的目录创建空 `.frac.md` 或生成更新计划 |
| `frac status`              | 判断哪些 `.frac.md` missing / stale / fresh                  |
| `frac plan`                | 输出 bottom-up 更新顺序，最深目录在前                        |
| `frac inputs <dir>`        | 告诉 Agent：更新这个目录的 `.frac.md` 时只能读哪些文件       |
| `frac chain <file-or-dir>` | 输出从根到目标路径的 `.frac.md` 链，用于编码前快速读上下文   |
| `frac stamp`               | 在“信任当前 `.frac.md` 内容正确”的前提下，按自底向上顺序 touch，恢复 mtime 不变量 |

其中 `stamp` 很重要。因为 Git checkout / clone 不会天然保留“`.frac.md` 晚于输入文件”的语义时间关系。如果 `.frac.md` 要纳入版本控制，那么 clone 后需要一次 `frac stamp` 来重建本地 mtime 状态。Git hook 的 `post-checkout` 可以用于恢复工作区元数据，但它不应成为 MVP 必需项。([Git](https://git-scm.com/docs/githooks))

------

## 6. 忽略规则：直接复用 Git 生态，但不要依赖 Git 语义

目录扫描应默认排除：

```text
.git/
node_modules/
dist/
build/
coverage/
.venv/
venv/
__pycache__/
.next/
.turbo/
.cache/
.DS_Store
*.lock? 视项目决定，不一概忽略
```

如果在 Git 仓库中，建议读取 `.gitignore` / `git check-ignore` / `git ls-files -co --exclude-standard` 来决定有效文件。Git 官方文档说明 `.gitignore` 用来指定 Git 应忽略的未跟踪文件，并且会按命令行规则、各层 `.gitignore`、`info/exclude`、全局 ignore 文件等来源处理。([Git](https://git-scm.com/docs/gitignore))

但要注意：**Git 只辅助筛文件，不负责 freshness。freshness 仍然由文件系统 mtime 判断。**

------

## 7. 更新流程：Agent 只按计划读输入

一次标准更新应该是：

```bash
frac plan
```

输出：

```text
stale:
  src/auth/.frac.md
  src/.frac.md
  .frac.md

update-order:
  1. src/auth
  2. src
  3. .
```

然后 Agent 对每个目录执行：

```bash
frac inputs src/auth
```

输出：

```text
DIRECT FILES:
  src/auth/login.ts
  src/auth/session.ts
  src/auth/README.md

CHILD FRACS:
  src/auth/providers/.frac.md
```

Agent 规则：

```text
1. 只读取 frac inputs 给出的输入。
2. 不读取孙目录源码。
3. 不用搜索补材料。
4. 不根据记忆编造。
5. 重写当前目录 .frac.md。
6. 写完后继续更新父级。
```

这就是系统的“认知边界”。只要 Agent 遵守这个边界，系统就不会膨胀。

------

## 8. 编码前怎么用上下文

我不建议做复杂的 `/fractal-get L1/L2/L3/L4`。

更简单的规则是：

```bash
frac chain src/auth/login.ts
```

输出：

```text
.frac.md
src/.frac.md
src/auth/.frac.md
```

编码前，Agent 读：

```text
1. 根 .frac.md
2. 目标路径上的所有 .frac.md
3. 目标文件本身
4. 必要时再按 .frac.md 的“什么时候下钻”提示读相邻文件
```

这不是 pack 系统，不做 token 排名，不做相关性打分。它只是“沿目录路径拿上下文”。这足够简单，也符合人类理解代码库的方式。

------

## 9. 和 Claude Code / Agent Skill 的集成方式

这里建议用 **Agent Skill**，不是把所有 `.frac.md` 塞进 `CLAUDE.md`。Anthropic 对 Agent Skills 的定义是：一个 skill 是包含 `SKILL.md` 的目录，里面可以有 instructions、scripts、resources；`name` 和 `description` 会先被加载，完整正文只在相关时加载，这正好适合你的场景。([Anthropic](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills))

Skill 目录可以这样：

```text
.claude/skills/frac-context/
  SKILL.md
  scripts/
    frac.py
  references/
    frac-template.md
    update-rules.md
```

`SKILL.md` 最小骨架：

~~~markdown
---
name: frac-context
description: Maintain and use .frac.md recursive directory context files. Use when initializing, checking, updating, or consulting fractal context for coding or knowledge-management projects.
---

# Frac Context Skill

## Core rule

A directory .frac.md summarizes only:
1. direct eligible files in that directory
2. immediate child directories' .frac.md files

Never read grandchildren source files while updating a parent .frac.md.

## Before coding

Run:

```bash
python .claude/skills/frac-context/scripts/frac.py chain <target-path>
~~~

Read the listed .frac.md files from root to target.

## After editing files

Run:

```bash
python .claude/skills/frac-context/scripts/frac.py plan --changed
```

Update stale .frac.md files bottom-up.

For each directory:

```bash
python .claude/skills/frac-context/scripts/frac.py inputs <dir>
```

Read only those inputs, then rewrite `<dir>/.frac.md`.

```
根目录 `CLAUDE.md` 只放一句短规则：

```markdown
When working in this repo, use the frac-context skill. Before editing, read the .frac.md chain for the target path. After editing, update stale .frac.md files bottom-up.
```

不要在 `CLAUDE.md` 里 `@` 导入大量 `.frac.md`。Claude Code 文档明确说 `CLAUDE.md` 会进入上下文并消耗 token，建议单个文件控制在 200 行以内；`@path` import 会把被引用文件也加载进上下文，所以递归导入 `.frac.md` 会反向制造上下文膨胀。([Claude](https://code.claude.com/docs/en/memory))

------

## 10. 版本控制策略：分两种模式

### 模式 A：本地缓存模式

```text
.frac.md 加入 .gitignore
```

适合：

```text
个人 VibeCoding
快速实验
上下文只给本机 Agent 用
不想让 Git diff 变脏
```

优点是 mtime 不变量最纯粹。缺点是换机器 / clone 后要重新生成。

### 模式 B：共享文档模式

```text
.frac.md 纳入 Git
```

适合：

```text
团队共享项目认知
Obsidian / 知识库 / 长期项目
希望 .frac.md 成为项目活文档
```

但要加两条规则：

```text
1. commit 前运行 frac status，确保没有 stale。
2. clone / checkout 后运行 frac stamp，恢复本地 mtime 顺序。
```

如果要自动化，可以用 `pre-commit` 做检查。Git 官方文档说明 `pre-commit` 可以在提交前运行，非零退出会中止 commit；但它可以被 `--no-verify` 绕过，所以它是提醒机制，不是绝对安全边界。([Git](https://git-scm.com/docs/githooks))

------

## 11. 最小实现算法

### 11.1 扫描目录

```python
def find_frac_dirs(root):
    # walk root
    # apply ignore rules
    # directory is eligible if:
    #   - it has direct eligible files, or
    #   - it has eligible child dirs
    # return dirs sorted by depth
```

### 11.2 输入集合

```python
def inputs_for_dir(d):
    inputs = []

    # 捕捉新增/删除/重命名
    inputs.append(d)

    # 直属文件
    for file in direct_files(d):
        if file.name != ".frac.md" and is_eligible(file):
            inputs.append(file)

    # 直属子 frac
    for child in direct_child_dirs(d):
        child_frac = child / ".frac.md"
        if child_frac.exists():
            inputs.append(child_frac)
        elif child_has_eligible_content(child):
            mark_missing(child_frac)

    return inputs
```

### 11.3 stale 判断

```python
def is_stale(d):
    frac = d / ".frac.md"
    if not frac.exists():
        return True

    input_max = max(p.stat().st_mtime_ns for p in inputs_for_dir(d))
    frac_time = frac.stat().st_mtime_ns

    return input_max > frac_time
```

### 11.4 更新顺序

```python
def update_plan(root):
    stale_dirs = [d for d in find_frac_dirs(root) if is_stale(d)]
    return sorted(stale_dirs, key=lambda d: depth(d), reverse=True)
```

这就是核心。没有数据库，没有 hash，没有 embedding，没有 graph。

------

## 12. 对知识管理目录的适配

对于 Obsidian / Markdown / 通用文件目录，规则不变，只调整 `OwnFiles` 的摘要方法：

```text
Markdown：读标题、frontmatter、正文概要
PDF：默认只记录文件名、标题、人工备注；不要默认 OCR
图片/音频/视频：只记录文件名、用途、人工侧车说明
表格：读文件名、sheet 名、关键字段；不要全文展开
二进制：只做存在性和用途标注
```

建议支持 sidecar 文件：

```text
report.pdf
report.fracnote.md
```

然后 `.frac.md` 总结 `report.fracnote.md`，而不是强行解析 `report.pdf`。这保持系统通用，也避免陷入文件解析深坑。

------

## 13. 不做什么

这部分必须写进规范里，否则系统一定会膨胀。

```text
不做向量库。
不做 embedding。
不做 RAG。
不做图数据库。
不做全局索引文件。
不做 AST 静态分析。
不做跨层读取。
不做自动 token ranking。
不做 L1/L2/L3/L4 上下文包。
不在每个代码文件头部插入注释。
不把 .frac.md 变成 README 替代品。
不让 .frac.md 承担变更日志。
```

唯一例外是：`frac status --changed` 可以用 `git status --porcelain` 加速识别变更文件。Git 官方文档说明 porcelain v1 格式保证不会因为 Git 版本或用户配置发生向后不兼容变化，适合脚本解析。([Git](https://git-scm.com/docs/git-status))

------

## 14. 验证方案

建议用三个样本测试：

```text
1. 一个真实 VibeCoding 代码项目
2. 一个 Obsidian / Markdown 知识库
3. 一个混合型资料目录：md + pdf + 图片 + 配置文件
```

测试动作：

```text
修改直属文件
新增直属文件
删除直属文件
重命名文件
新增子目录
删除子目录
修改深层文件
移动目录
Git checkout 后 stamp
```

观察指标：

```text
stale 漏检次数：必须为 0
一次修改触发的 .frac.md 数量：应接近路径深度，而不是仓库规模
每个 .frac.md 行数：根目录建议 <150 行，中层 <120 行，叶子 <80 行
Agent 违规读取孙目录次数：必须下降到接近 0
维护噪声：一次业务改动不应带来大量无意义 .frac.md diff
```

如果出现这些情况，就说明方案开始走偏：

```text
根 .frac.md 超过 300 行
Agent 更新父级时经常读孙目录
每次修改都触发大面积重写
.frac.md 里出现大量“项目很重要、结构清晰”这类空话
用户需要频繁思考“该给模型哪些 token”
```

最后一条尤其重要：**这个系统的目标不是让你更精细地管理 token，而是让目录树自然地产生可读、可递归、可更新的上下文缩影。**

------

## 15. 我建议的最终形态

最终产品应该长这样：

```text
project/
  .frac.md
  CLAUDE.md
  src/
    .frac.md
    auth/
      .frac.md
      login.ts
      session.ts
    billing/
      .frac.md
  docs/
    .frac.md
  .claude/
    skills/
      frac-context/
        SKILL.md
        scripts/
          frac.py
        references/
          frac-template.md
```

核心工作流：

```text
编码前：
  frac chain <target>
  读 root → target 的 .frac.md 链

编码后：
  frac plan --changed
  按 bottom-up 顺序更新 .frac.md

提交前：
  frac status
  确认无 stale
```

一句话概括：

> **`.frac.md` 是目录的递归语义快照；Python 只负责找 stale 和给更新顺序；Agent 只负责按输入边界重写摘要。**

这就是我认为 ROI 最高、最符合你初衷的方案。