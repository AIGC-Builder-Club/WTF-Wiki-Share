# -*- coding: utf-8 -*-
"""frac-context 的实现，入口是旁边的 ../frac.py。

- project.py  目录树模型：输入、新鲜度、更新顺序、上下文链、占位、mtime、汇总
- budget.py   单份 .frac.md 的大小预算（计算引擎）
- lint.py     易变内容检查
- wrapup.py   收尾：大小报告、收尾清单、confirm、check
- usage.py    调用记录与提醒
- update.py   自动更新
- report.py   文本与 JSON 输出

发版：改 FRAC_VERSION，跑 `frac.py manifest --write`，再跑 tests/。
"""

FRAC_VERSION = "2.1.1"
SKILL_NAME = "frac-context"
