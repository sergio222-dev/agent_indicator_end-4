import qs.modules.common
import qs.modules.common.widgets
import qs.modules.ii.bar
import QtQuick
import QtQuick.Layouts

// One agent logo per live Claude Code / Copilot CLI session; takes no space when there are none.
RowLayout {
    visible: AiAlert.sessions.length > 0
    spacing: 2

    Repeater {
        model: AiAlert.sessions

        MouseArea {
            id: item
            required property var modelData
            implicitWidth: 24
            implicitHeight: Appearance.sizes.barHeight
            hoverEnabled: true

            AgentIcon {
                anchors.centerIn: parent
                agent: item.modelData.agent ?? "claude"
                color: AiAlert.colors[item.modelData.state] ?? AiAlert.colors.idle
            }

            StyledPopup {
                hoverTarget: item

                ColumnLayout {
                    anchors.centerIn: parent
                    spacing: 4

                    StyledPopupHeaderRow {
                        icon: "terminal"
                        label: item.modelData.cwd || (item.modelData.agent === "copilot" ? "Copilot CLI" : "Claude Code")
                    }
                    StyledPopupValueRow {
                        icon: "bolt"
                        label: "Status:"
                        value: AiAlert.labels[item.modelData.state] ?? item.modelData.state
                    }
                }
            }
        }
    }
}
