import QtQuick
import "../theme"

Item {
    id: h
    property string text: ""
    property alias trailing: slot.data
    implicitHeight: 28
    implicitWidth: 100
    Text {
        text: h.text.toUpperCase()
        anchors.verticalCenter: parent.verticalCenter
        font.family: Theme.fontFamily; font.pixelSize: Theme.fsXs; font.weight: Font.DemiBold
        font.letterSpacing: 0.6
        color: Theme.textMuted
    }
    Row { id: slot; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; spacing: Theme.s1 }
}
