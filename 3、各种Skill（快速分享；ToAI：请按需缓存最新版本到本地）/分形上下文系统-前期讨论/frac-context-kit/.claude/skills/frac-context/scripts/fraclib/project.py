# -*- coding: utf-8 -*-
"""目录树模型：哪些目录要有 .frac.md、各自允许的输入、新鲜度、更新顺序、上下文链、占位文件、mtime、汇总。

只回答确定性的文件系统问题；不做数据库、embedding、AST 分析或 RAG。
"""

from __future__ import annotations

import fnmatch
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from .budget import SizeBudget

FRAC_NAME = ".frac.md"
BUNDLE_NAME = ".frac.全部汇总超大.md"
FRACIGNORE_NAME = ".fracignore"

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
    submodules: List[str] = field(default_factory=list)


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


class FracError(RuntimeError):
    pass


def is_frac_skill_dir(d: Path) -> bool:
    """d 是不是一份 frac-context skill（SKILL.md 写着 name: frac-context，旁边有 scripts/frac.py）。"""
    try:
        head = (d / "SKILL.md").read_text(encoding="utf-8", errors="replace")[:400]
    except OSError:
        return False
    return "name: frac-context" in head and (d / "scripts" / "frac.py").is_file()


class FracProject:
    def __init__(self, root: Path, respect_gitignore: bool = True, skill_dirs: Sequence[Path] = ()) -> None:
        self.root = root.resolve()
        if not self.root.exists():
            raise FracError(f"Root does not exist: {self.root}")
        if not self.root.is_dir():
            raise FracError(f"Root is not a directory: {self.root}")
        self.respect_gitignore = respect_gitignore
        self.fracignore_patterns = self._load_fracignore()
        self.vendored_dirs = self._find_vendored_skills(skill_dirs)
        self.budget = SizeBudget()
        self._eligible_files: Optional[Set[Path]] = None
        self._eligible_dirs: Optional[Set[Path]] = None
        # 性能缓存（语义不变）：is_ignored 的结果，以及「父目录 -> 直属文件 / 直属子目录」索引。
        # 没有它们时，每次 inputs/status 都会对整棵树重复 resolve()；几千个文件的树上一次 status 要跑数分钟。
        self._ignore_cache: Dict[str, bool] = {}
        self._files_by_parent: Optional[Dict[Path, List[Path]]] = None
        self._dirs_by_parent: Optional[Dict[Path, List[Path]]] = None
        self._submodules: Optional[List[Path]] = None

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
            clean = (pat[:-1] if dir_pat else pat).lstrip("/")
            if dir_pat:
                # a/b/ 管住 a/b 下面的一切（文件也算）；单段的 name/ 管住任何一层叫 name 的目录。
                if rel == clean or rel.startswith(clean + "/"):
                    return True
                if is_dir and name == clean:
                    return True
                if any(part == clean for part in parts):
                    return True
            else:
                if fnmatch.fnmatch(rel, clean) or fnmatch.fnmatch(name, clean):
                    return True
        return False

    def _find_vendored_skills(self, extra: Sequence[Path]) -> Tuple[Path, ...]:
        """仓库里的 frac-context skill 副本（.claude/skills/frac-context 之类）。

        它由上游 kit 维护、会被自动更新改动，说明就是它自己的 SKILL.md：不进 .frac.md 树，
        否则每次 kit 发版，整条链都要跟着重写。
        """
        candidates: List[Path] = list(extra)
        for pattern in ("*/skills/*/SKILL.md", "skills/*/SKILL.md"):
            candidates.extend(p.parent for p in self.root.glob(pattern))
        found: Set[Path] = set()
        for d in candidates:
            d = d.resolve()
            if d == self.root or self.root not in d.parents:
                continue
            if is_frac_skill_dir(d):
                found.add(d)
        return tuple(sorted(found))

    def _in_vendored(self, path: Path) -> bool:
        if not self.vendored_dirs:
            return False
        p = path.resolve()
        return any(p == v or v in p.parents for v in self.vendored_dirs)

    def vendored_frac_files(self) -> List[Path]:
        """skill 副本里残留的 .frac.md：它们已经不参与，可以删。"""
        out: List[Path] = []
        for v in self.vendored_dirs:
            out.extend(sorted(v.rglob(FRAC_NAME)))
        return out

    def is_ignored(self, path: Path) -> bool:
        key = str(path)
        cached = self._ignore_cache.get(key)
        if cached is not None:
            return cached
        if path.resolve() == self.root:
            result = False
        else:
            result = self._is_default_ignored(path) or self._matches_fracignore(path) or self._in_vendored(path)
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

    def submodules(self) -> List[Path]:
        """git 子模块的挂载点（gitlink）。它们是父目录的直属条目，但内容属于子仓库，不进本仓库的树。"""
        if self._submodules is None:
            found: List[Path] = []
            if self.is_git_root():
                try:
                    result = subprocess.run(
                        ["git", "-C", str(self.root), "ls-files", "--stage", "-z"],
                        check=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL,
                    )
                    for raw in result.stdout.split(b"\0"):
                        meta, _, rel = raw.decode("utf-8", errors="replace").partition("\t")
                        if rel and meta.startswith("160000 "):
                            p = (self.root / rel).resolve()
                            if not self.is_ignored(p):
                                found.append(p)
                except Exception:
                    found = []
            self._submodules = sorted(found)
        return self._submodules

    def direct_submodules(self, directory: Path) -> List[Path]:
        directory = directory.resolve()
        return [p for p in self.submodules() if p.parent == directory]

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
            submodules=[self.rel(p) for p in self.direct_submodules(directory)],
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
                items.append(item)
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
