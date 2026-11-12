import QtQuick
import QtQuick.Controls.Basic as C
import "../theme"

// kind: "primary" (blue, editing) | "print" (green, printing) | "data" (violet outline, data source) | "secondary" | "ghost" | "danger"
C.Button {
    id: b
    property string kind: "secondary"
    property bool compact: false
    property bool large: false
    property string glyph: ""          // optional leading glyph
    readonly property bool filled: kind === "primary" || kind === "print"
    implicitHeight: large ? Theme.controlHLg : compact ? Theme.controlHSm : Theme.controlH
    implicitWidth: Math.max(compact ? 28 : 64, contentItem.implicitWidth + (compact ? Theme.s3 : Theme.s4) * 2)
    leftPadding: 0; rightPadding: 0; topPadding: 0; bottomPadding: 0
    focusPolicy: Qt.TabFocus
    hoverEnabled: true

    readonly property color fillColor: !enabled ? (filled ? Theme.border : "transparent")
        : kind === "primary" ? (down ? Theme.accentPressed : hovered ? Theme.accentHover : Theme.accent)
        : kind === "print" ? (down ? Theme.printPressed : hovered ? Theme.printHover : Theme.printColor)
        : kind === "danger" ? (down ? Theme.pressed : hovered ? Theme.dangerSoft : "transparent")
        : kind === "data" ? (down ? Theme.pressed : hovered ? Theme.dataSoft : Theme.surface)
        : kind === "ghost" ? (down ? Theme.pressed : hovered ? Theme.hover : "transparent")
        : (down ? Theme.pressed : hovered ? Theme.hover : Theme.surface)

    background: Rectangle {
        radius: Theme.radiusMd
        color: b.fillColor
        border.width: b.kind === "secondary" || b.kind === "danger" || b.kind === "data" ? 1 : 0
        border.color: b.kind === "danger" ? Qt.alpha(Theme.danger, 0.6) : b.kind === "data" ? Theme.data
                    : (b.hovered ? Theme.textFaint : Theme.borderStrong)
        Behavior on color { ColorAnimation { duration: Theme.dFast } }
        Rectangle {                               // keyboard focus ring
            anchors.fill: parent; anchors.margins: -2; radius: parent.radius + 2
            color: "transparent"; border.width: 2; border.color: Theme.accent
            visible: b.visualFocus; opacity: 0.7
        }
    }
    contentItem: Text {
        text: b.glyph.length ? b.glyph + "  " + b.text : b.text
        font.family: Theme.fontFamily
        font.pixelSize: b.large ? Theme.fsMd : Theme.fsBase
        font.weight: b.filled ? Font.DemiBold : Font.Medium
        color: !b.enabled ? Theme.disabledFg
             : b.kind === "primary" ? Theme.onAccent
             : b.kind === "print" ? Theme.onPrint
             : b.kind === "danger" ? Theme.danger
             : b.kind === "data" ? Theme.data : Theme.text
        horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
}
