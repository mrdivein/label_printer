import QtQuick
import QtQuick.Controls.Basic as C
import QtQuick.Layouts
import "../theme"
import "../components"

AppDialog {
    id: d
    title: "Chèn trường dữ liệu"
    subtitle: "Các cột của dữ liệu đang mở. {{Tên cột}} tự lấy giá trị theo từng dòng."
    contentPadding: Theme.s5
    property var fields: []
    property var picked: ({})
    property int pickedCount: 0
    function refresh() { fields = Data.fieldSamples(search.text) }
    function toggle(name) { var p = picked; if (p[name]) delete p[name]; else p[name] = true; picked = p; pickedCount = Object.keys(p).length }
    onAboutToShow: { search.text = ""; picked = ({}); pickedCount = 0; custom.text = ""; refresh() }
    function names() { var n = Object.keys(picked); if (n.length === 0 && custom.text.trim().length) n = [custom.text.trim().replace(/[{}]/g, "")]; return n }

    body: [
        ColumnLayout {
            Layout.preferredWidth: 560; spacing: Theme.s2
            AppTextField { id: search; Layout.fillWidth: true; placeholderText: "Tìm tên cột hoặc giá trị mẫu"; onTextChanged: d.refresh() }
            ListView {
                id: list
                Layout.fillWidth: true; Layout.preferredHeight: 280
                clip: true; model: d.fields
                boundsBehavior: Flickable.StopAtBounds
                C.ScrollBar.vertical: C.ScrollBar {}
                delegate: Rectangle {
                    required property var modelData; required property int index
                    readonly property bool on: d.picked[modelData.field] === true
                    width: list.width; height: 32; radius: Theme.radiusSm
                    color: on ? Theme.selected : (ma.containsMouse ? Theme.hover : "transparent")
                    RowLayout { anchors.fill: parent; anchors.leftMargin: Theme.s3; anchors.rightMargin: Theme.s3; spacing: Theme.s3
                        Text { text: modelData.field; Layout.preferredWidth: 200; elide: Text.ElideRight; font.family: Theme.fontFamily; font.pixelSize: Theme.fsBase; font.weight: Font.Medium; color: Theme.text }
                        Text { text: modelData.sample; Layout.fillWidth: true; elide: Text.ElideRight; textFormat: Text.PlainText; font.family: Theme.fontFamily; font.pixelSize: Theme.fsBase; color: Theme.textMuted } }
                    MouseArea { id: ma; anchors.fill: parent; hoverEnabled: true; onClicked: d.toggle(modelData.field)
                        onDoubleClicked: { d.picked = ({}); d.toggle(modelData.field); addText.clicked() } }
                }
                Text { visible: list.count === 0; anchors.centerIn: parent; text: Data.hasData ? "Không có cột phù hợp" : "Mở dữ liệu để thấy các cột, hoặc gõ tên cột bên dưới."
                    font.family: Theme.fontFamily; font.pixelSize: Theme.fsBase; color: Theme.textFaint }
            }
            PropertyRow { label: "Cột tự nhập"; labelWidth: 96; AppTextField { id: custom; Layout.fillWidth: true; placeholderText: "Tên cột" } }
        }
    ]
    buttons: [
        AppButton { text: "Huỷ"; kind: "ghost"; onClicked: d.close() },
        AppButton { text: "Chèn dạng mã vạch"; enabled: d.names().length === 1; onClicked: { Doc.addFields(d.names(), true); d.close() } },
        AppButton { id: addText; text: "Chèn dạng chữ"; kind: "primary"; enabled: d.names().length > 0; onClicked: { Doc.addFields(d.names(), false); d.close() } }
    ]
}
