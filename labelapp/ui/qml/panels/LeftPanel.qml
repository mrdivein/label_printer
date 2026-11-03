import QtQuick
import QtQuick.Controls.Basic as C
import QtQuick.Layouts
import QtQml.Models
import "../theme"
import "../components"
import "../dialogs"

Panel {
    id: p
    borderRight: true
    property int tab: 0                       // 0 = Elements, 1 = Data
    signal openExcel()
    signal openGoogle()
    signal addFieldRequested()
    signal addImageRequested()
    signal printQueue(string scope)
    signal openBatchScan()
    function focusScan() { tab = 1; dataTab.focusScan() }

    function showData() { tab = 1 }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // segmented tab control
        Item {
            Layout.fillWidth: true; Layout.preferredHeight: 48
            Rectangle {
                anchors.fill: parent; anchors.margins: Theme.s3; anchors.topMargin: Theme.s3; anchors.bottomMargin: Theme.s2
                radius: Theme.radiusMd; color: Theme.surfaceAlt; border.width: 1; border.color: Theme.border
                Row {
                    anchors.fill: parent; anchors.margins: 2; spacing: 2
                    Repeater {
                        model: [{t: "Elements", n: Doc.elementsModel.rowCount()}, {t: "Data", n: Data.rowCount}]
                        delegate: C.TabButton {
                            required property var modelData
                            required property int index
                            width: (parent.width - 2) / 2; height: parent.height
                            checked: p.tab === index
                            onClicked: p.tab = index
                            padding: 0
                            focusPolicy: Qt.TabFocus
                            contentItem: Text {
                                text: modelData.t + (index === 1 && Data.rowCount > 0 ? "  " + Data.rowCount : "")
                                font.family: Theme.fontFamily; font.pixelSize: Theme.fsBase; font.weight: Font.Medium
                                color: parent.checked ? Theme.text : Theme.textMuted
                                horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                            }
                            background: Rectangle {
                                radius: Theme.radiusSm
                                color: parent.checked ? Theme.surface : "transparent"
                                border.width: parent.checked ? 1 : 0; border.color: Theme.border
                                Behavior on color { ColorAnimation { duration: Theme.dFast } }
                            }
                        }
                    }
                }
            }
        }

        StackLayout {
            Layout.fillWidth: true; Layout.fillHeight: true
            currentIndex: p.tab

            // ---------------- Elements ----------------
            ColumnLayout {
                spacing: 0
                RowLayout {
                    Layout.fillWidth: true; Layout.leftMargin: Theme.s3; Layout.rightMargin: Theme.s3; Layout.bottomMargin: Theme.s2
                    spacing: Theme.s1
                    AppButton {
                        text: "＋  Add"; kind: "primary"; compact: true
                        onClicked: addMenu.popup(0, height + 4)
                        AppMenu {
                            id: addMenu
                            AppMenuItem { text: "Text"; onTriggered: textPrompt.openFor("Add text", "New text", function(t) { Doc.addText(t) }) }
                            AppMenuItem { text: "Data field…"; hint: "{{ }}"; onTriggered: p.addFieldRequested() }
                            AppMenuSeparator {}
                            AppMenuItem { text: "Barcode"; onTriggered: Doc.addSpecial("barcode") }
                            AppMenuItem { text: "QR code"; onTriggered: Doc.addSpecial("qr") }
                            AppMenuItem { text: "Image / logo…"; onTriggered: p.addImageRequested() }
                            AppMenuSeparator {}
                            AppMenuItem { text: "Line"; onTriggered: Doc.addShape("line") }
                            AppMenuItem { text: "Rectangle"; onTriggered: Doc.addShape("box") }
                            AppMenuItem { text: "Filled rectangle"; onTriggered: Doc.addShape("fill_box") }
                            AppMenuItem { text: "Ellipse"; onTriggered: Doc.addShape("ellipse") }
                            AppMenuSeparator {}
                            AppMenuItem { text: "Fold line"; onTriggered: Doc.ensureFoldLine() }
                            AppMenuItem { text: "Show print area"; onTriggered: Doc.showVirtualArea() }
                        }
                    }
                    Item { Layout.fillWidth: true }
                    IconButton { text: "↑"; tip: "Move layer up"; enabled: Doc.selectionCount === 1; onClicked: Doc.reorder(-1) }
                    IconButton { text: "↓"; tip: "Move layer down"; enabled: Doc.selectionCount === 1; onClicked: Doc.reorder(1) }
                    IconButton { text: "⧉"; tip: "Duplicate (Ctrl+D)"; enabled: Doc.selectionCount > 0; onClicked: Doc.duplicateSelected() }
                    IconButton { text: "✕"; tip: "Delete (Del)"; enabled: Doc.selectionCount > 0; onClicked: Doc.deleteSelected() }
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
                        width: ListView.view.width; height: 34
                        Rectangle {
                            anchors.fill: parent; anchors.leftMargin: Theme.s2; anchors.rightMargin: Theme.s2; anchors.topMargin: 1; anchors.bottomMargin: 1
                            radius: Theme.radiusSm
                            color: row.selected ? Theme.selected : (ma.containsMouse ? Theme.hover : "transparent")
                            Behavior on color { ColorAnimation { duration: Theme.dFast } }
                            Rectangle { visible: row.selected; width: 2; height: parent.height - 12; radius: 1; color: Theme.accent
                                anchors.left: parent.left; anchors.leftMargin: 3; anchors.verticalCenter: parent.verticalCenter }
                            Text { id: tcol; text: row.etype.replace("_", " "); width: 62; anchors.left: parent.left; anchors.leftMargin: Theme.s3
                                anchors.verticalCenter: parent.verticalCenter; elide: Text.ElideRight
                                font.family: Theme.fontFamily; font.pixelSize: Theme.fsXs; font.weight: Font.DemiBold; font.letterSpacing: 0.4
                                color: row.selected ? Theme.accent : Theme.textMuted; textFormat: Text.PlainText; font.capitalization: Font.AllUppercase }
                            Text { text: row.summary; anchors.left: tcol.right; anchors.right: lockText.left; anchors.rightMargin: Theme.s1
                                anchors.verticalCenter: parent.verticalCenter; elide: Text.ElideRight; textFormat: Text.PlainText
                                font.family: Theme.fontFamily; font.pixelSize: Theme.fsBase; color: Theme.text }
                            Text { id: lockText; visible: row.locked; text: "locked"; anchors.right: parent.right; anchors.rightMargin: Theme.s2
                                anchors.verticalCenter: parent.verticalCenter; font.family: Theme.fontFamily; font.pixelSize: Theme.fsXs; font.italic: true; color: Theme.textFaint
                                width: visible ? implicitWidth : 0 }
                            MouseArea {
                                id: ma; anchors.fill: parent; hoverEnabled: true
                                onClicked: (m) => Doc.selectIndex(row.index_, (m.modifiers & (Qt.ControlModifier | Qt.ShiftModifier)) !== 0)
                            }
                        }
                    }
                    Text {
                        visible: list.count === 0
                        anchors.centerIn: parent; text: "No elements yet.\nUse Add to place one."
                        horizontalAlignment: Text.AlignHCenter; color: Theme.textFaint
                        font.family: Theme.fontFamily; font.pixelSize: Theme.fsBase
                    }
                }
            }

            // ---------------- Data ----------------
            DataTab {
                id: dataTab
                onOpenExcel: p.openExcel()
                onOpenGoogle: p.openGoogle()
                onPrintQueue: (scope) => p.printQueue(scope)
                onOpenBatchScan: p.openBatchScan()
            }
        }
    }

    // generic one-line text prompt (add text)
    TextPromptDialog { id: textPrompt }
}
