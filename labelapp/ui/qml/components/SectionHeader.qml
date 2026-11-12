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
        font.family: Theme.fontFamily; font.pixelSize: Theme.fsXs; font.weight: Font.Bold
        font.letterSpacing: 0.8
        color: Theme.text
    }
    Row { id: slot; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; spacing: Theme.s1 }
}
