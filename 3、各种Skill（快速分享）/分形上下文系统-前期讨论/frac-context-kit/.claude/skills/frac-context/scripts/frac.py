#!/usr/bin/env python3
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

Python: 3.9+
Dependencies: standard library only.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

FRAC_NAME = ".frac.md"
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


class FracError(RuntimeError):
    pass


class FracProject:
    def __init__(self, root: Path, respect_gitignore: bool = True) -> None:
        self.root = root.resolve()
        if not self.root.exists():
            raise FracError(f"Root does not exist: {self.root}")
        if not self.root.is_dir():
            raise FracError(f"Root is not a directory: {self.root}")
        self.respect_gitignore = respect_gitignore
        self.fracignore_patterns = self._load_fracignore()
        self._eligible_files: Optional[Set[Path]] = None
        self._eligible_dirs: Optional[Set[Path]] = None

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
        rel = path.resolve().relative_to(self.root).as_posix()
        name = path.name
        is_dir = path.is_dir()
        for pat in self.fracignore_patterns:
            dir_pat = pat.endswith("/")
            clean = pat[:-1] if dir_pat else pat
            if dir_pat:
                if is_dir and (name == clean or rel == clean or rel.startswith(clean + "/")):
                    return True
                if any(part == clean for part in path.resolve().relative_to(self.root).parts):
                    return True
            else:
                if fnmatch.fnmatch(rel, clean) or fnmatch.fnmatch(name, clean):
                    return True
        return False

    def is_ignored(self, path: Path) -> bool:
        if path.resolve() == self.root:
            return False
        return self._is_default_ignored(path) or self._matches_fracignore(path)

    def _git_eligible_files(self) -> Optional[Set[Path]]:
        if not self.respect_gitignore:
            return None
        if not (self.root / ".git").exists():
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

    def direct_files(self, directory: Path) -> List[Path]:
        directory = directory.resolve()
        files = [
            f for f in self.eligible_files()
            if f.parent.resolve() == directory and f.name != FRAC_NAME
        ]
        return sorted(files, key=lambda p: p.name.lower())

    def direct_child_dirs(self, directory: Path) -> List[Path]:
        directory = directory.resolve()
        children = [
            d for d in self.eligible_dirs()
            if d != directory and d.parent.resolve() == directory
        ]
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

    # ---------- git changed support ----------

    def changed_paths_from_git(self) -> List[Path]:
        if not (self.root / ".git").exists():
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

    def stamp(self, dirs: Optional[Iterable[Path]] = None) -> List[Path]:
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


# ---------- formatting ----------


def print_json(obj: object) -> None:
    def default(o: object) -> object:
        if hasattr(o, "__dataclass_fields__"):
            return asdict(o)
        if isinstance(o, Path):
            return str(o)
        raise TypeError(type(o).__name__)
    print(json.dumps(obj, ensure_ascii=False, indent=2, default=default))


def format_status(items: Sequence[StatusItem]) -> str:
    if not items:
        return "No frac directories found."
    widths = {
        "state": max(len("state"), *(len(i.state + ("*" if i.propagated else "")) for i in items)),
        "dir": max(len("directory"), *(len(i.directory) for i in items)),
    }
    lines = []
    lines.append(f"{'state'.ljust(widths['state'])}  {'directory'.ljust(widths['dir'])}  reason")
    lines.append(f"{'-' * widths['state']}  {'-' * widths['dir']}  ------")
    for i in items:
        state = i.state + ("*" if i.propagated else "")
        lines.append(f"{state.ljust(widths['state'])}  {i.directory.ljust(widths['dir'])}  {i.reason}")
    lines.append("")
    lines.append("* = 当前 fresh，但由于后代将更新，按 bottom-up 计划也应连带更新。")
    return "\n".join(lines)


def format_plan(project: FracProject, dirs: Sequence[Path]) -> str:
    if not dirs:
        return "update-order: empty"
    lines = ["update-order:"]
    for idx, d in enumerate(dirs, 1):
        lines.append(f"  {idx}. {project.rel(d)}")
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


def format_chain(project: FracProject, chain: Sequence[Path]) -> str:
    if not chain:
        return "frac-chain: empty"
    lines = ["frac-chain:"]
    for f in chain:
        marker = "" if f.exists() else "  # missing"
        lines.append(f"  {project.rel(f)}{marker}")
    return "\n".join(lines)


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

    sp = sub.add_parser("status", help="Show missing/stale/fresh .frac.md files.")
    add_root(sp)
    sp.add_argument("--no-fresh", action="store_true", help="Hide fresh rows unless propagated.")

    sp = sub.add_parser("plan", help="Show bottom-up update order.")
    add_root(sp)
    sp.add_argument("--changed", action="store_true", help="Use Git changed paths to form an affected chain plan.")

    sp = sub.add_parser("inputs", help="Show allowed inputs for updating one directory .frac.md.")
    sp.add_argument("directory", help="Directory whose .frac.md will be updated.")
    sp.add_argument("--root", default=".", help="Project root. Default: current directory.")
    sp.add_argument("--json", action="store_true", help="Output JSON.")

    sp = sub.add_parser("chain", help="Show .frac.md chain for a target file or directory.")
    sp.add_argument("target", help="Target file or directory.")
    sp.add_argument("--root", default=".", help="Project root. Default: current directory.")
    sp.add_argument("--json", action="store_true", help="Output JSON.")

    sp = sub.add_parser("init", help="Create missing placeholder .frac.md files and mark them stale.")
    add_root(sp)

    sp = sub.add_parser("stamp", help="Touch existing .frac.md files bottom-up to restore mtime invariant.")
    add_root(sp)

    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        respect_gitignore = not getattr(args, "no_gitignore", False)

        if args.command in {"status", "plan", "init", "stamp"}:
            project = FracProject(Path(args.root), respect_gitignore=respect_gitignore)
        elif args.command in {"inputs", "chain"}:
            project = FracProject(Path(args.root), respect_gitignore=respect_gitignore)
        else:
            raise FracError(f"Unknown command: {args.command}")

        if args.command == "status":
            items = project.status(include_fresh=not args.no_fresh)
            if args.json:
                print_json(items)
            else:
                print(format_status(items))
            return 0

        if args.command == "plan":
            dirs = project.update_plan(changed_only=args.changed)
            if args.json:
                print_json([project.rel(d) for d in dirs])
            else:
                print(format_plan(project, dirs))
            return 0

        if args.command == "inputs":
            directory = project.abs_path(args.directory)
            if not directory.exists() or not directory.is_dir():
                raise FracError(f"Not a directory: {directory}")
            inputs = project.inputs_for_dir(directory)
            if args.json:
                print_json(inputs)
            else:
                print(format_inputs(inputs))
            return 0

        if args.command == "chain":
            target = project.abs_path(args.target)
            chain = project.chain_for_target(target)
            if args.json:
                print_json([project.rel(p) for p in chain])
            else:
                print(format_chain(project, chain))
            return 0

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

        if args.command == "stamp":
            touched = project.stamp()
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

        return 1
    except FracError as e:
        print(f"frac: error: {e}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("frac: interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
