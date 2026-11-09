# -*- coding: utf-8 -*-
"""调用记录与提醒：中途查看、查得太勤、同一条链重复取、同一目录重复取输入。"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .project import FracProject
from .wrapup import size_report

# 频率提醒只看最近这么久之内的调用。
RECENT_SECONDS = 3600
# 调用记录放在 git 目录里（git rev-parse --git-path），不进工作区；设 FRAC_USAGE_LOG=0 关掉。
USAGE_LOG_NAME = "frac-context-usage.json"
USAGE_LOG_KEEP = 80


class UsageLog:
    """记下最近的 frac 调用，用来提醒“查得太勤”。尽力而为：读写失败就当没有记录。"""

    def __init__(self, project: FracProject) -> None:
        self.path: Optional[Path] = None
        if os.environ.get("FRAC_USAGE_LOG", "1") != "0":
            self.path = project.git_path(USAGE_LOG_NAME)

    def record(self, command: str, key: str = "", final: bool = False) -> List[Dict[str, object]]:
        """记下这次调用；返回最近 RECENT_SECONDS 内更早的调用。"""
        if self.path is None:
            return []
        now = time.time()
        calls: List[Dict[str, object]] = []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("calls"), list):
                calls = [c for c in data["calls"] if isinstance(c, dict)]
        except Exception:
            calls = []
        recent = [c for c in calls if 0 <= now - float(c.get("t", 0) or 0) <= RECENT_SECONDS]
        calls = (calls + [{"t": now, "cmd": command, "key": key, "final": final}])[-USAGE_LOG_KEEP:]
        try:
            tmp = self.path.with_name(self.path.name + ".tmp")
            tmp.write_text(json.dumps({"calls": calls}, ensure_ascii=False), encoding="utf-8")
            os.replace(str(tmp), str(self.path))
        except Exception:
            pass
        return recent


def mid_task_notes(recent: Sequence[Dict[str, object]], premature: Sequence[str]) -> List[str]:
    lines = [
        "提示（中途查看）：.frac.md 只在收尾时更新，现在落后于代码是正常的，不用改。",
        "  你这次改了什么，你的对话里都有；读到对不上的地方，以代码和你自己的改动为准。",
        "  收尾时（代码和测试都定了、提交之前）跑一次：frac.py plan . --final",
    ]
    n = 1 + sum(1 for c in recent if c.get("cmd") in {"status", "plan"} and not c.get("final"))
    if n >= 3:
        lines.append(
            f"提示：一小时内这是第 {n} 次中途查看。查看本身不贵，贵的是接着去读、去改 .frac.md："
            "每多读一份，之后每一步都要多带它的上下文；整轮拖长，主对话的缓存（Claude Code 为 1 小时）过期后还得重写。"
        )
    if premature:
        lines.append("提示：下面这些 .frac.md 本轮已经改过，之后输入又变了——中途写的被推翻了。先停手，收尾时再看：")
        lines.extend(f"  {d}" for d in premature[:8])
    return lines


def final_notes(recent: Sequence[Dict[str, object]], premature: Sequence[str]) -> List[str]:
    lines: List[str] = []
    if premature:
        lines.append("提示：下面这些 .frac.md 本轮已经写过，之后输入又变了。这一层该写的没变就 confirm，不要再改一遍：")
        lines.extend(f"  {d}" for d in premature[:8])
    n = 1 + sum(1 for c in recent if c.get("cmd") == "plan" and c.get("final"))
    if n >= 3:
        lines.append(f"提示：收尾清单一小时内跑了 {n} 次。每份只写一次，写完不回头润色措辞。")
    return lines


def chain_notes(project: FracProject, chain: Sequence[Path], recent: Sequence[Dict[str, object]], key: str) -> List[str]:
    lines: List[str] = []
    stale = []
    over = []
    for f in chain:
        d = f.parent
        if not f.exists():
            continue
        if project.actual_status_for_dir(d).state != "fresh":
            stale.append(f)
        if size_report(project, d).level == "over-cap":
            over.append(f)
    if stale:
        lines.append("提示：标 stale 的比它的输入旧。照读：对不上的以代码和你自己的改动为准；不用现在修，收尾时一起处理。")
    if over:
        lines.append("提示：标超限的太长。先读第 1、4、5 节；第 2 节只找你要改的那个文件，不必通读。")
    for c in recent:
        if c.get("cmd") == "chain" and c.get("key") == key:
            minutes = max(1, int((time.time() - float(c.get("t", 0) or 0)) // 60))
            lines.append(f"提示：这条链约 {minutes} 分钟前取过；已经读过的不用再读。")
            break
    return lines


def inputs_notes(recent: Sequence[Dict[str, object]], key: str) -> List[str]:
    for c in recent:
        if c.get("cmd") == "inputs" and c.get("key") == key:
            return ["提示：这个目录的输入一小时内已经取过。同一份 .frac.md 一轮只写一次，写完就换下一个。"]
    return []
