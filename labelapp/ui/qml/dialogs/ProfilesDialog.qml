import QtQuick
import QtQuick.Controls.Basic as C
import QtQuick.Layouts
import "../theme"
import "../components"

AppDialog {
    id: d
    title: qsTr("Hồ sơ máy in")
    subtitle: qsTr("Mỗi hồ sơ lưu máy in, khổ giấy, độ lệch / nghiêng / tỉ lệ, vùng in và chất lượng in nhiệt.")
    property string selected: ""
    property string error: ""
    onAboutToShow: { selected = ""; nm.text = ""; error = "" }

    body: [
        ColumnLayout {
            Layout.preferredWidth: 480; spacing: Theme.s3
            ListView {
                id: list
                Layout.fillWidth: true; Layout.preferredHeight: 180
                clip: true; model: Profiles.names
                boundsBehavior: Flickable.StopAtBounds
                C.ScrollBar.vertical: C.ScrollBar {}
                delegate: Rectangle {
                    required property string modelData
                    width: list.width; height: 34; radius: Theme.radiusSm
                    color: d.selected === modelData ? Theme.selected : (ma.containsMouse ? Theme.hover : "transparent")
                    Text { anchors.fill: parent; anchors.leftMargin: Theme.s3; text: modelData; verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight
                        font.family: Theme.fontFamily; font.pixelSize: Theme.fsBase; color: Theme.text }
                    MouseArea { id: ma; anchors.fill: parent; hoverEnabled: true; onClicked: { d.selected = modelData; nm.text = modelData }
                        onDoubleClicked: { d.selected = modelData; loadBtn.clicked() } }
                }
                Text { visible: list.count === 0; anchors.centerIn: parent; text: qsTr("Chưa có hồ sơ nào"); color: Theme.textFaint
                    font.family: Theme.fontFamily; font.pixelSize: Theme.fsBase }
            }
            PropertyRow { label: qsTr("Tên hồ sơ"); AppTextField { id: nm; Layout.fillWidth: true; onAccepted: saveBtn.clicked() } }
            Text { visible: d.error.length > 0; text: I18n.tr(d.error); color: Theme.danger; Layout.fillWidth: true; wrapMode: Text.Wrap
                font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm }
        }
    ]
    buttons: [
        AppButton { text: qsTr("Xoá"); kind: "danger"; enabled: d.selected.length > 0; onClicked: { Profiles.delete(d.selected); d.selected = "" } },
        Item { Layout.fillWidth: true },
        AppButton { text: qsTr("Đóng"); kind: "ghost"; onClicked: d.close() },
        AppButton { id: saveBtn; text: qsTr("Lưu cài đặt hiện tại"); onClicked: { d.error = Profiles.save(nm.text); if (!d.error.length) d.selected = nm.text.trim() } },
        AppButton { id: loadBtn; text: qsTr("Dùng hồ sơ đã chọn"); kind: "primary"; enabled: d.selected.length > 0
            onClicked: { d.error = Profiles.load(d.selected); if (!d.error.length) d.close() } }
    ]
}
