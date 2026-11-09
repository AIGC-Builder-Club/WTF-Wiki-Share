#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
frac.py — lightweight .frac.md recursive context helper (entry point).

This script intentionally avoids databases, embeddings, AST analysis, and RAG.
It only answers deterministic filesystem questions:

- Which directories should have .frac.md?
- Which .frac.md files are missing/stale/fresh?
- What is the bottom-up update order?
- What inputs may an Agent read to update one .frac.md?
- What .frac.md chain should be read before editing a target path?
- How to refresh .frac.md mtimes after clone/checkout?
- How large may one .frac.md be, and what in it goes stale fastest?

实现在旁边的 fraclib/ 包里（各模块分工见 fraclib/__init__.py）。
每个命令跑完会顺路检查上游有没有新版并自动更新，见 fraclib/update.py。

Python: 3.9+
Dependencies: standard library only.
"""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True  # 不在仓库里留下 __pycache__

from pathlib import Path  # noqa: E402

SCRIPT = Path(__file__)
_HERE = str(SCRIPT.resolve().parent)
if _HERE not in sys.path:
    sys.path.append(_HERE)  # python -I / -P 也找得到旁边的 fraclib；放在最后，不遮住标准库

import argparse  # noqa: E402
from typing import Optional, Sequence  # noqa: E402

from fraclib import report, update, usage, wrapup  # noqa: E402
from fraclib.lint import lint_counts  # noqa: E402
from fraclib.project import BUNDLE_NAME, FracError, FracProject  # noqa: E402


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

    sub.add_parser("version", help="Show the skill version and the auto-update state.")

    sp = sub.add_parser("update", help="Check upstream now and update this skill copy if a newer version exists.")
    sp.add_argument("--check", action="store_true", help="Only report; do not change files.")
    sp.add_argument("--force", action="store_true", help="Overwrite even if local skill files were modified.")

    sp = sub.add_parser("manifest", help="Maintainers: verify (or --write) manifest.json against the skill files.")
    sp.add_argument("--write", action="store_true", help="Rewrite manifest.json from the current files and version.")

    return p


def run_command(args: argparse.Namespace) -> int:
    try:
        if args.command == "version":
            print("\n".join(update.describe(SCRIPT)))
            return 0

        if args.command == "update":
            code, lines = update.explicit(SCRIPT, check_only=args.check, force=args.force)
            print("\n".join(lines))
            return code

        if args.command == "manifest":
            code, lines = update.manifest_report(SCRIPT.resolve().parent.parent, write=args.write)
            print("\n".join(lines))
            return code

        respect_gitignore = not getattr(args, "no_gitignore", False)
        own_skill = update.skill_dir_for(SCRIPT)
        project = FracProject(Path(args.root), respect_gitignore=respect_gitignore,
                              skill_dirs=[own_skill] if own_skill else [])

        if args.command == "status":
            items = wrapup.enrich_status(project, project.status(include_fresh=not args.no_fresh))
            recent = usage.UsageLog(project).record("status")
            report.emit(args.json, items, report.format_status(project, items),
                        usage.mid_task_notes(recent, wrapup.premature_updates(project)))
            return 0

        if args.command == "plan":
            recent = usage.UsageLog(project).record("plan", final=args.final)
            premature = wrapup.premature_updates(project)
            if args.final:
                items = wrapup.final_plan(project, changed_only=args.changed)
                report.emit(args.json, items, report.format_final_plan(project, items), usage.final_notes(recent, premature))
            else:
                dirs = project.update_plan(changed_only=args.changed)
                report.emit(args.json, [project.rel(d) for d in dirs], report.format_plan(project, dirs),
                            usage.mid_task_notes(recent, premature))
            return 0

        if args.command == "inputs":
            directory = project.abs_path(args.directory)
            if not directory.exists() or not directory.is_dir():
                raise FracError(f"Not a directory: {directory}")
            inputs = project.inputs_for_dir(directory)
            size = wrapup.size_report(project, directory)
            hits = wrapup.lint_dir(project, directory)
            recent = usage.UsageLog(project).record("inputs", inputs.directory)
            payload = dict(report.to_jsonable(inputs))  # type: ignore[arg-type]
            payload["size"] = report.to_jsonable(size)
            payload["lint"] = lint_counts(hits)
            text = report.format_inputs(inputs) + "\n\n" + report.format_size_block(project, size, hits)
            report.emit(args.json, payload, text, usage.inputs_notes(recent, inputs.directory))
            return 0

        if args.command == "chain":
            target = project.abs_path(args.target)
            chain = project.chain_for_target(target)
            key = project.rel(chain[-1].parent) if chain else ""
            recent = usage.UsageLog(project).record("chain", key)
            report.emit(args.json, [project.rel(p) for p in chain], report.format_chain(project, chain),
                        usage.chain_notes(project, chain, recent, key))
            return 0

        if args.command == "confirm":
            dirs = [project.abs_path(d) for d in args.directories]
            problems = wrapup.confirm_problems(project, dirs)
            if problems:
                print("frac: confirm 拒绝（什么都没改）：", file=sys.stderr)
                for line in problems:
                    print(f"  {line}", file=sys.stderr)
                return 1
            result = wrapup.confirm(project, dirs)
            report.emit(args.json, result, report.format_confirm(result), [])
            return 0

        if args.command == "check":
            checked = wrapup.check(project, changed_only=args.changed)
            payload = {
                "scope": checked["scope"],
                "checked": checked["checked"],
                "over_cap": [r["size"] for r in checked["over_cap"]],  # type: ignore[union-attr]
                "over_budget": [r["size"] for r in checked["over_budget"]],  # type: ignore[union-attr]
                "near": [r["size"] for r in checked["near"]],  # type: ignore[union-attr]
                "volatile": {r["size"].frac: r["lint"] for r in checked["volatile"]},  # type: ignore[union-attr]
                "pending": checked["pending"],
                "removable": checked["removable"],
                "ok": not checked["over_cap"],
            }
            report.emit(args.json, payload, report.format_check(project, checked), [])
            return 1 if checked["over_cap"] else 0

        if args.command == "init":
            created = project.init_missing()
            if args.json:
                report.print_json([project.rel(p) for p in created])
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
                report.print_json([project.rel(p) for p in touched])
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
                report.print_json(result)
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


def main(argv: Optional[Sequence[str]] = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass
    args = build_arg_parser().parse_args(argv)
    code = run_command(args)
    if args.command not in {"version", "update", "manifest"}:
        notes = update.auto(SCRIPT)
        if notes:
            print("\n".join(notes), file=sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
