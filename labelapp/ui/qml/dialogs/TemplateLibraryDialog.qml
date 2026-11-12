import QtQuick
import QtQuick.Controls.Basic as C
import QtQuick.Layouts
import "../theme"
import "../components"

AppDialog {
    id: d
    title: qsTr("Thư viện mẫu")
    subtitle: Lib.libraryDir
    contentPadding: 0
    width: Math.min(parent ? parent.width - 80 : 900, 900)
    height: Math.min(parent ? parent.height - 80 : 600, 600)
    signal importRequested()
    signal exportRequested(string name)
    signal promptRequested(string title, string initial, string action, string name)
    signal shareRequested(string name)
    signal galleryRequested()

    property string current: ""
    property string message: ""
    function select(n) { current = n; message = ""; if (n.length) Lib.showPreview(n) }
    onOpened: { Lib.refresh(); select(Doc.templateName || (Lib.names.length ? Lib.names[0] : "")) }

    function finish(err) { message = err || "" }

    body: [
        RowLayout {
            Layout.fillWidth: true; Layout.fillHeight: true; spacing: 0
            ColumnLayout {
                Layout.preferredWidth: 300; Layout.fillHeight: true; spacing: 0
                ListView {
                    id: list
                    Layout.fillWidth: true; Layout.fillHeight: true
                    clip: true; model: Lib.names
                    boundsBehavior: Flickable.StopAtBounds
                    C.ScrollBar.vertical: C.ScrollBar {}
                    delegate: Rectangle {
                        required property string modelData
                        width: list.width; height: 36
                        color: d.current === modelData ? Theme.selected : (ma.containsMouse ? Theme.hover : "transparent")
                        Text { anchors.fill: parent; anchors.leftMargin: Theme.s5; anchors.rightMargin: Theme.s3
                            text: modelData.replace(/\.json$/i, ""); elide: Text.ElideRight; verticalAlignment: Text.AlignVCenter
                            font.family: Theme.fontFamily; font.pixelSize: Theme.fsBase; color: Theme.text
                            font.weight: modelData === Doc.templateName ? Font.DemiBold : Font.Normal }
                        MouseArea { id: ma; anchors.fill: parent; hoverEnabled: true; onClicked: d.select(modelData); onDoubleClicked: { d.select(modelData); useBtn.clicked() } }
                    }
                }
                Separator { Layout.fillWidth: true }
                Flow {
                    Layout.fillWidth: true; Layout.margins: Theme.s3; Layout.leftMargin: Theme.s5; spacing: Theme.s1
                    AppButton { text: qsTr("Tạo mới…"); compact: true; onClicked: newDlg.open() }
                    AppButton { text: qsTr("Nhân bản"); compact: true; enabled: d.current.length > 0
                        onClicked: d.promptRequested(qsTr("Nhân bản mẫu"), d.current.replace(/\.json$/i, "") + "_copy", "duplicate", d.current) }
                    AppButton { text: qsTr("Đổi tên"); compact: true; enabled: d.current.length > 0
                        onClicked: d.promptRequested(qsTr("Đổi tên mẫu"), d.current.replace(/\.json$/i, ""), "rename", d.current) }
                    AppButton { text: qsTr("Xoá"); compact: true; kind: "danger"; enabled: d.current.length > 0; onClicked: delDlg.open() }
                    AppButton { text: qsTr("Nhập từ tệp…"); compact: true; onClicked: d.importRequested() }
                    AppButton { text: qsTr("Xuất ra tệp…"); compact: true; enabled: d.current.length > 0; onClicked: d.exportRequested(d.current) }
                    AppButton { text: qsTr("Kiểm tra & chia sẻ…"); compact: true; enabled: d.current.length > 0; onClicked: d.shareRequested(d.current)
                        C.ToolTip.visible: hovered; C.ToolTip.delay: 500; C.ToolTip.text: qsTr("Xem mẫu gốc và tìm thông tin công ty / cá nhân trước khi gửi mẫu cho người khác") }
                    AppButton { text: qsTr("Mẫu có sẵn…"); compact: true; onClicked: d.galleryRequested() }
                    AppButton { text: qsTr("Mở thư mục"); compact: true; kind: "ghost"; onClicked: Lib.openFolder() }
                }
            }
            Rectangle { Layout.fillHeight: true; width: 1; color: Theme.border }
            ColumnLayout {
                Layout.fillWidth: true; Layout.fillHeight: true; spacing: 0
                CheckField { text: qsTr("Xem mẫu gốc (không ghép dữ liệu)"); checked: Lib.rawPreview; onToggled: Lib.rawPreview = checked
                    Layout.margins: Theme.s3; Layout.leftMargin: Theme.s5 }
                Rectangle {
                    Layout.fillWidth: true; Layout.fillHeight: true; color: Theme.canvas
                    Image { anchors.fill: parent; anchors.margins: Theme.s5; fillMode: Image.PreserveAspectFit; smooth: true; mipmap: true; cache: false
                        source: d.current.length ? Lib.previewSource : "" }
                }
                Text { text: d.message.length ? I18n.tr(d.message) : Lib.previewInfo; Layout.fillWidth: true; Layout.margins: Theme.s3; Layout.leftMargin: Theme.s5
                    elide: Text.ElideRight; font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm; color: d.message.length ? Theme.danger : Theme.textMuted }
            }
        }
    ]
    buttons: [
        AppButton { text: qsTr("Đóng"); kind: "ghost"; onClicked: d.close() },
        AppButton { id: useBtn; text: qsTr("Dùng mẫu này"); kind: "primary"; enabled: d.current.length > 0
            onClicked: { var n = d.current; var err = Doc.openTemplate(n); if (err.length) d.message = err; else d.close() } }
    ]

    NewTemplateDialog { id: newDlg; onCreated: (n) => { d.close() } }
    AppDialog {
        id: delDlg
        title: qsTr("Xoá mẫu?")
        body: [ Text { text: "'" + d.current + qsTr("' sẽ bị xoá khỏi thư viện.\nMột bản sao lưu được giữ trong template_backups.")
            wrapMode: Text.Wrap; Layout.preferredWidth: 360; font.family: Theme.fontFamily; font.pixelSize: Theme.fsBase; color: Theme.text } ]
        buttons: [ AppButton { text: qsTr("Huỷ"); kind: "ghost"; onClicked: delDlg.close() },
                   AppButton { text: qsTr("Xoá"); kind: "danger"; onClicked: { delDlg.close(); var n = d.current; var e = Lib.delete(n); d.finish(e); d.select(Lib.names.length ? Lib.names[0] : "") } } ]
    }
}
