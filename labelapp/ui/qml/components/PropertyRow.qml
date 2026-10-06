import QtQuick
import QtQuick.Layouts
import "../theme"

// Label column + field(s). Used by the inspector and the dialogs.
RowLayout {
    id: r
    property string label: ""
    property int labelWidth: 96
    default property alias field: slot.data
    spacing: Theme.s2
    Layout.fillWidth: true
    Text {
        text: r.label
        Layout.preferredWidth: r.labelWidth
        Layout.alignment: Qt.AlignVCenter
        font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm
        color: Theme.textMuted
        elide: Text.ElideRight
    }
    RowLayout { id: slot; Layout.fillWidth: true; spacing: Theme.s2 }
}
