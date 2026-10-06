import QtQuick
import QtQuick.Controls.Basic as C
import QtQuick.Layouts
import "../theme"
import "../components"

// Properties of the selection (schema comes from Python), or the label settings when nothing is selected.
Panel {
    id: p
    borderLeft: true
    signal pickImage()

    readonly property bool hasSel: Doc.selectionCount > 0
    readonly property var d: Doc.doc

    C.ScrollView {
        id: scroll
        anchors.fill: parent
        contentWidth: availableWidth
        clip: true
        C.ScrollBar.horizontal.policy: C.ScrollBar.AlwaysOff

        ColumnLayout {
            width: scroll.availableWidth
            spacing: 0

            // ---------- header ----------
            Item {
                Layout.fillWidth: true; Layout.preferredHeight: 56
                Column {
                    anchors.left: parent.left; anchors.leftMargin: Theme.s4; anchors.verticalCenter: parent.verticalCenter; spacing: 1
                    Text { text: p.hasSel ? Doc.selectionTitle : "Label"; font.family: Theme.fontFamily; font.pixelSize: Theme.fsLg; font.weight: Font.DemiBold; color: Theme.text }
                    Text { text: p.hasSel ? (Doc.selectionCount > 1 ? "Edits apply to every selected element" : "Element " + (Doc.selection[0] + 1))
                                          : (d.width_mm + " × " + d.height_mm + " mm  ·  " + d.dpi + " dpi")
                        font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm; color: Theme.textMuted }
                }
                AppButton {
                    visible: p.hasSel; text: Doc.selectionLocked ? "Unlock" : "Lock"; compact: true; kind: "secondary"
                    anchors.right: parent.right; anchors.rightMargin: Theme.s4; anchors.verticalCenter: parent.verticalCenter
                    onClicked: Doc.setLocked(!Doc.selectionLocked)
                }
            }
            Separator { Layout.fillWidth: true }

            // ---------- selection properties ----------
            ListView {
                id: props
                visible: p.hasSel
                Layout.fillWidth: true
                Layout.preferredHeight: contentHeight
                interactive: false
                model: Doc.inspectorModel
                spacing: 0
                section.property: "group"
                section.delegate: Item {
                    required property string section
                    width: props.width; height: 36
                    SectionHeader { text: parent.section; anchors.left: parent.left; anchors.right: parent.right
                        anchors.leftMargin: Theme.s4; anchors.rightMargin: Theme.s4; anchors.bottom: parent.bottom; anchors.bottomMargin: 0 }
                }
                delegate: Item {
                    id: row
                    required property string key
                    required property string label
                    required property string kind
                    required property string unit
                    required property var choices
                    required property var value
                    required property bool mixed
                    width: props.width; height: 36
                    PropertyRow {
                        anchors.left: parent.left; anchors.right: parent.right; anchors.leftMargin: Theme.s4; anchors.rightMargin: Theme.s4
                        anchors.verticalCenter: parent.verticalCenter
                        label: row.kind === "bool" ? "" : row.label
                        labelWidth: 92
                        Loader {
                            Layout.fillWidth: true
                            sourceComponent: row.kind === "number" ? numberC : row.kind === "bool" ? boolC : row.kind === "choice" ? choiceC
                                           : row.kind === "path" ? pathC : textC
                        }
                    }
                    Component { id: numberC
                        NumberField { value: row.value === null || row.value === "" ? 0 : Number(row.value); mixed: row.mixed; unit: row.unit
                            step: row.unit === "pt" ? 0.5 : row.unit === "°" ? 1 : 0.1
                            onEdited: (v) => Doc.setProp(row.key, v) } }
                    Component { id: boolC
                        CheckField { text: row.label; checked: row.value === true; mixed: row.mixed
                            onToggled: Doc.setProp(row.key, checked) } }
                    Component { id: choiceC
                        ComboField { model: row.choices; mixed: row.mixed
                            currentIndex: Math.max(0, row.choices.indexOf(row.value === null ? "" : row.value))
                            displayText: (!row.mixed && row.value === "") ? "None" : (row.value === null ? "" : String(row.value))
                            onActivated: (i) => Doc.setProp(row.key, row.choices[i]) } }
                    Component { id: textC
                        AppTextField { mixed: row.mixed; text: row.value === null ? "" : String(row.value)
                            placeholderText: row.key === "show_if" ? "e.g. {{Origin}}" : (row.mixed ? "Mixed" : "")
                            onEditingFinished: if (text !== (row.value === null ? "" : String(row.value))) Doc.setProp(row.key, text) } }
                    Component { id: pathC
                        RowLayout { spacing: Theme.s1
                            AppTextField { Layout.fillWidth: true; mixed: row.mixed; text: row.value === null ? "" : String(row.value)
                                onEditingFinished: if (text !== String(row.value)) Doc.setProp(row.key, text) }
                            AppButton { text: "…"; compact: true; implicitWidth: 30; onClicked: p.pickImage() } } }
                }
            }

            // ---------- arrange ----------
            ColumnLayout {
                visible: p.hasSel
                Layout.fillWidth: true; Layout.leftMargin: Theme.s4; Layout.rightMargin: Theme.s4; Layout.topMargin: Theme.s3
                spacing: Theme.s2
                SectionHeader { text: "Arrange"; Layout.fillWidth: true }
                Flow {
                    Layout.fillWidth: true; spacing: Theme.s1
                    AppButton { text: "Center H"; compact: true; onClicked: Doc.centerOnLabel("h") }
                    AppButton { text: "Center V"; compact: true; onClicked: Doc.centerOnLabel("v") }
                    AppButton { text: "↺ 90°"; compact: true; onClicked: Doc.rotateBy(-90) }
                    AppButton { text: "↻ 90°"; compact: true; onClicked: Doc.rotateBy(90) }
                    AppButton { text: "0°"; compact: true; onClicked: Doc.resetRotation() }
                }
                Flow {
                    visible: Doc.selectionCount > 1
                    Layout.fillWidth: true; spacing: Theme.s1
                    AppButton { text: "Align left"; compact: true; onClicked: Doc.align("left") }
                    AppButton { text: "Align top"; compact: true; onClicked: Doc.align("top") }
                    AppButton { text: "Center ↔"; compact: true; onClicked: Doc.align("hcenter") }
                    AppButton { text: "Center ↕"; compact: true; onClicked: Doc.align("vcenter") }
                }
                Item { Layout.preferredHeight: Theme.s4 }
            }

            // ---------- label settings (no selection) ----------
            ColumnLayout {
                visible: !p.hasSel
                Layout.fillWidth: true; Layout.leftMargin: Theme.s4; Layout.rightMargin: Theme.s4; Layout.topMargin: Theme.s1
                spacing: Theme.s2

                SectionHeader { text: "Paper"; Layout.fillWidth: true }
                PropertyRow { label: "Width"; NumberField { value: d.width_mm; unit: "mm"; from: 1; Layout.fillWidth: true; onEdited: (v) => Doc.setDoc("width_mm", v) } }
                PropertyRow { label: "Height"; NumberField { value: d.height_mm; unit: "mm"; from: 1; Layout.fillWidth: true; onEdited: (v) => Doc.setDoc("height_mm", v) } }
                PropertyRow { label: "Orientation"
                    ComboField { Layout.fillWidth: true; model: ["portrait", "landscape"]; currentIndex: d.orientation === "landscape" ? 1 : 0
                        onActivated: (i) => Doc.setDoc("orientation", model[i]) } }
                PropertyRow { label: "Printer DPI"
                    NumberField { value: d.dpi; step: 1; decimals: 0; from: 72; to: 1200; Layout.fillWidth: true; onEdited: (v) => Doc.setDoc("dpi", v) } }
                PropertyRow { label: "Copies"
                    NumberField { value: d.copies; step: 1; decimals: 0; from: 1; to: 999; Layout.fillWidth: true; onEdited: (v) => Doc.setDoc("copies", v) } }

                SectionHeader { text: "Printer compensation"; Layout.fillWidth: true; Layout.topMargin: Theme.s3 }
                PropertyRow { label: "Offset X"; NumberField { value: d.offset_x_mm; unit: "mm"; step: 0.1; Layout.fillWidth: true; onEdited: (v) => Doc.setDoc("offset_x_mm", v) } }
                PropertyRow { label: "Offset Y"; NumberField { value: d.offset_y_mm; unit: "mm"; step: 0.1; Layout.fillWidth: true; onEdited: (v) => Doc.setDoc("offset_y_mm", v) } }
                PropertyRow { label: "Skew"; NumberField { value: d.rotation_deg; unit: "°"; step: 0.05; Layout.fillWidth: true; onEdited: (v) => Doc.setDoc("rotation_deg", v) } }
                PropertyRow { label: "Scale X"; NumberField { value: d.scale_x_pct; unit: "%"; step: 0.1; Layout.fillWidth: true; from: 50; to: 150; onEdited: (v) => Doc.setDoc("scale_x_pct", v) } }
                PropertyRow { label: "Scale Y"; NumberField { value: d.scale_y_pct; unit: "%"; step: 0.1; Layout.fillWidth: true; from: 50; to: 150; onEdited: (v) => Doc.setDoc("scale_y_pct", v) } }

                SectionHeader { text: "Print quality"; Layout.fillWidth: true; Layout.topMargin: Theme.s3 }
                PropertyRow { label: "Render mode"
                    ComboField { Layout.fillWidth: true; model: ["thermal_crisp", "standard"]; currentIndex: d.render_mode === "standard" ? 1 : 0
                        onActivated: (i) => Doc.setDoc("render_mode", model[i]) } }
                PropertyRow { label: "Threshold"
                    NumberField { value: d.threshold; step: 1; decimals: 0; from: 1; to: 255; Layout.fillWidth: true; onEdited: (v) => Doc.setDoc("threshold", v) } }
                PropertyRow { label: "Oversample"
                    NumberField { value: d.oversample; step: 1; decimals: 0; from: 1; to: 6; Layout.fillWidth: true; onEdited: (v) => Doc.setDoc("oversample", v) } }
                Text { text: "Recommended for 300 dpi thermal: threshold 135–155, oversample 4."
                    Layout.fillWidth: true; wrapMode: Text.Wrap; font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm; color: Theme.textFaint }

                SectionHeader { text: "Guides"; Layout.fillWidth: true; Layout.topMargin: Theme.s3 }
                CheckField { text: "Show print area guide"; checked: d.virtual_area_show; onToggled: Doc.setDoc("virtual_area_show", checked) }
                CheckField { text: "Show preview guides"; checked: Doc.showGuides; onToggled: Doc.showGuides = checked }
                CheckField { text: "Show fold regions"; checked: Doc.showFold; onToggled: Doc.showFold = checked }
                PropertyRow { label: "Snap"
                    NumberField { value: Doc.snapMm; unit: "mm"; step: 0.05; from: 0; to: 5; Layout.fillWidth: true; onEdited: (v) => Doc.snapMm = v } }
                Item { Layout.preferredHeight: Theme.s5 }
            }
        }
    }
}
