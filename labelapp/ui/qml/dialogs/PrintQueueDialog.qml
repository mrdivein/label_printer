import QtQuick
import QtQuick.Controls.Basic as C
import QtQuick.Layouts
import "../theme"
import "../components"

AppDialog {
    id: d
    signal exportRequested()
    title: Printing.queueTitle
    subtitle: Printing.queueSummary
    contentPadding: 0
    width: Math.min(parent ? parent.width - 80 : 900, 920)
    height: Math.min(parent ? parent.height - 80 : 640, 640)

    property var info: ({})

    body: [
        ColumnLayout {
            Layout.fillWidth: true; Layout.fillHeight: true; spacing: 0
            // header row
            Rectangle {
                Layout.fillWidth: true; Layout.preferredHeight: 30; color: Theme.surfaceAlt
                RowLayout {
                    anchors.fill: parent; anchors.leftMargin: Theme.s5; anchors.rightMargin: Theme.s5; spacing: 0
                    Text { text: "#"; Layout.preferredWidth: 40; font.family: Theme.fontFamily; font.pixelSize: Theme.fsXs; font.weight: Font.DemiBold; color: Theme.textMuted }
                    Repeater { model: Printing.queueColumns
                        Text { required property string modelData; text: modelData; Layout.fillWidth: true; Layout.preferredWidth: 100; elide: Text.ElideRight
                            font.family: Theme.fontFamily; font.pixelSize: Theme.fsXs; font.weight: Font.DemiBold; color: Theme.textMuted } }
                    Text { text: "SL"; Layout.preferredWidth: 70; font.family: Theme.fontFamily; font.pixelSize: Theme.fsXs; font.weight: Font.DemiBold; color: Theme.textMuted }
                    Item { Layout.preferredWidth: 30 }
                }
                Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.border }
            }
            ListView {
                id: q
                Layout.fillWidth: true; Layout.fillHeight: true
                clip: true; model: Printing.queueModel
                boundsBehavior: Flickable.StopAtBounds
                C.ScrollBar.vertical: C.ScrollBar {}
                delegate: Rectangle {
                    required property int index
                    required property int number
                    required property var cells
                    required property int qty
                    width: q.width; height: 36
                    color: index % 2 ? Theme.surfaceAlt : Theme.surface
                    RowLayout {
                        anchors.fill: parent; anchors.leftMargin: Theme.s5; anchors.rightMargin: Theme.s5; spacing: 0
                        Text { text: number; Layout.preferredWidth: 40; font.family: Theme.fontFamily; font.pixelSize: Theme.fsBase; color: Theme.textMuted }
                        Repeater { model: cells
                            Text { required property string modelData; text: modelData; Layout.fillWidth: true; Layout.preferredWidth: 100; elide: Text.ElideRight; textFormat: Text.PlainText
                                font.family: Theme.fontFamily; font.pixelSize: Theme.fsBase; color: Theme.text } }
                        NumberField { Layout.preferredWidth: 70; implicitHeight: 26; value: qty; step: 1; decimals: 0; from: 1; to: 999
                            onEdited: (v) => Printing.setQty(index, v) }
                        IconButton { text: "✕"; tip: "Remove from queue"; implicitWidth: 30; implicitHeight: 26; onClicked: Printing.removeFromQueue(index) }
                    }
                }
            }
            Separator { Layout.fillWidth: true }
            RowLayout {
                Layout.fillWidth: true; Layout.margins: Theme.s3; Layout.leftMargin: Theme.s5; spacing: Theme.s2
                Text { text: "Đặt số lượng tất cả bằng"; font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm; color: Theme.textMuted }
                NumberField { id: allQty; Layout.preferredWidth: 64; implicitHeight: 26; value: 1; step: 1; decimals: 0; from: 1; to: 999; onEdited: (v) => Printing.setAllQty(v) }
                Item { Layout.fillWidth: true }
                Text { id: err; visible: text.length > 0; color: Theme.danger; font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm; elide: Text.ElideRight; Layout.maximumWidth: 360 }
            }
        }
    ]
    buttons: [
        AppButton { text: "Xuất tất cả ra PDF…"; kind: "ghost"; onClicked: d.exportRequested() },
        Item { Layout.fillWidth: true },
        AppButton { text: "Huỷ"; kind: "ghost"; onClicked: d.close() },
        AppButton { text: "In " + Printing.queueSummary.split("·").pop().trim(); kind: "primary"; enabled: !Printing.busy
            onClicked: {
                var r = Printing.prepareQueuePrint()
                if (!r.ok) { err.text = r.errors.join("  "); return }
                err.text = ""
                d.close(); Printing.startQueue()
            } }
    ]
}
