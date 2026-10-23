#!/usr/bin/env python3
"""Hook the ai_alert plugin into an illogical-impulse (ii) quickshell config, Claude Code and Copilot CLI.

ii has no plugin system and its updater runs `rsync --delete` over
~/.config/quickshell/ii, so this script re-applies the (tiny) integration:

  1. symlink  ii/ai_alert -> ./plugin
  2. two marker-tagged lines in ii's BarContent.qml (each ends with `// ai_alert`)
  3. hook entries in ~/.claude/settings.json and ~/.copilot/settings.json (our command is the marker;
     an agent whose config dir does not exist is skipped)

Usage: install.py [apply|status|remove] [--quiet]   (apply is the default, idempotent)
"""
import json
import os
import shutil
import sys

II = os.path.expanduser(os.environ.get("AI_ALERT_II_DIR", "~/.config/quickshell/ii"))
CLAUDE_SETTINGS = os.path.expanduser(os.environ.get("AI_ALERT_CLAUDE_SETTINGS", "~/.claude/settings.json"))
COPILOT_SETTINGS = os.path.expanduser(os.environ.get("AI_ALERT_COPILOT_SETTINGS", "~/.copilot/settings.json"))
PLUGIN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plugin")
LINK = os.path.join(II, "ai_alert")
MARK = "// ai_alert"
HOOK_CMD = f"python3 {os.path.join(PLUGIN, 'ai_alert.py')} hook"
# PascalCase event names make Copilot CLI send the same payload shape as Claude Code.
HOOK_EVENTS = ["SessionStart", "UserPromptSubmit", "PostToolUse", "Notification", "Stop", "SessionEnd"]

BAR = "modules/ii/bar/BarContent.qml"
# (anchor line (stripped), where to insert relative to it, line to insert)
PATCHES = [
    ("import qs.modules.common.functions", "after", f"import qs.ai_alert {MARK}"),
    ("Resources {", "before", f"AiAlertBar {{}} {MARK}"),
]


def log(msg, quiet):
    if not quiet:
        print(msg)


def read_lines(path):
    with open(path) as f:
        return f.read().split("\n")


def write_lines(path, lines):
    with open(path, "w") as f:
        f.write("\n".join(lines))


def apply_bar(quiet):
    path = os.path.join(II, BAR)
    lines = read_lines(path)
    changed = False
    for anchor, where, new in PATCHES:
        if any(l.strip() == new for l in lines):
            continue
        idx = next((i for i, l in enumerate(lines) if l.strip() == anchor), None)
        if idx is None:
            raise SystemExit(f"anchor not found in {BAR}: {anchor!r} "
                             "(ii changed upstream; update PATCHES in install.py)")
        indent = lines[idx][: len(lines[idx]) - len(lines[idx].lstrip())]
        lines.insert(idx + (1 if where == "after" else 0), indent + new)
        changed = True
    if changed:
        write_lines(path, lines)
        log(f"patched {BAR}", quiet)


# agent -> (settings path, hook entry). Claude nests hooks in groups, Copilot lists them flat.
AGENTS = {
    "claude": (CLAUDE_SETTINGS, {"hooks": [{"type": "command", "command": HOOK_CMD}]}),
    "copilot": (COPILOT_SETTINGS, {"type": "command", "bash": HOOK_CMD}),
}


def installed_agents():
    return {a: v for a, v in AGENTS.items() if os.path.isdir(os.path.dirname(v[0]))}


def load_settings(path):
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_settings(path, settings):
    backup = path + ".ai_alert.bak"
    if os.path.exists(path) and not os.path.exists(backup):
        shutil.copy2(path, backup)
    with open(path, "w") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)
        f.write("\n")


def is_ours(h):
    return HOOK_CMD in (h.get("command"), h.get("bash"))


def has_hook(entries):
    return any(is_ours(h) for e in entries for h in e.get("hooks", [e]))


def strip_ours(entries):
    kept = []
    for e in entries:
        if "hooks" in e:
            e = {**e, "hooks": [h for h in e["hooks"] if not is_ours(h)]}
            if e["hooks"]:
                kept.append(e)
        elif not is_ours(e):
            kept.append(e)
    return kept


def apply_hooks(quiet):
    for agent, (path, entry) in installed_agents().items():
        settings = load_settings(path)
        hooks = settings.setdefault("hooks", {})
        changed = False
        for event in HOOK_EVENTS:
            entries = hooks.setdefault(event, [])
            if not has_hook(entries):
                entries.append(entry)
                changed = True
        if changed:
            save_settings(path, settings)
            log(f"added {agent} hooks to {path}", quiet)


def apply(quiet):
    if not os.path.isdir(II):
        raise SystemExit(f"ii config not found: {II}")
    if os.path.islink(LINK):
        if os.path.realpath(LINK) != os.path.realpath(PLUGIN):
            os.remove(LINK)
    elif os.path.exists(LINK):
        raise SystemExit(f"{LINK} exists and is not a symlink; refusing to touch it")
    if not os.path.lexists(LINK):
        os.symlink(PLUGIN, LINK)
        log(f"linked {LINK} -> {PLUGIN}", quiet)
    apply_bar(quiet)
    apply_hooks(quiet)


def status():
    link = os.path.islink(LINK) and os.path.realpath(LINK) == os.path.realpath(PLUGIN)
    print(f"symlink: {'ok' if link else 'MISSING'}")
    ok = link
    lines = read_lines(os.path.join(II, BAR))
    for _, _, new in PATCHES:
        present = any(l.strip() == new for l in lines)
        ok &= present
        print(f"{'ok     ' if present else 'MISSING'} {BAR}: {new}")
    for agent, (path, _) in installed_agents().items():
        hooks = load_settings(path).get("hooks", {})
        for event in HOOK_EVENTS:
            present = has_hook(hooks.get(event, []))
            ok &= present
            print(f"{'ok     ' if present else 'MISSING'} {agent} hook {event}")
    return ok


def remove(quiet):
    if os.path.islink(LINK):
        os.remove(LINK)
        log(f"removed {LINK}", quiet)
    path = os.path.join(II, BAR)
    lines = read_lines(path)
    kept = [l for l in lines if not l.rstrip().endswith(MARK)]
    if kept != lines:
        write_lines(path, kept)
        log(f"unpatched {BAR}", quiet)
    for agent, (path, _) in installed_agents().items():
        settings = load_settings(path)
        hooks = settings.get("hooks", {})
        changed = False
        for event, entries in list(hooks.items()):
            kept = strip_ours(entries)
            changed |= kept != entries
            if kept:
                hooks[event] = kept
            else:
                del hooks[event]
        if changed:
            save_settings(path, settings)
            log(f"removed {agent} hooks from {path}", quiet)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    quiet = "--quiet" in sys.argv
    cmd = args[0] if args else "apply"
    if cmd == "apply":
        apply(quiet)
    elif cmd == "status":
        sys.exit(0 if status() else 1)
    elif cmd == "remove":
        remove(quiet)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
