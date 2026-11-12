import QtQuick
import QtQuick.Controls.Basic as C
import QtQuick.Layouts
import "../theme"
import "../components"

// Before a template leaves the company: show the ORIGINAL template (no data row bound) next to what will be
// sent, list everything that could identify the company (fixed texts, phone / email / website, logo files,
// hidden elements, printer settings) with an action per item, and export the cleaned copy.
AppDialog {
    id: d
    title: qsTr("Kiểm tra trước khi chia sẻ")
    subtitle: Lib.shareName.replace(/\.json$/i, "")
    contentPadding: 0
    width: Math.min(parent ? parent.width - 60 : 1100, 1100)
    height: Math.min(parent ? parent.height - 60 : 740, 740)
    signal exportRequested()

    function openFor(name) {
        var e = Lib.shareCheck(name)
        if (e.length) { App.errorRaised(qsTr("Kiểm tra trước khi chia sẻ"), e); return }
        open()
    }

    body: [
        RowLayout {
            Layout.fillWidth: true; Layout.fillHeight: true; spacing: 0
            // ---- preview: cleaned copy / original
            ColumnLayout {
                Layout.fillWidth: true; Layout.fillHeight: true; spacing: 0
                RowLayout {
                    Layout.fillWidth: true; Layout.margins: Theme.s3; spacing: 0
                    AppButton { text: qsTr("Bản sẽ gửi đi (đã làm sạch)"); compact: true; kind: Lib.shareShowsCleaned ? "primary" : "ghost"
                        onClicked: Lib.showShareCleaned(true) }
                    AppButton { text: qsTr("Bản gốc trong thư viện"); compact: true; kind: Lib.shareShowsCleaned ? "ghost" : "primary"
                        onClicked: Lib.showShareCleaned(false) }
                    Item { Layout.fillWidth: true }
                }
                Rectangle {
                    Layout.fillWidth: true; Layout.fillHeight: true; color: Theme.canvas
                    Image { anchors.fill: parent; anchors.margins: Theme.s5; fillMode: Image.PreserveAspectFit; smooth: true; mipmap: true
                        cache: false; source: Lib.shareName.length ? Lib.sharePreviewSource : "" }
                }
                Text { Layout.fillWidth: true; Layout.margins: Theme.s3; wrapMode: Text.Wrap
                    text: qsTr("Ghi chú: bản gửi đi bỏ cả lịch sử, đường dẫn dữ liệu và thông tin nguồn.")
                    font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm; color: Theme.textMuted }
            }
            Rectangle { Layout.fillHeight: true; width: 1; color: Theme.border }
            // ---- findings
            ColumnLayout {
                Layout.preferredWidth: 430; Layout.fillHeight: true; spacing: 0
                Text { text: Lib.shareSummary; Layout.fillWidth: true; Layout.margins: Theme.s3; wrapMode: Text.Wrap
                    font.family: Theme.fontFamily; font.pixelSize: Theme.fsMd; font.weight: Font.DemiBold
                    color: Lib.shareFindings.length && Lib.shareFindings[0].severity > 1 ? Theme.warning : Theme.success }
                Separator { Layout.fillWidth: true }
                ListView {
                    id: list
                    Layout.fillWidth: true; Layout.fillHeight: true
                    clip: true; spacing: Theme.s2
                    topMargin: Theme.s2; bottomMargin: Theme.s2
                    model: Lib.shareFindings
                    boundsBehavior: Flickable.StopAtBounds
                    C.ScrollBar.vertical: C.ScrollBar {}
                    delegate: Rectangle {
                        required property var modelData
                        x: Theme.s3; width: list.width - Theme.s3 * 2
                        height: col.implicitHeight + Theme.s3 * 2
                        radius: Theme.radiusMd; color: Theme.surface
                        border.width: 1; border.color: modelData.severity > 1 ? Theme.warning : Theme.border
                        ColumnLayout {
                            id: col
                            anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: Theme.s3
                            spacing: 3
                            Text { text: modelData.title; Layout.fillWidth: true; wrapMode: Text.Wrap
                                font.family: Theme.fontFamily; font.pixelSize: Theme.fsBase; font.weight: Font.DemiBold
                                color: modelData.severity > 1 ? Theme.warning : Theme.text }
                            Text { text: modelData.reason; Layout.fillWidth: true; wrapMode: Text.Wrap
                                font.family: Theme.fontFamily; font.pixelSize: Theme.fsXs; color: Theme.textMuted }
                            Text { text: "“" + modelData.detail + "”"; Layout.fillWidth: true; wrapMode: Text.WrapAnywhere; textFormat: Text.PlainText
                                font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm; color: Theme.text }
                            Text { visible: modelData.action === "replace" && modelData.replacement.length > 0; Layout.fillWidth: true
                                text: "→ " + modelData.replacement; wrapMode: Text.WrapAnywhere; textFormat: Text.PlainText
                                font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm; color: Theme.success }
                            ComboField {
                                Layout.fillWidth: true; Layout.topMargin: 2
                                model: modelData.actionLabels
                                currentIndex: Math.max(0, modelData.actions.indexOf(modelData.action))
                                onActivated: (i) => Lib.setShareAction(modelData.id, modelData.actions[i])
                            }
                        }
                    }
                }
            }
        }
    ]
    buttons: [
        AppButton { text: qsTr("Đóng"); kind: "ghost"; onClicked: d.close() },
        AppButton { text: qsTr("Xuất bản đã làm sạch…"); kind: "primary"; onClicked: d.exportRequested() }
    ]
}
