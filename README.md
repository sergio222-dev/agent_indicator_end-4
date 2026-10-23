# ai_alert

A bar widget for the [end-4/dots-hyprland](https://github.com/end-4/dots-hyprland) Hyprland dotfiles
(illogical-impulse, "ii", on Quickshell) that shows your live
[Claude Code](https://claude.com/claude-code) and [Copilot CLI](https://docs.github.com/en/copilot/concepts/agents/about-copilot-cli) sessions as sparks, colored by what each session is doing.

It only works with those dots: it patches ii's bar and relies on its components.

![Example of the indicator in the bar](indicator.png)

| Color  | Meaning                                         | Hook event                       |
| ------ | ----------------------------------------------- | -------------------------------- |
| Grey   | Session started, nothing asked yet              | `SessionStart`                   |
| Orange | Claude is thinking or running tools             | `UserPromptSubmit`, `PostToolUse` |
| Blue   | Needs your input (permission, question)         | `Notification`                   |
| Green  | Finished, waiting for your next prompt          | `Stop`, idle `Notification`      |

One spark per session, placed left of the system indicators. Hover for the project name and status.
The spark disappears on `SessionEnd`; if a terminal dies without firing it, the session is pruned within ~10 s.

## Requirements

- [end-4/dots-hyprland](https://github.com/end-4/dots-hyprland) installed, with Quickshell and the ii config
  (`~/.config/quickshell/ii`)
- Claude Code and/or Copilot CLI (each is hooked only if its config dir exists)
- Python 3 (standard library only)

## Install

```sh
python3 install.py          # apply (idempotent)
python3 install.py status   # check what is in place
python3 install.py remove   # undo everything
```

`apply` does three things:

1. Symlinks `~/.config/quickshell/ii/ai_alert` to `./plugin`.
2. Adds two lines (marked `// ai_alert`) to ii's `modules/ii/bar/BarContent.qml`.
3. Adds hook entries to `~/.claude/settings.json` and `~/.copilot/settings.json` (existing hooks are untouched; a backup is saved as
   `settings.json.ai_alert.bak`).

Agent sessions that were already open do not pick up new hooks until restarted.

### After updating your dots

ii has no plugin system and its updater runs `rsync --delete` over `~/.config/quickshell/ii`, which wipes the
symlink and the two lines. Re-run `python3 install.py`. If ii changed the anchor lines, the script stops with
`anchor not found`; update `PATCHES` in `install.py`.

## How it works

- Claude Code hooks call `plugin/ai_alert.py hook`, which writes the session state to
  `$XDG_RUNTIME_DIR/ai_alert/state.json`. Hooks never print or fail, so they cannot disturb the agent.
- `plugin/AiAlert.qml` watches that file; `AiAlertBar.qml` and `ClaudeSpark.qml` draw the icons.
- Each session is tied to its `claude` or `copilot` process, one session per process.

## Try it without Claude

```sh
cd plugin
echo '{"hook_event_name":"SessionStart","session_id":"demo"}' | python3 ai_alert.py hook   # grey
echo '{"hook_event_name":"UserPromptSubmit","session_id":"demo"}' | python3 ai_alert.py hook   # orange
echo '{"hook_event_name":"Notification","session_id":"demo"}' | python3 ai_alert.py hook   # blue
echo '{"hook_event_name":"Stop","session_id":"demo"}' | python3 ai_alert.py hook   # green
echo '{"hook_event_name":"SessionEnd","session_id":"demo"}' | python3 ai_alert.py hook   # removed
```

After editing files in `plugin/`, reload ii with `touch ~/.config/quickshell/ii/shell.qml` (changes through the
symlink do not trigger hot reload).

## Credits

Designed and built together with [Claude Code](https://claude.com/claude-code) by Anthropic.
The Claude name and spark belong to Anthropic; this project is not affiliated with or endorsed by Anthropic.
