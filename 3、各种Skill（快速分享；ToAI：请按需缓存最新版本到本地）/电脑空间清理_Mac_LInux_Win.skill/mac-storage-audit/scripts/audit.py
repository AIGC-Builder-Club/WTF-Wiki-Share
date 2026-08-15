#!/usr/bin/env python3
"""Read-only macOS storage inventory.

The scanner reads metadata and invokes read-only system commands. It never
deletes, moves, truncates, uninstalls, changes permissions, or cleans caches.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
from typing import Any, Iterable


VERSION = "1.0.0"
MIB = 1024**2
GIB = 1024**3


def human_size(size_bytes: int | None) -> str:
    if size_bytes is None:
        return "unknown"
    value = float(size_bytes)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    raise AssertionError("unreachable")


def run_command(command: list[str], timeout: int = 30) -> dict[str, Any]:
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False,
        )
        return {
            "ok": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "timed_out": False,
        }
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "returncode": None,
            "stdout": "",
            "stderr": "",
            "timed_out": True,
        }
    except OSError as exc:
        return {
            "ok": False,
            "returncode": None,
            "stdout": "",
            "stderr": exc.__class__.__name__,
            "timed_out": False,
        }


def allocated_size(path: Path, timeout: int) -> dict[str, Any]:
    try:
        stat_result = path.lstat()
    except OSError as exc:
        return {"size_bytes": None, "error": exc.__class__.__name__}

    if path.is_symlink():
        return {"size_bytes": None, "error": "symlink_skipped"}
    if not path.is_dir():
        blocks = getattr(stat_result, "st_blocks", 0)
        size_bytes = blocks * 512 if blocks else stat_result.st_size
        return {"size_bytes": size_bytes, "partial": False}

    result = run_command(["/usr/bin/du", "-sk", str(path)], timeout=timeout)
    parsed_kib: int | None = None
    for line in result["stdout"].splitlines():
        field = line.lstrip().split(None, 1)
        if field and field[0].isdigit():
            parsed_kib = int(field[0])
    if parsed_kib is None:
        error = "timeout" if result["timed_out"] else "unreadable"
        return {"size_bytes": None, "error": error}
    return {
        "size_bytes": parsed_kib * 1024,
        "partial": not result["ok"],
    }


def measured_item(path: Path, timeout: int, **fields: Any) -> dict[str, Any]:
    measurement = allocated_size(path, timeout)
    item: dict[str, Any] = {
        "name": path.name or str(path),
        "path": str(path),
        **fields,
        **measurement,
    }
    item["size"] = human_size(item.get("size_bytes"))
    return item


def scan_children(
    root: Path,
    *,
    min_bytes: int,
    top: int,
    workers: int,
    timeout: int,
    exclude: Iterable[str] = (),
) -> dict[str, Any]:
    excluded = set(exclude)
    try:
        entries = [
            Path(entry.path)
            for entry in os.scandir(root)
            if entry.name not in excluded and not entry.is_symlink()
        ]
    except OSError as exc:
        return {
            "root": str(root),
            "items": [],
            "scanned_count": 0,
            "error": exc.__class__.__name__,
        }

    items: list[dict[str, Any]] = []
    errors: dict[str, int] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        future_map = {
            pool.submit(measured_item, path, timeout): path for path in entries
        }
        for future in concurrent.futures.as_completed(future_map):
            try:
                item = future.result()
            except Exception as exc:  # Keep one bad path from losing the audit.
                key = exc.__class__.__name__
                errors[key] = errors.get(key, 0) + 1
                continue
            error = item.get("error")
            if error:
                errors[error] = errors.get(error, 0) + 1
                continue
            if item["size_bytes"] >= min_bytes:
                items.append(item)

    items.sort(key=lambda row: row["size_bytes"], reverse=True)
    return {
        "root": str(root),
        "items": items[:top],
        "scanned_count": len(entries),
        "reported_count": min(len(items), top),
        "errors": errors,
    }


def known_path_rules(home: Path) -> list[dict[str, Any]]:
    return [
        {
            "id": "user_library_caches",
            "path": home / "Library/Caches",
            "decision": "recreatable",
            "confidence": "high",
            "reason": "Application caches; inspect large app-owned children.",
            "summary": "cache",
        },
        {
            "id": "xdg_cache",
            "path": home / ".cache",
            "decision": "recreatable",
            "confidence": "high",
            "reason": "CLI and developer caches; model downloads can be exceptions.",
            "summary": "cache",
        },
        {
            "id": "npm_cache",
            "path": home / ".npm",
            "decision": "recreatable",
            "confidence": "high",
            "reason": "npm content cache, temporary npx installs, and small logs.",
            "summary": "cache",
        },
        {
            "id": "google_updater_cache",
            "path": home / "Library/Application Support/Google/GoogleUpdater/crx_cache",
            "decision": "recreatable",
            "confidence": "high",
            "reason": "Downloaded Chrome extension update packages.",
            "summary": "cache",
        },
        {
            "id": "downloads",
            "path": home / "Downloads",
            "decision": "review",
            "confidence": "owner",
            "reason": "User-owned downloads and possible installers.",
        },
        {
            "id": "user_logs",
            "path": home / "Library/Logs",
            "decision": "review",
            "confidence": "medium",
            "reason": "Logs may be useful for active troubleshooting.",
        },
        {
            "id": "trash",
            "path": home / ".Trash",
            "decision": "review",
            "confidence": "owner",
            "reason": "User data until inspected; emptying is a separate action.",
        },
        {
            "id": "opencode_state",
            "path": home / ".local/share/opencode",
            "decision": "review",
            "confidence": "low",
            "reason": "Active application database, storage, sessions, and binaries.",
        },
        {
            "id": "vscode_extensions",
            "path": home / ".vscode/extensions",
            "decision": "review",
            "confidence": "medium",
            "reason": "Installed editor extensions; use the editor lifecycle.",
        },
        {
            "id": "antigravity_extensions",
            "path": home / ".antigravity/extensions",
            "decision": "review",
            "confidence": "medium",
            "reason": "Installed editor extensions; use the editor lifecycle.",
        },
        {
            "id": "kiro_extensions",
            "path": home / ".kiro/extensions",
            "decision": "review",
            "confidence": "medium",
            "reason": "Installed editor extensions; use the editor lifecycle.",
        },
        {
            "id": "node_runtimes",
            "path": home / ".local/share/fnm",
            "decision": "review",
            "confidence": "medium",
            "reason": "Installed Node.js versions, not a cache by default.",
        },
        {
            "id": "rust_toolchains",
            "path": home / ".rustup",
            "decision": "review",
            "confidence": "medium",
            "reason": "Installed Rust toolchains, not a cache by default.",
        },
        {
            "id": "multica_workspaces",
            "path": home / "multica_workspaces",
            "decision": "managed",
            "confidence": "high",
            "reason": "Multica task lifecycle data; never remove manually.",
        },
        {
            "id": "system_updates",
            "path": Path("/Library/Updates"),
            "decision": "managed",
            "confidence": "high",
            "reason": "macOS update staging; leave to Software Update.",
        },
        {
            "id": "system_temp",
            "path": Path("/private/var/folders"),
            "decision": "managed",
            "confidence": "high",
            "reason": "macOS-managed caches and temporary data.",
        },
        {
            "id": "command_line_tools",
            "path": Path("/Library/Developer/CommandLineTools"),
            "decision": "managed",
            "confidence": "high",
            "reason": "Installed developer toolchain, not cache data.",
        },
    ]


def measure_known_paths(home: Path, workers: int, timeout: int) -> list[dict[str, Any]]:
    rules = [rule for rule in known_path_rules(home) if rule["path"].exists()]
    items: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        future_map = {
            pool.submit(
                measured_item,
                rule["path"],
                timeout,
                id=rule["id"],
                decision=rule["decision"],
                confidence=rule["confidence"],
                reason=rule["reason"],
                summary=rule.get("summary"),
            ): rule
            for rule in rules
        }
        for future in concurrent.futures.as_completed(future_map):
            items.append(future.result())
    items.sort(key=lambda row: row.get("size_bytes") or -1, reverse=True)
    return items


def scan_codex_data(home: Path, workers: int, timeout: int) -> list[dict[str, Any]]:
    targets: list[tuple[Path, str, str]] = []
    try:
        homes = [
            path
            for path in home.iterdir()
            if path.is_dir() and (path.name == ".codex" or path.name.startswith(".codex_"))
        ]
    except OSError:
        return []

    for codex_home in homes:
        try:
            children = list(codex_home.iterdir())
        except OSError:
            continue
        for child in children:
            if child.name.startswith("backup-"):
                targets.append((child, "backup", "Migration or repair restore point."))
            elif child.name in {"sessions", "archived_sessions"}:
                targets.append((child, "history", "Conversation and run history."))
            elif child.name.startswith("logs_") and child.suffix == ".sqlite":
                targets.append((child, "database", "Application database; may be active."))
            elif child.name == ".tmp":
                targets.append((child, "temporary", "App-owned temporary state; confirm app is closed."))

    items: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [
            pool.submit(
                measured_item,
                path,
                timeout,
                decision="review",
                subtype=subtype,
                reason=reason,
            )
            for path, subtype, reason in targets
        ]
        for future in concurrent.futures.as_completed(futures):
            items.append(future.result())
    items.sort(key=lambda row: row.get("size_bytes") or -1, reverse=True)
    return items


PROJECT_RULES: dict[str, tuple[str, str, str]] = {
    ".next": ("recreatable", "high", "Framework build output."),
    ".turbo": ("recreatable", "high", "Turborepo build cache."),
    ".pytest_cache": ("recreatable", "high", "Test runner cache."),
    ".mypy_cache": ("recreatable", "high", "Type-checker cache."),
    ".ruff_cache": ("recreatable", "high", "Linter cache."),
    "node_modules": ("review", "medium", "Requires a valid lockfile and package manager."),
    ".venv": ("review", "medium", "Requires a reproducible dependency manifest."),
    "venv": ("review", "medium", "Requires a reproducible dependency manifest."),
    "target": ("review", "medium", "Generated Rust output, but rebuild cost can be high."),
}


def discover_project_artifacts(project_roots: list[Path]) -> list[tuple[Path, Path]]:
    discovered: dict[str, tuple[Path, Path]] = {}
    ignored = {".git", ".svn", ".hg", ".Trash", "Library"}
    for project_root in project_roots:
        if not project_root.is_dir():
            continue
        try:
            root_device = project_root.stat().st_dev
        except OSError:
            continue
        for current, dirs, _files in os.walk(project_root, topdown=True, followlinks=False):
            current_path = Path(current)
            try:
                if current_path.stat().st_dev != root_device:
                    dirs[:] = []
                    continue
            except OSError:
                dirs[:] = []
                continue

            retained: list[str] = []
            for name in dirs:
                candidate = current_path / name
                if name in PROJECT_RULES:
                    key = str(candidate)
                    discovered[key] = (candidate, project_root)
                elif name not in ignored:
                    retained.append(name)
            dirs[:] = retained
    return list(discovered.values())


def scan_project_artifacts(
    project_roots: list[Path], workers: int, timeout: int
) -> list[dict[str, Any]]:
    targets = discover_project_artifacts(project_roots)
    items: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = []
        for path, project_root in targets:
            decision, confidence, reason = PROJECT_RULES[path.name]
            futures.append(
                pool.submit(
                    measured_item,
                    path,
                    timeout,
                    project_root=str(project_root),
                    decision=decision,
                    confidence=confidence,
                    reason=reason,
                )
            )
        for future in concurrent.futures.as_completed(futures):
            items.append(future.result())
    items.sort(key=lambda row: row.get("size_bytes") or -1, reverse=True)
    return items


def system_inventory() -> dict[str, Any]:
    os_version = run_command(["/usr/bin/sw_vers", "-productVersion"])["stdout"].strip()
    build = run_command(["/usr/bin/sw_vers", "-buildVersion"])["stdout"].strip()
    model = run_command(["/usr/sbin/sysctl", "-n", "hw.model"])["stdout"].strip()
    total, used, free = shutil.disk_usage("/")

    data_volume: dict[str, Any] = {}
    df_result = run_command(["/bin/df", "-k", "/System/Volumes/Data"])
    lines = [line for line in df_result["stdout"].splitlines() if line.strip()]
    if len(lines) >= 2:
        fields = lines[-1].split()
        if len(fields) >= 4 and all(value.isdigit() for value in fields[1:4]):
            data_volume = {
                "total_bytes": int(fields[1]) * 1024,
                "used_bytes": int(fields[2]) * 1024,
                "available_bytes": int(fields[3]) * 1024,
            }
            data_volume.update(
                {
                    "total": human_size(data_volume["total_bytes"]),
                    "used": human_size(data_volume["used_bytes"]),
                    "available": human_size(data_volume["available_bytes"]),
                }
            )

    snapshots_result = run_command(["/usr/bin/tmutil", "listlocalsnapshots", "/"])
    snapshot_lines = [
        line.strip()
        for line in snapshots_result["stdout"].splitlines()
        if line.strip() and not line.startswith("Snapshots for disk")
    ]
    return {
        "os": f"macOS {os_version}" if os_version else "macOS",
        "build": build,
        "architecture": platform.machine(),
        "model": model,
        "container": {
            "total_bytes": total,
            "used_bytes": used,
            "free_bytes": free,
            "total": human_size(total),
            "used": human_size(used),
            "free": human_size(free),
            "used_percent": round((used / total) * 100, 1) if total else None,
        },
        "data_volume": data_volume,
        "time_machine_local_snapshots": snapshot_lines,
    }


def multica_inventory() -> dict[str, Any]:
    executable = shutil.which("multica")
    if not executable:
        return {"available": False, "reason": "multica_not_found"}
    result = run_command(
        [executable, "daemon", "disk-usage", "--by-workspace", "--output", "json"],
        timeout=45,
    )
    if not result["stdout"].strip():
        return {"available": False, "reason": "disk_usage_unavailable"}
    try:
        raw = json.loads(result["stdout"])
    except json.JSONDecodeError:
        return {"available": False, "reason": "invalid_json"}
    fields = (
        "total_task_count",
        "total_workspace_count",
        "total_size_bytes",
        "total_artifact_size_bytes",
        "repo_cache_size_bytes",
        "repo_cache_count",
        "artifact_patterns",
    )
    inventory = {key: raw.get(key) for key in fields}
    for key in ("total_size_bytes", "total_artifact_size_bytes", "repo_cache_size_bytes"):
        inventory[key.removesuffix("_bytes")] = human_size(inventory.get(key))
    inventory["available"] = True
    inventory["decision"] = "managed"
    inventory["reason"] = "Use Multica lifecycle and retention; never remove task paths manually."
    return inventory


def sum_bytes(items: Iterable[dict[str, Any]], predicate: Any) -> int:
    return sum(
        item.get("size_bytes") or 0
        for item in items
        if predicate(item) and item.get("error") is None
    )


def summarize(
    known: list[dict[str, Any]],
    codex: list[dict[str, Any]],
    artifacts: list[dict[str, Any]],
    multica: dict[str, Any],
) -> dict[str, Any]:
    cache_bytes = sum_bytes(known, lambda item: item.get("summary") == "cache")
    project_generated = sum_bytes(
        artifacts, lambda item: item.get("decision") == "recreatable"
    )
    project_conditional = sum_bytes(
        artifacts, lambda item: item.get("decision") == "review"
    )
    codex_backup = sum_bytes(codex, lambda item: item.get("subtype") == "backup")
    codex_history = sum_bytes(codex, lambda item: item.get("subtype") == "history")
    codex_database = sum_bytes(codex, lambda item: item.get("subtype") == "database")
    summary = {
        "identified_recreatable_cache_bytes": cache_bytes,
        "identified_recreatable_cache": human_size(cache_bytes),
        "project_generated_output_bytes": project_generated,
        "project_generated_output": human_size(project_generated),
        "conditional_project_dependencies_bytes": project_conditional,
        "conditional_project_dependencies": human_size(project_conditional),
        "codex_backup_bytes": codex_backup,
        "codex_backups": human_size(codex_backup),
        "codex_history_bytes": codex_history,
        "codex_history": human_size(codex_history),
        "codex_database_bytes": codex_database,
        "codex_databases": human_size(codex_database),
        "sizes_are_non_additive": True,
    }
    if multica.get("available"):
        summary["multica_managed_bytes"] = multica.get("total_size_bytes", 0)
        summary["multica_managed"] = human_size(multica.get("total_size_bytes", 0))
    return summary


def markdown_path(value: str) -> str:
    return "`" + value.replace("`", "\\`") + "`"


def render_markdown(data: dict[str, Any]) -> str:
    system = data["system"]
    summary = data["summary"]
    lines = [
        "# Read-only Mac storage audit",
        "",
        f"Generated: {data['generated_at']}",
        "",
        "## Disk health",
        "",
        f"- System: {system['os']} ({system['architecture']}, {system['model']})",
        f"- APFS/container: {system['container']['used']} used of "
        f"{system['container']['total']}; {system['container']['free']} free "
        f"({system['container']['used_percent']}% used)",
        f"- Time Machine local snapshots found: {len(system['time_machine_local_snapshots'])}",
        "",
        "Sizes below are measured candidates, not guaranteed reclaimed space. "
        "Do not add them blindly because APFS clones and overlapping rollups are non-additive.",
        "",
        "## Decision summary",
        "",
        "| Group | Measured size | Decision |",
        "|---|---:|---|",
        f"| Known recreatable caches | {summary['identified_recreatable_cache']} | Validate app ownership; close apps |",
        f"| Generated project output | {summary['project_generated_output']} | Inactive projects only |",
        f"| Project dependencies/environments | {summary['conditional_project_dependencies']} | Require lockfiles/manifests |",
        f"| Codex migration/repair backups | {summary['codex_backups']} | Manual retention decision |",
        f"| Codex session history | {summary['codex_history']} | User history; app-managed |",
        f"| Codex databases | {summary['codex_databases']} | Active state; app-managed |",
    ]
    if "multica_managed" in summary:
        lines.append(
            f"| Multica task directories | {summary['multica_managed']} | Multica-managed lifecycle |"
        )

    lines.extend(
        [
            "",
            "## Known paths",
            "",
            "| Size | Decision | Confidence | Path | Reason |",
            "|---:|---|---|---|---|",
        ]
    )
    for item in data["known_paths"]:
        lines.append(
            f"| {item['size']} | {item['decision']} | {item['confidence']} | "
            f"{markdown_path(item['path'])} | {item['reason']} |"
        )

    lines.extend(["", "## Largest home entries", ""])
    for item in data["groups"]["home"]["items"]:
        suffix = " (partial)" if item.get("partial") else ""
        lines.append(f"- {item['size']}{suffix}: {markdown_path(item['path'])}")

    lines.extend(["", "## Largest project artifacts", ""])
    if data["project_artifacts"]:
        for item in data["project_artifacts"][:30]:
            lines.append(
                f"- {item['size']} [{item['decision']}]: {markdown_path(item['path'])}"
            )
    else:
        lines.append("- No project artifact roots were supplied or no matches were found.")

    lines.extend(
        [
            "",
            "## Coverage",
            "",
            "- Protected macOS data can be absent or partial without Full Disk Access.",
            "- The scanner did not use sudo and did not inspect file contents.",
            "- Container and group-container detail is included only with `--deep`.",
            "- No cleanup, move, uninstall, or permission-changing action was executed.",
            "",
        ]
    )
    return "\n".join(lines)


def default_project_roots(home: Path) -> list[Path]:
    candidates = [home / name for name in ("Projects", "Developer", "Code", "src", "work")]
    return [path for path in candidates if path.is_dir()]


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--output", type=Path, help="Write only the report to this explicit path.")
    parser.add_argument("--project-root", action="append", type=Path, default=[])
    parser.add_argument("--top", type=int, default=40)
    parser.add_argument("--min-mib", type=int, default=50)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--timeout", type=int, default=20, help="Per-path du timeout in seconds.")
    parser.add_argument(
        "--deep",
        action="store_true",
        help="Also scan top-level app containers; can be slow and TCC-limited.",
    )
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args(argv)


def self_test() -> None:
    assert human_size(0) == "0 B"
    assert human_size(1024) == "1.0 KiB"
    assert human_size(GIB) == "1.0 GiB"
    assert PROJECT_RULES[".next"][0] == "recreatable"
    assert PROJECT_RULES["node_modules"][0] == "review"
    print("self-test: ok")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if args.self_test:
        self_test()
        return 0
    if sys.platform != "darwin":
        print(json.dumps({"error": "unsupported_platform", "platform": sys.platform}))
        return 2
    if args.top < 1 or args.min_mib < 0 or not 1 <= args.workers <= 32 or args.timeout < 1:
        raise SystemExit("invalid scan limits")

    started = time.monotonic()
    home = args.home.expanduser().resolve()
    project_roots = [path.expanduser().resolve() for path in args.project_root]
    if not project_roots:
        project_roots = default_project_roots(home)

    groups = {
        "home": scan_children(
            home,
            min_bytes=args.min_mib * MIB,
            top=args.top,
            workers=args.workers,
            timeout=args.timeout,
            exclude={"Library", ".Trash"},
        ),
        "library_caches": scan_children(
            home / "Library/Caches",
            min_bytes=args.min_mib * MIB,
            top=args.top,
            workers=args.workers,
            timeout=args.timeout,
        ),
        "application_support": scan_children(
            home / "Library/Application Support",
            min_bytes=args.min_mib * MIB,
            top=args.top,
            workers=args.workers,
            timeout=args.timeout,
        ),
        "applications": scan_children(
            Path("/Applications"),
            min_bytes=args.min_mib * MIB,
            top=args.top,
            workers=args.workers,
            timeout=args.timeout,
        ),
    }
    if args.deep:
        groups["containers"] = scan_children(
            home / "Library/Containers",
            min_bytes=args.min_mib * MIB,
            top=args.top,
            workers=args.workers,
            timeout=args.timeout,
        )
        groups["group_containers"] = scan_children(
            home / "Library/Group Containers",
            min_bytes=args.min_mib * MIB,
            top=args.top,
            workers=args.workers,
            timeout=args.timeout,
        )

    known = measure_known_paths(home, args.workers, args.timeout)
    codex = scan_codex_data(home, args.workers, args.timeout)
    artifacts = scan_project_artifacts(project_roots, args.workers, args.timeout)
    multica = multica_inventory()
    data = {
        "schema_version": 1,
        "scanner_version": VERSION,
        "read_only": True,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "scan_seconds": round(time.monotonic() - started, 2),
        "system": system_inventory(),
        "project_roots": [str(path) for path in project_roots],
        "groups": groups,
        "known_paths": known,
        "codex_data": codex,
        "project_artifacts": artifacts,
        "multica": multica,
        "summary": summarize(known, codex, artifacts, multica),
        "coverage": {
            "used_sudo": False,
            "read_file_contents": False,
            "tcc_protected_paths_may_be_missing": True,
            "deep_container_scan": args.deep,
        },
    }

    output = json.dumps(data, ensure_ascii=False, indent=2)
    if args.format == "markdown":
        output = render_markdown(data)
    if args.output:
        args.output.write_text(output + ("\n" if not output.endswith("\n") else ""), encoding="utf-8")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
