import QtQuick
import QtQuick.Controls.Basic as C
import "../theme"

// kind: "primary" | "secondary" | "ghost" | "danger"
C.Button {
    id: b
    property string kind: "secondary"
    property bool compact: false
    implicitHeight: compact ? Theme.controlHSm : Theme.controlH
    implicitWidth: Math.max(compact ? 28 : 64, contentItem.implicitWidth + (compact ? Theme.s3 : Theme.s4) * 2)
    leftPadding: 0; rightPadding: 0; topPadding: 0; bottomPadding: 0
    focusPolicy: Qt.TabFocus
    hoverEnabled: true

    readonly property color fillColor: !enabled ? (kind === "primary" ? Theme.border : "transparent")
        : kind === "primary" ? (down ? Theme.accentPressed : hovered ? Theme.accentHover : Theme.accent)
        : kind === "danger" ? (down ? Theme.pressed : hovered ? Theme.hover : "transparent")
        : kind === "ghost" ? (down ? Theme.pressed : hovered ? Theme.hover : "transparent")
        : (down ? Theme.pressed : hovered ? Theme.hover : Theme.surface)

    background: Rectangle {
        radius: Theme.radiusMd
        color: b.fillColor
        border.width: b.kind === "secondary" || b.kind === "danger" ? 1 : 0
        border.color: b.kind === "danger" ? Qt.alpha(Theme.danger, 0.5) : Theme.borderStrong
        Behavior on color { ColorAnimation { duration: Theme.dFast } }
        Rectangle {                               // keyboard focus ring
            anchors.fill: parent; anchors.margins: -2; radius: parent.radius + 2
            color: "transparent"; border.width: 2; border.color: Theme.accent
            visible: b.visualFocus; opacity: 0.7
        }
    }
    contentItem: Text {
        text: b.text
        font.family: Theme.fontFamily
        font.pixelSize: Theme.fsBase
        font.weight: b.kind === "primary" ? Font.DemiBold : Font.Medium
        color: !b.enabled ? Theme.disabledFg
             : b.kind === "primary" ? Theme.onAccent
             : b.kind === "danger" ? Theme.danger : Theme.text
        horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
}
