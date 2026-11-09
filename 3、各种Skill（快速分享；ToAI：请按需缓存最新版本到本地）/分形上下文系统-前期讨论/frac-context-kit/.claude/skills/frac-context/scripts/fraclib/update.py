# -*- coding: utf-8 -*-
"""自动更新：frac.py 每次运行时顺路看一眼上游 kit 有没有新版；有，就把整个 skill 换成新版。

- 上游：kit 仓库 main 分支上的 skill 目录；manifest.json 列出版本号和每个文件的 sha256。
- 最多每 UPDATE_CHECK_SECONDS（一小时）联网查一次，结果记在用户缓存目录（同一台机器上的各个仓库共用）；
  离线、超时都静默跳过，不影响命令本身。
- 下载的每个文件都要对上 manifest 的 sha256，.py 还要能编译；全部通过才替换，任何一步失败都保留旧版。
- 只替换 manifest 列出、而且内容不同的文件；仓库自己放在 skill 目录里的 .frac.md 不动。
- 本地改过的文件（和本地 manifest 对不上）不自动覆盖，要 `frac.py update --force`。
- 环境变量：FRAC_UPDATE=auto（默认）/ notify（只提示）/ off（不查）；
  FRAC_UPDATE_URL 换来源（指到 skill 目录，末尾带 /）；FRAC_UPDATE_CACHE 换缓存文件。
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Dict, List, Optional, Tuple

from . import FRAC_VERSION, SKILL_NAME

MANIFEST_NAME = "manifest.json"
UPDATE_REPO = "hanshou101/Obsidian_PublicGitHubShare_InsteadOf_FeiShu"
UPDATE_BRANCH = "main"
UPDATE_PATH = (
    "3、各种Skill（快速分享；ToAI：请按需缓存最新版本到本地）/分形上下文系统-前期讨论/"
    "frac-context-kit/.claude/skills/frac-context"
)
# 多久联网查一次；没换成（校验没过，多半是 CDN 还没刷新；或者目录写不进去）隔多久再试；同一条“有新版没换”的提示多久说一次。
UPDATE_CHECK_SECONDS = 3600
RETRY_SECONDS = 15 * 60
NOTIFY_SECONDS = 3600
TIMEOUT_SECONDS = 4
# 不进 manifest 的：仓库自己的 .frac.md、manifest 本身、缓存与系统文件。
EXCLUDED_NAMES = {".frac.md", MANIFEST_NAME, ".DS_Store", "Thumbs.db"}
EXCLUDED_DIRS = {"__pycache__"}


class UpdateError(RuntimeError):
    pass


@dataclass
class Outcome:
    status: str  # off / not-skill / current / updated / available / modified / missing / error / failed
    local: str
    latest: Optional[str] = None
    files: List[str] = field(default_factory=list)
    removed: List[str] = field(default_factory=list)
    detail: str = ""
    checked_now: bool = False


# ---------- versions, digests, manifest ----------


def parse_version(text: object) -> Optional[Tuple[int, ...]]:
    try:
        parts = tuple(int(p) for p in str(text).strip().split("."))
    except ValueError:
        return None
    return parts or None


def is_newer(remote: object, local: object) -> bool:
    r, l = parse_version(remote), parse_version(local)
    return r is not None and l is not None and r > l


def file_digest(data: bytes) -> str:
    """换行统一成 LF 再算，Windows 上 autocrlf 签出的文件也对得上。"""
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def skill_files(skill_dir: Path) -> List[str]:
    out: List[str] = []
    for p in sorted(skill_dir.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(skill_dir)
        if any(part in EXCLUDED_DIRS for part in rel.parts):
            continue
        if p.name in EXCLUDED_NAMES or p.name.endswith((".pyc", ".tmp")):
            continue
        out.append(rel.as_posix())
    return out


def build_manifest(skill_dir: Path, version: str = FRAC_VERSION) -> Dict[str, object]:
    files = {rel: file_digest((skill_dir / rel).read_bytes()) for rel in skill_files(skill_dir)}
    return {"name": SKILL_NAME, "version": version, "files": files}


def manifest_bytes(manifest: Dict[str, object]) -> bytes:
    return (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def safe_rel(rel: object) -> bool:
    if not isinstance(rel, str) or not rel or "\\" in rel or rel.startswith("/"):
        return False
    parts = PurePosixPath(rel).parts
    return ".." not in parts and not PurePosixPath(rel).is_absolute()


def valid_manifest(m: object) -> bool:
    if not isinstance(m, dict) or m.get("name") != SKILL_NAME or parse_version(m.get("version")) is None:
        return False
    files = m.get("files")
    return isinstance(files, dict) and bool(files) and all(
        safe_rel(k) and isinstance(v, str) and len(v) == 64 for k, v in files.items()
    )


def read_local_manifest(skill_dir: Path) -> Optional[Dict[str, object]]:
    try:
        m = json.loads((skill_dir / MANIFEST_NAME).read_text(encoding="utf-8"))
    except Exception:
        return None
    return m if valid_manifest(m) else None


def local_modifications(skill_dir: Path, manifest: Optional[Dict[str, object]]) -> List[str]:
    """本地内容和本地 manifest 对不上的文件（缺的不算：更新会补回来）。"""
    if not manifest:
        return []
    changed: List[str] = []
    for rel, digest in manifest["files"].items():  # type: ignore[union-attr]
        p = skill_dir / PurePosixPath(rel)
        if p.is_file() and file_digest(p.read_bytes()) != digest:
            changed.append(rel)
    return changed


# ---------- where to look, where to remember ----------


def mode() -> str:
    m = os.environ.get("FRAC_UPDATE", "auto").strip().lower()
    return m if m in {"auto", "notify", "off"} else "auto"


def sources() -> List[str]:
    override = os.environ.get("FRAC_UPDATE_URL", "").strip()
    if override:
        return [override if override.endswith("/") else override + "/"]
    path = urllib.parse.quote(UPDATE_PATH)
    return [
        f"https://raw.githubusercontent.com/{UPDATE_REPO}/{UPDATE_BRANCH}/{path}/",
        # raw 连不上时（例如大陆网络）的备用；可能比 raw 晚几个小时，sha256 校验会挡住新旧混杂。
        f"https://cdn.jsdelivr.net/gh/{UPDATE_REPO}@{UPDATE_BRANCH}/{path}/",
    ]


def cache_file() -> Path:
    override = os.environ.get("FRAC_UPDATE_CACHE", "").strip()
    if override:
        return Path(override)
    base = os.environ.get("XDG_CACHE_HOME", "").strip() or str(Path.home() / ".cache")
    return Path(base) / "frac-context" / "update-check.json"


def load_cache() -> Dict[str, Dict[str, object]]:
    try:
        data = json.loads(cache_file().read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def save_cache(data: Dict[str, Dict[str, object]]) -> None:
    path = cache_file()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")  # 同一台机器上几个 agent 同时跑也不互相踩
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        os.replace(str(tmp), str(path))
    except Exception:
        pass


def skill_dir_for(script: Path) -> Optional[Path]:
    """frac.py 在 <skill>/scripts/ 下，而且 <skill>/SKILL.md 是 frac-context，才算可以自更新。"""
    d = script.resolve().parent.parent
    try:
        head = (d / "SKILL.md").read_text(encoding="utf-8", errors="replace")[:400]
    except OSError:
        return None
    return d if f"name: {SKILL_NAME}" in head else None


# ---------- network ----------


def fetch(url: str, timeout: float = TIMEOUT_SECONDS) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": f"frac-context/{FRAC_VERSION}"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def fetch_manifest() -> Tuple[Optional[str], Optional[Dict[str, object]], bytes, str]:
    """依次试各个来源。返回 (来源, manifest, 原始字节, 状态)；状态是 ok / missing（都 404）/ error。"""
    srcs = sources()
    missing = 0
    for src in srcs:
        try:
            raw = fetch(src + MANIFEST_NAME)
            m = json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                missing += 1
            continue
        except Exception:
            continue
        if valid_manifest(m):
            return src, m, raw, "ok"
    return None, None, b"", ("missing" if missing == len(srcs) else "error")


def apply(skill_dir: Path, src: str, manifest: Dict[str, object], raw_manifest: bytes) -> Tuple[List[str], List[str]]:
    """下载、逐个校验，全部通过才替换；返回（内容有变的文件，新版不再有、删掉了的文件）。

    只删旧 manifest 列过、新 manifest 没有的文件；本地改过的不会走到这里（run 先拦下，除非 --force）。
    """
    old = read_local_manifest(skill_dir)
    dropped = sorted(set(old["files"]) - set(manifest["files"])) if old else []  # type: ignore[arg-type]
    downloads: Dict[str, bytes] = {}
    for rel, digest in sorted(manifest["files"].items()):  # type: ignore[union-attr]
        target = skill_dir / PurePosixPath(rel)
        if target.is_file() and file_digest(target.read_bytes()) == digest:
            continue
        data = fetch(src + urllib.parse.quote(rel))
        if file_digest(data) != digest:
            raise UpdateError(f"{rel} 的 sha256 对不上")
        if rel.endswith(".py"):
            compile(data.decode("utf-8"), rel, "exec")
        downloads[rel] = data
    # 先把所有新文件写成临时文件，全部写成功再逐个改名换上：中途失败不会留下新旧混杂的一半。
    staged: List[Tuple[Path, Path]] = []
    try:
        for rel, data in list(downloads.items()) + [(MANIFEST_NAME, raw_manifest)]:
            target = skill_dir / PurePosixPath(rel)
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_name(f"{target.name}.{os.getpid()}.frac-update.tmp")
            tmp.write_bytes(data)
            staged.append((tmp, target))
    except Exception:
        for tmp, _ in staged:
            try:
                tmp.unlink()
            except OSError:
                pass
        raise
    for tmp, target in staged:  # manifest 排在最后：它一换上，这一版才算装好
        os.replace(str(tmp), str(target))
    removed: List[str] = []
    for rel in dropped:
        target = skill_dir / PurePosixPath(rel)
        try:
            target.unlink()
        except FileNotFoundError:  # 另一个进程刚删掉
            continue
        removed.append(rel)
        parent = target.parent
        try:
            while parent != skill_dir and not any(parent.iterdir()):
                parent.rmdir()
                parent = parent.parent
        except OSError:
            pass
    return sorted(downloads), removed


# ---------- the check itself ----------


def run(skill_dir: Optional[Path], how: str = "auto", force: bool = False, use_cache: bool = True) -> Outcome:
    local = FRAC_VERSION
    if how == "off":
        return Outcome("off", local)
    if skill_dir is None:
        return Outcome("not-skill", local)
    key = sources()[0]
    cache = load_cache()
    entry = dict(cache.get(key) or {})
    now = time.time()
    src: Optional[str] = None
    manifest: Optional[Dict[str, object]] = None
    raw = b""
    checked_now = False

    if use_cache and entry and now < float(entry.get("next_check") or 0):
        status = str(entry.get("status") or "ok")
        latest = entry.get("latest")
        if status == "failed":
            return Outcome("failed", local, str(latest), detail=str(entry.get("detail") or ""))
    else:
        src, manifest, raw, status = fetch_manifest()
        latest = manifest.get("version") if manifest else None
        entry.update(checked_at=now, status=status, latest=latest, next_check=now + UPDATE_CHECK_SECONDS, detail="")
        cache[key] = entry
        save_cache(cache)
        checked_now = True
    if status != "ok":
        return Outcome(status, local, checked_now=checked_now)
    if not is_newer(latest, local):
        return Outcome("current", local, str(latest), checked_now=checked_now)
    if how == "notify":
        return Outcome("available", local, str(latest), checked_now=checked_now)
    modified = local_modifications(skill_dir, read_local_manifest(skill_dir))
    if modified and not force:
        return Outcome("modified", local, str(latest), files=modified, checked_now=checked_now)

    if manifest is None:  # 缓存说有新版（例如同一台机器上别的仓库刚换过），现在去取
        src, manifest, raw, status = fetch_manifest()
        if status != "ok" or manifest is None:
            # 取不到就按失败记下，隔 RETRY_SECONDS 再试，不让每个命令都等一次超时
            entry.update(status=status, next_check=now + RETRY_SECONDS)
            cache[key] = entry
            save_cache(cache)
            return Outcome(status, local, str(latest), checked_now=True)
        if not is_newer(manifest.get("version"), local):
            return Outcome("current", local, str(manifest.get("version")), checked_now=True)
    assert src is not None
    try:
        written, removed = apply(skill_dir, src, manifest, raw)
    except Exception as e:
        entry.update(status="failed", latest=manifest.get("version"), detail=str(e)[:120], next_check=now + RETRY_SECONDS)
        cache[key] = entry
        save_cache(cache)
        return Outcome("failed", local, str(manifest.get("version")), detail=str(e)[:120], checked_now=True)
    entry.update(status="ok", latest=manifest.get("version"), next_check=now + UPDATE_CHECK_SECONDS, detail="")
    cache[key] = entry
    save_cache(cache)
    return Outcome("updated", local, str(manifest.get("version")), files=written, removed=removed, checked_now=True)


def _notify_due(outcome: Outcome) -> bool:
    """同一个新版本，“有新版没换”的提示一小时说一次。"""
    key = sources()[0]
    cache = load_cache()
    entry = dict(cache.get(key) or {})
    now = time.time()
    if entry.get("notified_version") == outcome.latest and now - float(entry.get("notified_at") or 0) < NOTIFY_SECONDS:
        return False
    entry.update(notified_version=outcome.latest, notified_at=now)
    cache[key] = entry
    save_cache(cache)
    return True


def notes(outcome: Outcome, script: str) -> List[str]:
    o = outcome
    if o.status == "updated":
        shown = "、".join(o.files[:6]) + ("……" if len(o.files) > 6 else "")
        gone = f"；删掉新版不再有的 {'、'.join(o.removed)}" if o.removed else ""
        return [
            f"frac-context 已自动更新：{o.local} → {o.latest}（{len(o.files)} 个文件：{shown}{gone}）。",
            "  这次命令还是旧版跑的，下一次起用新版；规矩可能有变，先重读 SKILL.md。",
            "  这些文件请跟你这次的改动一起提交，仓库里的副本就跟上了。",
        ]
    if o.status == "available":
        return [f"frac-context 有新版 {o.latest}（本地 {o.local}）：python {script} update"]
    if o.status == "modified":
        return [
            f"frac-context 有新版 {o.latest}（本地 {o.local}），但本地改过 {'、'.join(o.files[:4])}，没有自动覆盖。",
            f"  确认要覆盖：python {script} update --force",
        ]
    if o.status == "missing" and o.checked_now:
        return ["frac-context 的更新来源找不到（404），kit 可能换了位置：设 FRAC_UPDATE_URL 指到新位置，或手动更新。"]
    if o.status == "failed" and o.checked_now:
        return [f"frac-context 发现新版 {o.latest}，但这次没换成（{o.detail}），先保留旧版，{RETRY_SECONDS // 60} 分钟后再试。"]
    return []


def display_path(script: Path) -> str:
    try:
        return os.path.relpath(str(script))
    except ValueError:
        return str(script)


def auto(script: Path) -> List[str]:
    """frac.py 每个命令跑完都会调；不抛异常，不该说话的时候不说话。"""
    try:
        how = mode()
        if how == "off":
            return []
        outcome = run(skill_dir_for(script), how=how)
        if outcome.status in {"available", "modified"} and not _notify_due(outcome):
            return []
        return notes(outcome, display_path(script))
    except Exception:
        return []


# ---------- commands: update / version / manifest ----------


def explicit(script: Path, check_only: bool = False, force: bool = False) -> Tuple[int, List[str]]:
    o = run(skill_dir_for(script), how="notify" if check_only else "auto", force=force, use_cache=False)
    where = " / ".join(sources())
    if o.status == "not-skill":
        return 2, ["这个 frac.py 不在 frac-context 的 skill 目录（<skill>/scripts/）里，不能自更新。"]
    if o.status == "current":
        return 0, [f"已是最新：本地 {o.local}，上游 {o.latest}。"]
    if o.status == "available":
        return 0, [f"有新版 {o.latest}（本地 {o.local}）；去掉 --check 就会更新。"]
    if o.status == "missing":
        return 2, [f"更新来源找不到（404）：{where}"]
    if o.status == "error":
        return 2, [f"连不上更新来源（或内容不对）：{where}"]
    if o.status == "failed":
        return 2, [f"没换成，保留旧版：{o.detail}"]
    if o.status == "modified":
        return 1, notes(o, display_path(script))
    if o.status == "updated" and not o.files and not o.removed:
        return 0, [f"文件本来就和 {o.latest} 一样，只更新了 manifest.json。"]
    return 0, notes(o, display_path(script))


def describe(script: Path) -> List[str]:
    skill_dir = skill_dir_for(script)
    lines = [
        f"frac-context {FRAC_VERSION}",
        f"skill 目录：{skill_dir if skill_dir else '（不在 skill 目录里，不会自更新）'}",
        f"自动更新：{mode()}（FRAC_UPDATE=auto / notify / off）",
        f"来源：{sources()[0]}",
    ]
    entry = load_cache().get(sources()[0])
    if entry:
        hours = (time.time() - float(entry.get("checked_at") or 0)) / 3600
        lines.append(f"上次检查：约 {hours:.1f} 小时前，结果 {entry.get('status')}，上游 {entry.get('latest')}")
    if skill_dir:
        modified = local_modifications(skill_dir, read_local_manifest(skill_dir))
        if modified:
            lines.append(f"本地改过：{'、'.join(modified)}（不会自动覆盖）")
    return lines


def manifest_report(skill_dir: Path, write: bool = False) -> Tuple[int, List[str]]:
    """维护者用：发版前生成 manifest.json；不带 --write 只检查它和文件是否一致。"""
    want = build_manifest(skill_dir)
    path = skill_dir / MANIFEST_NAME
    if write:
        path.write_bytes(manifest_bytes(want))
        return 0, [f"写好了：{path}（{FRAC_VERSION}，{len(want['files'])} 个文件）"]  # type: ignore[arg-type]
    try:
        have = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        have = None
    if have == want:
        return 0, [f"manifest.json 与文件一致（{FRAC_VERSION}）。"]
    return 1, ["manifest.json 与文件不一致：改了文件或版本号之后，要跑 frac.py manifest --write。"]
