pragma Singleton
pragma ComponentBehavior: Bound

import Quickshell
import Quickshell.Io
import QtQuick

/**
 * Live Claude Code sessions, fed by the hooks in ai_alert.py through a state file.
 */
Singleton {
    id: root

    readonly property string scriptPath: Quickshell.shellPath("ai_alert/ai_alert.py")
    readonly property string statePath: (Quickshell.env("XDG_RUNTIME_DIR") ?? "/tmp") + "/ai_alert/state.json"

    property var sessions: []

    readonly property var colors: ({
        idle: "#9e9e9e",      // started, nothing asked yet
        working: "#d97757",   // thinking
        attention: "#4a90d9", // needs a decision (permission, question)
        waiting: "#4caf50"    // done, your turn
    })
    readonly property var labels: ({
        idle: "Idle",
        working: "Thinking",
        attention: "Needs your input",
        waiting: "Waiting for you"
    })

    function parse(text) {
        try {
            const d = JSON.parse(text);
            root.sessions = Object.values(d.sessions ?? {}).sort((a, b) => a.ts - b.ts);
        } catch (e) {
            // The hook rewrites the file in place; keep the last good state on a partial read.
        }
    }

    FileView {
        id: file
        path: root.statePath
        watchChanges: true
        printErrors: false
        onFileChanged: reload()
        onLoaded: root.parse(text())
        onLoadFailed: root.sessions = []
    }

    // Drops sessions whose claude process died without firing SessionEnd.
    Process {
        id: prune
        command: ["python3", root.scriptPath, "prune"]
        onRunningChanged: if (!running) file.reload()
    }

    Timer {
        interval: 10000
        running: root.sessions.length > 0
        repeat: true
        onTriggered: prune.running = true
    }

    Component.onCompleted: prune.running = true
}
