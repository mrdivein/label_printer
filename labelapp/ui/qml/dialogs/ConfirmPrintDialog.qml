import QtQuick
import QtQuick.Layouts
import "../theme"
import "../components"

// Shows the preflight result and the print summary. `mode`: "current" | "driver"
AppDialog {
    id: d
    property var info: ({})
    property string mode: "current"
    readonly property bool blocked: !!(info.errors && info.errors.length > 0)
    function show(r, m) { info = r; mode = m || "current"; open() }
    title: blocked ? "Cannot print yet" : (mode === "driver" ? "Print via Windows driver" : "Print current label")

    body: [
        ColumnLayout {
            visible: d.blocked
            Layout.preferredWidth: 440; spacing: Theme.s2
            Repeater { model: d.info.errors || []
                Text { required property string modelData; text: "•  " + modelData; Layout.fillWidth: true; wrapMode: Text.Wrap
                    font.family: Theme.fontFamily; font.pixelSize: Theme.fsBase; color: Theme.danger } }
        },
        GridLayout {
            visible: !d.blocked
            columns: 2; columnSpacing: Theme.s4; rowSpacing: Theme.s2; Layout.preferredWidth: 440
            Text { text: "Printer"; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: Theme.fsBase }
            Text { text: d.info.printer || ""; Layout.fillWidth: true; elide: Text.ElideRight; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: Theme.fsBase; font.weight: Font.Medium }
            Text { text: "Copies"; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: Theme.fsBase }
            Text { text: String(d.info.copies || 1); color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: Theme.fsBase; font.weight: Font.Medium }
            Text { text: "Paper"; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: Theme.fsBase }
            Text { text: (d.info.paper || "") + "  ·  " + (d.info.dpi || "") + " dpi"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: Theme.fsBase; font.weight: Font.Medium }
            Text { text: "Route"; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: Theme.fsBase }
            Text { text: d.mode === "driver" ? "VECTOR PDF → Windows driver" : (d.info.route || ""); Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.text
                font.family: Theme.fontFamily; font.pixelSize: Theme.fsBase; font.weight: Font.Medium }
        },
        ColumnLayout {
            visible: !d.blocked && !!(d.info.warnings && d.info.warnings.length > 0)
            Layout.preferredWidth: 440; spacing: Theme.s1
            SectionHeader { text: "Warnings"; Layout.fillWidth: true }
            Repeater { model: d.info.warnings || []
                Text { required property string modelData; text: "•  " + modelData; Layout.fillWidth: true; wrapMode: Text.Wrap
                    font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm; color: Theme.warning } }
        }
    ]
    buttons: [
        AppButton { text: d.blocked ? "Close" : "Cancel"; kind: d.blocked ? "primary" : "ghost"; onClicked: d.close() },
        AppButton { visible: !d.blocked; text: d.info.warnings && d.info.warnings.length ? "Print anyway" : "Print"; kind: "primary"
            onClicked: { d.close(); if (d.mode === "driver") Printing.printViaDriver(); else Printing.printCurrent() } }
    ]
}
