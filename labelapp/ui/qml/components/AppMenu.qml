import QtQuick
import QtQuick.Controls.Basic as C
import "../theme"

C.Menu {
    id: m
    padding: 4
    implicitWidth: Math.max(190, contentItem.implicitWidth + 8)
    font.family: Theme.fontFamily; font.pixelSize: Theme.fsBase
    enter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.dFast } }
    background: Rectangle {
        implicitWidth: 190
        radius: Theme.radiusMd; color: Theme.surface
        border.width: 1; border.color: Theme.borderStrong
    }
}
