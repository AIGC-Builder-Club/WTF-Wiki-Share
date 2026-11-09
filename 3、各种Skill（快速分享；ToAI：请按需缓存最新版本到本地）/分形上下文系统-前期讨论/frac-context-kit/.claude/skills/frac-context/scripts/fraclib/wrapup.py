# -*- coding: utf-8 -*-
"""收尾：大小报告、收尾清单、confirm、check，以及“本轮写过又被推翻”的检测。"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple

from .budget import SizeReport, kib
from .lint import LintHit, format_lint_detail, lint_counts, lint_frac_text
from .project import FRAC_NAME, FracProject, StatusItem


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


def entries_count(project: FracProject, directory: Path) -> int:
    """直属条目 = 直属有效文件 + 直属子目录 + 直属的 git 子模块。"""
    return (len(project.direct_files(directory)) + len(project.direct_child_dirs(directory))
            + len(project.direct_submodules(directory)))


def size_report(project: FracProject, directory: Path) -> SizeReport:
    directory = directory.resolve()
    frac = project.frac_path(directory)
    size = frac.stat().st_size if frac.exists() else None
    entries = entries_count(project, directory)
    budget = project.budget.budget(entries)
    return SizeReport(
        directory=project.rel(directory),
        frac=project.rel(frac),
        size=size,
        entries=entries,
        budget=budget,
        cap=project.budget.cap,
        level=project.budget.level(size, budget),
    )


def lint_dir(project: FracProject, directory: Path) -> List[LintHit]:
    frac = project.frac_path(directory.resolve())
    if not frac.exists():
        return []
    return lint_frac_text(frac.read_text(encoding="utf-8", errors="replace"))


def final_plan(project: FracProject, changed_only: bool = False) -> List[PlanItem]:
    changed = {d.resolve() for d in changed_frac_dirs(project)}
    items: List[PlanItem] = []
    for d in project.update_plan(changed_only=changed_only):
        st = project.actual_status_for_dir(d)
        state = st.state if st.state in {"missing", "stale"} else "propagated"
        size = size_report(project, d)
        items.append(PlanItem(
            directory=project.rel(d),
            state=state,
            size=size.size,
            entries=size.entries,
            budget=size.budget,
            level=size.level,
            lint=lint_counts(lint_dir(project, d)),
            changed_this_round=d in changed,
        ))
    return items


def check(project: FracProject, changed_only: bool = False) -> Dict[str, object]:
    eligible = project.eligible_dirs()
    scope_note = ""
    if changed_only and not project.is_git_root():
        changed_only = False
        scope_note = "不是 git 仓库根目录，--changed 用不了，改查全部。"
    if changed_only:
        dirs = [d for d in changed_frac_dirs(project) if d in eligible]
    else:
        dirs = [d for d in eligible if project.frac_path(d).exists()]
    dirs = sorted(set(dirs), key=lambda p: (-project.depth(p), project.rel(p)))
    reports = []
    for d in dirs:
        size = size_report(project, d)
        hits = lint_dir(project, d)
        reports.append({"size": size, "lint": lint_counts(hits), "lint_detail": format_lint_detail(hits)})
    return {
        "scope": "changed" if changed_only else "all",
        "scope_note": scope_note,
        "checked": len(reports),
        "over_cap": [r for r in reports if r["size"].level == "over-cap"],
        "over_budget": [r for r in reports if r["size"].level == "over-budget"],
        "near": [r for r in reports if r["size"].level == "near"],
        "volatile": [r for r in reports if r["lint"]],
        "pending": [project.rel(d) for d in project.update_plan()],
        "removable": removable_fracs(project),
    }


def removable_fracs(project: FracProject) -> List[str]:
    """已经不参与的 .frac.md：skill 副本里的，以及目录里除了它什么都没有的。删掉即可。"""
    out = [project.rel(p) for p in project.vendored_frac_files()]
    for d in sorted(project.eligible_dirs(), key=lambda p: (-project.depth(p), project.rel(p))):
        if d == project.root or not project.frac_path(d).exists():
            continue
        if not project.direct_files(d) and not project.direct_child_dirs(d) and not project.direct_submodules(d):
            out.append(project.rel(project.frac_path(d)))
    return out


def changed_frac_dirs(project: FracProject) -> List[Path]:
    """本轮（git 工作区）内容改过的 .frac.md 所在目录。"""
    out: List[Path] = []
    for p in project.changed_paths_from_git():
        if p.name == FRAC_NAME and p.exists():
            out.append(p.parent.resolve())
    return out


def premature_updates(project: FracProject) -> List[str]:
    """本轮已经改过内容、之后输入又变了的 .frac.md：中途写的被推翻了。"""
    eligible = project.eligible_dirs()
    out: List[str] = []
    for d in sorted(set(changed_frac_dirs(project)), key=lambda p: (-project.depth(p), project.rel(p))):
        if d in eligible and project.actual_status_for_dir(d).state == "stale":
            out.append(project.rel(d))
    return out


def confirm_problems(project: FracProject, dirs: Sequence[Path]) -> List[str]:
    eligible = project.eligible_dirs()
    problems: List[str] = []
    for d in dirs:
        d = d.resolve()
        rel = project.rel(d)
        if not d.is_dir() or d not in eligible:
            problems.append(f"{rel}：不是需要 .frac.md 的目录")
            continue
        frac = project.frac_path(d)
        if not frac.exists():
            problems.append(f"{rel}：还没有 .frac.md，没有可确认的；先写一份")
            continue
        size = size_report(project, d)
        if size.level == "over-cap":
            problems.append(
                f"{rel}：{size.size:,} B，超过硬上限 {size.cap:,} B，不能只确认。"
                f"这次要把它压到预算 {size.budget:,} B 以内：以现有内容为底稿删版本史、数字、原话、参数细目，"
                f"留职责、分工、对外接口、约束；不必重读全部直属文件"
            )
            continue
        if project.inputs_for_dir(d).missing_child_fracs:
            problems.append(f"{rel}：有子目录还没有 .frac.md，先处理子目录")
    return problems


def _stamp(project: FracProject, directory: Path) -> None:
    frac = project.frac_path(directory)
    max_input, _ = project.max_input_mtime_ns(directory)
    ts = max(time.time_ns(), (max_input or 0) + 1, frac.stat().st_mtime_ns)
    os.utime(frac, ns=(ts, ts))


def confirm(project: FracProject, dirs: Sequence[Path]) -> ConfirmResult:
    """确认这些目录的 .frac.md 内容不用改，只把时间戳更新到不早于输入。

    上面各层若在这之前是新的（只会因为下层时间戳变了而变旧），一起确认；
    原本就落后的上层要 Agent 自己看，不替它确认。
    """
    eligible = project.eligible_dirs()
    targets = sorted({d.resolve() for d in dirs}, key=lambda p: (-project.depth(p), project.rel(p)))
    target_set = set(targets)
    ancestors: Set[Path] = set()
    for d in targets:
        for a in project.ancestors_to_root(d)[:-1]:
            if a in eligible and a not in target_set:
                ancestors.add(a)
    before = {a: project.actual_status_for_dir(a).state for a in ancestors}

    confirmed: List[str] = []
    already: List[str] = []
    for d in targets:
        if project.actual_status_for_dir(d).state == "fresh":
            already.append(project.rel(d))
            continue
        _stamp(project, d)
        confirmed.append(project.rel(d))

    propagated: List[str] = []
    needs_review: List[Tuple[str, str]] = []
    for a in sorted(ancestors, key=lambda p: (-project.depth(p), project.rel(p))):
        now = project.actual_status_for_dir(a).state
        if now == "fresh":
            continue
        if before[a] == "missing":
            needs_review.append((project.rel(a), "还没有 .frac.md"))
            continue
        if before[a] != "fresh":
            needs_review.append((project.rel(a), "这一层本来就落后（有别的输入变了），要你自己看"))
            continue
        size = size_report(project, a)
        if size.level == "over-cap":
            needs_review.append((project.rel(a), f"{kib(size.size)}，超过硬上限：不能只确认，要压到预算 {kib(size.budget)} 以内"))
            continue
        _stamp(project, a)
        propagated.append(project.rel(a))
    return ConfirmResult(confirmed=confirmed, already_fresh=already, propagated=propagated, needs_review=needs_review)


def enrich_status(project: FracProject, items: Sequence[StatusItem]) -> List[StatusItem]:
    """给 status 的每一行补上大小、预算和标记。"""
    out: List[StatusItem] = []
    for item in items:
        size = size_report(project, project.abs_path(item.directory))
        out.append(replace(item, size=size.size, budget=size.budget, size_level=size.level))
    return out
