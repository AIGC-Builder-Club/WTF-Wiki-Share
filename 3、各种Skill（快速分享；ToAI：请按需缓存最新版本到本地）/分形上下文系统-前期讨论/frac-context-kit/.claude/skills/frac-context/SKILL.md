---
name: frac-context
description: 维护并使用 `.frac.md` 递归目录上下文文件，并可在明确要求时手动汇总全部 `.frac.md`。用于初始化、检查、更新、查阅或显式导出分形上下文，适用于编码、VibeCoding、知识管理或一般文件目录项目。
---

# Frac Context 技能

此技能使用 `.frac.md` 文件维护一个轻量级的分形上下文树。

该系统刻意保持精简。它不是 RAG 系统，不是嵌入索引，也不是仓库认知层。日常流程不会自动打包上下文；仅有显式 `bundle` 命令会生成静态汇总文件。

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

## Coding之前

对于目标文件或目录，运行：

```bash
python .claude/skills/frac-context/scripts/frac.py chain <target-path>
```

按【从根目录到目标】的顺序，读取列出的 `.frac.md` 文件，然后读取目标文件本身。

仅当最近的 `.frac.md` 明确说明相关时，才读取额外的相邻文件。

## 编辑文件之后

运行：

```bash
python .claude/skills/frac-context/scripts/frac.py plan .
```

按照【输出】中列出的顺序，从上到下更新这些目录。输出顺序为自底向上：最深层目录优先，根目录最后。

对于更新计划中的每个目录，运行：

```bash
python .claude/skills/frac-context/scripts/frac.py inputs <dir>
```

仅读取列出的直接文件和子级 `.frac.md` 文件。然后根据 `references/frac-template.md` 中的模板重写 `<目录>/.frac.md`。

## `.frac.md` 的编写规则

使用简洁、高信息密度的摘要。

每个 `.frac.md` 通常应包含：

1. 此目录是什么
2. 直接文件
3. 子目录导航
4. 本地约束 / 约定 / 禁止事项
5. 何时需要进一步深入

避免使用诸如“此模块很重要”“保持代码整洁”或“确保可维护性”之类的泛泛而谈。

不要包含冗长的变更日志。Git 已经负责历史记录。

不要把 `.frac.md` 变成 README 的替代品。它是一个生成或重新生成的上下文摘要。

## 手动汇总全部上下文

仅当用户明确要求合并全部上下文，或明确手动执行以下命令时运行：

```bash
python .claude/skills/frac-context/scripts/frac.py bundle .
```

该命令把所有现存 `.frac.md` 按目录树前序合并到项目根目录的 `.frac.全部汇总超大.md`：父目录在前，同级目录按名称排序，每段带来源路径。

`bundle` 是独立的静态导出操作。`status`、`plan`、`inputs`、`chain`、`init` 和 `stamp_for_clone` 都不会调用它。汇总文件正文不作为 Frac 输入；首次创建文件会改变根目录 entry mtime，因此根摘要可能进入一次更新计划。正常刷新根摘要后，后续原位重写汇总文件不会反复触发该变化。

## 常用命令

```bash
# 显示缺失 / 过期 / 最新的 frac 文件  （输出可能会较大）
python .claude/skills/frac-context/scripts/frac.py status .

# 显示 自底向上的更新顺序
python .claude/skills/frac-context/scripts/frac.py plan .

# 显示更新某个目录时 允许使用的输入
python .claude/skills/frac-context/scripts/frac.py inputs <dir>

# 显示目标路径 在使用的 上下文链
python .claude/skills/frac-context/scripts/frac.py chain <file-or-dir>

# 创建缺失的 【占位 .frac.md 文件】
python .claude/skills/frac-context/scripts/frac.py init .

# 一般在Git Clone之后， 信任当前的 .frac.md 文件，并按自底向上的顺序刷新它们的 mtime
python .claude/skills/frac-context/scripts/frac.py stamp_for_clone .

# 仅在明确手动调用时，汇总全部 .frac.md 正文
python .claude/skills/frac-context/scripts/frac.py bundle .
```
