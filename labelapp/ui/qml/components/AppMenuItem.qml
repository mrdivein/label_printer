import QtQuick
import QtQuick.Controls.Basic as C
import "../theme"

C.MenuItem {
    id: mi
    property string hint: ""
    implicitHeight: 32
    leftPadding: Theme.s3; rightPadding: Theme.s3; topPadding: 0; bottomPadding: 0
    font.family: Theme.fontFamily; font.pixelSize: Theme.fsBase
    contentItem: Item {
        implicitWidth: label.implicitWidth + (hintText.visible ? hintText.implicitWidth + Theme.s5 : 0)
        Text { id: label; text: mi.text; font: mi.font; anchors.verticalCenter: parent.verticalCenter
            color: mi.enabled ? Theme.text : Theme.disabledFg; elide: Text.ElideRight; width: parent.width - (hintText.visible ? hintText.implicitWidth + Theme.s4 : 0) }
        Text { id: hintText; visible: mi.hint.length > 0; text: mi.hint; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
            font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm; color: Theme.textFaint }
    }
    background: Rectangle { radius: Theme.radiusSm; color: mi.highlighted && mi.enabled ? Theme.accentSoft : "transparent" }
}
