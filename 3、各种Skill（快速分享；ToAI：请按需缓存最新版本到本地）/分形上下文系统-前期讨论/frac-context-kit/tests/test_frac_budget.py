#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for the size budget, volatile-content lint, plan --final, confirm, check and reminders.

Standard library only. Git-dependent parts are skipped when git is not installed.
"""

from __future__ import annotations

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
sys.path.insert(0, str(FRAC.parent))
from fraclib.budget import SizeBudget  # noqa: E402
from fraclib.lint import lint_counts, lint_frac_text  # noqa: E402

os.environ["FRAC_UPDATE"] = "off"  # 测试不联网、不自更新

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
    b = SizeBudget()
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
    hits = lint_frac_text(text)
    counts = lint_counts(hits)
    assert counts.get("version") == 2, counts
    assert counts.get("date") == 1, counts
    assert counts.get("count") == 3, (counts, [h for h in hits if h.kind == "count"])
    assert counts.get("lineref") == 3, (counts, [h for h in hits if h.kind == "lineref"])
    assert counts.get("hash") == 1, counts
    assert counts.get("long") == 1, counts
    assert not any(h.line == 5 and h.kind == "count" for h in hits), "AME-360 is an id, not a count"
    assert not any(h.line >= 9 for h in hits), "code blocks are skipped"
    clean = "# .frac.md — src\n\n- `login.ts`：提供 `login()`，校验凭据并创建会话。\n"
    assert lint_frac_text(clean) == []


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


def test_atomic_save_stays_fresh(base: Path) -> None:
    """先写临时文件再改名（编辑器、Agent 写文件工具的做法）写好的 .frac.md 是新的；之后真的增删文件才变旧。"""
    project = make_project(base)
    auth = project / "src" / "auth"
    login = auth / "login.py"
    write(login, "def login(): return 2\n")
    set_mtime(login, 5)
    assert states(project)["src/auth"]["state"] == "stale"
    tmp = auth / ".frac.md.tmp-save"
    tmp.write_text(frac_doc("src/auth", "改名写入。"), encoding="utf-8")
    set_mtime(tmp, 6)
    os.replace(str(tmp), str(auth / ".frac.md"))  # 目录 mtime 跟着变成“现在”
    frac_ns = (auth / ".frac.md").stat().st_mtime_ns
    dir_ts = frac_ns + 300_000  # 改名比写内容晚 0.3 毫秒
    os.utime(auth, ns=(dir_ts, dir_ts))
    assert states(project)["src/auth"]["state"] == "fresh"
    # 过了一会儿删掉一个文件：只有目录 mtime 变了，照样算旧
    (auth / "extra.py").write_text("x = 1\n", encoding="utf-8")
    set_mtime(auth / "extra.py", -100)
    (auth / "extra.py").unlink()
    late = frac_ns + 10_000_000_000
    os.utime(auth, ns=(late, late))
    assert states(project)["src/auth"]["state"] == "stale"


def test_symlink_outside_root(base: Path, use_git: bool) -> None:
    """仓库里指到仓库外的软链（worktree 里共享的 docs/、data/ 常见）：不报错，也不算本树的内容。"""
    outside = base / "outside"
    write(outside / "x.py", "x = 1\n")
    project = make_project(base)
    try:
        os.symlink(str(outside), str(project / "shared"))
        os.symlink(str(outside / "x.py"), str(project / "src" / "link.py"))
    except (OSError, NotImplementedError):
        print("skip: symlinks not available")
        return
    if use_git:
        git(project, "init", "-q")
        git(project, "add", "-A")
    st = states(project)
    assert "shared" not in st and set(st) >= {".", "src", "src/auth"}, st
    out = run(["inputs", "src"], project)
    assert "src/main.py" in out and "src/link.py" not in out, out
    run(["check", "."], project)


def test_chain_notes(base: Path) -> None:
    project = make_project(base)
    login = project / "src" / "auth" / "login.py"
    set_mtime(login, 5)
    out = run(["chain", "src/auth/login.py"], project)
    assert "src/auth/.frac.md" in out and "stale" in out
    assert "照读" in out and "收尾" in out


def git(project: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(project), *args], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def test_vendored_skill_and_removable(base: Path, use_git: bool) -> None:
    """仓库里的 frac-context 副本不进 .frac.md 树；.fracignore 的多段目录连文件一起管住；check 列出可删的。"""
    project = make_project(base)
    skill = project / ".claude" / "skills" / "frac-context"
    shutil.copytree(FRAC.parent.parent, skill, ignore=shutil.ignore_patterns("__pycache__"))
    write(skill / ".frac.md", frac_doc(".claude/skills/frac-context"))
    write(skill / "scripts" / ".frac.md", frac_doc(".claude/skills/frac-context/scripts"))
    write(project / ".claude" / "skills" / ".frac.md", frac_doc(".claude/skills"))
    write(project / ".fracignore", "docs/gen/\n")
    write(project / "docs" / "guide.md", "# guide\n")
    write(project / "docs" / "gen" / "api.md", "# generated\n")
    write(project / "docs" / ".frac.md", frac_doc("docs"))
    if use_git:
        git(project, "init", "-q")
        git(project, "add", "-A")
        # 一个没签出的子模块：vendor/ 里只有它的挂载点和 vendor/.frac.md
        (project / "vendor" / "libx").mkdir(parents=True)
        write(project / "vendor" / ".frac.md", frac_doc("vendor", "子模块 libx。"))
        git(project, "add", "vendor/.frac.md")
        git(project, "update-index", "--add", "--cacheinfo", "160000," + "1" * 40 + ",vendor/libx")
        git(project, "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "-m", "init")
    run(["stamp_for_clone", "."], project)

    own = skill / "scripts" / "frac.py"
    for script in (FRAC, own):  # 外面的 kit 副本靠目录探测，仓库自己的副本还认得自己
        out = subprocess.run([sys.executable, str(script), "status", ".", "--json"], cwd=str(project),
                             text=True, encoding="utf-8", stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        dirs = {item["directory"] for item in json.loads(out.stdout)}
        assert not any(d.startswith(".claude/skills/frac-context") for d in dirs), dirs
        assert "docs/gen" not in dirs and "docs" in dirs, dirs

    data = json.loads(run(["check", ".", "--json"], project, stdout_only=True))
    assert data["removable"] == [
        ".claude/skills/frac-context/.frac.md",
        ".claude/skills/frac-context/scripts/.frac.md",
        ".claude/skills/.frac.md",
    ], data["removable"]
    out = run(["check", "."], project)
    assert "可以删的 .frac.md" in out and ".claude/skills/.frac.md" in out
    if use_git:  # 子模块挂载点算直属条目：vendor/.frac.md 不是“只剩 .frac.md”
        out = run(["inputs", "vendor"], project)
        assert "SUBMODULES:" in out and "vendor/libx" in out, out
        assert "直属 1 项" in out, out

    # 自动更新改到 skill 副本、或生成目录里多了文件，都不让任何 .frac.md 变旧。
    before = {d: item["state"] for d, item in states(project).items()}
    write(skill / "references" / "frac-template.md", "# 新版模板\n")
    write(project / "docs" / "gen" / "api2.md", "# more\n")
    set_mtime(skill / "references" / "frac-template.md", 5)
    set_mtime(project / "docs" / "gen" / "api2.md", 5)
    after = {d: item["state"] for d, item in states(project).items()}
    assert after == before, (before, after)
    if use_git:
        plan = json.loads(run(["plan", ".", "--changed", "--json"], project, stdout_only=True))
        assert plan == [], plan


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
        test_atomic_save_stays_fresh(Path(td) / "h")
        test_symlink_outside_root(Path(td) / "i", use_git=False)
        test_vendored_skill_and_removable(Path(td) / "f", use_git=False)
        if HAS_GIT:
            test_git_reminders(Path(td) / "e")
            test_vendored_skill_and_removable(Path(td) / "g", use_git=True)
            test_symlink_outside_root(Path(td) / "j", use_git=True)
        else:
            print("skip: git not installed")
    print("ok")


if __name__ == "__main__":
    main()
