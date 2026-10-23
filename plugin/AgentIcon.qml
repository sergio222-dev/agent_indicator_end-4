import QtQuick
import QtQuick.Effects

// An agent's logo (icons/<agent>.svg, white on transparent) tinted to any color.
Item {
    id: root
    property string agent: "claude"
    property color color: "#9e9e9e"
    implicitWidth: 18
    implicitHeight: 18

    Image {
        id: logo
        anchors.fill: parent
        source: Qt.resolvedUrl("icons/" + root.agent + ".svg")
        sourceSize: Qt.size(root.width * 2, root.height * 2)
        fillMode: Image.PreserveAspectFit
        smooth: true
        visible: false
    }

    MultiEffect {
        anchors.fill: logo
        source: logo
        colorization: 1.0
        colorizationColor: root.color
    }
}
