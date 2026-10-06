import QtQuick
import QtQuick.Controls.Basic as C
import "../theme"

C.CheckBox {
    id: c
    property bool mixed: false
    implicitHeight: Theme.controlH
    spacing: Theme.s2
    padding: 0
    hoverEnabled: true
    font.family: Theme.fontFamily; font.pixelSize: Theme.fsBase
    indicator: Rectangle {
        x: 0; y: (c.height - height) / 2; width: 16; height: 16; radius: 4
        color: c.checked || c.mixed ? Theme.accent : Theme.surface
        border.width: 1; border.color: c.checked || c.mixed ? Theme.accent : (c.hovered ? Theme.borderStrong : Theme.borderStrong)
        Behavior on color { ColorAnimation { duration: Theme.dFast } }
        Text { anchors.centerIn: parent; visible: c.checked && !c.mixed; text: "✓"; color: Theme.onAccent
               font.pixelSize: 11; font.weight: Font.Bold }
        Rectangle { visible: c.mixed; anchors.centerIn: parent; width: 8; height: 2; color: Theme.onAccent }
        Rectangle { anchors.fill: parent; anchors.margins: -2; radius: 6; color: "transparent"; border.width: 2
                    border.color: Theme.accent; opacity: 0.7; visible: c.visualFocus }
    }
    contentItem: Text {
        leftPadding: 16 + c.spacing
        text: c.text; font: c.font; color: c.enabled ? Theme.text : Theme.disabledFg
        verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight
    }
}
