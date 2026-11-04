import QtQuick
import QtQuick.Controls.Basic as C
import QtQuick.Layouts
import "../theme"
import "../components"

Panel {
    id: bar
    implicitHeight: 52
    borderTop: true
    signal printRequested()
    signal printSelected()
    signal printAll()
    signal batchScanRequested()
    signal proofRequested()
    signal driverRequested()
    signal printerInfoRequested()
    signal testRequested(string kind)
    signal compensationRequested()
    signal profilesRequested()

    RowLayout {
        anchors.fill: parent; anchors.leftMargin: Theme.s4; anchors.rightMargin: Theme.s4
        spacing: Theme.s3

        Text {
            text: Doc.doc.width_mm + " × " + Doc.doc.height_mm + " mm   ·   " + Doc.doc.dpi + " dpi   ·   " + (Doc.doc.orientation === "landscape" ? "ngang" : "dọc")
            font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm; font.weight: Font.Medium; color: Theme.textMuted
        }
        Separator { vertical: true }
        Text {
            id: status
            text: App.status
            Layout.fillWidth: true; elide: Text.ElideRight
            font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm; color: Theme.textMuted
        }
        BusyIndicator2 { visible: Data.loading || Printing.printersLoading || Printing.busy }
        Text { text: "Máy in"; font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm; color: Theme.textMuted }
        ComboField {
            Layout.preferredWidth: 240
            model: Printing.printers
            currentIndex: Math.max(0, Printing.printers.indexOf(Printing.printer))
            displayText: Printing.printer.length ? Printing.printer : (Printing.printersLoading ? "Đang tìm máy in…" : "Chưa có máy in")
            onActivated: (i) => Printing.printer = Printing.printers[i]
            C.ToolTip.visible: hovered && !popup.visible; C.ToolTip.text: Printing.route.length ? "Đường in: " + Printing.route : "Chưa chọn máy in"; C.ToolTip.delay: 600
        }
        IconButton { text: "⟳"; tip: "Tìm lại máy in"; onClicked: Printing.refreshPrinters() }
        Text { text: "Số bản"; font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm; color: Theme.textMuted }
        NumberField {
            Layout.preferredWidth: 64
            value: Printing.copies; step: 1; decimals: 0; from: 1; to: 999
            onEdited: (v) => Printing.copies = v
        }
        RowLayout {
            spacing: 1
            AppButton {
                text: "In tem"; kind: "primary"; implicitWidth: 96
                enabled: !Printing.busy
                onClicked: bar.printRequested()
            }
            AppButton {
                text: "▾"; kind: "primary"; implicitWidth: 28; enabled: !Printing.busy
                onClicked: printMenu.popup(width - printMenu.implicitWidth, -printMenu.implicitHeight - 6)
                AppMenu {
                    id: printMenu
                    AppMenuItem { text: "In tem hiện tại"; hint: "Ctrl+P"; onTriggered: bar.printRequested() }
                    AppMenuItem { text: "In các dòng đã chọn…"; enabled: Data.hasData; onTriggered: bar.printSelected() }
                    AppMenuItem { text: "In tất cả các dòng…"; enabled: Data.hasData; onTriggered: bar.printAll() }
                    AppMenuItem { text: "Hàng đợi quét mã…"; hint: "F8"; enabled: Data.hasData; onTriggered: bar.batchScanRequested() }
                    AppMenuSeparator {}
                    AppMenuItem { text: "PDF kiểm tra (không in)"; onTriggered: bar.proofRequested() }
                    AppMenuItem { text: "In PDF vector qua driver Windows…"; onTriggered: bar.driverRequested() }
                    AppMenuSeparator {}
                    AppMenu {
                        title: "In thử"
                        AppMenuItem { text: "In thử tem hiện tại (1 bản)"; onTriggered: bar.testRequested("current") }
                        AppMenuItem { text: "Lưới hiệu chỉnh"; onTriggered: bar.testRequested("calibration") }
                        AppMenuItem { text: "Tem kèm thước mm"; onTriggered: bar.testRequested("ruler") }
                        AppMenuItem { text: "Chất lượng chữ"; onTriggered: bar.testRequested("text_quality") }
                        AppMenuItem { text: "Chất lượng mã vạch"; onTriggered: bar.testRequested("barcode_quality") }
                        AppMenuSeparator {}
                        AppMenuItem { text: "Tờ so sánh — gốc"; onTriggered: bar.testRequested("compare_raw") }
                        AppMenuItem { text: "Tờ so sánh — có bù"; onTriggered: bar.testRequested("compare_comp") }
                        AppMenuItem { text: "Đo && áp dụng bù sai số…"; onTriggered: bar.compensationRequested() }
                    }
                    AppMenuItem { text: "Hồ sơ máy in…"; onTriggered: bar.profilesRequested() }
                    AppMenuItem { text: "Thông tin máy in…"; onTriggered: bar.printerInfoRequested() }
                }
            }
        }
    }
}
