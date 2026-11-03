import QtQuick
import QtQuick.Layouts
import "../theme"

Panel {
    id: tb
    default property alias content: row.data
    implicitHeight: 48
    borderBottom: true
    RowLayout {
        id: row
        anchors.fill: parent
        anchors.leftMargin: Theme.s4; anchors.rightMargin: Theme.s4
        spacing: Theme.s2
    }
}
