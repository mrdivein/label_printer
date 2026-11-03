import QtQuick
import QtQuick.Layouts
import "../theme"
import "../components"

// One-line text prompt. Usage: dlg.openFor("Title", "initial", function(text) { ... }, "Confirm label")
AppDialog {
    id: d
    property var callback: null
    property alias value: field.text
    property string confirmText: "OK"
    property string hint: ""
    property bool multiline: false

    function openFor(ttl, initial, cb, okText, hintText) {
        title = ttl; field.text = initial || ""; callback = cb; confirmText = okText || "OK"; hint = hintText || ""
        open()
        field.forceActiveFocus(); field.selectAll()
    }
    function accept() { var cb = callback; var v = field.text; close(); if (cb) cb(v) }

    body: [
        AppTextField { id: field; Layout.preferredWidth: 380; Layout.fillWidth: true; onAccepted: d.accept(); selectByMouse: true },
        Text { visible: d.hint.length > 0; text: d.hint; Layout.fillWidth: true; wrapMode: Text.Wrap
            font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm; color: Theme.textMuted }
    ]
    buttons: [
        AppButton { text: "Cancel"; kind: "ghost"; onClicked: d.close() },
        AppButton { text: d.confirmText; kind: "primary"; onClicked: d.accept() }
    ]
}
