#!/usr/bin/env python3
"""Track Claude Code and Copilot CLI sessions for the ai_alert bar widget.

  hook   read a Claude Code / Copilot CLI hook payload on stdin and update the shared state
  prune  drop sessions whose agent process is gone (also creates the state file)

State file: $XDG_RUNTIME_DIR/ai_alert/state.json, {"sessions": {id: {...}}}.
Hooks never fail or print: a broken widget must not disturb the agent.
"""
import fcntl
import json
import os
import sys
import time

STATE_DIR = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "ai_alert")
STATE = os.path.join(STATE_DIR, "state.json")
LOCK = os.path.join(STATE_DIR, "lock")

AGENTS = ("claude", "copilot")  # executable names of the supported CLIs
# Notification types meaning "done, your turn"; everything else needs a decision, except background noise.
DONE = {"idle_prompt", "agent_idle", "agent_completed"}
IGNORED = {"shell_completed", "shell_detached_completed", "auth_success"}

# idle: started, nothing asked yet | working: thinking | attention: needs a decision | waiting: done, your turn
STATES = {
    "SessionStart": "idle",
    "UserPromptSubmit": "working",
    "PostToolUse": "working",  # clears "attention" once a permission was granted
    "Stop": "waiting",
}


def comm(pid):
    try:
        with open(f"/proc/{pid}/comm") as f:
            return f.read().strip()
    except OSError:
        return None


def agent_name(pid):
    """Which agent CLI a process is, or None. comm is not enough: copilot's main thread is "MainThread"."""
    if comm(pid) in AGENTS:
        return comm(pid)
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            argv0 = f.read().split(b"\0")[0].decode(errors="replace")
    except OSError:
        return None
    name = os.path.basename(argv0)
    return name if name in AGENTS else None


def agent_pid():
    """Nearest ancestor of this process that is a supported agent CLI."""
    pid = os.getpid()
    while pid > 1:
        if agent_name(pid):
            return pid
        try:
            with open(f"/proc/{pid}/stat") as f:
                pid = int(f.read().rsplit(")", 1)[1].split()[1])
        except (OSError, ValueError, IndexError):
            return None
    return None


def mutate(fn):
    """Apply fn(sessions) under a lock; rewrite the file in place only if it changed."""
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(LOCK, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        existed = os.path.exists(STATE)
        try:
            with open(STATE) as f:
                sessions = json.load(f).get("sessions", {})
        except (OSError, ValueError):
            sessions = {}
        before = json.dumps(sessions, sort_keys=True)
        fn(sessions)
        if not existed or json.dumps(sessions, sort_keys=True) != before:
            # In place (no rename): keeps the inode the widget is watching.
            with open(STATE, "w") as f:
                f.write(json.dumps({"sessions": sessions}))


def drop_dead(sessions):
    for sid, v in list(sessions.items()):
        if not v.get("pid"):
            continue
        name = agent_name(v["pid"])
        if name:
            v["agent"] = name  # backfills sessions recorded before the agent field existed
        else:
            del sessions[sid]


def hook():
    payload = json.load(sys.stdin)
    event, sid = payload.get("hook_event_name"), payload.get("session_id")
    if not sid:
        return
    if event == "Notification":
        kind = payload.get("notification_type")
        if kind in IGNORED:
            return
        state = "waiting" if kind in DONE else "attention"
    else:
        state = STATES.get(event)

    def apply(sessions):
        drop_dead(sessions)
        if event == "SessionEnd":
            sessions.pop(sid, None)
        elif state:
            pid = sessions.get(sid, {}).get("pid") or agent_pid()
            sessions[sid] = {
                "id": sid,
                "agent": agent_name(pid) if pid else None,
                "state": state,
                "cwd": os.path.basename(payload.get("cwd", "").rstrip("/")),
                "pid": pid,
                "ts": sessions.get(sid, {}).get("ts") or time.time(),
                "upd": time.time(),
            }
            # One process shows one session: /clear or resume leaves older ids behind.
            for other in [o for o, v in sessions.items() if o != sid and pid and v.get("pid") == pid]:
                del sessions[other]

    mutate(apply)


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        if cmd == "hook":
            hook()
        elif cmd == "prune":
            mutate(drop_dead)
        else:
            sys.exit(__doc__)
    except SystemExit:
        raise
    except Exception:
        pass


if __name__ == "__main__":
    main()
