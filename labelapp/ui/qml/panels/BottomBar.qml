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
    signal proofRequested()
    signal driverRequested()
    signal printerInfoRequested()

    RowLayout {
        anchors.fill: parent; anchors.leftMargin: Theme.s4; anchors.rightMargin: Theme.s4
        spacing: Theme.s3

        Text {
            text: Doc.doc.width_mm + " × " + Doc.doc.height_mm + " mm   ·   " + Doc.doc.dpi + " dpi   ·   " + Doc.doc.orientation
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
        Text { text: "Printer"; font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm; color: Theme.textMuted }
        ComboField {
            Layout.preferredWidth: 240
            model: Printing.printers
            currentIndex: Math.max(0, Printing.printers.indexOf(Printing.printer))
            displayText: Printing.printer.length ? Printing.printer : (Printing.printersLoading ? "Looking for printers…" : "No printer")
            onActivated: (i) => Printing.printer = Printing.printers[i]
            C.ToolTip.visible: hovered && !popup.visible; C.ToolTip.text: Printing.route.length ? "Route: " + Printing.route : "No printer selected"; C.ToolTip.delay: 600
        }
        IconButton { text: "⟳"; tip: "Refresh printers"; onClicked: Printing.refreshPrinters() }
        Text { text: "Copies"; font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm; color: Theme.textMuted }
        NumberField {
            Layout.preferredWidth: 64
            value: Printing.copies; step: 1; decimals: 0; from: 1; to: 999
            onEdited: (v) => Printing.copies = v
        }
        RowLayout {
            spacing: 1
            AppButton {
                text: "Print"; kind: "primary"; implicitWidth: 96
                enabled: !Printing.busy
                onClicked: bar.printRequested()
            }
            AppButton {
                text: "▾"; kind: "primary"; implicitWidth: 28; enabled: !Printing.busy
                onClicked: printMenu.popup(width - printMenu.implicitWidth, -printMenu.implicitHeight - 6)
                AppMenu {
                    id: printMenu
                    AppMenuItem { text: "Print current label"; hint: "Ctrl+P"; onTriggered: bar.printRequested() }
                    AppMenuItem { text: "Print selected rows…"; enabled: Data.hasData; onTriggered: bar.printSelected() }
                    AppMenuItem { text: "Print all rows…"; enabled: Data.hasData; onTriggered: bar.printAll() }
                    AppMenuSeparator {}
                    AppMenuItem { text: "PDF proof (nothing printed)"; onTriggered: bar.proofRequested() }
                    AppMenuItem { text: "Print vector PDF via Windows driver…"; onTriggered: bar.driverRequested() }
                    AppMenuSeparator {}
                    AppMenuItem { text: "Printer information…"; onTriggered: bar.printerInfoRequested() }
                }
            }
        }
    }
}
