#!/usr/bin/env python3
"""Smoke tests for frac.py. Standard library only."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRAC = ROOT / ".claude" / "skills" / "frac-context" / "scripts" / "frac.py"


def run(args, cwd):
    result = subprocess.run(
        [sys.executable, str(FRAC), *args],
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise AssertionError(f"command failed: {args}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
    return result.stdout


def main():
    with tempfile.TemporaryDirectory() as td:
        project = Path(td) / "project"
        project.mkdir()
        (project / "README.md").write_text("# Demo\n", encoding="utf-8")
        (project / "src" / "auth").mkdir(parents=True)
        (project / "src" / "main.py").write_text("print('hi')\n", encoding="utf-8")
        (project / "src" / "auth" / "login.py").write_text("def login(): pass\n", encoding="utf-8")

        out = run(["init", "."], project)
        assert ".frac.md" in out
        assert (project / ".frac.md").exists()
        assert (project / "src" / ".frac.md").exists()
        assert (project / "src" / "auth" / ".frac.md").exists()

        plan = run(["plan", "."], project)
        assert "src/auth" in plan
        assert "src" in plan
        assert "." in plan

        inputs = run(["inputs", "src/auth"], project)
        assert "src/auth/login.py" in inputs
        assert "DIRECT FILES" in inputs

        chain = run(["chain", "src/auth/login.py"], project)
        assert ".frac.md" in chain
        assert "src/.frac.md" in chain
        assert "src/auth/.frac.md" in chain

        stamp_for_clone = run(["stamp_for_clone", "."], project)
        assert "touched" in stamp_for_clone

        status = run(["status", "."], project)
        assert "fresh" in status

    print("ok")


if __name__ == "__main__":
    main()
