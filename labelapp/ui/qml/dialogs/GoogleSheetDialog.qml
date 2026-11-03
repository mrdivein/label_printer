import QtQuick
import QtQuick.Controls.Basic as C
import QtQuick.Layouts
import "../theme"
import "../components"

AppDialog {
    id: d
    title: "Google Sheets"
    subtitle: "The sheet must be shared as “Anyone with the link – Viewer”. Links are remembered."
    property int selected: -1
    onAboutToShow: { var g = Data.googleDefaults; url.text = g.url; tab.text = g.tab; nm.text = ""; selected = -1 }
    function pick(i) { selected = i; var it = Data.savedSheets[i]; nm.text = it.name || ""; url.text = it.url; tab.text = it.tab || "LABEL DATA" }

    body: [
        ColumnLayout {
            Layout.preferredWidth: 540; spacing: Theme.s3
            SectionHeader { text: "Saved sheets"; Layout.fillWidth: true; visible: Data.savedSheets.length > 0 }
            ListView {
                id: list
                visible: Data.savedSheets.length > 0
                Layout.fillWidth: true; Layout.preferredHeight: Math.min(150, Data.savedSheets.length * 34)
                clip: true; model: Data.savedSheets
                delegate: Rectangle {
                    required property var modelData; required property int index
                    width: list.width; height: 34; radius: Theme.radiusSm
                    color: d.selected === index ? Theme.selected : (ma.containsMouse ? Theme.hover : "transparent")
                    Text { anchors.fill: parent; anchors.leftMargin: Theme.s3; verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight
                        text: modelData.name + (modelData.tab ? "   [" + modelData.tab + "]" : ""); font.family: Theme.fontFamily; font.pixelSize: Theme.fsBase; color: Theme.text }
                    MouseArea { id: ma; anchors.fill: parent; hoverEnabled: true; onClicked: d.pick(index); onDoubleClicked: { d.pick(index); load.clicked() } }
                }
            }
            PropertyRow { label: "Name (optional)"; labelWidth: 110; AppTextField { id: nm; Layout.fillWidth: true } }
            PropertyRow { label: "Sheet URL or ID"; labelWidth: 110; AppTextField { id: url; Layout.fillWidth: true; selectByMouse: true } }
            PropertyRow { label: "Tab name"; labelWidth: 110; AppTextField { id: tab; Layout.fillWidth: true; onAccepted: load.clicked() } }
        }
    ]
    buttons: [
        AppButton { text: "Remove from list"; kind: "ghost"; enabled: d.selected >= 0; onClicked: { Data.removeSavedGoogle(d.selected); d.selected = -1 } },
        Item { Layout.fillWidth: true },
        AppButton { text: "Cancel"; kind: "ghost"; onClicked: d.close() },
        AppButton { id: load; text: "Load"; kind: "primary"; enabled: url.text.trim().length > 0 && !Data.loading
            onClicked: { Data.loadGoogle(url.text, tab.text, nm.text); d.close() } }
    ]
}
