#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
frac.py — lightweight .frac.md recursive context helper.

This script intentionally avoids databases, embeddings, AST analysis, and RAG.
It only answers deterministic filesystem questions:

- Which directories should have .frac.md?
- Which .frac.md files are missing/stale/fresh?
- What is the bottom-up update order?
- What inputs may an Agent read to update one .frac.md?
- What .frac.md chain should be read before editing a target path?
- How to refresh .frac.md mtimes after clone/checkout?
- How large may one .frac.md be, and what in it goes stale fastest?
  (SizeBudget: per-directory size budget; lint_frac_text: volatile content)

Python: 3.9+
Dependencies: standard library only.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, asdict, replace
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

FRAC_NAME = ".frac.md"
BUNDLE_NAME = ".frac.全部汇总超大.md"
FRACIGNORE_NAME = ".fracignore"

# ---------- size budget & volatile content ----------
# 单份 .frac.md 的硬上限（字节，按 UTF-8 计；中文约 3,400 字）。
# 超过即报错：check 不通过，confirm 拒绝只确认。
HARD_CAP_BYTES = 10 * 1024
# 每个目录的预算 = 起步 + 直属条目数 × 每项，封顶 HARD_CAP_BYTES。
# 直属条目 = 直属有效文件 + 直属子目录（与 inputs 的口径一致）。
BUDGET_BASE_BYTES = 2 * 1024
BUDGET_PER_ENTRY_BYTES = 340
# 到预算的这个比例，就提示“接近”。
NEAR_BUDGET_RATIO = 0.85
# 单行超过这么多字节，算“超长条目”（中文约 200 字）。
LONG_LINE_BYTES = 600
# 频率提醒只看最近这么久之内的调用。
RECENT_SECONDS = 3600
# 调用记录放在 git 目录里（git rev-parse --git-path），不进工作区；设 FRAC_USAGE_LOG=0 关掉。
USAGE_LOG_NAME = "frac-context-usage.json"
USAGE_LOG_KEEP = 80

DEFAULT_IGNORE_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".idea",
    ".vscode",
    "node_modules",
    "dist",
    "build",
    "coverage",
    ".venv",
    "venv",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".next",
    ".nuxt",
    ".turbo",
    ".cache",
}

DEFAULT_IGNORE_FILE_NAMES = {
    ".DS_Store",
    BUNDLE_NAME,
}

DEFAULT_IGNORE_GLOBS = {
    "*.pyc",
    "*.pyo",
    "*.log",
    "*.tmp",
    "*.swp",
}

BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico",
    ".pdf", ".zip", ".tar", ".gz", ".7z", ".rar",
    ".mp3", ".mp4", ".mov", ".avi", ".wav",
    ".ttf", ".otf", ".woff", ".woff2",
    ".sqlite", ".db",
}


@dataclass(frozen=True)
class DirInputs:
    directory: str
    directory_mtime_ns: int
    direct_files: List[str]
    child_fracs: List[str]
    missing_child_fracs: List[str]


@dataclass(frozen=True)
class StatusItem:
    directory: str
    frac: str
    state: str
    reason: str
    frac_mtime_ns: Optional[int]
    max_input_mtime_ns: Optional[int]
    propagated: bool = False
    size: Optional[int] = None
    budget: Optional[int] = None
    size_level: str = ""


@dataclass(frozen=True)
class BundleResult:
    output: str
    source_count: int
    sources: List[str]
    order: str


@dataclass(frozen=True)
class SizeReport:
    directory: str
    frac: str
    size: Optional[int]
    entries: int
    budget: int
    cap: int
    level: str  # missing / ok / near / over-budget / over-cap


@dataclass(frozen=True)
class LintHit:
    kind: str
    line: int
    excerpt: str


@dataclass(frozen=True)
class PlanItem:
    directory: str
    state: str  # missing / stale / propagated
    size: Optional[int]
    entries: int
    budget: int
    level: str
    lint: Dict[str, int]
    changed_this_round: bool


@dataclass(frozen=True)
class ConfirmResult:
    confirmed: List[str]
    already_fresh: List[str]
    propagated: List[str]
    needs_review: List[Tuple[str, str]]


class FracError(RuntimeError):
    pass


# ---------- size budget engine ----------


class SizeBudget:
    """单份 .frac.md 的大小预算（计算引擎）。

    budget(n) = min(cap, base + per_entry * n)，n = 本目录直属条目数。
    只看本目录自己：不和仓库里最大的目录比，别处多一个文件，这里的预算不会跟着动。
    """

    def __init__(
        self,
        cap: int = HARD_CAP_BYTES,
        base: int = BUDGET_BASE_BYTES,
        per_entry: int = BUDGET_PER_ENTRY_BYTES,
        near_ratio: float = NEAR_BUDGET_RATIO,
    ) -> None:
        self.cap = cap
        self.base = base
        self.per_entry = per_entry
        self.near_ratio = near_ratio

    def budget(self, entries: int) -> int:
        return min(self.cap, self.base + self.per_entry * max(0, entries))

    def saturation_entries(self) -> int:
        """直属条目到这个数，预算就封顶。"""
        return -(-(self.cap - self.base) // self.per_entry)

    def level(self, size: Optional[int], budget: int) -> str:
        if size is None:
            return "missing"
        if size > self.cap:
            return "over-cap"
        if size > budget:
            return "over-budget"
        if size >= budget * self.near_ratio:
            return "near"
        return "ok"

    def describe(self) -> str:
        return (
            f"硬上限 {self.cap:,} B；预算 = {self.base // 1024} KiB + 直属条目 × {self.per_entry} B，"
            f"{self.saturation_entries()} 项起封顶"
        )


LEVEL_LABELS = {
    "over-cap": "超限",
    "over-budget": "超预算",
    "near": "接近",
    "ok": "",
    "missing": "",
}


# ---------- volatile content lint ----------

# 可能会过时、或者把 .frac.md 写成变更日志的内容。只提示，不拦截（正则会误报）。
LINT_KINDS: Dict[str, Tuple[str, str]] = {
    "version": ("版本号", "写现在是什么，不写哪一版加了什么；历史在 git log"),
    "date": ("日期", "不写日期和“最近更新”：新鲜度看 mtime，历史看 git"),
    "count": ("测试/检查条数", "不写有几条：每加一条就过时；写测试在哪、测什么"),
    "lineref": ("行号/行数", "不写行号和行数：一改就漂；写函数名或小节名"),
    "hash": ("提交号/评论号", "不写提交号、评论号：历史在 git log 和 issue 里"),
    "long": ("超长条目", "一条只写做什么、对外给什么、改时注意什么；细节留在代码和 README"),
}
LINT_ORDER = ["version", "date", "count", "lineref", "hash", "long"]

_NB = r"(?<![A-Za-z0-9_.])"
_NB_COUNT = r"(?<![A-Za-z0-9_.\-])"  # 跟在 - 后面的是编号（AME-360），不是条数
_TEST_WORDS = r"(?:单元测试|單元測試|测试|測試|用例|断言|斷言|检查|檢查|自测|自測|端到端|e2e|E2E)"
_MEASURE = r"(?:个|個|条|條|项|項|处|處|组|組|段)"
LINT_PATTERNS: List[Tuple[str, "re.Pattern[str]"]] = [
    ("version", re.compile(_NB + r"v?\d+\.\d+\.\d+(?![A-Za-z0-9_])(?!\.\d)")),
    ("date", re.compile(r"(?<!\d)20\d\d(?:-\d{1,2}-\d{1,2}|/\d{1,2}/\d{1,2}|年\d{1,2}月\d{1,2}日?)(?!\d)")),
    ("count", re.compile(_NB_COUNT + r"\d+\s*" + _MEASURE + r"?\s*" + _TEST_WORDS)),
    ("count", re.compile(_TEST_WORDS + r"[^\d\n，,。；;]{0,40}?" + _NB_COUNT + r"\d+\s*" + _MEASURE)),
    ("count", re.compile(r"(?i)" + _NB_COUNT + r"\d+\s+(?:unit\s+|e2e\s+)?(?:tests?|cases?|checks?|assertions?|specs?)\b")),
    ("lineref", re.compile(r"[\w-]+\.[A-Za-z]{1,6}:\d+(?:-\d+)?(?!\d)")),
    ("lineref", re.compile(r"第\s*\d+\s*行|" + _NB_COUNT + r"\d{2,}\s*行(?![为為动動程政业業李走情驶駛列])")),
    ("hash", re.compile(r"(?<![A-Za-z0-9_])(?=[0-9a-f]*[a-f])(?=[0-9a-f]*\d)[0-9a-f]{7,12}(?![A-Za-z0-9_])")),
]


def lint_frac_text(text: str) -> List[LintHit]:
    """找出 .frac.md 里会过时、或者像变更日志的内容。代码块里的不查。"""
    hits: List[LintHit] = []
    in_code = False
    for no, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        spans: Dict[str, List[Tuple[int, int]]] = {}
        for kind, pattern in LINT_PATTERNS:
            for m in pattern.finditer(line):
                spans.setdefault(kind, []).append((m.start(), m.end()))
        for kind in LINT_ORDER:
            merged: List[Tuple[int, int]] = []
            for start, end in sorted(spans.get(kind, [])):
                if merged and start < merged[-1][1]:
                    merged[-1] = (merged[-1][0], max(merged[-1][1], end))
                else:
                    merged.append((start, end))
            for start, end in merged:
                hits.append(LintHit(kind=kind, line=no, excerpt=_excerpt(line, start, end)))
        size = len(line.encode("utf-8"))
        if size > LONG_LINE_BYTES:
            head = line.strip()[:24]
            hits.append(LintHit(kind="long", line=no, excerpt=f"{head}…（{size:,} B）"))
    return hits


def _excerpt(line: str, start: int, end: int, pad: int = 12) -> str:
    lo = max(0, start - pad)
    hi = min(len(line), end + pad)
    text = line[lo:hi].strip()
    return ("…" if lo > 0 else "") + text + ("…" if hi < len(line) else "")


def lint_counts(hits: Sequence[LintHit]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for h in hits:
        out[h.kind] = out.get(h.kind, 0) + 1
    return {k: out[k] for k in LINT_ORDER if k in out}


def format_lint_counts(counts: Dict[str, int]) -> str:
    return "、".join(f"{LINT_KINDS[k][0]}×{n}" for k, n in counts.items())


def format_lint_detail(hits: Sequence[LintHit], max_lines: int = 3) -> List[str]:
    """每类一行：几处、在哪几行、一个例子、怎么改。"""
    out: List[str] = []
    by_kind: Dict[str, List[LintHit]] = {}
    for h in hits:
        by_kind.setdefault(h.kind, []).append(h)
    for kind in LINT_ORDER:
        group = by_kind.get(kind)
        if not group:
            continue
        label, fix = LINT_KINDS[kind]
        lines: List[int] = []
        for h in group:
            if h.line not in lines:
                lines.append(h.line)
        where = "、".join(str(n) for n in lines[:max_lines]) + ("…" if len(lines) > max_lines else "")
        out.append(f"{label} ×{len(group)}（第 {where} 行，如「{group[0].excerpt}」）→ {fix}")
    return out


def kib(n: Optional[int]) -> str:
    if n is None:
        return "-"
    return f"{n / 1024:.1f}K"


class FracProject:
    def __init__(self, root: Path, respect_gitignore: bool = True) -> None:
        self.root = root.resolve()
        if not self.root.exists():
            raise FracError(f"Root does not exist: {self.root}")
        if not self.root.is_dir():
            raise FracError(f"Root is not a directory: {self.root}")
        self.respect_gitignore = respect_gitignore
        self.fracignore_patterns = self._load_fracignore()
        self.budget = SizeBudget()
        self._eligible_files: Optional[Set[Path]] = None
        self._eligible_dirs: Optional[Set[Path]] = None
        # 性能缓存（语义不变）：is_ignored 的结果，以及「父目录 -> 直属文件 / 直属子目录」索引。
        # 没有它们时，每次 inputs/status 都会对整棵树重复 resolve()；几千个文件的树上一次 status 要跑数分钟。
        self._ignore_cache: Dict[str, bool] = {}
        self._files_by_parent: Optional[Dict[Path, List[Path]]] = None
        self._dirs_by_parent: Optional[Dict[Path, List[Path]]] = None

    # ---------- path helpers ----------

    def rel(self, path: Path) -> str:
        path = path.resolve()
        try:
            rel = path.relative_to(self.root)
        except ValueError:
            raise FracError(f"Path is outside project root: {path}")
        s = rel.as_posix()
        return "." if s == "" else s

    def abs_path(self, path_str: str) -> Path:
        p = Path(path_str)
        if not p.is_absolute():
            p = self.root / p
        p = p.resolve()
        try:
            p.relative_to(self.root)
        except ValueError:
            raise FracError(f"Path is outside project root: {p}")
        return p

    def frac_path(self, directory: Path) -> Path:
        return directory / FRAC_NAME

    def depth(self, directory: Path) -> int:
        rel = directory.resolve().relative_to(self.root)
        if rel.as_posix() == ".":
            return 0
        return len(rel.parts)

    def ancestors_to_root(self, path: Path) -> List[Path]:
        """Return root..path for a directory path."""
        path = path.resolve()
        try:
            rel = path.relative_to(self.root)
        except ValueError:
            raise FracError(f"Path is outside project root: {path}")
        dirs = [self.root]
        cur = self.root
        for part in rel.parts:
            cur = cur / part
            dirs.append(cur)
        return dirs

    def is_git_root(self) -> bool:
        return (self.root / ".git").exists()

    def git_path(self, name: str) -> Optional[Path]:
        """git 目录里的一个路径（worktree 各有各的）；不是 git 仓库时返回 None。"""
        if not self.is_git_root():
            return None
        try:
            result = subprocess.run(
                ["git", "-C", str(self.root), "rev-parse", "--git-path", name],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            return None
        out = result.stdout.decode("utf-8", errors="replace").strip()
        if not out:
            return None
        p = Path(out)
        if not p.is_absolute():
            p = self.root / p
        return p

    # ---------- ignore and scanning ----------

    def _load_fracignore(self) -> List[str]:
        p = self.root / FRACIGNORE_NAME
        if not p.exists():
            return []
        patterns: List[str] = []
        for raw in p.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            patterns.append(line)
        return patterns

    def _is_default_ignored(self, path: Path) -> bool:
        rel_parts = path.resolve().relative_to(self.root).parts
        for part in rel_parts:
            if part in DEFAULT_IGNORE_DIR_NAMES:
                return True
        if path.is_file() or (not path.exists() and path.suffix):
            if path.name in DEFAULT_IGNORE_FILE_NAMES:
                return True
            if any(fnmatch.fnmatch(path.name, pat) for pat in DEFAULT_IGNORE_GLOBS):
                return True
        return False

    def _matches_fracignore(self, path: Path) -> bool:
        if not self.fracignore_patterns:
            return False
        rel_path = path.resolve().relative_to(self.root)
        rel = rel_path.as_posix()
        parts = rel_path.parts
        name = path.name
        is_dir = path.is_dir()
        for pat in self.fracignore_patterns:
            dir_pat = pat.endswith("/")
            clean = pat[:-1] if dir_pat else pat
            if dir_pat:
                if is_dir and (name == clean or rel == clean or rel.startswith(clean + "/")):
                    return True
                if any(part == clean for part in parts):
                    return True
            else:
                if fnmatch.fnmatch(rel, clean) or fnmatch.fnmatch(name, clean):
                    return True
        return False

    def is_ignored(self, path: Path) -> bool:
        key = str(path)
        cached = self._ignore_cache.get(key)
        if cached is not None:
            return cached
        if path.resolve() == self.root:
            result = False
        else:
            result = self._is_default_ignored(path) or self._matches_fracignore(path)
        self._ignore_cache[key] = result
        return result

    def _git_eligible_files(self) -> Optional[Set[Path]]:
        if not self.respect_gitignore:
            return None
        if not self.is_git_root():
            return None
        try:
            result = subprocess.run(
                [
                    "git",
                    "-C",
                    str(self.root),
                    "ls-files",
                    "--cached",
                    "--others",
                    "--exclude-standard",
                    "-z",
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            return None
        files: Set[Path] = set()
        for raw in result.stdout.split(b"\0"):
            if not raw:
                continue
            rel = raw.decode("utf-8", errors="replace")
            p = (self.root / rel).resolve()
            if p.exists() and p.is_file() and not self.is_ignored(p):
                files.add(p)
        return files

    def _walk_eligible_files(self) -> Set[Path]:
        files: Set[Path] = set()
        for dirpath, dirnames, filenames in os.walk(self.root):
            d = Path(dirpath).resolve()
            # prune ignored dirs in-place
            kept_dirs = []
            for dn in dirnames:
                child = d / dn
                if not self.is_ignored(child):
                    kept_dirs.append(dn)
            dirnames[:] = kept_dirs

            if self.is_ignored(d):
                continue
            for fn in filenames:
                p = d / fn
                if not self.is_ignored(p):
                    files.add(p.resolve())
        return files

    def eligible_files(self) -> Set[Path]:
        if self._eligible_files is None:
            git_files = self._git_eligible_files()
            if git_files is not None:
                self._eligible_files = git_files
            else:
                self._eligible_files = self._walk_eligible_files()
        return self._eligible_files

    def eligible_dirs(self) -> Set[Path]:
        if self._eligible_dirs is not None:
            return self._eligible_dirs

        dirs: Set[Path] = {self.root}

        # Any directory containing eligible files, plus its ancestors, is eligible.
        for f in self.eligible_files():
            if f.name == FRAC_NAME:
                # Existing .frac.md should keep its directory visible, but is not an OwnFile.
                d = f.parent.resolve()
            else:
                d = f.parent.resolve()
            for a in self.ancestors_to_root(d):
                if not self.is_ignored(a):
                    dirs.add(a)

        # Also include directories that already have .frac.md even if they currently have no other files.
        for dirpath, dirnames, filenames in os.walk(self.root):
            d = Path(dirpath).resolve()
            dirnames[:] = [dn for dn in dirnames if not self.is_ignored(d / dn)]
            if self.is_ignored(d):
                continue
            if FRAC_NAME in filenames:
                for a in self.ancestors_to_root(d):
                    if not self.is_ignored(a):
                        dirs.add(a)

        self._eligible_dirs = dirs
        return dirs

    # ---------- input model ----------

    def _build_parent_index(self) -> None:
        """一次性建立「父目录 -> 直属文件 / 直属子目录」索引；结果与逐次扫描整棵树相同。"""
        files_by_parent: Dict[Path, List[Path]] = {}
        for f in self.eligible_files():
            files_by_parent.setdefault(f.parent.resolve(), []).append(f)
        dirs_by_parent: Dict[Path, List[Path]] = {}
        for d in self.eligible_dirs():
            if d == self.root:
                continue
            dirs_by_parent.setdefault(d.parent.resolve(), []).append(d)
        self._files_by_parent = files_by_parent
        self._dirs_by_parent = dirs_by_parent

    def direct_files(self, directory: Path) -> List[Path]:
        directory = directory.resolve()
        if self._files_by_parent is None:
            self._build_parent_index()
        assert self._files_by_parent is not None
        files = [f for f in self._files_by_parent.get(directory, []) if f.name != FRAC_NAME]
        return sorted(files, key=lambda p: p.name.lower())

    def direct_child_dirs(self, directory: Path) -> List[Path]:
        directory = directory.resolve()
        if self._dirs_by_parent is None:
            self._build_parent_index()
        assert self._dirs_by_parent is not None
        children = [d for d in self._dirs_by_parent.get(directory, []) if d != directory]
        return sorted(children, key=lambda p: p.name.lower())

    def inputs_for_dir(self, directory: Path) -> DirInputs:
        directory = directory.resolve()
        if directory not in self.eligible_dirs():
            raise FracError(f"Directory is not eligible for frac context: {self.rel(directory)}")
        child_fracs: List[Path] = []
        missing: List[Path] = []
        for child in self.direct_child_dirs(directory):
            fp = self.frac_path(child)
            if fp.exists():
                child_fracs.append(fp.resolve())
            else:
                missing.append(fp.resolve())

        return DirInputs(
            directory=self.rel(directory),
            directory_mtime_ns=directory.stat().st_mtime_ns,
            direct_files=[self.rel(p) for p in self.direct_files(directory)],
            child_fracs=[self.rel(p) for p in sorted(child_fracs, key=lambda p: self.rel(p))],
            missing_child_fracs=[self.rel(p) for p in sorted(missing, key=lambda p: self.rel(p))],
        )

    def max_input_mtime_ns(self, directory: Path) -> Tuple[Optional[int], str]:
        directory = directory.resolve()
        inputs = self.inputs_for_dir(directory)
        if inputs.missing_child_fracs:
            return None, "missing child frac"

        mtimes: List[int] = [inputs.directory_mtime_ns]
        for rel in inputs.direct_files + inputs.child_fracs:
            p = self.root / rel
            if p.exists():
                mtimes.append(p.stat().st_mtime_ns)
        return max(mtimes) if mtimes else directory.stat().st_mtime_ns, "ok"

    def actual_status_for_dir(self, directory: Path) -> StatusItem:
        directory = directory.resolve()
        frac = self.frac_path(directory)
        max_input, reason = self.max_input_mtime_ns(directory)
        frac_mtime: Optional[int] = frac.stat().st_mtime_ns if frac.exists() else None

        if not frac.exists():
            return StatusItem(
                directory=self.rel(directory),
                frac=self.rel(frac),
                state="missing",
                reason=".frac.md does not exist",
                frac_mtime_ns=None,
                max_input_mtime_ns=max_input,
            )
        if max_input is None:
            return StatusItem(
                directory=self.rel(directory),
                frac=self.rel(frac),
                state="stale",
                reason=reason,
                frac_mtime_ns=frac_mtime,
                max_input_mtime_ns=None,
            )
        if max_input > frac_mtime:
            return StatusItem(
                directory=self.rel(directory),
                frac=self.rel(frac),
                state="stale",
                reason="input newer than .frac.md",
                frac_mtime_ns=frac_mtime,
                max_input_mtime_ns=max_input,
            )
        return StatusItem(
            directory=self.rel(directory),
            frac=self.rel(frac),
            state="fresh",
            reason=".frac.md is not older than inputs",
            frac_mtime_ns=frac_mtime,
            max_input_mtime_ns=max_input,
        )

    def status(self, include_fresh: bool = True) -> List[StatusItem]:
        dirs = sorted(self.eligible_dirs(), key=lambda p: (self.depth(p), self.rel(p)))
        actual = {d: self.actual_status_for_dir(d) for d in dirs}
        stale_dirs = {d for d, item in actual.items() if item.state in {"missing", "stale"}}
        propagated = self.propagated_update_dirs(stale_dirs)

        items: List[StatusItem] = []
        for d in dirs:
            item = actual[d]
            is_propagated = d in propagated and d not in stale_dirs
            if item.state == "fresh" and is_propagated:
                item = StatusItem(
                    directory=item.directory,
                    frac=item.frac,
                    state="fresh",
                    reason="fresh now, but should be updated after stale descendant is refreshed",
                    frac_mtime_ns=item.frac_mtime_ns,
                    max_input_mtime_ns=item.max_input_mtime_ns,
                    propagated=True,
                )
            if include_fresh or item.state != "fresh" or item.propagated:
                size = self.size_report(d)
                items.append(replace(item, size=size.size, budget=size.budget, size_level=size.level))
        return items

    def propagated_update_dirs(self, stale_dirs: Set[Path]) -> Set[Path]:
        eligible = self.eligible_dirs()
        out: Set[Path] = set()
        for d in stale_dirs:
            for a in self.ancestors_to_root(d):
                if a in eligible:
                    out.add(a)
        return out

    def update_plan(self, changed_only: bool = False) -> List[Path]:
        eligible = self.eligible_dirs()
        if changed_only:
            changed_dirs = self.changed_ancestor_dirs()
            if not changed_dirs:
                return []
            plan_dirs = {d for d in changed_dirs if d in eligible}
        else:
            actual_stale = {
                d for d in eligible
                if self.actual_status_for_dir(d).state in {"missing", "stale"}
            }
            plan_dirs = self.propagated_update_dirs(actual_stale)
        return sorted(plan_dirs, key=lambda p: (-self.depth(p), self.rel(p)))

    # ---------- size budget & lint ----------

    def entries_count(self, directory: Path) -> int:
        return len(self.direct_files(directory)) + len(self.direct_child_dirs(directory))

    def size_report(self, directory: Path) -> SizeReport:
        directory = directory.resolve()
        frac = self.frac_path(directory)
        size = frac.stat().st_size if frac.exists() else None
        entries = self.entries_count(directory)
        budget = self.budget.budget(entries)
        return SizeReport(
            directory=self.rel(directory),
            frac=self.rel(frac),
            size=size,
            entries=entries,
            budget=budget,
            cap=self.budget.cap,
            level=self.budget.level(size, budget),
        )

    def lint(self, directory: Path) -> List[LintHit]:
        frac = self.frac_path(directory.resolve())
        if not frac.exists():
            return []
        return lint_frac_text(frac.read_text(encoding="utf-8", errors="replace"))

    def final_plan(self, changed_only: bool = False) -> List[PlanItem]:
        changed = {d.resolve() for d in self.changed_frac_dirs()}
        items: List[PlanItem] = []
        for d in self.update_plan(changed_only=changed_only):
            st = self.actual_status_for_dir(d)
            state = st.state if st.state in {"missing", "stale"} else "propagated"
            size = self.size_report(d)
            items.append(PlanItem(
                directory=self.rel(d),
                state=state,
                size=size.size,
                entries=size.entries,
                budget=size.budget,
                level=size.level,
                lint=lint_counts(self.lint(d)),
                changed_this_round=d in changed,
            ))
        return items

    def check(self, changed_only: bool = False) -> Dict[str, object]:
        eligible = self.eligible_dirs()
        scope_note = ""
        if changed_only and not self.is_git_root():
            changed_only = False
            scope_note = "不是 git 仓库根目录，--changed 用不了，改查全部。"
        if changed_only:
            dirs = [d for d in self.changed_frac_dirs() if d in eligible]
        else:
            dirs = [d for d in eligible if self.frac_path(d).exists()]
        dirs = sorted(set(dirs), key=lambda p: (-self.depth(p), self.rel(p)))
        reports = []
        for d in dirs:
            size = self.size_report(d)
            hits = self.lint(d)
            reports.append({"size": size, "lint": lint_counts(hits), "lint_detail": format_lint_detail(hits)})
        return {
            "scope": "changed" if changed_only else "all",
            "scope_note": scope_note,
            "checked": len(reports),
            "over_cap": [r for r in reports if r["size"].level == "over-cap"],
            "over_budget": [r for r in reports if r["size"].level == "over-budget"],
            "near": [r for r in reports if r["size"].level == "near"],
            "volatile": [r for r in reports if r["lint"]],
            "pending": [self.rel(d) for d in self.update_plan()],
        }

    def changed_frac_dirs(self) -> List[Path]:
        """本轮（git 工作区）内容改过的 .frac.md 所在目录。"""
        out: List[Path] = []
        for p in self.changed_paths_from_git():
            if p.name == FRAC_NAME and p.exists():
                out.append(p.parent.resolve())
        return out

    def premature_updates(self) -> List[str]:
        """本轮已经改过内容、之后输入又变了的 .frac.md：中途写的被推翻了。"""
        eligible = self.eligible_dirs()
        out: List[str] = []
        for d in sorted(set(self.changed_frac_dirs()), key=lambda p: (-self.depth(p), self.rel(p))):
            if d in eligible and self.actual_status_for_dir(d).state == "stale":
                out.append(self.rel(d))
        return out

    # ---------- confirm ----------

    def confirm_problems(self, dirs: Sequence[Path]) -> List[str]:
        eligible = self.eligible_dirs()
        problems: List[str] = []
        for d in dirs:
            d = d.resolve()
            rel = self.rel(d)
            if not d.is_dir() or d not in eligible:
                problems.append(f"{rel}：不是需要 .frac.md 的目录")
                continue
            frac = self.frac_path(d)
            if not frac.exists():
                problems.append(f"{rel}：还没有 .frac.md，没有可确认的；先写一份")
                continue
            size = self.size_report(d)
            if size.level == "over-cap":
                problems.append(
                    f"{rel}：{size.size:,} B，超过硬上限 {size.cap:,} B，不能只确认。"
                    f"这次要把它压到预算 {size.budget:,} B 以内：以现有内容为底稿删版本史、数字、原话、参数细目，"
                    f"留职责、分工、对外接口、约束；不必重读全部直属文件"
                )
                continue
            if self.inputs_for_dir(d).missing_child_fracs:
                problems.append(f"{rel}：有子目录还没有 .frac.md，先处理子目录")
        return problems

    def _stamp(self, directory: Path) -> None:
        frac = self.frac_path(directory)
        max_input, _ = self.max_input_mtime_ns(directory)
        ts = max(time.time_ns(), (max_input or 0) + 1, frac.stat().st_mtime_ns)
        os.utime(frac, ns=(ts, ts))

    def confirm(self, dirs: Sequence[Path]) -> ConfirmResult:
        """确认这些目录的 .frac.md 内容不用改，只把时间戳更新到不早于输入。

        上面各层若在这之前是新的（只会因为下层时间戳变了而变旧），一起确认；
        原本就落后的上层要 Agent 自己看，不替它确认。
        """
        eligible = self.eligible_dirs()
        targets = sorted({d.resolve() for d in dirs}, key=lambda p: (-self.depth(p), self.rel(p)))
        target_set = set(targets)
        ancestors: Set[Path] = set()
        for d in targets:
            for a in self.ancestors_to_root(d)[:-1]:
                if a in eligible and a not in target_set:
                    ancestors.add(a)
        before = {a: self.actual_status_for_dir(a).state for a in ancestors}

        confirmed: List[str] = []
        already: List[str] = []
        for d in targets:
            if self.actual_status_for_dir(d).state == "fresh":
                already.append(self.rel(d))
                continue
            self._stamp(d)
            confirmed.append(self.rel(d))

        propagated: List[str] = []
        needs_review: List[Tuple[str, str]] = []
        for a in sorted(ancestors, key=lambda p: (-self.depth(p), self.rel(p))):
            now = self.actual_status_for_dir(a).state
            if now == "fresh":
                continue
            if before[a] == "missing":
                needs_review.append((self.rel(a), "还没有 .frac.md"))
                continue
            if before[a] != "fresh":
                needs_review.append((self.rel(a), "这一层本来就落后（有别的输入变了），要你自己看"))
                continue
            size = self.size_report(a)
            if size.level == "over-cap":
                needs_review.append((self.rel(a), f"{kib(size.size)}，超过硬上限：不能只确认，要压到预算 {kib(size.budget)} 以内"))
                continue
            self._stamp(a)
            propagated.append(self.rel(a))
        return ConfirmResult(confirmed=confirmed, already_fresh=already, propagated=propagated, needs_review=needs_review)

    # ---------- git changed support ----------

    def changed_paths_from_git(self) -> List[Path]:
        if not self.is_git_root():
            return []
        try:
            result = subprocess.run(
                ["git", "-C", str(self.root), "status", "--porcelain=v1", "-z"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            return []

        chunks = [c for c in result.stdout.split(b"\0") if c]
        paths: List[Path] = []
        i = 0
        while i < len(chunks):
            entry = chunks[i].decode("utf-8", errors="replace")
            if len(entry) < 4:
                i += 1
                continue
            status = entry[:2]
            path_text = entry[3:]
            # Rename/copy porcelain -z has an additional source path chunk after the destination.
            if "R" in status or "C" in status:
                dest = path_text
                paths.append((self.root / dest).resolve())
                i += 2
            else:
                paths.append((self.root / path_text).resolve())
                i += 1
        return paths

    def changed_ancestor_dirs(self) -> Set[Path]:
        out: Set[Path] = set()
        for p in self.changed_paths_from_git():
            try:
                p.relative_to(self.root)
            except ValueError:
                continue
            if self.is_ignored(p):
                continue
            d = p if p.exists() and p.is_dir() else p.parent
            if not d.exists():
                # For deleted files, parent may still exist. If not, walk upward.
                while d != self.root and not d.exists():
                    d = d.parent
            for a in self.ancestors_to_root(d):
                out.add(a)
        return out

    # ---------- commands ----------

    def init_missing(self) -> List[Path]:
        created: List[Path] = []
        for d in sorted(self.eligible_dirs(), key=lambda p: (-self.depth(p), self.rel(p))):
            frac = self.frac_path(d)
            if not frac.exists():
                frac.write_text(self.placeholder_content(d), encoding="utf-8")
                # Make placeholder definitely stale.
                try:
                    os.utime(frac, ns=(0, 0))
                except Exception:
                    pass
                created.append(frac)
        return created

    def placeholder_content(self, directory: Path) -> str:
        rel = self.rel(directory)
        return f"""# .frac.md — {rel}

> 状态：NEEDS-UPDATE
> 生成规则：本文件只总结当前目录的直属文件，以及直属子目录的 `.frac.md`。
> 输入范围：direct-files + child-fracs only

## 1. 本目录是什么

TODO

## 2. 直属文件

TODO

## 3. 子目录导航

TODO

## 4. 本层约束 / 约定 / 禁忌

TODO

## 5. 什么时候需要下钻

TODO
"""

    def chain_for_target(self, target: Path) -> List[Path]:
        target = target.resolve()
        if not target.exists():
            # Treat non-existing target as a file path to be created.
            d = target.parent
        else:
            d = target if target.is_dir() else target.parent
        chain_dirs = [a for a in self.ancestors_to_root(d) if a in self.eligible_dirs()]
        return [self.frac_path(d) for d in chain_dirs]

    def stamp_for_clone(self, dirs: Optional[Iterable[Path]] = None) -> List[Path]:
        if dirs is None:
            dirs = self.eligible_dirs()
        ordered = sorted(set(dirs), key=lambda p: (-self.depth(p), self.rel(p)))
        touched: List[Path] = []
        base = time.time_ns()
        for idx, d in enumerate(ordered):
            frac = self.frac_path(d)
            if not frac.exists():
                continue
            ts = base + idx + 1
            os.utime(frac, ns=(ts, ts))
            touched.append(frac)
        return touched

    def dirs_in_tree_order(self) -> List[Path]:
        """Return eligible directories in deterministic parent-first tree order."""
        eligible = self.eligible_dirs()
        ordered: List[Path] = []

        def visit(directory: Path) -> None:
            ordered.append(directory)
            children = [d for d in eligible if d.parent.resolve() == directory]
            children.sort(key=lambda p: (p.name.casefold(), p.name))
            for child in children:
                visit(child)

        visit(self.root)
        return ordered

    def bundle_sources(self) -> List[Path]:
        return [
            self.frac_path(directory)
            for directory in self.dirs_in_tree_order()
            if self.frac_path(directory).is_file()
        ]

    def render_bundle(self, sources: Sequence[Path]) -> str:
        lines = [
            "# `.frac.md` 全部汇总",
            "",
            "> 本文件只会在显式运行 `frac bundle` 时生成或更新。",
            "> 合并顺序：目录树前序（父目录在前，同级目录按名称排序）。",
            f"> 来源文件数：{len(sources)}。",
            "",
        ]
        for index, source in enumerate(sources, 1):
            rel = self.rel(source)
            content = source.read_text(encoding="utf-8", errors="replace").rstrip("\n")
            lines.extend([
                "---",
                "",
                f"## {index}. `{rel}`",
                "",
                content,
                "",
            ])
        return "\n".join(lines).rstrip() + "\n"

    def write_bundle(self) -> BundleResult:
        sources = self.bundle_sources()
        if not sources:
            raise FracError(f"No {FRAC_NAME} files found under project root")

        output = self.root / BUNDLE_NAME
        content = self.render_bundle(sources)
        with output.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)

        return BundleResult(
            output=self.rel(output),
            source_count=len(sources),
            sources=[self.rel(source) for source in sources],
            order="parent-first tree order; siblings sorted by name",
        )


# ---------- usage log (frequency reminders) ----------


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


# ---------- notes (reminders printed after the main output) ----------


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
        if project.size_report(d).level == "over-cap":
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


# ---------- formatting ----------


def to_jsonable(obj: object) -> object:
    def default(o: object) -> object:
        if hasattr(o, "__dataclass_fields__"):
            return asdict(o)
        if isinstance(o, Path):
            return str(o)
        raise TypeError(type(o).__name__)
    return json.loads(json.dumps(obj, ensure_ascii=False, default=default))


def print_json(obj: object) -> None:
    print(json.dumps(to_jsonable(obj), ensure_ascii=False, indent=2))


def size_cell(size: Optional[int], budget: Optional[int]) -> str:
    if size is None:
        return f"-/{kib(budget)}"
    return f"{kib(size)}/{kib(budget)}"


def format_status(project: FracProject, items: Sequence[StatusItem]) -> str:
    if not items:
        return "No frac directories found."
    cells = [size_cell(i.size, i.budget) for i in items]
    flags = [LEVEL_LABELS.get(i.size_level, "") for i in items]
    widths = {
        "state": max(len("state"), *(len(i.state + ("*" if i.propagated else "")) for i in items)),
        "size": max(len("size/budget"), *(len(c) for c in cells)),
        "flag": max(4, *(len(f) * 2 for f in flags)),
        "dir": max(len("directory"), *(len(i.directory) for i in items)),
    }
    lines = []
    lines.append(
        f"{'state'.ljust(widths['state'])}  {'size/budget'.ljust(widths['size'])}  {'flag'.ljust(widths['flag'])}  "
        f"{'directory'.ljust(widths['dir'])}  reason"
    )
    lines.append(f"{'-' * widths['state']}  {'-' * widths['size']}  {'-' * widths['flag']}  {'-' * widths['dir']}  ------")
    for i, cell, flag in zip(items, cells, flags):
        state = i.state + ("*" if i.propagated else "")
        flag_text = flag + " " * (widths["flag"] - len(flag) * 2)
        lines.append(
            f"{state.ljust(widths['state'])}  {cell.ljust(widths['size'])}  {flag_text}  "
            f"{i.directory.ljust(widths['dir'])}  {i.reason}"
        )
    lines.append("")
    lines.append("* = 当前 fresh，但由于后代将更新，按 bottom-up 计划也应连带更新。")
    over_cap = sum(1 for i in items if i.size_level == "over-cap")
    over_budget = sum(1 for i in items if i.size_level == "over-budget")
    near = sum(1 for i in items if i.size_level == "near")
    if over_cap or over_budget or near:
        lines.append(
            f"大小：超过硬上限 {over_cap} 份、超过预算 {over_budget} 份、接近预算 {near} 份"
            f"（{project.budget.describe()}）。详情：frac.py check ."
        )
    return "\n".join(lines)


def format_plan(project: FracProject, dirs: Sequence[Path]) -> str:
    if not dirs:
        return "update-order: empty"
    lines = ["update-order:"]
    for idx, d in enumerate(dirs, 1):
        lines.append(f"  {idx}. {project.rel(d)}")
    return "\n".join(lines)


STATE_TAGS = {"missing": "新写", "stale": "输入变了", "propagated": "连带"}


def format_final_plan(project: FracProject, items: Sequence[PlanItem]) -> str:
    if not items:
        return "收尾清单：空。.frac.md 都不旧于输入；最后跑一次 frac.py check . --changed 就收尾完了。"
    lines = ["收尾清单（自底向上，按顺序处理；每份只写一次）："]
    width = max(len(i.directory) for i in items)
    tag_cols = max(len(t) * 2 for t in STATE_TAGS.values())
    for idx, it in enumerate(items, 1):
        flag = LEVEL_LABELS.get(it.level, "")
        tag = STATE_TAGS[it.state]
        lines.append(
            f"  {idx:>2}. {it.directory.ljust(width)}  [{tag}]{' ' * (tag_cols - len(tag) * 2)}  "
            f"{size_cell(it.size, it.budget)}{('  ' + flag) if flag else ''}"
        )
        if it.lint:
            lines.append(f"      易变内容：{format_lint_counts(it.lint)}（frac.py inputs {it.directory} 看在哪几行）")
    over = [it for it in items if it.level == "over-cap"]
    lines.append("")
    lines.append("做法：")
    lines.append("  - 每一项先 frac.py inputs <dir>：看允许读的输入、预算和现有内容里的易变项。")
    lines.append("  - 这一层该写的变了（职责、文件分工、对外接口、约束、下钻建议）：以现有内容为底稿整份重写，不超预算，不在旧文后面追加。")
    lines.append("  - 没变（函数内部、修 bug、调数字、改测试）：frac.py confirm <dir>；上面没有别的改动的各层会一起确认。")
    if over:
        lines.append(f"  - 标超限的 {len(over)} 份不能只 confirm：轮到它时压到预算内（删版本史、数字、原话、参数细目）。")
    lines.append("  - 全部处理完：frac.py check . --changed；没有“超过硬上限”才算收尾完成。")
    return "\n".join(lines)


def format_inputs(inputs: DirInputs) -> str:
    lines: List[str] = []
    lines.append(f"DIRECTORY: {inputs.directory}")
    lines.append("")
    lines.append("MTIME SOURCE:")
    lines.append(f"  {inputs.directory}/")
    lines.append("  # directory entry mtime; do not read as content")
    lines.append("")
    lines.append("DIRECT FILES:")
    if inputs.direct_files:
        for f in inputs.direct_files:
            lines.append(f"  {f}")
    else:
        lines.append("  <none>")
    lines.append("")
    lines.append("CHILD FRACS:")
    if inputs.child_fracs:
        for f in inputs.child_fracs:
            lines.append(f"  {f}")
    else:
        lines.append("  <none>")
    if inputs.missing_child_fracs:
        lines.append("")
        lines.append("MISSING CHILD FRACS:")
        for f in inputs.missing_child_fracs:
            lines.append(f"  {f}")
        lines.append("  # update/create these children before updating this directory")
    return "\n".join(lines)


def format_size_block(project: FracProject, size: SizeReport, hits: Sequence[LintHit]) -> str:
    b = project.budget
    lines = ["SIZE BUDGET:"]
    rule = f"直属 {size.entries} 项；{b.base // 1024} KiB 起，每项 +{b.per_entry} B，封顶 {b.cap // 1024} KiB"
    if size.size is None:
        lines.append(f"  还没有 .frac.md。写完不超过 {size.budget:,} B（{rule}）")
    else:
        verdict = {
            "over-cap": f"超过硬上限 {size.cap:,} B——这次要压到预算内，不能只 confirm",
            "over-budget": "超过预算——这次顺手压到预算内",
            "near": "接近预算——要加内容先删旧的",
            "ok": "没问题",
        }[size.level]
        lines.append(f"  现在 {size.size:,} B，预算 {size.budget:,} B（{rule}）：{verdict}")
    detail = format_lint_detail(hits)
    if detail:
        lines.append("  易变内容：")
        lines.extend(f"    {d}" for d in detail)
    lines.append("")
    lines.append("WRITING RULES:")
    lines.append("  - 该写的变了：以现有 .frac.md 为底稿整份重写成“现在是什么”，只读这次变了的输入；不在旧文后面追加。")
    lines.append(f"  - 没变（函数内部、修 bug、调数字、改测试）：不改内容，frac.py confirm {size.directory}")
    lines.append("  - 不写版本史、日期、测试/检查条数、行号、提交号、用户原话、参数和默认值的细目。")
    lines.append("  - 直属文件多就按功能分组，一组一行。")
    return "\n".join(lines)


def format_chain(project: FracProject, chain: Sequence[Path]) -> str:
    if not chain:
        return "frac-chain: empty"
    lines = ["frac-chain:"]
    width = max(len(project.rel(f)) for f in chain)
    for f in chain:
        rel = project.rel(f)
        if not f.exists():
            lines.append(f"  {rel}  # missing")
            continue
        tags = [kib(f.stat().st_size)]
        flag = LEVEL_LABELS.get(project.size_report(f.parent).level, "")
        if flag:
            tags.append(flag)
        if project.actual_status_for_dir(f.parent).state != "fresh":
            tags.append("stale")
        lines.append(f"  {rel.ljust(width)}  {' '.join(tags)}")
    return "\n".join(lines)


def format_check(project: FracProject, report: Dict[str, object]) -> str:
    lines: List[str] = []
    if report["scope_note"]:
        lines.append(str(report["scope_note"]))
    scope = "本轮改过的" if report["scope"] == "changed" else "全部"
    lines.append(f"检查{scope} .frac.md：{report['checked']} 份（{project.budget.describe()}）")

    def row(r: Dict[str, object]) -> str:
        s: SizeReport = r["size"]  # type: ignore[assignment]
        return f"  {s.frac}  {s.size:,} B / 预算 {s.budget:,} B（直属 {s.entries} 项）"

    groups = [
        ("over_cap", "超过硬上限（必须压到预算内）："),
        ("over_budget", "超过预算（建议压缩）："),
        ("near", "接近预算（要加内容先删旧的）："),
    ]
    for key, title in groups:
        rows = sorted(report[key], key=lambda r: -(r["size"].size or 0))  # type: ignore[index]
        if rows:
            lines.append("")
            lines.append(title)
            lines.extend(row(r) for r in rows)
    volatile = sorted(report["volatile"], key=lambda r: -sum(r["lint"].values()))  # type: ignore[union-attr]
    if volatile:
        detailed = len(volatile) <= 5
        lines.append("")
        lines.append("易变内容（建议删；正则判断，可能误报）：")
        for r in volatile[:15]:
            lines.append(f"  {r['size'].frac}：{format_lint_counts(r['lint'])}")
            if detailed:
                lines.extend(f"    {d}" for d in r["lint_detail"])
        if len(volatile) > 15:
            lines.append(f"  ……另有 {len(volatile) - 15} 份")
        if not detailed:
            lines.append("  在哪几行、怎么改：frac.py inputs <dir>")
    pending = report["pending"]
    if pending:
        lines.append("")
        lines.append(f"还有 {len(pending)} 个目录的 .frac.md 旧于输入：frac.py plan . --final 看收尾清单。")
    lines.append("")
    if report["over_cap"]:
        lines.append(f"结果：不通过（{len(report['over_cap'])} 份超过硬上限）。")  # type: ignore[arg-type]
    else:
        lines.append("结果：通过。")
    return "\n".join(lines)


def format_confirm(result: ConfirmResult) -> str:
    lines: List[str] = []
    if result.confirmed:
        lines.append("已确认（内容不变，只更新时间戳）：")
        lines.extend(f"  {d}" for d in result.confirmed)
    if result.already_fresh:
        lines.append("本来就不旧于输入，没动：")
        lines.extend(f"  {d}" for d in result.already_fresh)
    if result.propagated:
        lines.append("连带确认（上一层原本是新的，只因下层时间戳变了才变旧）：")
        lines.extend(f"  {d}" for d in result.propagated)
    if result.needs_review:
        lines.append("要你自己看的上层（照 plan . --final 的顺序处理）：")
        lines.extend(f"  {d}：{why}" for d, why in result.needs_review)
    if not lines:
        lines.append("没有要确认的。")
    return "\n".join(lines)


def emit(as_json: bool, payload: object, text: str, notes: Sequence[str]) -> None:
    if as_json:
        print_json(payload)
        if notes:
            print("\n".join(notes), file=sys.stderr)
        return
    print(text)
    if notes:
        print("")
        print("\n".join(notes))


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="frac",
        description="Lightweight .frac.md recursive context helper.",
    )
    p.add_argument(
        "--no-gitignore",
        action="store_true",
        help="Do not use git ls-files --exclude-standard even inside Git repositories.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    def add_root(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("root", nargs="?", default=".", help="Project root. Default: current directory.")
        sp.add_argument("--json", action="store_true", help="Output JSON.")

    sp = sub.add_parser("status", help="Show missing/stale/fresh .frac.md files with size vs budget.")
    add_root(sp)
    sp.add_argument("--no-fresh", action="store_true", help="Hide fresh rows unless propagated.")

    sp = sub.add_parser("plan", help="Show bottom-up update order (use --final at wrap-up).")
    add_root(sp)
    sp.add_argument("--changed", action="store_true", help="Use Git changed paths to form an affected chain plan.")
    sp.add_argument("--final", action="store_true", help="Wrap-up checklist: size, budget and volatile content per directory.")

    sp = sub.add_parser("inputs", help="Show allowed inputs and the size budget for one directory .frac.md.")
    sp.add_argument("directory", help="Directory whose .frac.md will be updated.")
    sp.add_argument("--root", default=".", help="Project root. Default: current directory.")
    sp.add_argument("--json", action="store_true", help="Output JSON.")

    sp = sub.add_parser("chain", help="Show .frac.md chain for a target file or directory.")
    sp.add_argument("target", help="Target file or directory.")
    sp.add_argument("--root", default=".", help="Project root. Default: current directory.")
    sp.add_argument("--json", action="store_true", help="Output JSON.")

    sp = sub.add_parser("confirm", help="Mark .frac.md as still accurate (mtime only); ancestors that were fresh follow.")
    sp.add_argument("directories", nargs="+", help="Directories whose .frac.md content needs no change.")
    sp.add_argument("--root", default=".", help="Project root. Default: current directory.")
    sp.add_argument("--json", action="store_true", help="Output JSON.")

    sp = sub.add_parser("check", help="Gate: fail when a .frac.md exceeds the hard cap; warn on budget and volatile content.")
    add_root(sp)
    sp.add_argument("--changed", action="store_true", help="Only check .frac.md files changed in the Git working tree.")

    sp = sub.add_parser("init", help="Create missing placeholder .frac.md files and mark them stale.")
    add_root(sp)

    sp = sub.add_parser("stamp_for_clone", help="Touch existing .frac.md files bottom-up to restore mtime invariant.")
    add_root(sp)

    sp = sub.add_parser("bundle", help=f"Explicitly merge all .frac.md files into {BUNDLE_NAME}.")
    add_root(sp)

    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass
    args = build_arg_parser().parse_args(argv)
    try:
        respect_gitignore = not getattr(args, "no_gitignore", False)
        project = FracProject(Path(args.root), respect_gitignore=respect_gitignore)

        if args.command == "status":
            items = project.status(include_fresh=not args.no_fresh)
            recent = UsageLog(project).record("status")
            emit(args.json, items, format_status(project, items), mid_task_notes(recent, project.premature_updates()))
            return 0

        if args.command == "plan":
            recent = UsageLog(project).record("plan", final=args.final)
            premature = project.premature_updates()
            if args.final:
                items = project.final_plan(changed_only=args.changed)
                emit(args.json, items, format_final_plan(project, items), final_notes(recent, premature))
            else:
                dirs = project.update_plan(changed_only=args.changed)
                emit(args.json, [project.rel(d) for d in dirs], format_plan(project, dirs), mid_task_notes(recent, premature))
            return 0

        if args.command == "inputs":
            directory = project.abs_path(args.directory)
            if not directory.exists() or not directory.is_dir():
                raise FracError(f"Not a directory: {directory}")
            inputs = project.inputs_for_dir(directory)
            size = project.size_report(directory)
            hits = project.lint(directory)
            recent = UsageLog(project).record("inputs", inputs.directory)
            payload = dict(to_jsonable(inputs))  # type: ignore[arg-type]
            payload["size"] = to_jsonable(size)
            payload["lint"] = lint_counts(hits)
            text = format_inputs(inputs) + "\n\n" + format_size_block(project, size, hits)
            emit(args.json, payload, text, inputs_notes(recent, inputs.directory))
            return 0

        if args.command == "chain":
            target = project.abs_path(args.target)
            chain = project.chain_for_target(target)
            key = project.rel(chain[-1].parent) if chain else ""
            recent = UsageLog(project).record("chain", key)
            emit(args.json, [project.rel(p) for p in chain], format_chain(project, chain),
                 chain_notes(project, chain, recent, key))
            return 0

        if args.command == "confirm":
            dirs = [project.abs_path(d) for d in args.directories]
            problems = project.confirm_problems(dirs)
            if problems:
                print("frac: confirm 拒绝（什么都没改）：", file=sys.stderr)
                for line in problems:
                    print(f"  {line}", file=sys.stderr)
                return 1
            result = project.confirm(dirs)
            emit(args.json, result, format_confirm(result), [])
            return 0

        if args.command == "check":
            report = project.check(changed_only=args.changed)
            payload = {
                "scope": report["scope"],
                "checked": report["checked"],
                "over_cap": [r["size"] for r in report["over_cap"]],  # type: ignore[union-attr]
                "over_budget": [r["size"] for r in report["over_budget"]],  # type: ignore[union-attr]
                "near": [r["size"] for r in report["near"]],  # type: ignore[union-attr]
                "volatile": {r["size"].frac: r["lint"] for r in report["volatile"]},  # type: ignore[union-attr]
                "pending": report["pending"],
                "ok": not report["over_cap"],
            }
            emit(args.json, payload, format_check(project, report), [])
            return 1 if report["over_cap"] else 0

        if args.command == "init":
            created = project.init_missing()
            if args.json:
                print_json([project.rel(p) for p in created])
            else:
                if created:
                    print("created:")
                    for p in created:
                        print(f"  {project.rel(p)}")
                else:
                    print("created: none")
            return 0

        if args.command == "stamp_for_clone":
            touched = project.stamp_for_clone()
            if args.json:
                print_json([project.rel(p) for p in touched])
            else:
                if touched:
                    print("touched:")
                    for p in touched:
                        print(f"  {project.rel(p)}")
                else:
                    print("touched: none")
            return 0

        if args.command == "bundle":
            result = project.write_bundle()
            if args.json:
                print_json(result)
            else:
                print(f"bundled: {result.output}")
                print(f"sources: {result.source_count}")
                print(f"order: {result.order}")
            return 0

        raise FracError(f"Unknown command: {args.command}")
    except FracError as e:
        print(f"frac: error: {e}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("frac: interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
