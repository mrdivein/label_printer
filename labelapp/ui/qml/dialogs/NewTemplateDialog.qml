import QtQuick
import QtQuick.Layouts
import "../theme"
import "../components"

AppDialog {
    id: d
    title: "New template"
    signal created(string name)
    property string error: ""
    onAboutToShow: { error = ""; nm.text = "New_Label"; preset.currentIndex = 0; applyPreset() }
    function applyPreset() { var p = Lib.presets[preset.currentIndex]; if (p) { w.value = p.w; h.value = p.h } }

    body: [
        ColumnLayout {
            Layout.preferredWidth: 400; spacing: Theme.s3
            PropertyRow { label: "Name"; AppTextField { id: nm; Layout.fillWidth: true; onAccepted: ok.clicked() } }
            PropertyRow { label: "Size preset"
                ComboField { id: preset; Layout.fillWidth: true; model: Lib.presets.map(function(p) { return p.name }); onActivated: d.applyPreset() } }
            PropertyRow { label: "Width × height"
                NumberField { id: w; Layout.fillWidth: true; value: 50; unit: "mm"; from: 1 }
                NumberField { id: h; Layout.fillWidth: true; value: 68; unit: "mm"; from: 1 } }
            PropertyRow { label: "Printer DPI"
                ComboField { id: dpi; Layout.fillWidth: true; model: ["203", "300", "600"]; currentIndex: 1 } }
            Text { visible: d.error.length > 0; text: d.error; color: Theme.danger; Layout.fillWidth: true; wrapMode: Text.Wrap
                font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm }
        }
    ]
    buttons: [
        AppButton { text: "Cancel"; kind: "ghost"; onClicked: d.close() },
        AppButton { id: ok; text: "Create"; kind: "primary"
            onClicked: { var e = Lib.createTemplate(nm.text, w.value, h.value, parseInt(dpi.currentText)); if (e.length) d.error = e; else { d.close(); d.created(nm.text) } } }
    ]
}
