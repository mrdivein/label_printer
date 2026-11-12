import QtQuick
import QtQuick.Controls.Basic as C
import "../theme"

// Text field that commits on Enter / focus loss (editingFinished). Empty-state shows `placeholder`.
C.TextField {
    id: f
    property bool mixed: false
    implicitHeight: Theme.controlH
    leftPadding: Theme.s2 + 2; rightPadding: Theme.s2 + 2; topPadding: 0; bottomPadding: 0
    verticalAlignment: TextInput.AlignVCenter
    font.family: Theme.fontFamily; font.pixelSize: Theme.fsBase
    color: Theme.text
    placeholderTextColor: Theme.textFaint
    placeholderText: mixed ? qsTr("Nhiều giá trị") : ""
    selectionColor: Theme.accent; selectedTextColor: Theme.onAccent
    selectByMouse: true
    hoverEnabled: true
    background: Rectangle {
        radius: Theme.radiusMd
        color: f.enabled ? Theme.surface : Theme.surfaceAlt
        border.width: 1
        border.color: f.activeFocus ? Theme.accent : f.hovered ? Theme.textFaint : Theme.borderStrong
        Behavior on border.color { ColorAnimation { duration: Theme.dFast } }
        Rectangle { visible: f.activeFocus; anchors.fill: parent; anchors.margins: -1; radius: parent.radius + 1
            color: "transparent"; border.width: 1; border.color: Theme.accent; opacity: 0.55 }
    }
}
