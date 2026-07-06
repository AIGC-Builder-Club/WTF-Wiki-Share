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
        scripts/
          frac.py
        references/
          frac-template.md
          update-rules.md
          design-principles.md
  examples/
    minimal-project/
    knowledge-base/
  tests/
    test_frac_smoke.py
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

---

## 推荐工作流

### 1. 初始化

```bash
python .claude/skills/frac-context/scripts/frac.py init .
```

`init` 会为需要维护上下文的目录创建 `.frac.md` 占位文件，并故意把它们标记为 stale。接下来运行：

```bash
python .claude/skills/frac-context/scripts/frac.py plan .
```

按输出顺序，从最深目录开始更新 `.frac.md`。

---

### 2. 查看哪些上下文过期

```bash
python .claude/skills/frac-context/scripts/frac.py status .
```

状态含义：

```text
missing     当前目录应该有 .frac.md，但文件不存在
stale       输入比当前 .frac.md 更新
fresh       当前 .frac.md 晚于或等于所有输入
```

注意：`status` 会区分“当前实际 stale”和“由于子目录更新而应该连带更新的祖先”。

---

### 3. 获取自底向上的更新顺序

```bash
python .claude/skills/frac-context/scripts/frac.py plan .
```

示例输出：

```text
update-order:
  1. src/auth
  2. src
  3. .
```

Agent 应该严格按这个顺序更新。

---

### 4. 更新某个目录 `.frac.md` 时，只读取规定输入

```bash
python .claude/skills/frac-context/scripts/frac.py inputs src/auth
```

它会输出：

```text
DIRECT FILES:
  src/auth/login.ts
  src/auth/session.ts

CHILD FRACS:
  src/auth/providers/.frac.md
```

更新 `src/auth/.frac.md` 时，只读这些输入。不读孙目录源码，不搜索全仓库，不做 RAG。

---

### 5. 编码前读取目标路径的上下文链

```bash
python .claude/skills/frac-context/scripts/frac.py chain src/auth/login.ts
```

示例输出：

```text
.frac.md
src/.frac.md
src/auth/.frac.md
```

编码前读取这条链，再读取目标文件本身。必要时根据最近一级 `.frac.md` 的“什么时候需要下钻”提示，读相邻文件。

---

### 6. Git clone / checkout 后修复 mtime

如果你把 `.frac.md` 纳入 Git，clone 或 checkout 后，mtime 不一定能表达“摘要晚于输入”的语义。这时可以在确认 `.frac.md` 内容可信后运行：

```bash
python .claude/skills/frac-context/scripts/frac.py stamp_for_clone .
```

`stamp_for_clone` 会自底向上 touch 所有 `.frac.md`，让父级 mtime 不早于子级 mtime。

---

## `.frac.md` 最小模板

见：

```text
.claude/skills/frac-context/references/frac-template.md
```

建议每个 `.frac.md` 控制长度：

```text
根目录：小于 150 行
中层目录：小于 120 行
叶子目录：小于 80 行
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
```

测试只依赖 Python 标准库。
