# Frac Context Kit

一个轻量的“分形上下文系统”工具包，用于 VibeCoding 项目、知识管理目录、通用文件目录。

核心目标不是做 RAG、索引、知识图谱或代码认知缓存，而是维护一棵可解释、可重建、低成本的递归摘要树：

```text
Frac(D) = Summary( OwnFiles(D), ChildFracs(D) )
```

其中：

```text
OwnFiles(D)   = D 目录下的直属有效文件，不含 .frac.md，不含被忽略文件
ChildFracs(D) = D 的直属子目录中的 .frac.md
```

父级 `.frac.md` 只相信直属子目录的 `.frac.md`，不跨层读取孙目录源码或资料。

三条规矩（详见 `SKILL.md`）：

```text
1. 只在收尾时更新：代码和测试都定了、提交之前，一次做完；中途落后是正常的
2. 单份有上限：硬上限 10 KiB；每个目录的预算 = 2 KiB + 直属条目 × 340 B，封顶 10 KiB
3. 不写会过时的东西：版本史、日期、测试条数、行号、提交号、原话、参数细目
```

---

## 目录结构

```text
frac-context-kit/
  README.md
  CLAUDE.md.example
  .fracignore.example
  .claude/
    skills/
      frac-context/
        SKILL.md
        manifest.json          版本号 + 每个文件的 sha256（自动更新用）
        scripts/
          frac.py              入口：命令行参数与分派；每个命令跑完顺路查更新
          fraclib/
            project.py         目录树：哪些目录要有 .frac.md、输入、新鲜度、顺序、链、mtime、汇总
            budget.py          计算引擎：单份 .frac.md 的硬上限与预算
            lint.py            易变内容检查
            wrapup.py          收尾：清单、confirm、check、可删的 .frac.md
            usage.py           调用记录与提醒
            update.py          自动更新，以及 version / update / manifest 命令
            report.py          文本与 JSON 输出
        references/
          frac-template.md
          update-rules.md
          design-principles.md
  examples/
    minimal-project/
    knowledge-base/
  tests/
    test_frac_smoke.py
    test_frac_budget.py
    test_frac_update.py
```

---

## 快速安装

把下面这个目录复制到你的项目根目录：

```text
.claude/skills/frac-context/
```

然后可选地复制：

```text
CLAUDE.md.example  ->  CLAUDE.md
.fracignore.example ->  .fracignore
```

在项目根目录运行：

```bash
python .claude/skills/frac-context/scripts/frac.py status .
```

已经装过旧版的项目，整个目录覆盖即可；命令和参数都向下兼容。项目 README 里那段说明照下面“项目 README 里怎么写”改一下。2.1 起装好之后会自己跟上新版，见“自动更新”。

---

## 推荐工作流

### 1. 初始化

```bash
python .claude/skills/frac-context/scripts/frac.py init .
```

`init` 会为需要维护上下文的目录创建 `.frac.md` 占位文件，并故意把它们标记为 stale。接下来按第 4 步的收尾流程，从最深目录开始写。

---

### 2. 动手前：读目标路径的上下文链

```bash
python .claude/skills/frac-context/scripts/frac.py chain src/auth/login.ts
```

示例输出：

```text
frac-chain:
  .frac.md           0.8K
  src/.frac.md       0.7K
  src/auth/.frac.md  0.8K stale

提示：标 stale 的比它的输入旧。照读：对不上的以代码和你自己的改动为准；不用现在修，收尾时一起处理。
```

编码前读取这条链，再读取目标文件本身。必要时根据最近一级 `.frac.md` 的“什么时候需要下钻”提示，读相邻文件。同一条链本轮读过就不再读。

标 `stale` 的比它的输入旧：照读，对不上的以代码为准。标“超限”的太长：先读第 1、4、5 节，第 2 节只找你要改的文件。

---

### 3. 中途：不管 `.frac.md`

中途不更新 `.frac.md`，也不为了对齐去反复跑 `status` / `plan`。中途写的会被后面的改动推翻；每读写一份，上下文就大一圈，整轮就长一截。

中途读到 `.frac.md` 和代码对不上，是正常的。你这次改了什么，你的对话里都有。

中途跑了 `status` / `plan`，工具会提醒这些；一小时内跑到第三次，还会提醒查得太勤。

---

### 4. 收尾：一次做完

代码和测试都定了、提交之前：

```bash
python .claude/skills/frac-context/scripts/frac.py plan . --final
```

示例输出：

```text
收尾清单（自底向上，按顺序处理；每份只写一次）：
   1. src/auth  [输入变了]  0.8K/2.7K
   2. src       [连带]      0.7K/2.7K
   3. .         [连带]      0.8K/3.0K
```

`0.8K/2.7K` 是现在的大小 / 这个目录的预算。

逐个处理：

```bash
# 看这一层允许读的输入、预算、现有内容里的易变项
python .claude/skills/frac-context/scripts/frac.py inputs src/auth
```

- 这一层该写的变了（职责、文件分工、对外接口、约束、下钻建议）：以现有内容为底稿整份重写，不超预算，不在旧文后面追加。只读这次变了的输入，不读孙目录源码，不搜索全仓库，不做 RAG。
- 没变（函数内部、修 bug、调数字、改测试）：只确认，上面没有别的改动的各层一起确认：

```bash
python .claude/skills/frac-context/scripts/frac.py confirm src/auth
```

全部处理完：

```bash
python .claude/skills/frac-context/scripts/frac.py check . --changed
```

本轮改过的 `.frac.md` 没有超过硬上限，才算收尾完成（退出码 0）。

---

### 5. 查看全部状态

```bash
python .claude/skills/frac-context/scripts/frac.py status .
```

状态含义：

```text
missing     当前目录应该有 .frac.md，但文件不存在
stale       输入比当前 .frac.md 更新
fresh       当前 .frac.md 晚于或等于所有输入
```

每行带 `size/budget` 和标记（超限 / 超预算 / 接近）。`status` 会区分“当前实际 stale”和“由于子目录更新而应该连带更新的祖先”。

不带 `--final` 的 `plan .` 只列更新顺序，向下兼容旧用法。

---

### 6. Git clone / checkout 后修复 mtime

如果你把 `.frac.md` 纳入 Git，clone 或 checkout 后，mtime 不一定能表达“摘要晚于输入”的语义。这时可以在确认 `.frac.md` 内容可信后运行：

```bash
python .claude/skills/frac-context/scripts/frac.py stamp_for_clone .
```

`stamp_for_clone` 会自底向上 touch 所有 `.frac.md`，让父级 mtime 不早于子级 mtime。

---

### 7. 手动汇总全部上下文

只有明确需要单文件上下文包时，才手动运行：

```bash
python .claude/skills/frac-context/scripts/frac.py bundle .
```

该命令按目录树前序合并所有现存 `.frac.md`：父目录在前，同级目录按名称排序，每段带来源路径。默认输出为所指定目录下的：

```text
.frac.全部汇总超大.md
```

位置参数也可以是特定子目录。例如：

```bash
python .claude/skills/frac-context/scripts/frac.py bundle examples/minimal-project/src
```

这只会合并 `src/` 及其后代的 `.frac.md`，并写入 `src/.frac.全部汇总超大.md`。

`bundle` 不会被 `status`、`plan`、`inputs`、`chain`、`confirm`、`check`、`init` 或 `stamp_for_clone` 自动调用。汇总文件也被排除在 Frac 内容输入之外。首次创建文件会改变所在根目录的 entry mtime，因此对应根摘要可能进入一次正常更新计划；后续原位重写不会反复触发该变化。

---

## 大小：硬上限与预算

```text
硬上限 = 10 KiB（10,240 字节，按 UTF-8 计；中文约 3,400 字）
预算   = min(10 KiB, 2 KiB + 直属条目数 × 340 B)
直属条目数 = 直属有效文件数 + 直属子目录数 + 直属的 git 子模块数
```

| 直属条目 | 预算 |
|---|---|
| 0 | 2.0 KiB |
| 3 | 3.0 KiB |
| 10 | 5.3 KiB |
| 18 | 8.0 KiB |
| 25 及以上 | 10 KiB（封顶） |

预算只看本目录自己，不和仓库里别的目录比：别处多一个文件，这里的预算不会跟着动。

`frac.py` 每次运行都量：超过硬上限，`check` 不通过、`confirm` 拒绝；超过预算提示压缩；到预算 85% 提示“接近”。超了先删易变内容和细节；直属文件多就按功能分组写；只有拆目录不用改配置、打包、路径时才拆目录。

常量和算法在 `scripts/fraclib/budget.py`（`HARD_CAP_BYTES`、`BUDGET_BASE_BYTES`、`BUDGET_PER_ENTRY_BYTES`、`SizeBudget`）。

---

## 易变内容

`inputs`、`plan --final`、`check` 会找出 `.frac.md` 里会过时、或者会让它变成变更日志的内容，并给出在哪几行、怎么改：

```text
版本号        写现在是什么，不写哪一版加了什么
日期          不写日期和“最近更新”：新鲜度看 mtime，历史看 git
测试/检查条数  不写有几条：写测试在哪、测什么
行号/行数      写函数名或小节名
提交号/评论号  历史在 git log 和 issue 里
超长条目      一条只写做什么、对外给什么、改时注意什么
```

这是正则判断，可能误报，所以只提示、不拦截。代码块里的内容不查。

---

## 调用记录

`status`、`plan`、`chain`、`inputs` 会把调用时间记在 git 目录里：

```bash
git rev-parse --git-path frac-context-usage.json
```

它不进工作区，只用来提醒“一小时内查了好几次”“这条链刚取过”。不是 git 仓库就不记。设环境变量 `FRAC_USAGE_LOG=0` 可关掉。

---

## 自动更新

`frac.py` 的每个命令跑完，都会顺路看一眼上游（本 kit 在 GitHub main 上的 `.claude/skills/frac-context/`）有没有新版：

- 每台机器最多每小时联网查一次，结果记在 `~/.cache/frac-context/update-check.json`，同一台机器上的各个仓库共用；离线、超时（4 秒）都静默跳过，命令本身照常。
- 有新版，就把 skill 目录里内容不同的文件换成新版：每个文件都要对上 `manifest.json` 里的 sha256，`.py` 还要能编译，全部通过才替换；任何一步不过，保留旧版，15 分钟后再试。新版不再有的文件会删掉。
- 只动 `manifest.json` 列出的文件：仓库自己放在 skill 目录里的东西不动。本地改过的文件（和本地 `manifest.json` 对不上）不自动覆盖，会提示 `frac.py update --force`。
- 换完在 stderr 提示“已自动更新”：这次命令还是旧版跑的；规矩可能有变，先重读 `SKILL.md`；换下来的文件跟这次的改动一起提交，仓库里的副本就跟上了。
- raw.githubusercontent.com 连不上时改用 jsDelivr（可能晚几个小时，sha256 校验挡住新旧混杂）。

```bash
python .claude/skills/frac-context/scripts/frac.py version         # 版本、来源、上次检查结果
python .claude/skills/frac-context/scripts/frac.py update --check  # 现在就查，只报告
python .claude/skills/frac-context/scripts/frac.py update          # 现在就查，有新版就换
```

环境变量：

```text
FRAC_UPDATE=auto     默认：有新版就换
FRAC_UPDATE=notify   只提示，不换
FRAC_UPDATE=off      不联网（CI、离线环境、测试）
FRAC_UPDATE_URL      换来源：指到一个 skill 目录，末尾带 /
FRAC_UPDATE_CACHE    换缓存文件的位置
```

### 维护者：发版

1. 改代码或文档；要让各仓库换上，就调高 `scripts/fraclib/__init__.py` 里的 `FRAC_VERSION`（修正调第三位，规矩或命令变了调第二位）。
2. 重写 manifest：`python .claude/skills/frac-context/scripts/frac.py manifest --write`。
3. 跑 `tests/` 下的测试（`test_frac_update.py` 会检查 `manifest.json` 和文件、版本号一致）。
4. 合进 main。各机器在一小时内的下一次运行就会换上（走 jsDelivr 的可能再晚几个小时）。

只改文件、不调版本号，各仓库不会换（上游版本不比本地新）。

---

## 项目 README 里怎么写

`SKILL.md` 的 Meta 说明要求在项目根目录的 README 里简要说明这一机制。可以照抄这一段：

````markdown
> **分形上下文 `.frac.md`**：每个目录下的 `.frac.md` 只总结本目录的直属文件和直属子目录的 `.frac.md`。
> **只在收尾时更新**（代码和测试都定了、提交之前），中途落后是正常的；单份不超过 10 KiB；不写版本史、测试条数这类会过时的东西。
> 规则与工具在 [`.claude/skills/frac-context/`](.claude/skills/frac-context/SKILL.md)（会自己更新，换下来的文件随改动一起提交），根目录的摘要见 [`.frac.md`](.frac.md)：
>
> ```bash
> python3 .claude/skills/frac-context/scripts/frac.py stamp_for_clone .   # 刚 clone 完先跑一次
> python3 .claude/skills/frac-context/scripts/frac.py chain <目标路径>     # 动手前：该读哪几份
> python3 .claude/skills/frac-context/scripts/frac.py plan . --final      # 收尾：清单，逐个重写或 confirm
> python3 .claude/skills/frac-context/scripts/frac.py check . --changed   # 收尾最后一步
> ```
````

---

## `.frac.md` 最小模板

见：

```text
.claude/skills/frac-context/references/frac-template.md
```

---

## `.fracignore`

可以在项目根目录创建 `.fracignore`。语法是极简 glob，不是完整 gitignore：

```text
# 忽略目录
node_modules/
dist/
build/

# 忽略文件
*.log
*.tmp
```

默认已忽略常见噪声目录，例如 `.git/`、`node_modules/`、`dist/`、`build/`、`.venv/`、`__pycache__/`、`.next/` 等。

带斜杠的目录模式（如 `docs/generated/`）从项目根目录算起，连同下面的文件一起忽略；单段的（如 `build/`）忽略任何一层叫这个名字的目录。

仓库里的 frac-context skill 副本（`*/skills/frac-context/`、`skills/frac-context/`，以及正在运行的那一份）自动不进 `.frac.md` 树：它的说明就是 `SKILL.md`，内容又由自动更新维护。副本里以前写的 `.frac.md`，以及目录里除了 `.frac.md` 什么都没有的，`check` 会列为“可以删”。

如果当前目录是 Git 仓库，工具会优先使用：

```bash
git ls-files --cached --others --exclude-standard
```

来获得 Git 视角下的有效文件；失败时自动回退到普通文件系统扫描。

---

## 这个工具明确不做什么

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
不让 .frac.md 替代 README。
不让 .frac.md 承担变更日志。
不在 .frac.md 里记版本史、测试条数这类易变数字。
```

---

## 适合场景

```text
个人 VibeCoding 项目
中小型代码仓库
Obsidian / Markdown 知识库
通用资料目录
需要让 AI Agent 快速理解目录职责的项目
```

不适合场景：

```text
需要全局语义搜索的知识库
需要精确代码调用图的静态分析平台
超大 monorepo 的自动上下文调度系统
高合规审计文档系统
```

---

## 运行测试

```bash
python tests/test_frac_smoke.py
python tests/test_frac_budget.py
python tests/test_frac_update.py
```

测试只依赖 Python 标准库（3.9+），都设了 `FRAC_UPDATE=off`；`test_frac_budget.py` 里依赖 git 的部分在没装 git 时跳过；`test_frac_update.py` 在本机起一个 HTTP 服务当上游，不连外网。
