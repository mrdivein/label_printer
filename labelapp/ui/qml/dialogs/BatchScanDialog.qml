import QtQuick
import QtQuick.Controls.Basic as C
import QtQuick.Layouts
import "../theme"
import "../components"

// Scanner-first queue: scan / paste codes, review matches, then print the checked rows.
AppDialog {
    id: d
    title: "Hàng đợi quét mã"
    subtitle: Scan.dataInfo
    contentPadding: 0
    width: Math.min(parent ? parent.width - 60 : 1100, 1100)
    height: Math.min(parent ? parent.height - 60 : 700, 700)
    property int resolvePos: -1
    property var candidates: []
    property var info: ({})

    onOpened: scanField.forceActiveFocus()
    function submit() {
        scanTimer.stop()
        var t = scanField.text
        scanField.text = ""
        Scan.process(t)
        scanField.forceActiveFocus()
    }

    body: [
        ColumnLayout {
            Layout.fillWidth: true; Layout.fillHeight: true; spacing: 0

            ColumnLayout {
                Layout.fillWidth: true; Layout.margins: Theme.s5; Layout.bottomMargin: Theme.s3; spacing: Theme.s2
                RowLayout {
                    spacing: Theme.s2
                    AppTextField {
                        id: scanField
                        Layout.fillWidth: true
                        placeholderText: "Quét hoặc dán UPC / EAN (được nhiều mã)…"
                        font.family: "Consolas"; font.pixelSize: Theme.fsMd
                        onAccepted: d.submit()
                        onTextEdited: {
                            scanTimer.stop()
                            if (autoCheck.checked && text.trim().length >= Scan.minLength) scanTimer.restart()
                        }
                        Keys.onEscapePressed: (e) => { text = ""; e.accepted = true }
                        Timer { id: scanTimer; interval: 350; onTriggered: d.submit() }
                    }
                    AppButton { text: "Xử lý"; onClicked: d.submit() }
                    AppButton { text: "Xoá ô nhập"; kind: "ghost"; onClicked: { scanField.text = ""; scanField.forceActiveFocus() } }
                }
                RowLayout {
                    spacing: Theme.s4
                    CheckField { id: autoCheck; text: "Tự xử lý khi máy quét dừng"; checked: true }
                    Text { text: "Quét trùng"; font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm; color: Theme.textMuted }
                    ComboField {
                        Layout.preferredWidth: 130
                        model: ["Tăng số lượng", "Thêm dòng"]
                        currentIndex: Scan.repeatMode === "Add Row" ? 1 : 0
                        onActivated: (i) => Scan.repeatMode = ["Increase Qty", "Add Row"][i]
                    }
                    CheckField { text: "Xoá dòng đã in thành công"; checked: Scan.removeAfterPrint; onToggled: Scan.removeAfterPrint = checked }
                    Item { Layout.fillWidth: true }
                    AppButton { text: "Làm mới chỉ mục dữ liệu"; kind: "ghost"; onClicked: Scan.refreshIndex() }
                }
            }

            // header
            Rectangle {
                Layout.fillWidth: true; Layout.preferredHeight: 30; color: Theme.surfaceAlt
                RowLayout {
                    anchors.fill: parent; anchors.leftMargin: Theme.s5; anchors.rightMargin: Theme.s5; spacing: Theme.s2
                    Text { text: "In"; Layout.preferredWidth: 44; font.family: Theme.fontFamily; font.pixelSize: Theme.fsXs; font.weight: Font.DemiBold; color: Theme.textMuted }
                    Text { text: "UPC / Mã vạch"; Layout.preferredWidth: 140; font.family: Theme.fontFamily; font.pixelSize: Theme.fsXs; font.weight: Font.DemiBold; color: Theme.textMuted }
                    Text { text: "Thương hiệu"; Layout.fillWidth: true; Layout.preferredWidth: 100; font.family: Theme.fontFamily; font.pixelSize: Theme.fsXs; font.weight: Font.DemiBold; color: Theme.textMuted }
                    Text { text: "Mẫu mã"; Layout.fillWidth: true; Layout.preferredWidth: 120; font.family: Theme.fontFamily; font.pixelSize: Theme.fsXs; font.weight: Font.DemiBold; color: Theme.textMuted }
                    Text { text: "Giá"; Layout.preferredWidth: 110; font.family: Theme.fontFamily; font.pixelSize: Theme.fsXs; font.weight: Font.DemiBold; color: Theme.textMuted }
                    Text { text: "SL"; Layout.preferredWidth: 70; font.family: Theme.fontFamily; font.pixelSize: Theme.fsXs; font.weight: Font.DemiBold; color: Theme.textMuted }
                    Text { text: "Trạng thái"; Layout.preferredWidth: 120; font.family: Theme.fontFamily; font.pixelSize: Theme.fsXs; font.weight: Font.DemiBold; color: Theme.textMuted }
                    Item { Layout.preferredWidth: 96 }
                }
                Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.border }
            }
            ListView {
                id: list
                Layout.fillWidth: true; Layout.fillHeight: true
                clip: true; model: Scan.queueModel
                boundsBehavior: Flickable.StopAtBounds
                C.ScrollBar.vertical: C.ScrollBar {}
                onCountChanged: positionViewAtEnd()
                Text { visible: list.count === 0; anchors.centerIn: parent; color: Theme.textFaint
                    text: "Quét một sản phẩm để bắt đầu."; font.family: Theme.fontFamily; font.pixelSize: Theme.fsBase }
                delegate: Rectangle {
                    required property int index
                    required property string code
                    required property string brand
                    required property string model
                    required property string price
                    required property int qty
                    required property bool checked
                    required property string status
                    required property bool ready
                    readonly property bool isChecked: checked
                    width: list.width; height: 36
                    color: index % 2 ? Theme.surfaceAlt : Theme.surface
                    RowLayout {
                        anchors.fill: parent; anchors.leftMargin: Theme.s5; anchors.rightMargin: Theme.s5; spacing: Theme.s2
                        CheckField { Layout.preferredWidth: 44; text: ""; enabled: ready; checked: isChecked; onToggled: Scan.toggle(index) }
                        Text { text: code; Layout.preferredWidth: 140; elide: Text.ElideRight; textFormat: Text.PlainText
                            font.family: "Consolas"; font.pixelSize: Theme.fsBase; color: Theme.text }
                        Text { text: brand; Layout.fillWidth: true; Layout.preferredWidth: 100; elide: Text.ElideRight; textFormat: Text.PlainText
                            font.family: Theme.fontFamily; font.pixelSize: Theme.fsBase; color: Theme.text }
                        Text { text: model; Layout.fillWidth: true; Layout.preferredWidth: 120; elide: Text.ElideRight; textFormat: Text.PlainText
                            font.family: Theme.fontFamily; font.pixelSize: Theme.fsBase; color: Theme.text }
                        Text { text: price; Layout.preferredWidth: 110; elide: Text.ElideRight; textFormat: Text.PlainText
                            font.family: Theme.fontFamily; font.pixelSize: Theme.fsBase; color: Theme.textMuted }
                        NumberField { Layout.preferredWidth: 70; implicitHeight: 26; enabled: ready; value: qty; step: 1; decimals: 0; from: 1; to: 999
                            onEdited: (v) => Scan.setQty(index, v) }
                        Text { text: status; Layout.preferredWidth: 120; elide: Text.ElideRight
                            font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm; font.weight: Font.Medium; color: ready ? Theme.success : Theme.danger }
                        RowLayout {
                            Layout.preferredWidth: 96; spacing: 2
                            AppButton { visible: status.indexOf("DUPLICATE") === 0; text: "Chọn"; compact: true
                                onClicked: { d.resolvePos = index; d.candidates = Scan.candidates(index); resolveDlg.open() } }
                            AppButton { visible: ready; text: "Xem"; kind: "ghost"; compact: true; onClicked: Scan.showInEditor(index) }
                            IconButton { text: "✕"; tip: "Bỏ"; implicitWidth: 28; implicitHeight: 26; onClicked: Scan.remove(index) }
                        }
                    }
                }
            }
            Separator { Layout.fillWidth: true }
            RowLayout {
                Layout.fillWidth: true; Layout.margins: Theme.s3; Layout.leftMargin: Theme.s5; Layout.rightMargin: Theme.s5; spacing: Theme.s2
                AppButton { text: "Chọn tất cả"; kind: "ghost"; compact: true; onClicked: Scan.setAllChecked(true) }
                AppButton { text: "Bỏ chọn"; kind: "ghost"; compact: true; onClicked: Scan.setAllChecked(false) }
                AppButton { text: "Xoá hàng đợi"; kind: "ghost"; compact: true; enabled: list.count > 0; onClicked: Scan.clearQueue() }
                Item { Layout.fillWidth: true }
                Text { text: Scan.summary; font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm; color: Theme.textMuted }
            }
        }
    ]
    buttons: [
        Text { text: "Enter = xử lý   Esc = xoá ô nhập"; color: Theme.textFaint; font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm },
        Item { Layout.fillWidth: true },
        AppButton { text: "Đóng"; kind: "ghost"; onClicked: d.close() },
        AppButton { text: "In các dòng đã chọn (" + Scan.checkedLabels + ")"; kind: "primary"; enabled: !Printing.busy && Scan.checkedLabels > 0
            onClicked: { d.info = Scan.prepareBatch(); confirmDlg.open() } }
    ]

    // ---- confirm
    AppDialog {
        id: confirmDlg
        readonly property bool blocked: !!(d.info.errors && d.info.errors.length > 0)
        title: blocked ? "Chưa in được" : "In hàng đợi quét mã"
        body: [
            ColumnLayout {
                Layout.preferredWidth: 440; spacing: Theme.s2
                Repeater { model: d.info.errors || []
                    Text { required property string modelData; text: "•  " + modelData; Layout.fillWidth: true; wrapMode: Text.Wrap
                        font.family: Theme.fontFamily; font.pixelSize: Theme.fsBase; color: Theme.danger } }
                Text { visible: !confirmDlg.blocked; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.text
                    font.family: Theme.fontFamily; font.pixelSize: Theme.fsBase
                    text: "Máy in: " + (d.info.printer || "") + "\nSản phẩm: " + (d.info.products || 0) + "\nTổng số tem: " + (d.info.labels || 0) }
                Repeater { model: confirmDlg.blocked ? [] : (d.info.warnings || [])
                    Text { required property string modelData; text: "•  " + modelData; Layout.fillWidth: true; wrapMode: Text.Wrap
                        font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm; color: Theme.warning } }
            }
        ]
        buttons: [
            AppButton { text: confirmDlg.blocked ? "Đóng" : "Huỷ"; kind: confirmDlg.blocked ? "primary" : "ghost"; onClicked: confirmDlg.close() },
            AppButton { visible: !confirmDlg.blocked; text: "In"; kind: "primary"
                onClicked: { confirmDlg.close(); Scan.printChecked() } }
        ]
    }

    // ---- resolve duplicate UPC
    AppDialog {
        id: resolveDlg
        title: "Mã này là sản phẩm nào?"
        body: [
            ColumnLayout {
                Layout.preferredWidth: 560; spacing: 0
                Repeater { model: d.candidates
                    delegate: Rectangle {
                        required property var modelData
                        required property int index
                        Layout.fillWidth: true; implicitHeight: 40
                        color: hov.hovered ? Theme.hover : (index % 2 ? Theme.surfaceAlt : Theme.surface)
                        HoverHandler { id: hov }
                        TapHandler { onTapped: { Scan.resolveDuplicate(d.resolvePos, modelData.index); resolveDlg.close() } }
                        RowLayout {
                            anchors.fill: parent; anchors.leftMargin: Theme.s3; anchors.rightMargin: Theme.s3; spacing: Theme.s3
                            Text { text: "Dòng " + modelData.sheetRow; Layout.preferredWidth: 60; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm }
                            Text { text: modelData.brand; Layout.preferredWidth: 130; elide: Text.ElideRight; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: Theme.fsBase }
                            Text { text: modelData.model; Layout.fillWidth: true; elide: Text.ElideRight; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: Theme.fsBase }
                            Text { text: modelData.price; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: Theme.fsBase }
                        }
                    } }
            }
        ]
        buttons: [ AppButton { text: "Huỷ"; kind: "ghost"; onClicked: resolveDlg.close() } ]
    }
}
