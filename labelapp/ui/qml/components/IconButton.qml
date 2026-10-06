import QtQuick
import QtQuick.Controls.Basic as C
import "../theme"

// Compact square button with a short glyph/label and a tooltip.
C.ToolButton {
    id: b
    property string tip: ""
    property bool active: false
    implicitWidth: Theme.controlH; implicitHeight: Theme.controlH
    padding: 0
    hoverEnabled: true
    focusPolicy: Qt.TabFocus
    background: Rectangle {
        radius: Theme.radiusMd
        color: !b.enabled ? "transparent" : b.down ? Theme.pressed : b.active ? Theme.selected : b.hovered ? Theme.hover : "transparent"
        Behavior on color { ColorAnimation { duration: Theme.dFast } }
        Rectangle { anchors.fill: parent; anchors.margins: -2; radius: parent.radius + 2; color: "transparent"
            border.width: 2; border.color: Theme.accent; visible: b.visualFocus; opacity: 0.7 }
    }
    contentItem: Text {
        text: b.text
        font.family: Theme.fontFamily; font.pixelSize: Theme.fsMd; font.weight: Font.Medium
        color: !b.enabled ? Theme.disabledFg : b.active ? Theme.accent : Theme.text
        horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
    }
    C.ToolTip.visible: hovered && tip.length > 0
    C.ToolTip.text: tip
    C.ToolTip.delay: 600
}
