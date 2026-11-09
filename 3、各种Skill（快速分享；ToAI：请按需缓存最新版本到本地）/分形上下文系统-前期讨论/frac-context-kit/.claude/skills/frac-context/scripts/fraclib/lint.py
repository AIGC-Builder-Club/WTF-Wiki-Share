# -*- coding: utf-8 -*-
"""易变内容检查：版本号、日期、测试/检查条数、行号行数、提交号/评论号、超长条目。

只提示，不拦截（正则会误报）。代码块里的不查。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

# 单行超过这么多字节，算“超长条目”（中文约 200 字）。
LONG_LINE_BYTES = 600


@dataclass(frozen=True)
class LintHit:
    kind: str
    line: int
    excerpt: str


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
