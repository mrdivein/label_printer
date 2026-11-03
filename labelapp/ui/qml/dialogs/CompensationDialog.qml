import QtQuick
import QtQuick.Layouts
import "../theme"
import "../components"

// Ruler measurements of the printed compare sheet -> width/height scale and X/Y offset for every print.
AppDialog {
    id: d
    title: "Measure & apply compensation"
    signal verifyRequested()
    property var info: ({})
    property string error: ""
    onAboutToShow: {
        info = Printing.compareInfo(); error = ""
        mx.text = ""; my.text = ""; ml.text = ""; mt.text = ""
        sx.value = Doc.doc.scale_x_pct; sy.value = Doc.doc.scale_y_pct; ox.value = Doc.doc.offset_x_mm; oy.value = Doc.doc.offset_y_mm
    }
    function calc() {
        var r = Printing.computeCompensation({mx: mx.text, my: my.text, ml: ml.text, mt: mt.text})
        if (!r.ok) { error = r.error; return false }
        error = ""
        sx.value = r.scale_x_pct; sy.value = r.scale_y_pct; ox.value = r.offset_x_mm; oy.value = r.offset_y_mm
        return true
    }
    function apply() { Doc.setDocMany({scale_x_pct: sx.value, scale_y_pct: sy.value, offset_x_mm: ox.value, offset_y_mm: oy.value}) }

    body: [
        ColumnLayout {
            Layout.preferredWidth: 520; spacing: Theme.s3
            Text { Layout.fillWidth: true; wrapMode: Text.Wrap; font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm; color: Theme.textMuted
                text: d.info.hasSheet ? "Based on the last compare sheet printed (" + (d.info.compensated ? "with compensation" : "raw") + ")."
                                     : "Print a compare sheet first (Print ▾ → Test prints), measure it on the paper, then come back." }
            SectionHeader { text: "Measured on the paper (mm)"; Layout.fillWidth: true }
            PropertyRow { label: "Horizontal line"; labelWidth: 150; AppTextField { id: mx; Layout.fillWidth: true; placeholderText: "nominal " + d.info.refX } }
            PropertyRow { label: "Vertical line"; labelWidth: 150; AppTextField { id: my; Layout.fillWidth: true; placeholderText: "nominal " + d.info.refY } }
            PropertyRow { label: "Left edge → frame"; labelWidth: 150; AppTextField { id: ml; Layout.fillWidth: true; placeholderText: "nominal " + d.info.inset } }
            PropertyRow { label: "Top edge → frame"; labelWidth: 150; AppTextField { id: mt; Layout.fillWidth: true; placeholderText: "nominal " + d.info.inset } }
            AppButton { text: "Calculate from measurements"; enabled: d.info.hasSheet === true; onClicked: d.calc() }
            Text { visible: d.error.length > 0; text: d.error; color: Theme.danger; Layout.fillWidth: true; wrapMode: Text.Wrap; font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm }
            Separator { Layout.fillWidth: true }
            SectionHeader { text: "Compensation applied to every print"; Layout.fillWidth: true }
            GridLayout {
                columns: 4; columnSpacing: Theme.s2; rowSpacing: Theme.s2; Layout.fillWidth: true
                Text { text: "Width scale"; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm }
                NumberField { id: sx; Layout.fillWidth: true; unit: "%"; step: 0.1; from: 50; to: 150 }
                Text { text: "Height scale"; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm }
                NumberField { id: sy; Layout.fillWidth: true; unit: "%"; step: 0.1; from: 50; to: 150 }
                Text { text: "Offset X (+ right)"; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm }
                NumberField { id: ox; Layout.fillWidth: true; unit: "mm"; step: 0.1 }
                Text { text: "Offset Y (+ down)"; color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm }
                NumberField { id: oy; Layout.fillWidth: true; unit: "mm"; step: 0.1 }
            }
            Text { text: "Save the template to keep the compensation."; font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm; color: Theme.textFaint }
        }
    ]
    buttons: [
        AppButton { text: "Reset"; kind: "ghost"; onClicked: { sx.value = 100; sy.value = 100; ox.value = 0; oy.value = 0 } },
        Item { Layout.fillWidth: true },
        AppButton { text: "Cancel"; kind: "ghost"; onClicked: d.close() },
        AppButton { text: "Apply + verify print"; onClicked: { d.apply(); d.close(); d.verifyRequested() } },
        AppButton { text: "Apply"; kind: "primary"; onClicked: { d.apply(); d.close() } }
    ]
}
