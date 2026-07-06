---
name: frac-context
description: Maintain and use .frac.md recursive directory context files. Use when initializing, checking, updating, or consulting fractal context for coding, VibeCoding, knowledge-management, or general file-directory projects.
---

# Frac Context Skill

This skill maintains a lightweight fractal context tree using `.frac.md` files.

The system is intentionally small. It is not a RAG system, not an embedding index, not a repo cognition layer, and not a context-pack generator.

## Core invariant

For every directory `D`:

```text
Frac(D) = Summary( OwnFiles(D), ChildFracs(D) )
```

Where:

```text
OwnFiles(D)   = direct eligible files in D, excluding .frac.md
ChildFracs(D) = .frac.md files in immediate child directories
```

A parent `.frac.md` must not read grandchildren source files or deep nested documents. A parent only trusts the child `.frac.md` summaries.

Freshness is based on filesystem mtime:

```text
fresh(D) ⇔ .frac.md exists and frac_mtime_ns >= max(input_mtime_ns)
stale(D) ⇔ .frac.md is missing or any input is newer
```

The directory entry mtime is also treated as an input so direct file add/delete/rename operations can be detected.

## Before coding

For a target file or directory, run:

```bash
python .claude/skills/frac-context/scripts/frac.py chain <target-path>
```

Read the listed `.frac.md` files from root to target. Then read the target file itself.

Only read extra neighboring files when the closest `.frac.md` explicitly says they are relevant.

## After editing files

Run:

```bash
python .claude/skills/frac-context/scripts/frac.py plan .
```

Update the listed directories from top of the output to bottom. The order is bottom-up: deepest directories first, root last.

For each directory in the update plan, run:

```bash
python .claude/skills/frac-context/scripts/frac.py inputs <dir>
```

Read only the listed direct files and child `.frac.md` files. Then rewrite `<dir>/.frac.md` according to the template in `references/frac-template.md`.

## Writing rules for .frac.md

Use concise, high-signal summaries.

Each `.frac.md` should usually contain:

1. What this directory is
2. Direct files
3. Child directory navigation
4. Local constraints / conventions / prohibitions
5. When to drill down

Avoid generic filler such as “this module is important,” “keep code clean,” or “ensure maintainability.”

Do not include a long changelog. Git already handles history.

Do not turn `.frac.md` into a README replacement. It is a generated or regenerated context summary.

## What not to do

Do not build or request:

```text
vector database
embedding index
RAG pipeline
graph database
global repo map
AST static-analysis layer
token ranking system
L1/L2/L3/L4 context pack
file-header annotation system
```

## Useful commands

```bash
# show missing/stale/fresh frac files
python .claude/skills/frac-context/scripts/frac.py status .

# show bottom-up update order
python .claude/skills/frac-context/scripts/frac.py plan .

# show allowed inputs for updating one directory
python .claude/skills/frac-context/scripts/frac.py inputs <dir>

# show context chain for a target path
python .claude/skills/frac-context/scripts/frac.py chain <file-or-dir>

# create missing placeholder .frac.md files
python .claude/skills/frac-context/scripts/frac.py init .

# trust current .frac.md files and refresh their mtimes bottom-up
python .claude/skills/frac-context/scripts/frac.py stamp .
```
