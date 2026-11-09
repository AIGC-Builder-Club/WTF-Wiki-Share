# Frac Update Rules

## 0. 什么时候更新

只在收尾时：代码和测试都定了、提交之前，一次做完。

```bash
python .claude/skills/frac-context/scripts/frac.py plan . --final
```

中途不更新，也不为了“对齐”去反复跑 `status` / `plan`：

```text
中途写的，会被后面的改动推翻，收尾时还得再写一遍
每读写一份 .frac.md，上下文就大一圈，之后每一步都要多带它
整轮拖长，主对话的缓存（Claude Code 为 1 小时）过期后还得重写
```

中途读到 `.frac.md` 和代码对不上，是正常的：它只在收尾时追上。你这次改了什么，你的对话里都有，以代码和你自己的改动为准。知道“这份落后了”本身就是有用的信息，不必现在去修。

真发现它写错了（不是落后，是错），记下来，收尾时一起改。

---

## 1. 核心公式

```text
Frac(D) = Summary( OwnFiles(D), ChildFracs(D) )
```

一个目录下的 `.frac.md` 只总结两类东西：

```text
1. 这个目录直属的有效文件
2. 直属子目录的 .frac.md
```

它不直接总结孙目录。
它不跨层读取深层代码。
它不试图理解整个仓库。
父级只相信子级 `.frac.md`。

---

## 2. Fresh / Stale 判断

```text
fresh(D) ⇔ .frac.md exists and frac_mtime_ns >= max(input_mtime_ns)
stale(D) ⇔ .frac.md missing or max(input_mtime_ns) > frac_mtime_ns
```

输入包括：

```text
1. 当前目录 entry mtime，用于发现直属文件新增、删除、重命名
2. 当前目录直属有效文件的 mtime
3. 直属子目录 .frac.md 的 mtime
```

stale 只说明“输入比它新”，不说明内容错了。内容还对，就用 `confirm` 确认，不改内容（见第 7 节）。

---

## 3. 更新顺序

更新必须自底向上：

```text
最深 stale 目录
父目录
祖父目录
...
根目录
```

原因：父级摘要的输入包含子级 `.frac.md`。只有子级更新后，父级才能得到正确输入。

---

## 4. 更新一个目录时 Agent 只能读什么

运行：

```bash
python .claude/skills/frac-context/scripts/frac.py inputs <dir>
```

Agent 只能读取输出中的：

```text
DIRECT FILES
CHILD FRACS
```

以现有 `.frac.md` 为底稿，只读这次变了的那几个输入；没变的不必重读。

不要读取孙目录文件。
不要搜索整个仓库。
不要用 embedding/RAG 补材料。
不要根据记忆编造当前目录事实。

---

## 5. 编码前读取上下文链

运行：

```bash
python .claude/skills/frac-context/scripts/frac.py chain <target-path>
```

读取输出的 `.frac.md` 链：

```text
根 .frac.md
中间目录 .frac.md
目标所在目录 .frac.md
```

然后读取目标文件本身。同一条链本轮读过就不再读。

---

## 6. 改还是不改：这一层该写的变了没有

`.frac.md` 只写这一层看得见的东西：

```text
目录职责与边界
直属文件的分工、对外接口
子目录各负责什么（一句话）
本层约束 / 约定 / 禁忌
什么时候下钻
```

这些变了，才改；改就整份重写成“现在是什么”，不在旧文后面追加一段“这次加了什么”。

这些没变——函数内部改动、修 bug、调数字和默认值、改测试、改文案——就不改内容。

上层同理：子目录的变化只要不改变上层那一句话，上层就不改。一个改动通常只需要改一两份 `.frac.md`，其余各层 `confirm`。

---

## 7. confirm：内容不用改时

```bash
python .claude/skills/frac-context/scripts/frac.py confirm <dir> [<dir> ...]
```

只把 `<dir>/.frac.md` 的 mtime 更新到不早于输入，不碰内容。

上面各层如果在这之前是新的（只会因为下层时间戳变了而变旧），一起确认；原本就落后的上层（有别的输入变了）不替你确认，会列出来让你自己看。

以下情况拒绝，什么都不改：

```text
.frac.md 不存在
超过硬上限（见第 8 节）——轮到它时要压到预算内
有子目录还没有 .frac.md
```

---

## 8. 大小与预算

```text
硬上限 = 10 KiB（10,240 字节，按 UTF-8 计；中文约 3,400 字）
预算   = min(10 KiB, 2 KiB + 直属条目数 × 340 B)
直属条目数 = 直属有效文件数 + 直属子目录数 + 直属的 git 子模块数（与 inputs 的口径一致）
```

| 直属条目 | 预算 |
|---|---|
| 0 | 2.0 KiB |
| 3 | 3.0 KiB |
| 10 | 5.3 KiB |
| 18 | 8.0 KiB |
| 25 及以上 | 10 KiB（封顶） |

`frac.py` 每次运行都量：

```text
超过硬上限  check 不通过（退出码 1），confirm 拒绝
超过预算    提示压缩
到预算 85%  提示“接近”：要加内容，先删旧的
```

超了怎么办，按顺序：

```text
1. 删易变内容：版本史、日期、条数、行号、提交号、原话
2. 删细节：参数、默认值、实现步骤——留在代码注释和 README
3. 直属文件多：按功能分组，一组一行
4. 还是放不下，且拆目录不用改配置、打包、路径：才拆子目录；要动配置才拆得了的，不拆
```

现有文件超过硬上限，轮到它时（在收尾清单里）压到预算内：以现有内容为底稿压缩，不必重读全部直属文件。

---

## 9. 不写会过时的东西

| 不写 | 为什么 | 写什么 |
|---|---|---|
| 版本史（“0.32.0 起……”“此前……”） | `.frac.md` 会变成变更日志，只增不减 | 现在是什么 |
| 日期、“最近更新” | 新鲜度看 mtime，历史看 git | 不写 |
| 测试 / 检查有几条 | 每加一条就过时，改一个数要改好几份 | 测试在哪、测什么 |
| 行号、行数 | 一改就漂 | 函数名、小节名 |
| 提交号、评论号 | 历史指针，不是现状 | 不写 |
| 用户原话 | 长、会被后来的话推翻 | 由它定下的约束本身 |
| 参数、默认值细目 | 重复代码，代码一改就错 | 去哪看 |

`frac.py inputs <dir>` 和 `check` 会把这几类找出来（正则判断，可能误报）。

---

## 10. Git clone / checkout 后的 stamp_for_clone

如果 `.frac.md` 纳入 Git，clone 或 checkout 后 mtime 不一定可信。

在确认 `.frac.md` 内容可信后运行：

```bash
python .claude/skills/frac-context/scripts/frac.py stamp_for_clone .
```

`stamp_for_clone` 会自底向上 touch `.frac.md`，恢复本地 mtime 不变量。

---

## 11. 收尾完成的标准

```bash
python .claude/skills/frac-context/scripts/frac.py check . --changed
```

本轮改过的 `.frac.md` 没有超过硬上限，才算收尾完成。去掉 `--changed` 检查全部（可接进 CI 或 pre-commit）。

`check` 还会列出“已经不参与、可以删”的 `.frac.md`：skill 副本里的（skill 不进 `.frac.md` 树），以及目录里除了它什么都没有的。删掉即可，不用改写。
