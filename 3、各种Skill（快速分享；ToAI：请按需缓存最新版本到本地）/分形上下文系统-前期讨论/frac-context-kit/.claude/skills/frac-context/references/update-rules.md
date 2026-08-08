# Frac Update Rules

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

然后读取目标文件本身。

---

## 6. Git clone / checkout 后的 stamp_for_clone

如果 `.frac.md` 纳入 Git，clone 或 checkout 后 mtime 不一定可信。

在确认 `.frac.md` 内容可信后运行：

```bash
python .claude/skills/frac-context/scripts/frac.py stamp_for_clone .
```

`stamp_for_clone` 会自底向上 touch `.frac.md`，恢复本地 mtime 不变量。
