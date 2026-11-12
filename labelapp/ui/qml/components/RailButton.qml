import QtQuick
import QtQuick.Controls.Basic as C
import "../theme"

// Icon + caption button of the vertical tool rail on the left edge.
C.AbstractButton {
    id: b
    property string glyph: ""
    property bool active: false
    property int badge: 0
    property color badgeColor: Theme.textMuted
    property string tip: ""
    implicitWidth: 72; implicitHeight: 62
    hoverEnabled: true
    focusPolicy: Qt.TabFocus

    // 4795 -> "4.8k": short enough to never cover the icon
    function shortCount(n) { return n >= 10000 ? Math.round(n / 1000) + "k" : n >= 1000 ? (Math.round(n / 100) / 10) + "k" : String(n) }

    background: Rectangle {
        anchors.fill: parent; anchors.margins: 5
        radius: Theme.radiusMd
        color: b.active ? Theme.accentSoft : b.down ? Theme.pressed : b.hovered ? Theme.hover : "transparent"
        Behavior on color { ColorAnimation { duration: Theme.dFast } }
        Rectangle { visible: b.active; width: 3; height: parent.height - 14; radius: 1.5; color: Theme.accent
            anchors.left: parent.left; anchors.leftMargin: -5; anchors.verticalCenter: parent.verticalCenter }
        Rectangle { anchors.fill: parent; anchors.margins: -2; radius: parent.radius + 2; color: "transparent"
            border.width: 2; border.color: Theme.accent; visible: b.visualFocus; opacity: 0.7 }
    }
    contentItem: Item {
        Text {
            id: g
            anchors.horizontalCenter: parent.horizontalCenter; anchors.top: parent.top; anchors.topMargin: 10
            text: b.glyph
            font.family: Theme.fontFamily; font.pixelSize: 20
            color: b.active ? Theme.accent : Theme.text
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter; anchors.top: g.bottom; anchors.topMargin: 1
            text: b.text
            font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm; font.weight: b.active ? Font.Bold : Font.DemiBold
            color: b.active ? Theme.accent : Theme.textMuted
        }
    }
    // count pill on the top-right corner, outside the icon
    Rectangle {
        visible: b.badge > 0
        anchors.right: parent.right; anchors.rightMargin: 6; anchors.top: parent.top; anchors.topMargin: 6
        height: 16; width: Math.max(16, badgeText.implicitWidth + 8); radius: 8
        color: b.badgeColor
        border.width: 2; border.color: Theme.surfaceAlt
        Text { id: badgeText; anchors.centerIn: parent; text: b.shortCount(b.badge)
            font.family: Theme.fontFamily; font.pixelSize: 10; font.weight: Font.Bold; color: Theme.surface }
    }
    C.ToolTip.visible: hovered && tip.length > 0
    C.ToolTip.text: tip
    C.ToolTip.delay: 600
}
