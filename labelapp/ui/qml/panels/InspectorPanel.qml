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
    // printer-specific tuning lives in printer profiles; keep it out of the way unless asked for
    property bool showAdvanced: false
    property bool showView: false

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
                    Text { text: p.hasSel ? Doc.selectionTitle : qsTr("Khổ tem"); font.family: Theme.fontFamily; font.pixelSize: Theme.fsLg; font.weight: Font.DemiBold; color: Theme.text }
                    Text { text: p.hasSel ? (Doc.selectionCount > 1 ? qsTr("Thay đổi áp dụng cho mọi phần tử đang chọn") : qsTr("Phần tử số ") + (Doc.selection[0] + 1))
                                          : (d.width_mm + qsTr(" × ") + d.height_mm + " mm  ·  " + d.dpi + " dpi")
                        font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm; color: Theme.textMuted }
                }
                AppButton {
                    visible: p.hasSel; text: Doc.selectionLocked ? qsTr("Mở khoá") : qsTr("Khoá"); compact: true; kind: "secondary"
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
                    required property var choice_labels
                    required property var value
                    required property bool mixed
                    readonly property var val: (value === undefined || value === null) ? null : value     // Python None arrives as undefined
                    // what the combo shows: Vietnamese labels when the schema has them, else the stored values
                    readonly property var shown: (choice_labels && choice_labels.length === (choices ? choices.length : -1)) ? choice_labels : choices
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
                        NumberField { value: row.val === null || row.val === "" ? 0 : Number(row.val); mixed: row.mixed; unit: row.unit
                            step: row.unit === "pt" ? 0.5 : row.unit === "°" ? 1 : 0.1
                            onEdited: (v) => Doc.setProp(row.key, v) } }
                    Component { id: boolC
                        CheckField { text: row.label; checked: row.val === true; mixed: row.mixed
                            onToggled: Doc.setProp(row.key, checked) } }
                    Component { id: choiceC
                        ComboField { model: row.shown; mixed: row.mixed
                            readonly property int at: row.choices.indexOf(row.val === null ? "" : row.val)
                            currentIndex: Math.max(0, at)
                            displayText: at >= 0 ? String(row.shown[at]) : (row.val === null || row.val === "" ? qsTr("Không") : String(row.val))
                            onActivated: (i) => Doc.setProp(row.key, row.choices[i]) } }
                    Component { id: textC
                        AppTextField { mixed: row.mixed; text: row.val === null ? "" : String(row.val)
                            placeholderText: row.key === "show_if" ? "vd. {{XuatXu}}" : (row.mixed ? qsTr("Nhiều giá trị") : "")
                            onEditingFinished: if (text !== (row.val === null ? "" : String(row.val))) Doc.setProp(row.key, text) } }
                    Component { id: pathC
                        RowLayout { spacing: Theme.s1
                            AppTextField { Layout.fillWidth: true; mixed: row.mixed; text: row.val === null ? "" : String(row.val)
                                onEditingFinished: if (text !== (row.val === null ? "" : String(row.val))) Doc.setProp(row.key, text) }
                            AppButton { text: "…"; compact: true; implicitWidth: 30; onClicked: p.pickImage() } } }
                }
            }

            // ---------- arrange (several elements: the floating toolbar covers single ones) ----------
            ColumnLayout {
                visible: p.hasSel
                Layout.fillWidth: true; Layout.leftMargin: Theme.s4; Layout.rightMargin: Theme.s4; Layout.topMargin: Theme.s3
                spacing: Theme.s2
                SectionHeader { text: qsTr("Sắp xếp"); Layout.fillWidth: true }
                Flow {
                    Layout.fillWidth: true; spacing: Theme.s1
                    AppButton { text: qsTr("Giữa ngang"); compact: true; onClicked: Doc.centerOnLabel("h") }
                    AppButton { text: qsTr("Giữa dọc"); compact: true; onClicked: Doc.centerOnLabel("v") }
                    AppButton { text: "↺ 90°"; compact: true; onClicked: Doc.rotateBy(-90) }
                    AppButton { text: "↻ 90°"; compact: true; onClicked: Doc.rotateBy(90) }
                    AppButton { text: "0°"; compact: true; onClicked: Doc.resetRotation() }
                }
                Flow {
                    visible: Doc.canGroup || Doc.canUngroup
                    Layout.fillWidth: true; spacing: Theme.s1
                    AppButton { visible: Doc.canGroup; text: qsTr("Nhóm (Ctrl+G)"); compact: true; onClicked: Doc.groupSelected() }
                    AppButton { visible: Doc.canUngroup; text: qsTr("Bỏ nhóm (Ctrl+Shift+G)"); compact: true; onClicked: Doc.ungroupSelected() }
                }
                Flow {
                    visible: Doc.selectionCount > 1 && !Doc.selectionIsGroup
                    Layout.fillWidth: true; spacing: Theme.s1
                    AppButton { text: qsTr("Căn trái"); compact: true; onClicked: Doc.align("left") }
                    AppButton { text: qsTr("Căn trên"); compact: true; onClicked: Doc.align("top") }
                    AppButton { text: qsTr("Giữa ↔"); compact: true; onClicked: Doc.align("hcenter") }
                    AppButton { text: qsTr("Giữa ↕"); compact: true; onClicked: Doc.align("vcenter") }
                }
                Item { Layout.preferredHeight: Theme.s4 }
            }

            // ---------- label settings (no selection) ----------
            ColumnLayout {
                visible: !p.hasSel
                Layout.fillWidth: true; Layout.leftMargin: Theme.s4; Layout.rightMargin: Theme.s4; Layout.topMargin: Theme.s1
                spacing: Theme.s2

                SectionHeader { text: qsTr("Kích thước"); Layout.fillWidth: true }
                PropertyRow { label: qsTr("Rộng"); NumberField { value: d.width_mm; unit: "mm"; from: 1; Layout.fillWidth: true; onEdited: (v) => Doc.setDoc("width_mm", v) } }
                PropertyRow { label: "Cao"; NumberField { value: d.height_mm; unit: "mm"; from: 1; Layout.fillWidth: true; onEdited: (v) => Doc.setDoc("height_mm", v) } }
                PropertyRow { label: qsTr("Hướng in")
                    ComboField { Layout.fillWidth: true; model: [qsTr("Dọc"), "Ngang"]; currentIndex: d.orientation === "landscape" ? 1 : 0
                        onActivated: (i) => Doc.setDoc("orientation", ["portrait", "landscape"][i]) } }
                PropertyRow { label: qsTr("DPI máy in")
                    ComboField { Layout.fillWidth: true; model: ["203", "300", "600"]
                        currentIndex: Math.max(0, model.indexOf(String(d.dpi)))
                        displayText: String(d.dpi)
                        onActivated: (i) => Doc.setDoc("dpi", parseInt(model[i])) } }
                PropertyRow { label: qsTr("Số bản (mẫu)")
                    NumberField { value: d.copies; step: 1; decimals: 0; from: 1; to: 999; Layout.fillWidth: true; onEdited: (v) => Doc.setDoc("copies", v) } }
                Text { text: qsTr("Bấm vào một phần tử trên tem để chỉnh thuộc tính của nó.")
                    Layout.fillWidth: true; Layout.topMargin: Theme.s1; wrapMode: Text.Wrap
                    font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm; color: Theme.textFaint }

                // ---- view options (collapsed) ----
                Disclosure { text: qsTr("Hiển thị & canh lề"); open: p.showView; onClicked: p.showView = !p.showView; Layout.topMargin: Theme.s3 }
                ColumnLayout {
                    visible: p.showView; Layout.fillWidth: true; spacing: Theme.s2
                    CheckField { text: qsTr("Hiện khung vùng in"); checked: d.virtual_area_show; onToggled: Doc.setDoc("virtual_area_show", checked) }
                    CheckField { text: qsTr("Hiện đường hướng dẫn"); checked: Doc.showGuides; onToggled: Doc.showGuides = checked }
                    CheckField { text: qsTr("Hiện vùng gập"); checked: Doc.showFold; onToggled: Doc.showFold = checked }
                    PropertyRow { label: qsTr("Bước bám")
                        NumberField { value: Doc.snapMm; unit: "mm"; step: 0.05; from: 0; to: 5; Layout.fillWidth: true; onEdited: (v) => Doc.snapMm = v } }
                }

                // ---- printer tuning (collapsed) ----
                Disclosure { text: qsTr("Nâng cao — bù sai số & chất lượng in"); open: p.showAdvanced; onClicked: p.showAdvanced = !p.showAdvanced }
                ColumnLayout {
                    visible: p.showAdvanced; Layout.fillWidth: true; spacing: Theme.s2
                    Text { text: qsTr("Các thông số này phụ thuộc máy in. Nên chỉnh một lần rồi lưu vào Hồ sơ máy in (menu ▾ cạnh nút In).")
                        Layout.fillWidth: true; wrapMode: Text.Wrap; font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm; color: Theme.textFaint }
                    SectionHeader { text: qsTr("Bù sai số máy in"); Layout.fillWidth: true }
                    PropertyRow { label: qsTr("Lệch X"); NumberField { value: d.offset_x_mm; unit: "mm"; step: 0.1; Layout.fillWidth: true; onEdited: (v) => Doc.setDoc("offset_x_mm", v) } }
                    PropertyRow { label: qsTr("Lệch Y"); NumberField { value: d.offset_y_mm; unit: "mm"; step: 0.1; Layout.fillWidth: true; onEdited: (v) => Doc.setDoc("offset_y_mm", v) } }
                    PropertyRow { label: qsTr("Nghiêng"); NumberField { value: d.rotation_deg; unit: "°"; step: 0.05; Layout.fillWidth: true; onEdited: (v) => Doc.setDoc("rotation_deg", v) } }
                    PropertyRow { label: qsTr("Tỉ lệ X"); NumberField { value: d.scale_x_pct; unit: "%"; step: 0.1; Layout.fillWidth: true; from: 50; to: 150; onEdited: (v) => Doc.setDoc("scale_x_pct", v) } }
                    PropertyRow { label: qsTr("Tỉ lệ Y"); NumberField { value: d.scale_y_pct; unit: "%"; step: 0.1; Layout.fillWidth: true; from: 50; to: 150; onEdited: (v) => Doc.setDoc("scale_y_pct", v) } }

                    SectionHeader { text: qsTr("Chất lượng in"); Layout.fillWidth: true; Layout.topMargin: Theme.s2 }
                    PropertyRow { label: qsTr("Chế độ")
                        ComboField { Layout.fillWidth: true; model: [qsTr("Nhiệt — nét sắc"), qsTr("Chuẩn")]; currentIndex: d.render_mode === "standard" ? 1 : 0
                            onActivated: (i) => Doc.setDoc("render_mode", ["thermal_crisp", "standard"][i]) } }
                    PropertyRow { label: qsTr("Ngưỡng đen")
                        NumberField { value: d.threshold; step: 1; decimals: 0; from: 1; to: 255; Layout.fillWidth: true; onEdited: (v) => Doc.setDoc("threshold", v) } }
                    PropertyRow { label: qsTr("Lấy mẫu")
                        NumberField { value: d.oversample; step: 1; decimals: 0; from: 1; to: 6; Layout.fillWidth: true; onEdited: (v) => Doc.setDoc("oversample", v) } }
                    Text { text: qsTr("Gợi ý cho máy in nhiệt 300 dpi: ngưỡng 135–155, lấy mẫu 4.")
                        Layout.fillWidth: true; wrapMode: Text.Wrap; font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm; color: Theme.textFaint }
                }
                Item { Layout.preferredHeight: Theme.s5 }
            }
        }
    }

    // clickable section title that shows / hides the block below it
    component Disclosure: C.AbstractButton {
        id: dc
        property bool open: false
        Layout.fillWidth: true
        implicitHeight: 32
        hoverEnabled: true
        background: Rectangle { radius: Theme.radiusSm; color: dc.hovered ? Theme.hover : "transparent" }
        contentItem: Row {
            spacing: Theme.s2
            leftPadding: 2
            Text { text: dc.open ? "▾" : "▸"; anchors.verticalCenter: parent.verticalCenter
                font.pixelSize: Theme.fsBase; color: Theme.textMuted }
            Text { text: dc.text.toUpperCase(); anchors.verticalCenter: parent.verticalCenter
                font.family: Theme.fontFamily; font.pixelSize: Theme.fsXs; font.weight: Font.DemiBold; font.letterSpacing: 0.6; color: Theme.textMuted }
        }
    }
}
