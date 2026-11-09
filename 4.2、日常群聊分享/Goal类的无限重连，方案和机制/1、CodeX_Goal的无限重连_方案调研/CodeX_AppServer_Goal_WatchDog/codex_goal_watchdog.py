#!/usr/bin/env python3
"""Codex Goal watchdog for codex app-server (stdio transport).

Monitors one persisted Codex thread. When a goal becomes blocked by a retryable
transport/server error, waits with exponential backoff, probes connectivity, and
sets the existing goal status back to ``active``. It never replaces the goal
objective.

This script intentionally uses only the Python standard library.
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import fcntl
import json
import os
import queue
import random
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

VERSION = "0.1.0"
HIGH_VOLUME_NOTIFICATIONS = [
    "command/exec/outputDelta",
    "item/agentMessage/delta",
    "item/plan/delta",
    "item/fileChange/outputDelta",
    "item/reasoning/summaryTextDelta",
    "item/reasoning/textDelta",
]


class TransportClosed(RuntimeError):
    pass


class RpcError(RuntimeError):
    def __init__(self, code: int | None, message: str, data: Any = None) -> None:
        super().__init__(f"JSON-RPC error {code}: {message}")
        self.code = code
        self.message = message
        self.data = data


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def log(level: str, message: str, **fields: Any) -> None:
    suffix = ""
    if fields:
        suffix = " " + json.dumps(fields, ensure_ascii=False, sort_keys=True, default=str)
    print(f"{utc_now_iso()} [{level}] {message}{suffix}", flush=True)


class AppServerClient:
    """Minimal JSON-RPC client for ``codex app-server --listen stdio://``."""

    def __init__(
        self,
        command: list[str],
        *,
        auto_approve: bool = False,
        env: dict[str, str] | None = None,
    ) -> None:
        self.command = command
        self.auto_approve = auto_approve
        self.env = env
        self.proc: subprocess.Popen[str] | None = None
        self.pending: dict[str, queue.Queue[Any]] = {}
        self.pending_lock = threading.Lock()
        self.write_lock = threading.Lock()
        self.notifications: queue.Queue[dict[str, Any]] = queue.Queue()
        self.closed = threading.Event()
        self.stderr_tail: collections.deque[str] = collections.deque(maxlen=200)
        self.reader_thread: threading.Thread | None = None
        self.stderr_thread: threading.Thread | None = None

    def start(self) -> None:
        log("INFO", "starting codex app-server", command=self.command)
        self.proc = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
            env=self.env,
            start_new_session=True,
        )
        self.reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self.stderr_thread = threading.Thread(target=self._stderr_loop, daemon=True)
        self.reader_thread.start()
        self.stderr_thread.start()
        self.request(
            "initialize",
            {
                "clientInfo": {
                    "name": "codex_goal_watchdog",
                    "title": "Codex Goal Watchdog",
                    "version": VERSION,
                },
                "capabilities": {
                    "experimentalApi": True,
                    "optOutNotificationMethods": HIGH_VOLUME_NOTIFICATIONS,
                },
            },
            timeout=45,
        )
        self.notify("initialized", None)
        log("INFO", "app-server initialized")

    def close(self) -> None:
        proc = self.proc
        self.proc = None
        if proc is None:
            return
        try:
            if proc.stdin:
                proc.stdin.close()
        except Exception:
            pass
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        self.closed.set()
        self._fail_all_pending(TransportClosed("app-server closed"))

    def request(self, method: str, params: dict[str, Any] | None, *, timeout: float = 30) -> Any:
        if self.closed.is_set():
            raise TransportClosed("app-server transport is closed")
        request_id = str(uuid.uuid4())
        waiter: queue.Queue[Any] = queue.Queue(maxsize=1)
        with self.pending_lock:
            self.pending[request_id] = waiter
        payload: dict[str, Any] = {"id": request_id, "method": method}
        if params is not None:
            payload["params"] = params
        try:
            self._write(payload)
            try:
                item = waiter.get(timeout=timeout)
            except queue.Empty as exc:
                raise TimeoutError(f"timeout waiting for {method}") from exc
            if isinstance(item, BaseException):
                raise item
            if not isinstance(item, dict):
                raise RuntimeError(f"invalid response for {method}: {item!r}")
            if "error" in item:
                err = item.get("error") or {}
                raise RpcError(err.get("code"), str(err.get("message", "unknown error")), err.get("data"))
            return item.get("result")
        finally:
            with self.pending_lock:
                self.pending.pop(request_id, None)

    def notify(self, method: str, params: dict[str, Any] | None) -> None:
        payload: dict[str, Any] = {"method": method}
        if params is not None:
            payload["params"] = params
        self._write(payload)

    def _write(self, payload: dict[str, Any]) -> None:
        proc = self.proc
        if proc is None or proc.stdin is None or proc.poll() is not None:
            raise TransportClosed("app-server process is not running")
        line = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        with self.write_lock:
            proc.stdin.write(line + "\n")
            proc.stdin.flush()

    def _reader_loop(self) -> None:
        proc = self.proc
        if proc is None or proc.stdout is None:
            return
        try:
            for line in proc.stdout:
                line = line.rstrip("\n")
                if not line:
                    continue
                try:
                    message = json.loads(line)
                except json.JSONDecodeError:
                    log("WARN", "non-JSON line from app-server", line=line[:1000])
                    continue
                if not isinstance(message, dict):
                    continue
                if "method" in message and "id" in message:
                    self._handle_server_request(message)
                elif "method" in message:
                    self.notifications.put(message)
                elif "id" in message:
                    request_id = str(message["id"])
                    with self.pending_lock:
                        waiter = self.pending.get(request_id)
                    if waiter is not None:
                        waiter.put(message)
        except BaseException as exc:
            self._fail_all_pending(exc)
        finally:
            self.closed.set()
            tail = "\n".join(self.stderr_tail)
            error = TransportClosed(f"app-server stdout closed; stderr tail: {tail[-4000:]}")
            self._fail_all_pending(error)
            self.notifications.put({"method": "__transport_closed__", "params": {"error": str(error)}})

    def _stderr_loop(self) -> None:
        proc = self.proc
        if proc is None or proc.stderr is None:
            return
        for line in proc.stderr:
            line = line.rstrip("\n")
            self.stderr_tail.append(line)
            if os.environ.get("CODEX_WATCHDOG_DEBUG_APP_SERVER") == "1":
                log("DEBUG", "app-server stderr", line=line)

    def _handle_server_request(self, message: dict[str, Any]) -> None:
        method = str(message.get("method", ""))
        request_id = message.get("id")
        result: dict[str, Any]
        if method in {
            "item/commandExecution/requestApproval",
            "item/fileChange/requestApproval",
        }:
            decision = "accept" if self.auto_approve else "decline"
            result = {"decision": decision}
            log(
                "WARN",
                "responding to unattended approval request",
                method=method,
                decision=decision,
            )
        else:
            # Matches the official SDK's fallback behavior for unhandled requests.
            result = {}
            log("WARN", "unhandled server request", method=method)
        try:
            self._write({"id": request_id, "result": result})
        except Exception as exc:
            log("ERROR", "failed to answer server request", method=method, error=str(exc))

    def _fail_all_pending(self, exc: BaseException) -> None:
        with self.pending_lock:
            waiters = list(self.pending.values())
        for waiter in waiters:
            try:
                waiter.put_nowait(exc)
            except queue.Full:
                pass


@dataclass
class WatchState:
    consecutive_failures: int = 0
    next_attempt_at: float = 0.0
    last_attempt_at: float = 0.0
    last_success_at: float = 0.0
    last_reassert_at: float = 0.0
    last_goal_status: str | None = None
    last_error_kind: str | None = None
    last_error_message: str | None = None


class StateStore:
    def __init__(self, path: Path) -> None:
        self.path = path.expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> WatchState:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            allowed = set(WatchState.__dataclass_fields__)
            return WatchState(**{k: v for k, v in raw.items() if k in allowed})
        except FileNotFoundError:
            return WatchState()
        except Exception as exc:
            log("WARN", "failed to read state file; starting fresh", path=str(self.path), error=str(exc))
            return WatchState()

    def save(self, state: WatchState) -> None:
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        temp.write_text(json.dumps(asdict(state), indent=2, sort_keys=True), encoding="utf-8")
        os.replace(temp, self.path)


class SingleInstanceLock:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.file: Any = None

    def __enter__(self) -> "SingleInstanceLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.file = self.path.open("a+")
        try:
            fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError(f"another watchdog already holds {self.path}") from exc
        self.file.seek(0)
        self.file.truncate()
        self.file.write(str(os.getpid()))
        self.file.flush()
        return self

    def __exit__(self, _exc_type: Any, _exc: Any, _tb: Any) -> None:
        if self.file is not None:
            try:
                fcntl.flock(self.file.fileno(), fcntl.LOCK_UN)
            finally:
                self.file.close()


@dataclass
class RetryDecision:
    retryable: bool
    base_delay: float
    kind: str
    reason: str


NETWORK_MESSAGE_RE = re.compile(
    r"429|too many requests|stream disconnected|connection|network|dns|tls|timeout|timed out|"
    r"temporar(?:y|ily)|overload|502|503|504|econnreset|broken pipe",
    re.IGNORECASE,
)


def normalize_error_info(info: Any) -> tuple[str | None, dict[str, Any]]:
    if isinstance(info, str):
        return info, {}
    if isinstance(info, dict) and info:
        key = next(iter(info))
        details = info.get(key)
        return str(key), details if isinstance(details, dict) else {}
    return None, {}


def classify_failure(
    turn: dict[str, Any] | None,
    *,
    normal_base: float,
    rate_limit_base: float,
    allow_unknown: bool,
) -> RetryDecision:
    error = (turn or {}).get("error") if isinstance(turn, dict) else None
    if not isinstance(error, dict):
        return RetryDecision(
            allow_unknown,
            normal_base,
            "unknown",
            "no persisted turn error was available",
        )
    message = str(error.get("message") or "")
    kind, details = normalize_error_info(error.get("codexErrorInfo"))

    if kind == "responseTooManyFailedAttempts":
        status = details.get("httpStatusCode")
        if status == 429 or "429" in message:
            return RetryDecision(True, rate_limit_base, kind, "upstream 429 after internal retries")
        return RetryDecision(True, normal_base, kind, f"upstream retries exhausted (HTTP {status})")

    retryable_kinds = {
        "httpConnectionFailed",
        "responseStreamConnectionFailed",
        "responseStreamDisconnected",
        "internalServerError",
        "serverOverloaded",
    }
    if kind in retryable_kinds:
        return RetryDecision(True, normal_base, kind or "retryable", "transient transport/server error")

    non_retryable_kinds = {
        "contextWindowExceeded",
        "sessionBudgetExceeded",
        "usageLimitExceeded",
        "cyberPolicy",
        "unauthorized",
        "badRequest",
        "threadRollbackFailed",
        "sandboxError",
    }
    if kind in non_retryable_kinds:
        return RetryDecision(False, normal_base, kind or "nonRetryable", "requires user/configuration action")

    if NETWORK_MESSAGE_RE.search(message):
        base = rate_limit_base if ("429" in message or "too many requests" in message.lower()) else normal_base
        return RetryDecision(True, base, kind or "messageMatch", "error message looks transient")

    return RetryDecision(
        allow_unknown,
        normal_base,
        kind or "unknown",
        "unclassified error" if allow_unknown else "unknown errors are not auto-resumed",
    )


def exponential_delay(base: float, failures: int, maximum: float) -> float:
    exponent = max(0, min(failures, 20))
    raw = min(maximum, base * (2**exponent))
    return max(0.0, raw * random.uniform(0.85, 1.15))


def network_reachable(url: str, timeout: float) -> tuple[bool, str]:
    request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "codex-goal-watchdog/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return True, f"HTTP {response.status}"
    except urllib.error.HTTPError as exc:
        # Any HTTP response proves DNS/TCP/TLS and the route are reachable.
        return True, f"HTTP {exc.code}"
    except Exception as exc:
        return False, str(exc)


def last_turn_from_resume(result: dict[str, Any]) -> dict[str, Any] | None:
    page = result.get("initialTurnsPage")
    if isinstance(page, dict):
        data = page.get("data")
        if isinstance(data, list) and data:
            return data[0] if isinstance(data[0], dict) else None
    thread = result.get("thread")
    if isinstance(thread, dict):
        turns = thread.get("turns")
        if isinstance(turns, list) and turns:
            return turns[-1] if isinstance(turns[-1], dict) else None
    return None


def get_last_failed_turn(client: AppServerClient, thread_id: str) -> dict[str, Any] | None:
    try:
        result = client.request(
            "thread/read",
            {"threadId": thread_id, "includeTurns": True},
            timeout=90,
        )
        turns = (((result or {}).get("thread") or {}).get("turns") or [])
        if isinstance(turns, list):
            for turn in reversed(turns):
                if isinstance(turn, dict) and (turn.get("status") == "failed" or turn.get("error")):
                    return turn
    except Exception as exc:
        log("WARN", "could not read failed turn history", error=str(exc))
    return None


def resume_thread(
    client: AppServerClient,
    thread_id: str,
    *,
    approval_policy: str,
    sandbox: str,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    params: dict[str, Any] = {
        "threadId": thread_id,
        "excludeTurns": True,
        "initialTurnsPage": {"limit": 1, "sortDirection": "desc", "itemsView": "summary"},
    }
    if approval_policy != "preserve":
        params["approvalPolicy"] = approval_policy
    if sandbox != "preserve":
        params["sandbox"] = sandbox
    try:
        result = client.request("thread/resume", params, timeout=120)
    except RpcError as exc:
        # Compatibility fallback for a Codex build that predates experimental paging fields.
        if exc.code not in {-32600, -32602}:
            raise
        fallback: dict[str, Any] = {"threadId": thread_id}
        if approval_policy != "preserve":
            fallback["approvalPolicy"] = approval_policy
        if sandbox != "preserve":
            fallback["sandbox"] = sandbox
        log("WARN", "retrying thread/resume without experimental paging fields", error=exc.message)
        result = client.request("thread/resume", fallback, timeout=120)
    if not isinstance(result, dict):
        raise RuntimeError("thread/resume returned a non-object result")
    return result, last_turn_from_resume(result)


def get_goal(client: AppServerClient, thread_id: str) -> dict[str, Any] | None:
    result = client.request("thread/goal/get", {"threadId": thread_id}, timeout=30)
    if not isinstance(result, dict):
        return None
    goal = result.get("goal")
    return goal if isinstance(goal, dict) else None


def read_thread_status(client: AppServerClient, thread_id: str) -> dict[str, Any] | None:
    result = client.request(
        "thread/read", {"threadId": thread_id, "includeTurns": False}, timeout=45
    )
    if not isinstance(result, dict):
        return None
    thread = result.get("thread")
    if not isinstance(thread, dict):
        return None
    status = thread.get("status")
    return status if isinstance(status, dict) else None


def set_goal_active(client: AppServerClient, thread_id: str, *, dry_run: bool) -> dict[str, Any] | None:
    if dry_run:
        log("INFO", "dry-run: would set goal status to active", thread_id=thread_id)
        return None
    result = client.request(
        "thread/goal/set", {"threadId": thread_id, "status": "active"}, timeout=45
    )
    if isinstance(result, dict) and isinstance(result.get("goal"), dict):
        return result["goal"]
    return None


def list_threads(client: AppServerClient, limit: int) -> int:
    result = client.request(
        "thread/list",
        {
            "limit": limit,
            "sortKey": "updated_at",
            "sortDirection": "desc",
            "archived": False,
        },
        timeout=120,
    )
    rows = result.get("data", []) if isinstance(result, dict) else []
    print("\nRecent Codex threads:\n")
    print(f"{'UPDATED':19}  {'GOAL':13}  {'THREAD ID':36}  PREVIEW / CWD")
    print("-" * 120)
    for thread in rows:
        if not isinstance(thread, dict):
            continue
        thread_id = str(thread.get("id", ""))
        updated = thread.get("updatedAt") or thread.get("createdAt")
        stamp = "-"
        if isinstance(updated, (int, float)):
            stamp = dt.datetime.fromtimestamp(updated).strftime("%Y-%m-%d %H:%M")
        goal_status = "-"
        try:
            goal = get_goal(client, thread_id)
            if goal:
                goal_status = str(goal.get("status", "-"))
        except Exception:
            pass
        preview = str(thread.get("name") or thread.get("preview") or "").replace("\n", " ")[:55]
        cwd = str(thread.get("cwd") or "")
        print(f"{stamp:19}  {goal_status:13}  {thread_id:36}  {preview}")
        if cwd:
            print(f"{'':75}  {cwd}")
    return 0


def watch_session(client: AppServerClient, args: argparse.Namespace, store: StateStore) -> int:
    result, last_turn = resume_thread(
        client,
        args.thread,
        approval_policy=args.approval_policy,
        sandbox=args.sandbox,
    )
    thread = result.get("thread") if isinstance(result, dict) else None
    thread_status = thread.get("status") if isinstance(thread, dict) else None
    log(
        "INFO",
        "thread resumed and subscribed",
        thread_id=args.thread,
        thread_status=thread_status,
    )

    state = store.load()
    goal = get_goal(client, args.thread)
    if goal is None:
        log("ERROR", "thread has no persisted goal", thread_id=args.thread)
        return 2

    last_activity = time.time()
    next_poll = 0.0
    stop = False

    def request_stop(_signum: int, _frame: Any) -> None:
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    def persist_success() -> None:
        state.consecutive_failures = 0
        state.next_attempt_at = 0.0
        state.last_success_at = time.time()
        state.last_error_kind = None
        state.last_error_message = None
        store.save(state)

    while not stop:
        now = time.time()
        timeout = 1.0
        if next_poll > now:
            timeout = min(timeout, max(0.05, next_poll - now))
        if state.next_attempt_at > now:
            timeout = min(timeout, max(0.05, state.next_attempt_at - now))
        try:
            message = client.notifications.get(timeout=timeout)
        except queue.Empty:
            message = None

        if message is not None:
            method = str(message.get("method", ""))
            params = message.get("params")
            params = params if isinstance(params, dict) else {}
            if method == "__transport_closed__":
                raise TransportClosed(str(params.get("error", "transport closed")))
            if params.get("threadId") not in {None, args.thread}:
                continue
            if method == "thread/goal/updated":
                candidate = params.get("goal")
                if isinstance(candidate, dict):
                    goal = candidate
                    log(
                        "INFO",
                        "goal status update",
                        status=goal.get("status"),
                        tokens_used=goal.get("tokensUsed"),
                        time_used_seconds=goal.get("timeUsedSeconds"),
                    )
            elif method == "thread/status/changed":
                candidate = params.get("status")
                if isinstance(candidate, dict):
                    thread_status = candidate
            elif method in {"turn/started", "item/completed", "item/started"}:
                last_activity = time.time()
            elif method == "turn/completed":
                candidate = params.get("turn")
                if isinstance(candidate, dict):
                    last_turn = candidate
                    last_activity = time.time()
                    status = candidate.get("status")
                    error = candidate.get("error")
                    log("INFO", "turn completed", status=status, error=error)
                    if status == "completed":
                        persist_success()

        now = time.time()
        if now >= next_poll:
            goal = get_goal(client, args.thread)
            thread_status = read_thread_status(client, args.thread)
            next_poll = now + args.poll_seconds
            if goal is None:
                log("ERROR", "goal was cleared; stopping watchdog")
                return 3
            current_status = str(goal.get("status", ""))
            status_changed = current_status != state.last_goal_status
            if status_changed:
                state.last_goal_status = current_status
                store.save(state)

            if current_status == "blocked" and (last_turn is None or not last_turn.get("error")):
                last_turn = get_last_failed_turn(client, args.thread)

            if current_status == "blocked":
                decision = classify_failure(
                    last_turn,
                    normal_base=args.base_delay_seconds,
                    rate_limit_base=args.rate_limit_base_seconds,
                    allow_unknown=args.allow_unknown_errors,
                )
                error = (last_turn or {}).get("error") if isinstance(last_turn, dict) else None
                state.last_error_kind = decision.kind
                state.last_error_message = (
                    str(error.get("message")) if isinstance(error, dict) else decision.reason
                )
                if not decision.retryable:
                    state.next_attempt_at = 0.0
                    store.save(state)
                    log(
                        "ERROR",
                        "blocked goal is not eligible for automatic retry",
                        kind=decision.kind,
                        reason=decision.reason,
                        error=state.last_error_message,
                    )
                    if args.once:
                        return 4
                elif args.max_reactivations > 0 and state.consecutive_failures >= args.max_reactivations:
                    state.next_attempt_at = 0.0
                    store.save(state)
                    if status_changed:
                        log(
                            "ERROR",
                            "reactivation circuit breaker is open",
                            attempts=state.consecutive_failures,
                            max_reactivations=args.max_reactivations,
                        )
                    if args.once:
                        return 6
                elif state.next_attempt_at <= 0:
                    delay = exponential_delay(
                        decision.base_delay,
                        state.consecutive_failures,
                        args.max_delay_seconds,
                    )
                    state.next_attempt_at = now + delay
                    store.save(state)
                    log(
                        "WARN",
                        "blocked goal scheduled for reactivation",
                        kind=decision.kind,
                        reason=decision.reason,
                        delay_seconds=round(delay, 1),
                        failures=state.consecutive_failures,
                    )

            elif current_status == "usageLimited":
                if args.auto_resume_usage_limited and state.next_attempt_at <= 0:
                    delay = exponential_delay(
                        args.usage_limit_delay_seconds,
                        state.consecutive_failures,
                        args.usage_limit_max_seconds,
                    )
                    state.next_attempt_at = now + delay
                    store.save(state)
                    log(
                        "WARN",
                        "usage-limited goal scheduled for a low-frequency probe",
                        delay_seconds=round(delay, 1),
                    )
                elif not args.auto_resume_usage_limited:
                    state.next_attempt_at = 0.0
                    store.save(state)
                    if status_changed:
                        log("INFO", "usage-limited goal left paused by policy")
                    if args.once:
                        return 0

            elif current_status == "active":
                state.next_attempt_at = 0.0
                store.save(state)
                status_type = (thread_status or {}).get("type")
                if (
                    status_type == "idle"
                    and args.active_stall_seconds > 0
                    and now - last_activity >= args.active_stall_seconds
                    and now - state.last_reassert_at >= args.active_stall_seconds
                ):
                    reachable, detail = network_reachable(args.probe_url, args.probe_timeout_seconds)
                    if reachable:
                        log("WARN", "active goal appears idle; reasserting active status", probe=detail)
                        set_goal_active(client, args.thread, dry_run=args.dry_run)
                        state.last_reassert_at = now
                        last_activity = now
                        store.save(state)
                    else:
                        log("WARN", "active goal is idle but network probe failed", probe_error=detail)

            elif current_status in {"paused", "budgetLimited", "complete"}:
                state.next_attempt_at = 0.0
                store.save(state)
                if status_changed:
                    log("INFO", "goal is intentionally terminal/paused; no automatic action", status=current_status)
                if args.once:
                    return 0

            if args.once and state.next_attempt_at <= now:
                # Fall through to the attempt block below, then exit.
                pass

        now = time.time()
        if state.next_attempt_at > 0 and now >= state.next_attempt_at:
            reachable, probe_detail = network_reachable(args.probe_url, args.probe_timeout_seconds)
            if not reachable:
                state.next_attempt_at = now + args.probe_retry_seconds
                store.save(state)
                log(
                    "WARN",
                    "network still unavailable; postponing goal reactivation",
                    probe_error=probe_detail,
                    retry_in_seconds=args.probe_retry_seconds,
                )
                if args.once:
                    return 5
                continue

            state.consecutive_failures += 1
            state.last_attempt_at = now
            state.next_attempt_at = 0.0
            store.save(state)
            try:
                activated = set_goal_active(client, args.thread, dry_run=args.dry_run)
                log(
                    "INFO",
                    "goal reactivation requested",
                    probe=probe_detail,
                    attempt=state.consecutive_failures,
                    returned_status=(activated or {}).get("status"),
                )
                last_activity = now
            except Exception as exc:
                delay = exponential_delay(
                    args.base_delay_seconds,
                    state.consecutive_failures,
                    args.max_delay_seconds,
                )
                state.next_attempt_at = time.time() + delay
                store.save(state)
                log("ERROR", "goal reactivation RPC failed", error=str(exc), retry_in_seconds=round(delay, 1))
            if args.once:
                return 0

    log("INFO", "watchdog stopping on signal")
    return 0


def build_codex_command(args: argparse.Namespace) -> list[str]:
    codex_bin = args.codex_bin or os.environ.get("CODEX_BIN") or shutil.which("codex")
    if not codex_bin:
        raise FileNotFoundError("codex binary not found; pass --codex-bin or install Codex CLI")
    command = [codex_bin]
    for override in args.config:
        command.extend(["--config", override])
    command.extend(["app-server", "--listen", "stdio://"])
    return command


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Auto-resume retryable blocked Codex Goals")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--thread", help="persisted Codex thread UUID to supervise")
    mode.add_argument("--list", action="store_true", help="list recent threads and their goal status")
    parser.add_argument("--limit", type=int, default=20, help="thread count for --list")
    parser.add_argument("--codex-bin", help="path to the codex executable")
    parser.add_argument(
        "--config",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="forwarded as repeated 'codex --config KEY=VALUE' overrides",
    )
    parser.add_argument("--poll-seconds", type=float, default=15.0)
    parser.add_argument("--base-delay-seconds", type=float, default=30.0)
    parser.add_argument("--max-delay-seconds", type=float, default=900.0)
    parser.add_argument("--rate-limit-base-seconds", type=float, default=300.0)
    parser.add_argument(
        "--max-reactivations",
        type=int,
        default=0,
        help="circuit breaker: maximum consecutive reactivations; 0 means unlimited",
    )
    parser.add_argument("--usage-limit-delay-seconds", type=float, default=1800.0)
    parser.add_argument("--usage-limit-max-seconds", type=float, default=21600.0)
    parser.add_argument("--probe-retry-seconds", type=float, default=30.0)
    parser.add_argument("--probe-timeout-seconds", type=float, default=8.0)
    parser.add_argument("--probe-url", default="https://chatgpt.com/")
    parser.add_argument("--active-stall-seconds", type=float, default=300.0)
    parser.add_argument("--auto-resume-usage-limited", action="store_true")
    parser.add_argument("--allow-unknown-errors", action="store_true")
    parser.add_argument(
        "--approval-policy",
        choices=["preserve", "never", "on-request", "untrusted"],
        default="preserve",
    )
    parser.add_argument(
        "--sandbox",
        choices=["preserve", "read-only", "workspace-write", "danger-full-access"],
        default="preserve",
    )
    parser.add_argument(
        "--auto-approve",
        action="store_true",
        help="DANGEROUS: accept command/file approval requests received by this client",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--once", action="store_true", help="evaluate/act once, then exit")
    parser.add_argument("--state-file", help="override persistent backoff state path")
    args = parser.parse_args()
    numeric_nonnegative = [
        "poll_seconds",
        "base_delay_seconds",
        "max_delay_seconds",
        "rate_limit_base_seconds",
        "usage_limit_delay_seconds",
        "usage_limit_max_seconds",
        "probe_retry_seconds",
        "probe_timeout_seconds",
        "active_stall_seconds",
        "max_reactivations",
    ]
    for name in numeric_nonnegative:
        if getattr(args, name) < 0:
            parser.error(f"--{name.replace('_', '-')} must be non-negative")
    return args


def main() -> int:
    args = parse_args()
    command = build_codex_command(args)
    if args.list:
        client = AppServerClient(command, auto_approve=False)
        try:
            client.start()
            return list_threads(client, args.limit)
        finally:
            client.close()

    assert args.thread is not None
    state_path = (
        Path(args.state_file).expanduser()
        if args.state_file
        else Path.home() / ".codex" / "watchdogs" / f"{args.thread}.json"
    )
    lock_path = state_path.with_suffix(state_path.suffix + ".lock")
    process_failures = 0

    with SingleInstanceLock(lock_path):
        while True:
            client = AppServerClient(command, auto_approve=args.auto_approve)
            try:
                client.start()
                process_failures = 0
                return watch_session(client, args, StateStore(state_path))
            except (KeyboardInterrupt, SystemExit):
                return 130
            except Exception as exc:
                process_failures += 1
                delay = min(300.0, 5.0 * (2 ** min(process_failures - 1, 6)))
                log(
                    "ERROR",
                    "watchdog/app-server session failed",
                    error=str(exc),
                    restart_in_seconds=delay,
                )
                if args.once:
                    return 10
                time.sleep(delay)
            finally:
                client.close()


if __name__ == "__main__":
    raise SystemExit(main())
