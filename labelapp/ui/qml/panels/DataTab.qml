import QtQuick
import QtQuick.Controls.Basic as C
import QtQuick.Layouts
import QtQml.Models
import "../theme"
import "../components"

ColumnLayout {
    id: t
    spacing: 0
    signal openExcel()
    signal openGoogle()
    signal printQueue(string scope)
    signal openBatchScan()
    function focusScan() { scanField.forceActiveFocus(); scanField.selectAll() }

    // ---- empty state ----
    Item {
        visible: !Data.hasData
        Layout.fillWidth: true; Layout.fillHeight: true
        ColumnLayout {
            anchors.centerIn: parent; width: parent.width - Theme.s6 * 2; spacing: Theme.s3
            Text { text: Data.loading ? "Đang tải dữ liệu…" : "Chưa có dữ liệu"; Layout.alignment: Qt.AlignHCenter
                font.family: Theme.fontFamily; font.pixelSize: Theme.fsLg; font.weight: Font.DemiBold; color: Theme.text }
            Text { text: "Mở tệp Excel hoặc Google Sheet để xem trước và in mỗi dòng một tem."
                Layout.fillWidth: true; wrapMode: Text.Wrap; horizontalAlignment: Text.AlignHCenter
                font.family: Theme.fontFamily; font.pixelSize: Theme.fsBase; color: Theme.textMuted }
            AppButton { text: "Mở tệp Excel…"; kind: "primary"; Layout.alignment: Qt.AlignHCenter; onClicked: t.openExcel(); enabled: !Data.loading }
            AppButton { text: "Google Sheet…"; Layout.alignment: Qt.AlignHCenter; onClicked: t.openGoogle(); enabled: !Data.loading }
        }
    }

    // ---- loaded ----
    ColumnLayout {
        visible: Data.hasData
        Layout.fillWidth: true; Layout.fillHeight: true
        spacing: 0

        ColumnLayout {
            Layout.fillWidth: true; Layout.leftMargin: Theme.s3; Layout.rightMargin: Theme.s3; Layout.bottomMargin: Theme.s2
            spacing: Theme.s2
            RowLayout {
                spacing: Theme.s2
                Text { text: Data.sourceLabel; Layout.fillWidth: true; elide: Text.ElideMiddle
                    font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm; font.weight: Font.Medium; color: Theme.textMuted }
                ComboField {
                    visible: Data.sheetNames.length > 1
                    Layout.preferredWidth: 110; implicitHeight: Theme.controlHSm
                    model: Data.sheetNames
                    currentIndex: Math.max(0, Data.sheetNames.indexOf(Data.sheet))
                    onActivated: (i) => Data.selectSheet(Data.sheetNames[i])
                }
            }
            // ---- scan -> (print) ----
            RowLayout {
                spacing: Theme.s2
                AppTextField {
                    id: scanField
                    Layout.fillWidth: true
                    property var hits: []
                    property int hi: -1
                    placeholderText: Scan.instantPrint ? "Quét mã vạch…" : "Quét / tìm UPC, SKU, tên, thương hiệu…"
                    function refresh() {
                        hits = (Scan.instantPrint || text.trim().length === 0) ? [] : Scan.suggest(text)
                        hi = hits.length > 0 ? 0 : -1
                    }
                    function submit() {
                        scanTimer.stop(); suggestTimer.stop()
                        if (Scan.submit(text, (hits.length > 0 && hi >= 0 && hits[hi]) ? hits[hi].index : -1)) text = ""
                        hits = []; hi = -1; forceActiveFocus()
                    }
                    onAccepted: submit()
                    onTextEdited: {
                        scanTimer.stop()
                        if (Scan.instantPrint) {
                            hits = []
                            if (text.trim().length >= Scan.minLength) scanTimer.restart()    // scanner finished typing
                        } else {
                            suggestTimer.restart()
                            if (text.trim().length >= Scan.minLength) scanTimer.restart()
                        }
                    }
                    Connections { target: Scan; function onSettingsChanged() { scanField.refresh() } }
                    onActiveFocusChanged: if (!activeFocus) { hits = []; hi = -1 }
                    Keys.onEscapePressed: (e) => { text = ""; hits = []; hi = -1; e.accepted = true }
                    Keys.onDownPressed: (e) => { if (hits.length > 0) { hi = (hi + 1) % hits.length; e.accepted = true } }
                    Keys.onUpPressed: (e) => { if (hits.length > 0) { hi = (hi - 1 + hits.length) % hits.length; e.accepted = true } }
                    Timer { id: suggestTimer; interval: 120; onTriggered: scanField.refresh() }
                    // Instant print: act on the full code; otherwise only a complete scanned code auto-selects its row
                    Timer { id: scanTimer; interval: 280
                        onTriggered: {
                            if (Scan.instantPrint || Scan.isExactCode(scanField.text)) {
                                if (Scan.quickScan(scanField.text)) scanField.text = ""
                                scanField.hits = []; scanField.hi = -1
                            }
                        } }

                    C.Popup {
                        id: sugg
                        parent: scanField
                        y: scanField.height + 2
                        width: scanField.width
                        padding: 1
                        focus: false
                        closePolicy: C.Popup.NoAutoClose
                        visible: scanField.visible && scanField.activeFocus && scanField.hits.length > 0
                        background: Rectangle { radius: Theme.radiusMd; color: Theme.surface; border.width: 1; border.color: Theme.borderStrong }
                        contentItem: ListView {
                            id: suggList
                            implicitHeight: contentHeight
                            interactive: false
                            model: scanField.hits
                            currentIndex: scanField.hi
                            delegate: Rectangle {
                                required property var modelData
                                required property int index
                                width: suggList.width; height: 40
                                color: index === scanField.hi ? Theme.selected : (hov.hovered ? Theme.hover : "transparent")
                                HoverHandler { id: hov }
                                TapHandler { onTapped: { Scan.pick(modelData.index); scanField.text = ""; scanField.hits = []; scanField.hi = -1; scanField.forceActiveFocus() } }
                                Column {
                                    anchors.verticalCenter: parent.verticalCenter
                                    anchors.left: parent.left; anchors.right: parent.right
                                    anchors.leftMargin: Theme.s2; anchors.rightMargin: Theme.s2
                                    Text { width: parent.width; elide: Text.ElideRight; textFormat: Text.PlainText
                                        text: [modelData.brand, modelData.name].filter(function(x) { return x }).join(" · ") || modelData.sku || modelData.upc
                                        font.family: Theme.fontFamily; font.pixelSize: Theme.fsBase; font.weight: Font.Medium; color: Theme.text }
                                    Text { width: parent.width; elide: Text.ElideRight; textFormat: Text.PlainText
                                        text: [modelData.upc, modelData.sku, modelData.price].filter(function(x) { return x }).join("  ·  ")
                                        font.family: Theme.fontFamily; font.pixelSize: Theme.fsXs; color: Theme.textMuted }
                                }
                            }
                        }
                    }
                }
                AppButton { text: "Quét loạt…"; compact: true; onClicked: t.openBatchScan()
                    C.ToolTip.visible: hovered; C.ToolTip.text: "Hàng đợi quét mã (F8)"; C.ToolTip.delay: 600 }
            }
            RowLayout {
                spacing: Theme.s2
                CheckField { text: "In ngay khi quét"; checked: Scan.instantPrint; onToggled: Scan.instantPrint = checked
                    C.ToolTip.visible: hovered; C.ToolTip.text: "Bật: in ngay khi quét đủ mã UPC (khớp chính xác). Tắt: gợi ý theo UPC, SKU, tên, thương hiệu"; C.ToolTip.delay: 600 }
                Item { Layout.fillWidth: true }
                Text { text: "SL"; font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm; color: Theme.textMuted }
                NumberField { Layout.preferredWidth: 56; implicitHeight: 26; value: Scan.qty; step: 1; decimals: 0; from: 1; to: 999; onEdited: (v) => Scan.qty = v }
                AppButton { text: "In lại"; compact: true; enabled: Scan.hasLast && !Printing.busy; onClicked: Scan.printLast() }
            }
            Text {
                visible: Scan.status.length > 0
                text: Scan.status; Layout.fillWidth: true; elide: Text.ElideRight
                font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm; font.weight: Font.Medium
                color: Scan.statusKind === "error" ? Theme.danger : (Scan.statusKind === "ok" ? Theme.success : Theme.textMuted)
            }
            AppTextField {
                id: search
                Layout.fillWidth: true
                placeholderText: "Tìm mã vạch, mẫu mã, thương hiệu…"
                onTextChanged: searchDebounce.restart()
                onAccepted: Data.searchEnter(text)
                Timer { id: searchDebounce; interval: 160; onTriggered: Data.search(search.text) }
                Keys.onDownPressed: { Data.step(1); event.accepted = true }
                Keys.onUpPressed: { Data.step(-1); event.accepted = true }
            }
            RowLayout {
                spacing: Theme.s1
                Text { text: Data.rowLabel + (Data.filteredCount !== Data.rowCount ? "  ·  " + Data.filteredCount + " kết quả" : "")
                    Layout.fillWidth: true; font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm; color: Theme.textMuted; elide: Text.ElideRight }
                IconButton { text: "‹"; tip: "Dòng trước"; width: 26; height: 26; implicitWidth: 26; implicitHeight: 26; onClicked: Data.step(-1) }
                IconButton { text: "›"; tip: "Dòng sau"; width: 26; height: 26; implicitWidth: 26; implicitHeight: 26; onClicked: Data.step(1) }
            }
        }

        Separator { Layout.fillWidth: true }

        // header + rows
        Item {
            Layout.fillWidth: true; Layout.fillHeight: true
            clip: true
            C.HorizontalHeaderView {
                id: header
                anchors.left: table.left; anchors.top: parent.top
                width: table.width
                syncView: table
                clip: true
                model: Data.rowsModel
                delegate: Rectangle {
                    implicitWidth: 120; implicitHeight: 28
                    color: Theme.surfaceAlt
                    Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.border }
                    Text { anchors.fill: parent; anchors.leftMargin: Theme.s2; anchors.rightMargin: Theme.s2
                        text: model.display; elide: Text.ElideRight; verticalAlignment: Text.AlignVCenter
                        font.family: Theme.fontFamily; font.pixelSize: Theme.fsXs; font.weight: Font.DemiBold; color: Theme.textMuted }
                }
            }
            TableView {
                id: table
                anchors.top: header.bottom; anchors.bottom: parent.bottom; anchors.left: parent.left; anchors.right: parent.right
                clip: true
                model: Data.rowsModel
                boundsBehavior: Flickable.StopAtBounds
                columnWidthProvider: function(c) { return Math.max(70, Math.min(170, (Data.headers[c] ? Data.headers[c].length : 6) * 9 + 30)) }
                rowHeightProvider: function() { return 28 }
                selectionBehavior: TableView.SelectRows
                selectionMode: TableView.ExtendedSelection
                selectionModel: ItemSelectionModel { id: sel; model: table.model }
                pointerNavigationEnabled: true
                keyNavigationEnabled: true
                C.ScrollBar.vertical: C.ScrollBar {}
                C.ScrollBar.horizontal: C.ScrollBar {}

                Connections {
                    target: sel
                    function onSelectionChanged() {
                        var rows = {}, idx = sel.selectedIndexes
                        for (var i = 0; i < idx.length; i++) rows[idx[i].row] = true
                        Data.setSelectedViewRows(Object.keys(rows).map(Number))
                    }
                    function onCurrentChanged(cur) { if (cur.row >= 0 && cur.row !== Data.currentViewRow) Data.selectViewRow(cur.row) }
                }
                Connections {
                    target: Data
                    function onCurrentChanged() {
                        var r = Data.currentViewRow
                        if (r >= 0 && sel.currentIndex.row !== r) {
                            sel.setCurrentIndex(table.model.index(r, 0), ItemSelectionModel.ClearAndSelect | ItemSelectionModel.Rows)
                            table.positionViewAtRow(r, TableView.Contain)
                        }
                    }
                    function onDataChanged() { sel.clear() }
                }

                delegate: Rectangle {
                    required property bool selected
                    required property bool current
                    required property int row
                    implicitWidth: 120; implicitHeight: 28
                    color: selected ? Theme.selected : (row % 2 ? Theme.surfaceAlt : Theme.surface)
                    Text {
                        anchors.fill: parent; anchors.leftMargin: Theme.s2; anchors.rightMargin: Theme.s2
                        text: model.display; elide: Text.ElideRight; verticalAlignment: Text.AlignVCenter; textFormat: Text.PlainText
                        font.family: Theme.fontFamily; font.pixelSize: Theme.fsBase
                        font.weight: current ? Font.DemiBold : Font.Normal
                        color: Theme.text
                    }
                    Rectangle { visible: current; width: 2; height: parent.height; color: Theme.accent }
                }
            }
        }

        Separator { Layout.fillWidth: true }
        RowLayout {
            Layout.fillWidth: true; Layout.margins: Theme.s3; spacing: Theme.s2
            AppButton { text: "In dòng đã chọn…"; compact: true; Layout.fillWidth: true; onClicked: t.printQueue("selected") }
            AppButton { text: "In tất cả…"; compact: true; Layout.fillWidth: true; onClicked: t.printQueue("all") }
        }
    }
}
