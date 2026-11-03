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

    // ---- empty state ----
    Item {
        visible: !Data.hasData
        Layout.fillWidth: true; Layout.fillHeight: true
        ColumnLayout {
            anchors.centerIn: parent; width: parent.width - Theme.s6 * 2; spacing: Theme.s3
            Text { text: Data.loading ? "Loading data…" : "No data loaded"; Layout.alignment: Qt.AlignHCenter
                font.family: Theme.fontFamily; font.pixelSize: Theme.fsLg; font.weight: Font.DemiBold; color: Theme.text }
            Text { text: "Load an Excel sheet or a Google Sheet to preview and print one label per row."
                Layout.fillWidth: true; wrapMode: Text.Wrap; horizontalAlignment: Text.AlignHCenter
                font.family: Theme.fontFamily; font.pixelSize: Theme.fsBase; color: Theme.textMuted }
            AppButton { text: "Open Excel file…"; kind: "primary"; Layout.alignment: Qt.AlignHCenter; onClicked: t.openExcel(); enabled: !Data.loading }
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
            AppTextField {
                id: search
                Layout.fillWidth: true
                placeholderText: "Search barcode, model, brand…"
                onTextChanged: searchDebounce.restart()
                onAccepted: Data.searchEnter(text)
                Timer { id: searchDebounce; interval: 160; onTriggered: Data.search(search.text) }
                Keys.onDownPressed: { Data.step(1); event.accepted = true }
                Keys.onUpPressed: { Data.step(-1); event.accepted = true }
            }
            RowLayout {
                spacing: Theme.s1
                Text { text: Data.rowLabel + (Data.filteredCount !== Data.rowCount ? "  ·  " + Data.filteredCount + " match" + (Data.filteredCount === 1 ? "" : "es") : "")
                    Layout.fillWidth: true; font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm; color: Theme.textMuted; elide: Text.ElideRight }
                IconButton { text: "‹"; tip: "Previous row"; width: 26; height: 26; implicitWidth: 26; implicitHeight: 26; onClicked: Data.step(-1) }
                IconButton { text: "›"; tip: "Next row"; width: 26; height: 26; implicitWidth: 26; implicitHeight: 26; onClicked: Data.step(1) }
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
            AppButton { text: "Print selected…"; compact: true; Layout.fillWidth: true; onClicked: t.printQueue("selected") }
            AppButton { text: "Print all…"; compact: true; Layout.fillWidth: true; onClicked: t.printQueue("all") }
        }
    }
}
