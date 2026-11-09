# -*- coding: utf-8 -*-
"""文本与 JSON 输出：status、plan、收尾清单、inputs、chain、check、confirm。"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .budget import LEVEL_LABELS, SizeReport, kib
from .lint import LintHit, format_lint_counts, format_lint_detail
from .project import DirInputs, FracProject, StatusItem
from .wrapup import ConfirmResult, PlanItem, size_report


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
    if inputs.submodules:
        lines.append("")
        lines.append("SUBMODULES:")
        for f in inputs.submodules:
            lines.append(f"  {f}")
        lines.append("  # 子仓库：只写它是什么、去哪看；它的内容和它自己的 .frac.md 在它自己的仓库里，不读")
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
        flag = LEVEL_LABELS.get(size_report(project, f.parent).level, "")
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
    removable = report.get("removable") or []
    if removable:
        lines.append("")
        lines.append("已经不参与、可以删的 .frac.md（skill 副本不进 .frac.md 树；只剩 .frac.md 的目录也不用再写）：")
        lines.extend(f"  {p}" for p in removable[:15])  # type: ignore[index]
        if len(removable) > 15:  # type: ignore[arg-type]
            lines.append(f"  ……另有 {len(removable) - 15} 份")  # type: ignore[arg-type]
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
