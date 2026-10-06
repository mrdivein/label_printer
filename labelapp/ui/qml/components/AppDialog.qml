import QtQuick
import QtQuick.Controls.Basic as C
import QtQuick.Layouts
import "../theme"

// Modal dialog with title, content area and a button footer (use `buttons` for AppButton items).
C.Dialog {
    id: d
    property alias body: bodySlot.data
    property alias buttons: footerRow.data
    property string subtitle: ""
    property int contentPadding: Theme.s5
    modal: true
    anchors.centerIn: C.Overlay.overlay
    padding: 0
    closePolicy: C.Popup.CloseOnEscape
    enter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.dFast }
                        NumberAnimation { property: "scale"; from: 0.98; to: 1; duration: Theme.dFast } }
    exit: Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: Theme.dFast } }

    C.Overlay.modal: Rectangle { color: Theme.dark ? "#99000000" : "#55141c30" }
    background: Rectangle {
        radius: Theme.radiusLg; color: Theme.surface
        border.width: 1; border.color: Theme.border
    }
    header: Item {
        implicitHeight: d.title.length ? (d.subtitle.length ? 64 : 52) : 0
        Column {
            anchors.left: parent.left; anchors.leftMargin: d.contentPadding; anchors.verticalCenter: parent.verticalCenter
            spacing: 2
            Text { text: d.title; font.family: Theme.fontFamily; font.pixelSize: Theme.fsLg; font.weight: Font.DemiBold; color: Theme.text }
            Text { visible: d.subtitle.length > 0; text: d.subtitle; font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm; color: Theme.textMuted }
        }
        Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.border }
    }
    contentItem: Item {
        implicitWidth: bodySlot.implicitWidth + d.contentPadding * 2
        implicitHeight: bodySlot.implicitHeight + d.contentPadding * 2
        ColumnLayout {
            id: bodySlot
            anchors.fill: parent; anchors.margins: d.contentPadding
            spacing: Theme.s3
        }
    }
    footer: Item {
        implicitHeight: footerRow.children.length ? 56 : 0
        Rectangle { width: parent.width; height: 1; color: Theme.border }
        RowLayout {
            id: footerRow
            anchors.right: parent.right; anchors.rightMargin: d.contentPadding
            anchors.verticalCenter: parent.verticalCenter
            spacing: Theme.s2
        }
    }
}
