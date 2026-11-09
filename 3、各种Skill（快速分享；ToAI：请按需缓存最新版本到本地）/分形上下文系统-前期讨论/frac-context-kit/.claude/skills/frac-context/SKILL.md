---
name: frac-context
description: 维护并使用 `.frac.md` 递归目录上下文文件，并可在明确要求时手动汇总全部 `.frac.md`。用于初始化、检查、更新、查阅或显式导出分形上下文，适用于编码、VibeCoding、知识管理或一般文件目录项目。
---

# Frac Context 技能

此技能使用 `.frac.md` 文件维护一个轻量级的分形上下文树。

该系统刻意保持精简。它不是 RAG 系统，不是嵌入索引，也不是仓库认知层。日常流程不会自动打包上下文；仅有显式 `bundle` 命令会生成静态汇总文件。

## Meta说明

- 1、本【分形上下文机制】，最新在线版保持在【 https://github.com/hanshou101/Obsidian_PublicGitHubShare_InsteadOf_FeiShu/blob/main/3%E3%80%81%E5%90%84%E7%A7%8DSkill%EF%BC%88%E5%BF%AB%E9%80%9F%E5%88%86%E4%BA%AB%EF%BC%9BToAI%EF%BC%9A%E8%AF%B7%E6%8C%89%E9%9C%80%E7%BC%93%E5%AD%98%E6%9C%80%E6%96%B0%E7%89%88%E6%9C%AC%E5%88%B0%E6%9C%AC%E5%9C%B0%EF%BC%89/%E5%88%86%E5%BD%A2%E4%B8%8A%E4%B8%8B%E6%96%87%E7%B3%BB%E7%BB%9F-%E5%89%8D%E6%9C%9F%E8%AE%A8%E8%AE%BA/frac-context-kit/.claude/skills/frac-context/SKILL.md 】
- 2、该机制需要定期同步；所以请你在【项目根目录】下相关说明文件（如 README.md ）中，简要说明这一机制（比如在 清楚说明机制 后，加上对【根目录的.frac.md文件】的引用、以及相关skill的文件位置。）


## 核心不变量

For every directory `D`:

```text
Frac(D) = Summary( OwnFiles(D), ChildFracs(D) )
```

其中：

```text
OwnFiles(D)   = D 中符合条件的直接文件，不包括 .frac.md
ChildFracs(D) = 直接子目录中的 .frac.md 文件
```

父级 `.frac.md` 不得读取孙级目录的源文件或更深层嵌套的文档。父级只能信任子级 `.frac.md` 的摘要。

【新鲜度】基于文件系统的 mtime：

```text
fresh(D) ⇔ .frac.md 存在且 frac_mtime_ns >= max(input_mtime_ns)
stale(D) ⇔  .frac.md 缺失 或 任一输入比它更新
```

目录条目的 mtime 也视为输入，因此可以检测直接文件的新增、删除或重命名操作。

仓库里的 frac-context skill 副本（例如 `.claude/skills/frac-context/`）不进 `.frac.md` 树：它的说明就是这份 SKILL.md，内容由自动更新维护。

## 三条规矩（先看这里）

1. **只在收尾时更新。** 代码和测试都定了、提交之前，跑一次 `plan . --final`，照清单一次做完。中途不为对齐去跑 `status` / `plan`，也不改 `.frac.md`：中途写的会被后面的改动推翻；每多读写一份，上下文就大一圈、整轮就长一截（Claude Code 主对话的缓存 1 小时过期，拖得越久越贵）。中途读到 `.frac.md` 和代码对不上是正常的：它只在收尾时追上，你这次改了什么，你的对话里都有，以代码和你自己的改动为准。
2. **单份有上限。** 硬上限 10 KiB（10,240 字节，按 UTF-8 计；中文约 3,400 字）。每个目录另有预算：2 KiB 起，每个直属条目（直属文件、直属子目录、git 子模块）加 340 B，25 项起封顶 10 KiB——简单目录 2~5 KiB，大目录 5~10 KiB。`frac.py` 每次都量：超过硬上限，`check` 不通过、`confirm` 拒绝；超过预算或接近预算会提示。超了先删易变内容和细节；直属文件多就按功能分组写（一组一行）；只有拆目录不用改配置、打包、路径时才拆目录。
3. **不写会过时的东西。** 不写版本史（“0.32.0 起……”）、日期和“最近更新”、测试/检查有几条、行号和行数、提交号和评论号、用户原话、函数参数和默认值的细目。`.frac.md` 写“现在是什么”：职责、文件分工、对外接口、约束、什么时候下钻。历史在 git log，数字在代码和测试里。

## 自动更新

`frac.py` 每个命令跑完，会顺路查上游有没有新版（每台机器最多每小时联网一次，离线就跳过）；有，就把这份 skill 换成新版：每个文件都校验 sha256，本地改过的文件不覆盖，仓库自己的 `.frac.md` 不动。

- stderr 里出现“frac-context 已自动更新”：这次命令还是旧版跑的。先重读本文件（规矩可能变了）再继续；换下来的 skill 文件跟你这次的改动一起提交。
- 出现“本地改过……没有自动覆盖”：有人改过这份副本。确认不要那些改动，再 `frac.py update --force`；拿不准就留着，在交付里说一句。
- `frac.py version` 看版本和上次检查结果，`frac.py update [--check]` 立刻查。`FRAC_UPDATE=notify` 只提示不换，`FRAC_UPDATE=off` 不联网（CI、离线环境）。

## Coding之前

对于目标文件或目录，运行：

```bash
python .claude/skills/frac-context/scripts/frac.py chain <target-path>
```

按【从根目录到目标】的顺序，读取列出的 `.frac.md` 文件，然后读取目标文件本身。同一条链本轮读过就不再读。

仅当最近的 `.frac.md` 明确说明相关时，才读取额外的相邻文件。

`chain` 会标出 `stale`（比输入旧：照读，对不上的以代码为准）和“超限”（太长：先读第 1、4、5 节，第 2 节只找你要改的文件）。

## 收尾时（只在这里更新）

```bash
python .claude/skills/frac-context/scripts/frac.py plan . --final
```

清单自底向上：最深层目录优先，根目录最后。逐个处理，每份只写一次：

1. `frac.py inputs <dir>`：看这一层允许读的输入、预算、现有内容里的易变项。
2. 判断这一层该写的东西变没变（目录职责、文件分工、对外接口、约束、下钻建议）：
   - **变了**：以现有 `.frac.md` 为底稿，整份重写成“现在是什么”，写完不超过预算。只读这次变了的那几个输入；不在旧文后面追加。
   - **没变**（函数内部改动、修 bug、调数字、改测试）：`frac.py confirm <dir>`，只更新时间戳。上面几层如果没有别的改动，会一起确认。
3. 全部处理完：`frac.py check . --changed`。有“超过硬上限”就没收尾完。

现有文件超过硬上限的，轮到它时不能只 `confirm`，要压到预算内：以现有内容为底稿压缩即可（删版本史、数字、原话、参数细目，留职责、分工、接口、约束），不必重读全部直属文件。

## `.frac.md` 的编写规则

使用简洁、高信息密度的摘要。格式见 `references/frac-template.md`，更新细则见 `references/update-rules.md`。

每个 `.frac.md` 通常应包含：

1. 此目录是什么
2. 直接文件
3. 子目录导航
4. 本地约束 / 约定 / 禁止事项
5. 何时需要进一步深入

避免使用诸如“此模块很重要”“保持代码整洁”或“确保可维护性”之类的泛泛而谈。

不要包含变更日志。Git 已经负责历史记录。

不要把 `.frac.md` 变成 README 的替代品。它是一个生成或重新生成的上下文摘要。

## 手动汇总全部上下文

仅当用户明确要求合并全部上下文，或明确手动执行以下命令时运行：

```bash
python .claude/skills/frac-context/scripts/frac.py bundle .
```

该命令把所有现存 `.frac.md` 按目录树前序合并到项目根目录的 `.frac.全部汇总超大.md`：父目录在前，同级目录按名称排序，每段带来源路径。

`bundle` 是独立的静态导出操作。`status`、`plan`、`inputs`、`chain`、`confirm`、`check`、`init` 和 `stamp_for_clone` 都不会调用它。汇总文件正文不作为 Frac 输入；首次创建文件会改变根目录 entry mtime，因此根摘要可能进入一次更新计划。正常刷新根摘要后，后续原位重写汇总文件不会反复触发该变化。

## 常用命令

```bash
# 动手前：目标路径的上下文链（标出 stale 与超限）
python .claude/skills/frac-context/scripts/frac.py chain <file-or-dir>

# 收尾：自底向上的清单，带每份的大小、预算、易变内容
python .claude/skills/frac-context/scripts/frac.py plan . --final

# 收尾：更新某个目录前，看允许的输入、预算、易变内容在哪几行
python .claude/skills/frac-context/scripts/frac.py inputs <dir>

# 收尾：这一层该写的没变，只确认（更新时间戳；没有别的改动的上层一起确认）
python .claude/skills/frac-context/scripts/frac.py confirm <dir> [<dir> ...]

# 收尾最后一步：超过硬上限就不通过（退出码 1）；去掉 --changed 查全部
python .claude/skills/frac-context/scripts/frac.py check . --changed

# 缺失 / 过期 / 最新，带大小与预算（输出可能较大；中途不用看）
python .claude/skills/frac-context/scripts/frac.py status .

# 创建缺失的【占位 .frac.md 文件】
python .claude/skills/frac-context/scripts/frac.py init .

# 一般在 Git Clone 之后，信任当前的 .frac.md 文件，并按自底向上的顺序刷新它们的 mtime
python .claude/skills/frac-context/scripts/frac.py stamp_for_clone .

# 仅在明确手动调用时，汇总全部 .frac.md 正文
python .claude/skills/frac-context/scripts/frac.py bundle .

# 版本与自动更新状态；立刻查上游（--check 只报告，--force 连本地改过的也覆盖）
python .claude/skills/frac-context/scripts/frac.py version
python .claude/skills/frac-context/scripts/frac.py update [--check] [--force]
```

`status`、`plan`、`chain`、`inputs` 会把调用时间记在 git 目录里（`git rev-parse --git-path frac-context-usage.json`，不进工作区），用来提醒“一小时内查了好几次”；设环境变量 `FRAC_USAGE_LOG=0` 可关掉。
