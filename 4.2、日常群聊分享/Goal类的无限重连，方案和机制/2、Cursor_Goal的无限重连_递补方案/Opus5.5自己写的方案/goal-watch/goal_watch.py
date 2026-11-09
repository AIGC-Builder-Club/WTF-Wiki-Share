"""Watchdog for one Cursor agent conversation that is running a Goal.

Each check reads the conversation's transcript (agent-transcripts/<id>.jsonl)
and its rows in Cursor's state DB (opened read-only), classifies the
conversation, and appends one line to goal-watch.log.

  status  one check, printed as JSON; does not touch state.json
  loop    check every --interval seconds; print a GOALWATCH_WAKE line when the
          conversation needs a nudge (interrupted, stalled, goal finished)
  note    append a free-form line to the log

Statuses:
  RUNNING      a turn is open and something changed recently
  RESUMED      the last turn ended in an error, but Cursor already started a
               new run after it (the transcript lags behind the live run)
  ERROR_FRESH  the last turn ended in an error less than ERROR_GRACE_S ago
  INTERRUPTED  the last turn ended in an error and nothing restarted it
  STALLED      a run is open but nothing changed for STALL_S
  IDLE         the last turn ended normally (waiting for the user, a
               checkpoint, or Cursor's own goal continuation)
  DONE         the agent marked the goal complete
"""

import argparse
import json
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

CID = "31aaa9b2-256f-4914-9785-fe52b409b6b3"
TITLE = "Beta website UI analysis"
TRANSCRIPT = (
    Path.home()
    / ".cursor/projects/c-Users-Administrator-pingtai-beta/agent-transcripts"
    / CID
    / f"{CID}.jsonl"
)
STATE_DB = Path.home() / "AppData/Roaming/Cursor/User/globalStorage/state.vscdb"
HERE = Path(__file__).resolve().parent
LOG = HERE / "goal-watch.log"
STATE = HERE / "state.json"

# Cursor usually retries on its own within seconds of an error.
ERROR_GRACE_S = 180
STALL_S = 25 * 60
# After this many back-to-back interrupted checks, wake only on every 3rd one.
FULL_RATE_WAKES = 12

WAKE_PROMPT = (
    f"goal-watch 唤醒：目标会话「{TITLE}」({CID[:8]}) 状态 {{status}}。"
    "先运行 goal_watch.py status 复核；仍是 INTERRUPTED/STALLED 就截图确认它确实停了，"
    "再在该会话里发送继续消息恢复 Goal，然后切回本会话简短汇报；DONE 则停掉监控循环。"
)


def hms(t):
    return datetime.fromtimestamp(t).strftime("%H:%M:%S") if t else "-"


def read_transcript():
    st = TRANSCRIPT.stat()
    lines = [
        line
        for line in TRANSCRIPT.read_text(encoding="utf-8", errors="replace").splitlines()
        if line.strip()
    ]
    last = {}
    for line in reversed(lines[-2:]):
        try:
            last = json.loads(line)
            break
        except json.JSONDecodeError:
            continue  # the last line may be mid-write

    created = completed = -1
    for i, line in enumerate(lines):
        if "Goal" not in line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        for part in (entry.get("message") or {}).get("content", []):
            if part.get("type") != "tool_use":
                continue
            name, args = part.get("name"), part.get("input") or {}
            if name == "CallDynamicTool":
                name, args = args.get("toolName"), args.get("arguments") or {}
            if name == "CreateGoal":
                created = i
            elif name == "UpdateGoal" and args.get("status") == "complete":
                completed = i

    if last.get("type") == "turn_ended":
        kind = f"turn_ended:{last.get('status')}"
    else:
        kind = last.get("role") or "?"
    return {
        "mtime": st.st_mtime,
        "size": st.st_size,
        "lines": len(lines),
        "kind": kind,
        "error": last.get("error"),
        "goal_done": completed > created,
    }


def read_db():
    con = sqlite3.connect(f"file:{STATE_DB.as_posix()}?mode=ro", uri=True, timeout=10)
    try:
        cur = con.cursor()
        row = cur.execute(
            "select checkpointAt from composerHeaders where composerId = ?", (CID,)
        ).fetchone()
        checkpoint_ms = row[0] if row else None
        row = cur.execute(
            "select value from cursorDiskKV where key = ?", (f"composerData:{CID}",)
        ).fetchone()
        data = json.loads(row[0]) if row else {}
    finally:
        con.close()
    run_ms = data.get("unfinishedRunAt")
    return {
        "checkpoint_at": checkpoint_ms / 1000 if checkpoint_ms else None,
        "run_started_at": run_ms / 1000 if run_ms else None,
        "db_status": data.get("status"),
        "headers": (data.get("headerLog") or {}).get("count"),
    }


def check(state):
    """Classify the conversation. Updates progress tracking in `state`."""
    now = time.time()
    t = read_transcript()
    try:
        db = read_db()
    except Exception as exc:  # the DB is optional; the transcript alone still works
        db = {"db_error": f"{type(exc).__name__}: {exc}"}

    progress = [t["size"], db.get("headers"), db.get("checkpoint_at")]
    if progress != state.get("progress"):
        state["progress"] = progress
        state["progress_at"] = now
    quiet_for = now - state.get("progress_at", now)

    if t["goal_done"]:
        status = "DONE"
    elif t["kind"] == "turn_ended:error":
        err_at = t["mtime"]
        started = db.get("run_started_at")
        checkpoint = db.get("checkpoint_at")
        restarted = (started and started > err_at - 5) or (checkpoint and checkpoint > err_at + 60)
        if restarted:
            status = "STALLED" if quiet_for >= STALL_S else "RESUMED"
        elif now - err_at < ERROR_GRACE_S:
            status = "ERROR_FRESH"
        else:
            status = "INTERRUPTED"
    elif t["kind"].startswith("turn_ended"):
        status = "IDLE"
    else:
        status = "STALLED" if quiet_for >= STALL_S else "RUNNING"

    return {
        "at": hms(now),
        "status": status,
        "last": t["kind"],
        "error": t["error"],
        "transcript_at": hms(t["mtime"]),
        "lines": t["lines"],
        "quiet_min": round(quiet_for / 60, 1),
        "run_started": hms(db.get("run_started_at")),
        "checkpoint": hms(db.get("checkpoint_at")),
        "db_status": db.get("db_status"),
        "db_error": db.get("db_error"),
    }


def summary(r):
    s = (
        f"[{r['at']}] {r['status']:<11} last={r['last']} transcript@{r['transcript_at']} "
        f"quiet={r['quiet_min']}m run@{r['run_started']} checkpoint@{r['checkpoint']}"
    )
    if r["error"]:
        s += f" error={r['error']!r}"
    if r["db_error"]:
        s += f" db_error={r['db_error']!r}"
    return s


def log(line):
    with LOG.open("a", encoding="utf-8") as f:
        f.write(f"{datetime.now():%Y-%m-%d} {line}\n")


def load_state():
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(state):
    STATE.write_text(json.dumps(state), encoding="utf-8")


def should_wake(r, state):
    status = r["status"]
    if status == "INTERRUPTED":
        state["interrupted_checks"] = state.get("interrupted_checks", 0) + 1
        n = state["interrupted_checks"]
        return n <= FULL_RATE_WAKES or n % 3 == 0
    state["interrupted_checks"] = 0
    if status == "STALLED":
        episode = state.get("progress_at")
        if state.get("stall_woken") != episode:
            state["stall_woken"] = episode
            return True
        return False
    return status == "DONE"


def loop(interval):
    state = load_state()
    first = True
    while True:
        if not first:
            time.sleep(interval)
        try:
            r = check(state)
            line = summary(r)
            wake = not first and should_wake(r, state)
            save_state(state)
            log(line)
            print(line, flush=True)
            if wake:
                payload = {"status": r["status"], "prompt": WAKE_PROMPT.format(status=r["status"])}
                print("GOALWATCH_WAKE " + json.dumps(payload, ensure_ascii=False), flush=True)
                log(f"[{r['at']}] WAKE sent ({r['status']})")
            if r["status"] == "DONE" and not first:
                log(f"[{r['at']}] goal complete, loop exits")
                return
        except Exception as exc:
            msg = f"[{hms(time.time())}] CHECK_FAILED {type(exc).__name__}: {exc}"
            log(msg)
            print(msg, flush=True)
        first = False


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    lp = sub.add_parser("loop")
    lp.add_argument("--interval", type=int, default=300)
    np_ = sub.add_parser("note")
    np_.add_argument("text")
    a = p.parse_args()

    if a.cmd == "status":
        print(json.dumps(check(load_state()), ensure_ascii=False))
    elif a.cmd == "loop":
        loop(a.interval)
    else:
        log(f"[{hms(time.time())}] NOTE {a.text}")


if __name__ == "__main__":
    main()
