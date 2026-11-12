import QtQuick
import QtQuick.Layouts
import "../theme"
import "../components"

AppDialog {
    id: d
    property string text: ""
    function show(ttl, msg) { title = I18n.tr(ttl); text = I18n.tr(msg); open() }
    body: [ Text { text: d.text; Layout.preferredWidth: 440; Layout.maximumWidth: 560; wrapMode: Text.Wrap; textFormat: Text.PlainText
        font.family: Theme.fontFamily; font.pixelSize: Theme.fsBase; color: Theme.text } ]
    buttons: [ AppButton { text: "OK"; kind: "primary"; onClicked: d.close() } ]
}
