import QtQuick
import QtQuick.Controls.Basic as C
import "../theme"

// Icon + caption button of the vertical tool rail on the left edge.
C.AbstractButton {
    id: b
    property string glyph: ""
    property bool active: false
    property int badge: 0
    implicitWidth: 64; implicitHeight: 58
    hoverEnabled: true
    focusPolicy: Qt.TabFocus

    background: Rectangle {
        anchors.fill: parent; anchors.margins: 4
        radius: Theme.radiusMd
        color: b.active ? Theme.accentSoft : b.hovered ? Theme.hover : "transparent"
        Behavior on color { ColorAnimation { duration: Theme.dFast } }
        Rectangle { visible: b.active; width: 3; height: parent.height - 16; radius: 1.5; color: Theme.accent
            anchors.left: parent.left; anchors.leftMargin: -4; anchors.verticalCenter: parent.verticalCenter }
    }
    contentItem: Item {
        Text {
            id: g
            anchors.horizontalCenter: parent.horizontalCenter; anchors.top: parent.top; anchors.topMargin: 9
            text: b.glyph
            font.family: Theme.fontFamily; font.pixelSize: 18
            color: b.active ? Theme.accent : Theme.textMuted
        }
        Rectangle {
            visible: b.badge > 0
            anchors.left: g.right; anchors.leftMargin: -4; anchors.top: g.top; anchors.topMargin: -4
            height: 14; width: Math.max(14, badgeText.implicitWidth + 6); radius: 7; color: Theme.accent
            Text { id: badgeText; anchors.centerIn: parent; text: b.badge > 999 ? "999+" : b.badge
                font.family: Theme.fontFamily; font.pixelSize: 9; font.weight: Font.DemiBold; color: Theme.onAccent }
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter; anchors.top: g.bottom; anchors.topMargin: 2
            text: b.text
            font.family: Theme.fontFamily; font.pixelSize: Theme.fsXs; font.weight: b.active ? Font.DemiBold : Font.Medium
            color: b.active ? Theme.accent : Theme.textMuted
        }
    }
}
