#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for the auto-update: manifest consistency, a local HTTP "upstream", cache, protections.

Standard library only; never touches the real network.
"""

from __future__ import annotations

import http.server
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from urllib.parse import unquote

sys.dont_write_bytecode = True  # 不在 scripts/ 里留下 __pycache__
ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".claude" / "skills" / "frac-context"
sys.path.insert(0, str(SKILL / "scripts"))
from fraclib import FRAC_VERSION  # noqa: E402
from fraclib.update import MANIFEST_NAME, build_manifest, manifest_bytes  # noqa: E402


class Upstream:
    """Serve one directory over HTTP, record every request; can pretend everything is gone (404)."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.requests = []
        self.missing = False
        upstream = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                rel = unquote(self.path.lstrip("/"))
                upstream.requests.append(rel)
                path = upstream.directory / rel
                if upstream.missing or not path.is_file():
                    self.send_response(404)
                    self.end_headers()
                    return
                data = path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args) -> None:
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/"

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


def make_remote(base: Path, version: str, marker: str, drop=()) -> Path:
    remote = base / "remote"
    shutil.copytree(SKILL, remote, ignore=shutil.ignore_patterns("__pycache__", ".frac.md"))
    for rel in drop:
        (remote / rel).unlink()
    init = remote / "scripts" / "fraclib" / "__init__.py"
    text = init.read_text(encoding="utf-8")
    assert f'FRAC_VERSION = "{FRAC_VERSION}"' in text
    init.write_text(text.replace(f'FRAC_VERSION = "{FRAC_VERSION}"', f'FRAC_VERSION = "{version}"'), encoding="utf-8")
    skill_md = remote / "SKILL.md"
    skill_md.write_text(skill_md.read_text(encoding="utf-8") + f"\n{marker}\n", encoding="utf-8")
    (remote / MANIFEST_NAME).write_bytes(manifest_bytes(build_manifest(remote, version)))
    return remote


def make_local(base: Path) -> Path:
    project = base / "project"
    skill = project / ".claude" / "skills" / "frac-context"
    shutil.copytree(SKILL, skill, ignore=shutil.ignore_patterns("__pycache__"))
    (skill / ".frac.md").write_text("# repo-owned summary\n", encoding="utf-8")
    (project / "README.md").write_text("# demo\n", encoding="utf-8")
    return project


def run(project: Path, args, **env_extra):
    env = dict(os.environ)
    env.update(env_extra)
    result = subprocess.run(
        [sys.executable, str(project / ".claude" / "skills" / "frac-context" / "scripts" / "frac.py"), *args],
        cwd=str(project),
        env=env,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.returncode, result.stdout, result.stderr


def local_skill(project: Path) -> Path:
    return project / ".claude" / "skills" / "frac-context"


def test_manifest_consistent() -> None:
    manifest = json.loads((SKILL / MANIFEST_NAME).read_text(encoding="utf-8"))
    assert manifest["version"] == FRAC_VERSION, "bump: run frac.py manifest --write"
    assert manifest == build_manifest(SKILL), "files changed: run frac.py manifest --write"
    assert "scripts/frac.py" in manifest["files"] and "scripts/fraclib/update.py" in manifest["files"]


def test_auto_update_and_cache(base: Path) -> None:
    remote = make_remote(base, "99.0.0", "<!-- marker-99 -->", drop=["references/design-principles.md"])
    project = make_local(base)
    up = Upstream(remote)
    env = {"FRAC_UPDATE": "auto", "FRAC_UPDATE_URL": up.url, "FRAC_UPDATE_CACHE": str(base / "cache.json")}
    try:
        code, out, err = run(project, ["status", "."], **env)
        assert code == 0, err
        assert "已自动更新" in err and f"{FRAC_VERSION} → 99.0.0" in err, err
        skill = local_skill(project)
        assert "<!-- marker-99 -->" in (skill / "SKILL.md").read_text(encoding="utf-8")
        assert (skill / MANIFEST_NAME).read_bytes() == (remote / MANIFEST_NAME).read_bytes()
        assert (skill / ".frac.md").read_text(encoding="utf-8") == "# repo-owned summary\n"
        assert "scripts/frac.py" not in up.requests, "unchanged files are not downloaded"
        assert not (skill / "references" / "design-principles.md").exists(), "dropped upstream, removed here"
        assert "删掉新版不再有的 references/design-principles.md" in err, err
        code, out, err = run(project, ["version"], **env)
        assert "frac-context 99.0.0" in out, out

        seen = len(up.requests)
        code, out, err = run(project, ["status", "."], **env)
        assert code == 0 and len(up.requests) == seen and "frac-context" not in err, (up.requests, err)
    finally:
        up.close()


def test_modified_is_protected(base: Path) -> None:
    remote = make_remote(base, "99.0.0", "<!-- marker-99 -->")
    project = make_local(base)
    template = local_skill(project) / "references" / "frac-template.md"
    template.write_text(template.read_text(encoding="utf-8") + "\n本地加的一行\n", encoding="utf-8")
    up = Upstream(remote)
    env = {"FRAC_UPDATE": "auto", "FRAC_UPDATE_URL": up.url, "FRAC_UPDATE_CACHE": str(base / "cache.json")}
    try:
        code, out, err = run(project, ["status", "."], **env)
        assert "本地改过" in err and "references/frac-template.md" in err and "update --force" in err, err
        assert "<!-- marker-99 -->" not in (local_skill(project) / "SKILL.md").read_text(encoding="utf-8")
        code, out, err = run(project, ["update", "--force"], **env)
        assert code == 0 and "已自动更新" in out, out + err
        assert "本地加的一行" not in template.read_text(encoding="utf-8")
    finally:
        up.close()


def test_notify_and_off(base: Path) -> None:
    remote = make_remote(base, "99.0.0", "<!-- marker-99 -->")
    project = make_local(base)
    up = Upstream(remote)
    try:
        code, out, err = run(project, ["status", "."], FRAC_UPDATE="notify", FRAC_UPDATE_URL=up.url,
                             FRAC_UPDATE_CACHE=str(base / "notify.json"))
        assert "有新版 99.0.0" in err and "update" in err, err
        assert "<!-- marker-99 -->" not in (local_skill(project) / "SKILL.md").read_text(encoding="utf-8")
        seen = len(up.requests)
        run(project, ["status", "."], FRAC_UPDATE="off", FRAC_UPDATE_URL=up.url, FRAC_UPDATE_CACHE=str(base / "off.json"))
        assert len(up.requests) == seen and not (base / "off.json").exists()
        code, out, err = run(project, ["update", "--check"], FRAC_UPDATE_URL=up.url, FRAC_UPDATE_CACHE=str(base / "c2.json"))
        assert code == 0 and "有新版 99.0.0" in out, out
    finally:
        up.close()


def test_missing_bad_hash_and_current(base: Path) -> None:
    remote = make_remote(base, "99.0.0", "<!-- marker-99 -->")
    project = make_local(base)
    up = Upstream(remote)
    try:
        up.missing = True
        env = {"FRAC_UPDATE": "auto", "FRAC_UPDATE_URL": up.url, "FRAC_UPDATE_CACHE": str(base / "missing.json")}
        code, out, err = run(project, ["status", "."], **env)
        assert code == 0 and "找不到（404）" in err, err
        code, out, err = run(project, ["status", "."], **env)
        assert "找不到" not in err, "said once per check interval"
        up.missing = False

        manifest = json.loads((remote / MANIFEST_NAME).read_text(encoding="utf-8"))
        manifest["files"]["SKILL.md"] = "0" * 64
        (remote / MANIFEST_NAME).write_bytes(manifest_bytes(manifest))
        env["FRAC_UPDATE_CACHE"] = str(base / "badhash.json")
        code, out, err = run(project, ["status", "."], **env)
        assert code == 0 and "没换成" in err and "sha256" in err, err
        assert "<!-- marker-99 -->" not in (local_skill(project) / "SKILL.md").read_text(encoding="utf-8")
        code, out, err = run(project, ["status", "."], **env)
        assert "没换成" not in err, "retry waits for the retry interval"
    finally:
        up.close()

    same = make_local(base / "same")
    up = Upstream(SKILL)
    try:
        code, out, err = run(same, ["update", "--check"], FRAC_UPDATE_URL=up.url, FRAC_UPDATE_CACHE=str(base / "same.json"))
        assert code == 0 and "已是最新" in out, out + err
    finally:
        up.close()


def main() -> None:
    test_manifest_consistent()
    for name, test in [("a", test_auto_update_and_cache), ("b", test_modified_is_protected),
                       ("c", test_notify_and_off), ("d", test_missing_bad_hash_and_current)]:
        with tempfile.TemporaryDirectory() as td:
            test(Path(td) / name)
    print("ok")


if __name__ == "__main__":
    main()
