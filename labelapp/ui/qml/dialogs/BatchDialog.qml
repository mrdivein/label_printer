import QtQuick
import QtQuick.Controls.Basic as C
import QtQuick.Layouts
import "../theme"
import "../components"

// Progress of a running print batch + the skip / retry / stop choice when a row fails.
AppDialog {
    id: d
    title: "Đang in…"
    closePolicy: C.Popup.NoAutoClose
    property int errorRow: 0
    property string errorText: ""
    property bool failed: false

    Connections {
        target: Printing
        function onBusyChanged() { if (Printing.busy) { d.failed = false; d.open() } }
        function onBatchError(row, msg) { d.errorRow = row; d.errorText = msg; d.failed = true }
        function onBatchFinished(text) { d.failed = false; d.close() }
    }

    body: [
        ColumnLayout {
            Layout.preferredWidth: 420; spacing: Theme.s3
            Text { text: d.failed ? "Dòng " + d.errorRow + " bị lỗi" : Printing.progressText
                font.family: Theme.fontFamily; font.pixelSize: Theme.fsBase; font.weight: Font.Medium; color: d.failed ? Theme.danger : Theme.text }
            Text { visible: d.failed; text: d.errorText; Layout.fillWidth: true; wrapMode: Text.Wrap; textFormat: Text.PlainText
                font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm; color: Theme.textMuted }
            C.ProgressBar {
                Layout.fillWidth: true; value: Printing.progress
                background: Rectangle { implicitHeight: 6; radius: 3; color: Theme.border }
                contentItem: Item { Rectangle { width: parent.width * Printing.progress; height: parent.height; radius: 3; color: Theme.accent
                    Behavior on width { NumberAnimation { duration: Theme.dFast } } } }
            }
        }
    ]
    buttons: [
        AppButton { visible: !d.failed; text: "Huỷ"; kind: "ghost"; onClicked: Printing.cancelBatch() },
        AppButton { visible: d.failed; text: "Dừng"; kind: "danger"; onClicked: Printing.batchDecision("stop") },
        AppButton { visible: d.failed; text: "Bỏ qua dòng"; onClicked: { d.failed = false; Printing.batchDecision("skip") } },
        AppButton { visible: d.failed; text: "Thử lại"; kind: "primary"; onClicked: { d.failed = false; Printing.batchDecision("retry") } }
    ]
}
