# -*- coding: utf-8 -*-
"""单份 .frac.md 的大小预算（计算引擎）。

budget(n) = min(cap, base + per_entry * n)，n = 本目录直属条目数（直属有效文件 + 直属子目录 + 直属的 git 子模块）。
只看本目录自己，不和仓库里别的目录比。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# 单份 .frac.md 的硬上限（字节，按 UTF-8 计；中文约 3,400 字）。
# 超过即报错：check 不通过，confirm 拒绝只确认。
HARD_CAP_BYTES = 10 * 1024
# 每个目录的预算 = 起步 + 直属条目数 × 每项，封顶 HARD_CAP_BYTES。
# 直属条目 = 直属有效文件 + 直属子目录 + 直属的 git 子模块（与 inputs 的口径一致）。
BUDGET_BASE_BYTES = 2 * 1024
BUDGET_PER_ENTRY_BYTES = 340
# 到预算的这个比例，就提示“接近”。
NEAR_BUDGET_RATIO = 0.85


@dataclass(frozen=True)
class SizeReport:
    directory: str
    frac: str
    size: Optional[int]
    entries: int
    budget: int
    cap: int
    level: str  # missing / ok / near / over-budget / over-cap


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


def kib(n: Optional[int]) -> str:
    if n is None:
        return "-"
    return f"{n / 1024:.1f}K"
