#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for the size budget, volatile-content lint, plan --final, confirm, check and reminders.

Standard library only. Git-dependent parts are skipped when git is not installed.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRAC = ROOT / ".claude" / "skills" / "frac-context" / "scripts" / "frac.py"

sys.dont_write_bytecode = True  # 不在 scripts/ 里留下 __pycache__
spec = importlib.util.spec_from_file_location("frac_module", FRAC)
frac = importlib.util.module_from_spec(spec)
sys.modules["frac_module"] = frac
assert spec.loader is not None
spec.loader.exec_module(frac)

HAS_GIT = shutil.which("git") is not None


def run(args, cwd, expect=0, env=None, stdout_only=False):
    result = subprocess.run(
        [sys.executable, str(FRAC), *args],
        cwd=str(cwd),
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    if result.returncode != expect:
        raise AssertionError(
            f"command {args} exited {result.returncode}, expected {expect}\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return result.stdout if stdout_only else result.stdout + result.stderr


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def frac_doc(rel: str, body: str = "") -> str:
    return f"# .frac.md — {rel}\n\n## 1. 本目录是什么\n\n示例目录。{body}\n"


def set_mtime(path: Path, seconds_from_now: float) -> None:
    ts = int((time.time() + seconds_from_now) * 1e9)
    os.utime(path, ns=(ts, ts))


def states(cwd) -> dict:
    data = json.loads(run(["status", ".", "--json"], cwd, stdout_only=True))
    return {item["directory"]: item for item in data}


def make_project(base: Path) -> Path:
    """root/README.md, root/src/main.py, root/src/auth/login.py, all with fresh .frac.md."""
    project = base / "project"
    write(project / "README.md", "# Demo\n")
    write(project / "src" / "main.py", "print('hi')\n")
    write(project / "src" / "auth" / "login.py", "def login(): pass\n")
    write(project / ".frac.md", frac_doc("."))
    write(project / "src" / ".frac.md", frac_doc("src"))
    write(project / "src" / "auth" / ".frac.md", frac_doc("src/auth"))
    run(["stamp_for_clone", "."], project)
    return project


def test_budget_engine() -> None:
    b = frac.SizeBudget()
    assert b.cap == 10 * 1024
    assert b.budget(0) == 2048
    assert b.budget(1) == 2048 + 340
    assert b.budget(10) == 2048 + 3400
    assert b.budget(24) == 2048 + 24 * 340
    assert b.budget(25) == 10240 and b.budget(500) == 10240
    assert b.saturation_entries() == 25
    assert b.level(None, 5000) == "missing"
    assert b.level(10241, 10240) == "over-cap"
    assert b.level(5001, 5000) == "over-budget"
    assert b.level(4300, 5000) == "near"
    assert b.level(1000, 5000) == "ok"


def test_lint() -> None:
    text = "\n".join([
        "# .frac.md — src",
        "> 最近更新：2026-11-09 +0800（AME-1211）",
        "- `settings.ts`：0.24.1 起多一个开关；0.32.0 再加两个。",
        "- 测试在 `test/checkin-rules.test.js`（12 条：读得宽）。共 963 个测试，104 checks。",
        "- AME-360 自测的原始数据在 `notes/`。",
        "- 入口在 `main.ts:120`，见第 13 行；全文 146 行。",
        "- 从 `82d2240` 推到新版。",
        "- " + "很长的说明" * 60,
        "```",
        "npm i foo@1.2.3  # 代码块里的不查",
        "```",
    ])
    hits = frac.lint_frac_text(text)
    counts = frac.lint_counts(hits)
    assert counts.get("version") == 2, counts
    assert counts.get("date") == 1, counts
    assert counts.get("count") == 3, (counts, [h for h in hits if h.kind == "count"])
    assert counts.get("lineref") == 3, (counts, [h for h in hits if h.kind == "lineref"])
    assert counts.get("hash") == 1, counts
    assert counts.get("long") == 1, counts
    assert not any(h.line == 5 and h.kind == "count" for h in hits), "AME-360 is an id, not a count"
    assert not any(h.line >= 9 for h in hits), "code blocks are skipped"
    clean = "# .frac.md — src\n\n- `login.ts`：提供 `login()`，校验凭据并创建会话。\n"
    assert frac.lint_frac_text(clean) == []


def test_check_and_inputs_budget(base: Path) -> None:
    project = make_project(base)
    out = run(["check", "."], project)
    assert "结果：通过" in out
    big = frac_doc("src", "很长" * 2000)  # ~12 KB of UTF-8
    write(project / "src" / ".frac.md", big)
    out = run(["check", "."], project, expect=1)
    assert "超过硬上限" in out and "src/.frac.md" in out
    data = json.loads(run(["check", ".", "--json"], project, expect=1, stdout_only=True))
    assert data["ok"] is False and data["over_cap"][0]["frac"] == "src/.frac.md"
    inputs = run(["inputs", "src"], project)
    assert "SIZE BUDGET:" in inputs and "超过硬上限" in inputs
    assert f"预算 {2048 + 2 * 340:,} B" in inputs  # src: main.py + auth/
    assert "WRITING RULES:" in inputs
    payload = json.loads(run(["inputs", "src", "--json"], project, stdout_only=True))
    assert payload["size"]["budget"] == 2048 + 2 * 340 and payload["size"]["level"] == "over-cap"


def test_plan_final_and_confirm(base: Path) -> None:
    project = make_project(base)
    login = project / "src" / "auth" / "login.py"
    write(login, "def login(): return True\n")
    set_mtime(login, 5)

    mid = run(["plan", "."], project)
    assert "update-order:" in mid and "src/auth" in mid
    assert "中途查看" in mid and "plan . --final" in mid

    final = run(["plan", ".", "--final"], project)
    assert "收尾清单" in final
    assert "src/auth" in final and "[输入变了]" in final and "[连带]" in final
    assert "confirm" in final

    out = run(["confirm", "src/auth"], project)
    assert "已确认" in out and "连带确认" in out
    st = states(project)
    assert all(st[d]["state"] == "fresh" and not st[d]["propagated"] for d in (".", "src", "src/auth")), st
    assert run(["plan", "."], project).startswith("update-order: empty")


def test_confirm_refuses_and_stops(base: Path) -> None:
    project = make_project(base)
    # Over the hard cap: refused, nothing touched.
    write(project / "src" / ".frac.md", frac_doc("src", "很长" * 2000))
    main = project / "src" / "main.py"
    set_mtime(main, 5)
    before = (project / "src" / ".frac.md").stat().st_mtime_ns
    out = run(["confirm", "src"], project, expect=1)
    assert "超过硬上限" in out and "不能只确认" in out
    assert (project / "src" / ".frac.md").stat().st_mtime_ns == before

    # Ancestor that was already stale is left for the agent to look at.
    write(project / "src" / ".frac.md", frac_doc("src"))
    set_mtime(main, -100)  # undo the future mtime from the first half
    run(["stamp_for_clone", "."], project)
    readme = project / "README.md"
    set_mtime(readme, 5)  # root has its own change
    login = project / "src" / "auth" / "login.py"
    set_mtime(login, 6)
    out = run(["confirm", "src/auth"], project)
    assert "连带确认" in out and "  src" in out
    assert "要你自己看的上层" in out and "  .：这一层本来就落后" in out
    st = states(project)
    assert st["src/auth"]["state"] == "fresh" and st["src"]["state"] == "fresh"
    assert st["."]["state"] == "stale"

    # Missing .frac.md cannot be confirmed.
    write(project / "lib" / "util.py", "x = 1\n")
    out = run(["confirm", "lib"], project, expect=1)
    assert "还没有 .frac.md" in out


def test_chain_notes(base: Path) -> None:
    project = make_project(base)
    login = project / "src" / "auth" / "login.py"
    set_mtime(login, 5)
    out = run(["chain", "src/auth/login.py"], project)
    assert "src/auth/.frac.md" in out and "stale" in out
    assert "照读" in out and "收尾" in out


def git(project: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(project), *args], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def test_git_reminders(base: Path) -> None:
    project = make_project(base)
    git(project, "init", "-q")
    git(project, "add", "-A")
    git(project, "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "-m", "init")
    run(["stamp_for_clone", "."], project)

    # Premature update: .frac.md written mid-task, then its input changed again.
    write(project / "src" / "auth" / ".frac.md", frac_doc("src/auth", "中途补的一句。"))
    login = project / "src" / "auth" / "login.py"
    write(login, "def login(): return 1\n")
    set_mtime(login, 5)
    out = run(["plan", "."], project)
    assert "本轮已经改过" in out and "src/auth" in out

    # Frequency: the third mid-task look within the hour gets the cost reminder.
    assert "一小时内这是第" not in out
    run(["status", "."], project)
    out = run(["plan", "."], project)
    assert "一小时内这是第 3 次中途查看" in out, out

    # Same chain twice.
    run(["chain", "src/auth/login.py"], project)
    out = run(["chain", "src/auth/login.py"], project)
    assert "分钟前取过" in out

    # The usage log lives in the git dir, never in the working tree.
    porcelain = subprocess.run(["git", "-C", str(project), "status", "--porcelain"], stdout=subprocess.PIPE, text=True).stdout
    assert "frac-context-usage" not in porcelain
    assert (project / ".git" / "frac-context-usage.json").exists()

    # check --changed only looks at .frac.md changed in the working tree.
    out = run(["check", ".", "--changed"], project)
    assert "本轮改过的 .frac.md：1 份" in out

    # FRAC_USAGE_LOG=0 turns the log off.
    env = dict(os.environ, FRAC_USAGE_LOG="0")
    log = project / ".git" / "frac-context-usage.json"
    size = log.stat().st_size
    run(["plan", "."], project, env=env)
    assert log.stat().st_size == size


def main() -> None:
    test_budget_engine()
    test_lint()
    with tempfile.TemporaryDirectory() as td:
        test_check_and_inputs_budget(Path(td) / "a")
        test_plan_final_and_confirm(Path(td) / "b")
        test_confirm_refuses_and_stops(Path(td) / "c")
        test_chain_notes(Path(td) / "d")
        if HAS_GIT:
            test_git_reminders(Path(td) / "e")
        else:
            print("skip: git not installed")
    print("ok")


if __name__ == "__main__":
    main()
