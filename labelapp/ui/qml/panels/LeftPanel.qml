import QtQuick
import QtQuick.Controls.Basic as C
import QtQuick.Layouts
import QtQml.Models
import "../theme"
import "../components"
import "../dialogs"

// Left side: a tool rail (Mẫu · Chèn · Dữ liệu · Lớp) and the panel of the active tool.
Panel {
    id: p
    borderRight: true
    property int tab: 1                       // 0 = templates, 1 = insert, 2 = data, 3 = layers
    readonly property int tabData: 2
    signal openExcel()
    signal openGoogle()
    signal addFieldRequested()
    signal addImageRequested()
    signal printQueue(string scope)
    signal openBatchScan()
    signal openTemplateRequested(string name)
    signal newTemplateRequested()
    signal openLibraryRequested()
    function focusScan() { tab = tabData; dataTab.focusScan() }

    function showData() { tab = tabData }

    // A symbol tile appends to the selected text element; with no text selected it becomes a new text element.
    function insertSymbol(s) {
        if (Doc.selectionCount === 1 && Doc.elementType(Doc.selection[0]) === "text")
            Doc.setProp("text", Doc.elementText(Doc.selection[0]) + s)
        else
            Doc.addText(s)
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0

        // ---------------- tool rail ----------------
        Rectangle {
            Layout.fillHeight: true; Layout.preferredWidth: 64
            color: Theme.surfaceAlt
            Rectangle { anchors.right: parent.right; width: 1; height: parent.height; color: Theme.border }
            Column {
                anchors.top: parent.top; anchors.topMargin: Theme.s2
                width: parent.width
                RailButton { width: parent.width; glyph: "▦"; text: "Mẫu"; active: p.tab === 0; onClicked: p.tab = 0 }
                RailButton { width: parent.width; glyph: "＋"; text: "Chèn"; active: p.tab === 1; onClicked: p.tab = 1 }
                RailButton { width: parent.width; glyph: "☷"; text: "Dữ liệu"; active: p.tab === 2; badge: Data.rowCount; onClicked: p.tab = 2 }
                RailButton { width: parent.width; glyph: "≡"; text: "Lớp"; active: p.tab === 3; badge: list.count; onClicked: p.tab = 3 }
            }
        }

        StackLayout {
            Layout.fillWidth: true; Layout.fillHeight: true
            currentIndex: p.tab

            // ---------------- Mẫu (templates) ----------------
            ColumnLayout {
                spacing: 0
                Text { text: "Mẫu tem"; Layout.margins: Theme.s3; Layout.bottomMargin: Theme.s2
                    font.family: Theme.fontFamily; font.pixelSize: Theme.fsLg; font.weight: Font.DemiBold; color: Theme.text }
                AppButton { text: "＋  Tạo tem mới"; kind: "primary"; Layout.fillWidth: true; Layout.leftMargin: Theme.s3; Layout.rightMargin: Theme.s3
                    onClicked: p.newTemplateRequested() }
                AppButton { text: "Quản lý thư viện mẫu…"; kind: "ghost"; Layout.fillWidth: true; Layout.leftMargin: Theme.s3; Layout.rightMargin: Theme.s3
                    Layout.topMargin: Theme.s1; Layout.bottomMargin: Theme.s2; onClicked: p.openLibraryRequested() }
                Separator { Layout.fillWidth: true }
                ListView {
                    id: tplList
                    Layout.fillWidth: true; Layout.fillHeight: true
                    clip: true; model: Lib.names; spacing: 4
                    topMargin: Theme.s2; bottomMargin: Theme.s2
                    boundsBehavior: Flickable.StopAtBounds
                    C.ScrollBar.vertical: C.ScrollBar { policy: C.ScrollBar.AsNeeded }
                    delegate: Rectangle {
                        required property string modelData
                        readonly property bool cur: modelData === Doc.templateName
                        x: Theme.s2; width: tplList.width - Theme.s2 * 2; height: 40
                        radius: Theme.radiusMd
                        color: cur ? Theme.selected : (tma.containsMouse ? Theme.hover : Theme.surface)
                        border.width: 1; border.color: cur ? Theme.accent : Theme.border
                        Text { text: "▭"; anchors.left: parent.left; anchors.leftMargin: Theme.s3; anchors.verticalCenter: parent.verticalCenter
                            font.pixelSize: Theme.fsLg; color: cur ? Theme.accent : Theme.textFaint }
                        Text { anchors.left: parent.left; anchors.leftMargin: 34; anchors.right: parent.right; anchors.rightMargin: Theme.s3
                            anchors.verticalCenter: parent.verticalCenter
                            text: modelData.replace(/\.json$/i, "").replace(/_/g, " "); elide: Text.ElideRight
                            font.family: Theme.fontFamily; font.pixelSize: Theme.fsBase; font.weight: cur ? Font.DemiBold : Font.Normal; color: Theme.text }
                        MouseArea { id: tma; anchors.fill: parent; hoverEnabled: true; onClicked: p.openTemplateRequested(modelData) }
                    }
                    Text { visible: tplList.count === 0; anchors.centerIn: parent; width: parent.width - Theme.s5 * 2
                        text: "Chưa có mẫu nào.\nBấm “Tạo tem mới” để bắt đầu."; wrapMode: Text.Wrap
                        horizontalAlignment: Text.AlignHCenter; color: Theme.textFaint; font.family: Theme.fontFamily; font.pixelSize: Theme.fsBase }
                }
            }

            // ---------------- Chèn (insert palette) ----------------
            C.ScrollView {
                id: ins
                contentWidth: availableWidth
                clip: true
                C.ScrollBar.horizontal.policy: C.ScrollBar.AlwaysOff
                readonly property real tileW: Math.floor((availableWidth - Theme.s3 * 2 - Theme.s2 * 2) / 3)

                ColumnLayout {
                    width: ins.availableWidth
                    spacing: Theme.s2

                    Text { text: "Chèn vào tem"; Layout.margins: Theme.s3; Layout.bottomMargin: 0
                        font.family: Theme.fontFamily; font.pixelSize: Theme.fsLg; font.weight: Font.DemiBold; color: Theme.text }
                    Text { text: "Bấm một ô để thêm lên tem, rồi kéo vào vị trí."; Layout.fillWidth: true; Layout.leftMargin: Theme.s3; Layout.rightMargin: Theme.s3
                        wrapMode: Text.Wrap; font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm; color: Theme.textMuted }

                    SectionHeader { text: "Văn bản"; Layout.fillWidth: true; Layout.leftMargin: Theme.s3; Layout.rightMargin: Theme.s3; Layout.topMargin: Theme.s2 }
                    Flow {
                        Layout.fillWidth: true; Layout.leftMargin: Theme.s3; Layout.rightMargin: Theme.s3; spacing: Theme.s2
                        PaletteTile { width: ins.tileW; glyph: "T"; glyphSize: 24; glyphBold: true; text: "Tiêu đề"
                            onClicked: Doc.addTextStyled("Tiêu đề", 10, true, 40, 6) }
                        PaletteTile { width: ins.tileW; glyph: "T"; glyphSize: 17; glyphBold: true; text: "Phụ đề"
                            onClicked: Doc.addTextStyled("Phụ đề", 7, true, 35, 4.5) }
                        PaletteTile { width: ins.tileW; art: "body"; text: "Nội dung"
                            onClicked: Doc.addTextStyled("Nội dung", 5, false, 30, 3.5) }
                        PaletteTile { width: ins.tileW; art: "field"; text: "Trường dữ liệu"; enabled: Data.hasData
                            tip: Data.hasData ? "Chèn cột {{ }} từ Excel / Google Sheet" : "Mở Excel hoặc Google Sheet ở mục Dữ liệu trước"
                            onClicked: p.addFieldRequested() }
                        PaletteTile { width: ins.tileW; glyph: "Aa"; glyphSize: 18; text: "Chữ tuỳ ý…"
                            onClicked: textPrompt.openFor("Thêm chữ", "Chữ mới", function(t) { Doc.addText(t) }, "Thêm", "Dùng {{TênCột}} để chèn dữ liệu.") }
                    }

                    SectionHeader { text: "Ký hiệu nhanh"; Layout.fillWidth: true; Layout.leftMargin: Theme.s3; Layout.rightMargin: Theme.s3; Layout.topMargin: Theme.s2 }
                    Text { text: "Đang chọn một khối chữ thì ký hiệu được nối vào cuối chữ đó."; Layout.fillWidth: true
                        Layout.leftMargin: Theme.s3; Layout.rightMargin: Theme.s3; wrapMode: Text.Wrap
                        font.family: Theme.fontFamily; font.pixelSize: Theme.fsXs; color: Theme.textFaint }
                    Flow {
                        Layout.fillWidth: true; Layout.leftMargin: Theme.s3; Layout.rightMargin: Theme.s3; spacing: Theme.s1
                        Repeater {
                            model: ["m²", "m³", "°C", "±", "×", "½", "≤", "≥", "₫", "™", "®", "©", "№", "•", "→", "✓"]
                            delegate: C.AbstractButton {
                                id: sb
                                required property string modelData
                                width: Math.floor((ins.availableWidth - Theme.s3 * 2 - Theme.s1 * 7) / 8); height: 32
                                hoverEnabled: true
                                background: Rectangle { radius: Theme.radiusSm; color: sb.down ? Theme.pressed : sb.hovered ? Theme.accentSoft : Theme.surface
                                    border.width: 1; border.color: sb.hovered ? Theme.accent : Theme.border }
                                contentItem: Text { text: sb.modelData; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                                    font.family: Theme.fontFamily; font.pixelSize: Theme.fsMd; color: Theme.text }
                                onClicked: p.insertSymbol(modelData)
                            }
                        }
                    }

                    SectionHeader { text: "Biểu tượng"; Layout.fillWidth: true; Layout.leftMargin: Theme.s3; Layout.rightMargin: Theme.s3; Layout.topMargin: Theme.s2 }
                    Text { text: "Hàng dễ vỡ, tem niêm phong, QC… In đen trắng sắc nét, kéo góc để đổi cỡ."; Layout.fillWidth: true
                        Layout.leftMargin: Theme.s3; Layout.rightMargin: Theme.s3; wrapMode: Text.Wrap
                        font.family: Theme.fontFamily; font.pixelSize: Theme.fsXs; color: Theme.textFaint }
                    Repeater {
                        // t = name shown in the app (its UI language, Vietnamese); e = English name, used only by the
                        // README symbol gallery (tools/make_symbol_sheet.py).
                        model: [
                            { title: "Vận chuyển", items: [
                                { k: "fragile", t: "Dễ vỡ", e: "Fragile" }, { k: "this_way_up", t: "Hướng lên", e: "This way up" }, { k: "keep_dry", t: "Tránh ẩm", e: "Keep dry" },
                                { k: "keep_away_sun", t: "Tránh nắng", e: "Keep out of sun" }, { k: "do_not_stack", t: "Không xếp chồng", e: "Do not stack" },
                                { k: "no_knife", t: "Không dùng dao", e: "No knives" }, { k: "warning", t: "Chú ý", e: "Caution" }, { k: "recycle", t: "Tái chế", e: "Recycle" } ] },
                            { title: "Niêm phong & chất lượng", items: [
                                { k: "seal", t: "Tem niêm phong", e: "Seal" }, { k: "seal_lock", t: "Niêm phong khoá", e: "Sealed" }, { k: "genuine", t: "Chính hãng", e: "Genuine" },
                                { k: "qc_pass", t: "QC đạt", e: "QC passed" }, { k: "tick", t: "Đã kiểm", e: "Checked" }, { k: "scissors", t: "Cắt tại đây", e: "Cut here" } ] },
                            { title: "Bán hàng", items: [ { k: "new_burst", t: "Hàng mới", e: "New" }, { k: "sale", t: "Giảm giá", e: "Sale" } ] }
                        ]
                        delegate: ColumnLayout {
                            required property var modelData
                            Layout.fillWidth: true; Layout.leftMargin: Theme.s3; Layout.rightMargin: Theme.s3
                            spacing: Theme.s1
                            Text { text: modelData.title; font.family: Theme.fontFamily; font.pixelSize: Theme.fsXs
                                font.weight: Font.DemiBold; color: Theme.textMuted }
                            Flow {
                                Layout.fillWidth: true; spacing: Theme.s2
                                Repeater {
                                    model: modelData.items
                                    delegate: PaletteTile {
                                        required property var modelData
                                        width: ins.tileW; source: Qt.resolvedUrl("../../resources/symbols/" + modelData.k + ".svg")
                                        text: modelData.t; tip: modelData.t
                                        onClicked: Doc.addSymbol(modelData.k)
                                    }
                                }
                            }
                        }
                    }

                    SectionHeader { text: "Mã vạch & ảnh"; Layout.fillWidth: true; Layout.leftMargin: Theme.s3; Layout.rightMargin: Theme.s3; Layout.topMargin: Theme.s2 }
                    Flow {
                        Layout.fillWidth: true; Layout.leftMargin: Theme.s3; Layout.rightMargin: Theme.s3; spacing: Theme.s2
                        PaletteTile { width: ins.tileW; art: "barcode"; text: "Mã vạch"; tip: "Code 128 / EAN-13 / UPC… (đổi loại ở bảng bên phải)"
                            onClicked: Doc.addSpecial("barcode") }
                        PaletteTile { width: ins.tileW; art: "qr"; text: "Mã QR"; onClicked: Doc.addSpecial("qr") }
                        PaletteTile { width: ins.tileW; art: "image"; text: "Ảnh / logo"; onClicked: p.addImageRequested() }
                    }

                    SectionHeader { text: "Hình & đường kẻ"; Layout.fillWidth: true; Layout.leftMargin: Theme.s3; Layout.rightMargin: Theme.s3; Layout.topMargin: Theme.s2 }
                    Flow {
                        Layout.fillWidth: true; Layout.leftMargin: Theme.s3; Layout.rightMargin: Theme.s3; spacing: Theme.s2
                        PaletteTile { width: ins.tileW; art: "line"; text: "Đường kẻ"; onClicked: Doc.addShape("line") }
                        PaletteTile { width: ins.tileW; art: "box"; text: "Khung"; onClicked: Doc.addShape("box") }
                        PaletteTile { width: ins.tileW; art: "fill_box"; text: "Khối tô"; onClicked: Doc.addShape("fill_box") }
                        PaletteTile { width: ins.tileW; art: "ellipse"; text: "Elip / tròn"; onClicked: Doc.addShape("ellipse") }
                    }

                    SectionHeader { text: "Tem gập & vùng in"; Layout.fillWidth: true; Layout.leftMargin: Theme.s3; Layout.rightMargin: Theme.s3; Layout.topMargin: Theme.s2 }
                    Flow {
                        Layout.fillWidth: true; Layout.leftMargin: Theme.s3; Layout.rightMargin: Theme.s3; spacing: Theme.s2
                        PaletteTile { width: ins.tileW; art: "fold"; text: "Đường gập"; tip: "Mặt dưới đường gập được in lật 180° để gập thành tem 2 mặt"
                            onClicked: Doc.ensureFoldLine() }
                        PaletteTile { width: ins.tileW; art: "area"; text: "Vùng in"; tip: "Hiện khung vùng in (chỉ để canh, không cắt nội dung)"
                            onClicked: Doc.showVirtualArea() }
                    }
                    Item { Layout.preferredHeight: Theme.s5 }
                }
            }

            // ---------------- Dữ liệu ----------------
            DataTab {
                id: dataTab
                onOpenExcel: p.openExcel()
                onOpenGoogle: p.openGoogle()
                onPrintQueue: (scope) => p.printQueue(scope)
                onOpenBatchScan: p.openBatchScan()
            }

            // ---------------- Lớp (element list) ----------------
            ColumnLayout {
                spacing: 0
                RowLayout {
                    Layout.fillWidth: true; Layout.margins: Theme.s3; Layout.bottomMargin: Theme.s2
                    spacing: Theme.s1
                    Text { text: "Các lớp trên tem"; Layout.fillWidth: true
                        font.family: Theme.fontFamily; font.pixelSize: Theme.fsLg; font.weight: Font.DemiBold; color: Theme.text }
                    IconButton { text: "↑"; tip: "Đưa lớp lên trên"; enabled: Doc.selectionCount === 1; onClicked: Doc.reorder(-1) }
                    IconButton { text: "↓"; tip: "Đưa lớp xuống dưới"; enabled: Doc.selectionCount === 1; onClicked: Doc.reorder(1) }
                    IconButton { text: "⧉"; tip: "Nhân bản (Ctrl+D)"; enabled: Doc.selectionCount > 0; onClicked: Doc.duplicateSelected() }
                    IconButton { text: "✕"; tip: "Xoá (Del)"; enabled: Doc.selectionCount > 0; onClicked: Doc.deleteSelected() }
                }
                Separator { Layout.fillWidth: true }
                ListView {
                    id: list
                    Layout.fillWidth: true; Layout.fillHeight: true
                    clip: true
                    model: Doc.elementsModel
                    boundsBehavior: Flickable.StopAtBounds
                    C.ScrollBar.vertical: C.ScrollBar { policy: C.ScrollBar.AsNeeded }
                    delegate: Item {
                        id: row
                        required property int index_
                        required property string etype
                        required property string summary
                        required property bool locked
                        required property bool selected
                        required property bool printed
                        width: ListView.view.width; height: 34
                        Rectangle {
                            anchors.fill: parent; anchors.leftMargin: Theme.s2; anchors.rightMargin: Theme.s2; anchors.topMargin: 1; anchors.bottomMargin: 1
                            radius: Theme.radiusSm
                            color: row.selected ? Theme.selected : (ma.containsMouse ? Theme.hover : "transparent")
                            Behavior on color { ColorAnimation { duration: Theme.dFast } }
                            Rectangle { visible: row.selected; width: 2; height: parent.height - 12; radius: 1; color: Theme.accent
                                anchors.left: parent.left; anchors.leftMargin: 3; anchors.verticalCenter: parent.verticalCenter }
                            Text { id: tcol; text: Doc.typeLabel(row.etype); width: 66; anchors.left: parent.left; anchors.leftMargin: Theme.s3
                                anchors.verticalCenter: parent.verticalCenter; elide: Text.ElideRight
                                font.family: Theme.fontFamily; font.pixelSize: Theme.fsXs; font.weight: Font.DemiBold
                                color: row.selected ? Theme.accent : Theme.textMuted; textFormat: Text.PlainText }
                            Text { text: row.summary; anchors.left: tcol.right; anchors.right: lockText.left; anchors.rightMargin: Theme.s1
                                anchors.verticalCenter: parent.verticalCenter; elide: Text.ElideRight; textFormat: Text.PlainText
                                font.family: Theme.fontFamily; font.pixelSize: Theme.fsBase
                                font.strikeout: !row.printed; opacity: row.printed ? 1 : 0.55
                                // shapes are described by their size: muted so the content-bearing rows stand out
                                color: ["box", "fill_box", "line", "ellipse"].indexOf(row.etype) >= 0 ? Theme.textMuted : Theme.text }
                            Text { id: lockText; visible: row.locked; text: "đã khoá"; anchors.right: printSw.left; anchors.rightMargin: Theme.s1
                                anchors.verticalCenter: parent.verticalCenter; font.family: Theme.fontFamily; font.pixelSize: Theme.fsXs; font.italic: true; color: Theme.textFaint
                                width: visible ? implicitWidth : 0 }
                            MouseArea {
                                id: ma; anchors.fill: parent; hoverEnabled: true
                                onClicked: (m) => Doc.selectIndex(row.index_, (m.modifiers & (Qt.ControlModifier | Qt.ShiftModifier)) !== 0)
                            }
                            // Print switch: the element stays on the label either way, "Không in" only keeps it off the paper.
                            Rectangle {
                                id: printSw
                                anchors.right: parent.right; anchors.rightMargin: Theme.s2; anchors.verticalCenter: parent.verticalCenter
                                width: swText.implicitWidth + 12; height: 20; radius: 10
                                color: swMa.containsMouse ? Theme.hover : "transparent"
                                border.width: 1; border.color: row.printed ? Theme.border : Theme.danger
                                Text { id: swText; anchors.centerIn: parent; text: row.printed ? "In" : "Không in"
                                    font.family: Theme.fontFamily; font.pixelSize: Theme.fsXs; font.weight: Font.DemiBold
                                    color: row.printed ? Theme.textMuted : Theme.danger }
                                MouseArea { id: swMa; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                    onClicked: Doc.togglePrint(row.index_) }
                                C.ToolTip.visible: swMa.containsMouse
                                C.ToolTip.text: row.printed ? "Đang in phần này — bấm để KHÔNG in (vẫn giữ trên tem)" : "Phần này không in — bấm để in lại"
                                C.ToolTip.delay: 400
                            }
                        }
                    }
                    Text {
                        visible: list.count === 0
                        anchors.centerIn: parent; text: "Tem chưa có phần tử nào.\nVào mục Chèn để thêm."
                        horizontalAlignment: Text.AlignHCenter; color: Theme.textFaint
                        font.family: Theme.fontFamily; font.pixelSize: Theme.fsBase
                    }
                }
            }
        }
    }

    // generic one-line text prompt (add text)
    TextPromptDialog { id: textPrompt }
}
