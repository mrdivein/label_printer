import QtQuick
import QtQuick.Controls.Basic as C
import QtQuick.Layouts
import "../theme"
import "../components"

AppDialog {
    id: d
    title: "Template library"
    subtitle: Lib.libraryDir
    contentPadding: 0
    width: Math.min(parent ? parent.width - 80 : 900, 900)
    height: Math.min(parent ? parent.height - 80 : 600, 600)
    signal importRequested()
    signal exportRequested(string name)
    signal promptRequested(string title, string initial, string action, string name)

    property string current: ""
    property string message: ""
    function select(n) { current = n; message = ""; if (n.length) Lib.showPreview(n) }
    onOpened: { Lib.refresh(); select(Doc.templateName || (Lib.names.length ? Lib.names[0] : "")) }

    function finish(err) { message = err || "" }

    body: [
        RowLayout {
            Layout.fillWidth: true; Layout.fillHeight: true; spacing: 0
            ColumnLayout {
                Layout.preferredWidth: 300; Layout.fillHeight: true; spacing: 0
                ListView {
                    id: list
                    Layout.fillWidth: true; Layout.fillHeight: true
                    clip: true; model: Lib.names
                    boundsBehavior: Flickable.StopAtBounds
                    C.ScrollBar.vertical: C.ScrollBar {}
                    delegate: Rectangle {
                        required property string modelData
                        width: list.width; height: 36
                        color: d.current === modelData ? Theme.selected : (ma.containsMouse ? Theme.hover : "transparent")
                        Text { anchors.fill: parent; anchors.leftMargin: Theme.s5; anchors.rightMargin: Theme.s3
                            text: modelData.replace(/\.json$/i, ""); elide: Text.ElideRight; verticalAlignment: Text.AlignVCenter
                            font.family: Theme.fontFamily; font.pixelSize: Theme.fsBase; color: Theme.text
                            font.weight: modelData === Doc.templateName ? Font.DemiBold : Font.Normal }
                        MouseArea { id: ma; anchors.fill: parent; hoverEnabled: true; onClicked: d.select(modelData); onDoubleClicked: { d.select(modelData); useBtn.clicked() } }
                    }
                }
                Separator { Layout.fillWidth: true }
                Flow {
                    Layout.fillWidth: true; Layout.margins: Theme.s3; Layout.leftMargin: Theme.s5; spacing: Theme.s1
                    AppButton { text: "New…"; compact: true; onClicked: newDlg.open() }
                    AppButton { text: "Duplicate"; compact: true; enabled: d.current.length > 0
                        onClicked: d.promptRequested("Duplicate template", d.current.replace(/\.json$/i, "") + "_copy", "duplicate", d.current) }
                    AppButton { text: "Rename"; compact: true; enabled: d.current.length > 0
                        onClicked: d.promptRequested("Rename template", d.current.replace(/\.json$/i, ""), "rename", d.current) }
                    AppButton { text: "Delete"; compact: true; kind: "danger"; enabled: d.current.length > 0; onClicked: delDlg.open() }
                    AppButton { text: "Import…"; compact: true; onClicked: d.importRequested() }
                    AppButton { text: "Export…"; compact: true; enabled: d.current.length > 0; onClicked: d.exportRequested(d.current) }
                    AppButton { text: "Open folder"; compact: true; kind: "ghost"; onClicked: Lib.openFolder() }
                }
            }
            Rectangle { Layout.fillHeight: true; width: 1; color: Theme.border }
            ColumnLayout {
                Layout.fillWidth: true; Layout.fillHeight: true; spacing: 0
                Rectangle {
                    Layout.fillWidth: true; Layout.fillHeight: true; color: Theme.canvas
                    Image { anchors.fill: parent; anchors.margins: Theme.s5; fillMode: Image.PreserveAspectFit; smooth: true; mipmap: true; cache: false
                        source: d.current.length ? Lib.previewSource : "" }
                }
                Text { text: d.message.length ? d.message : Lib.previewInfo; Layout.fillWidth: true; Layout.margins: Theme.s3; Layout.leftMargin: Theme.s5
                    elide: Text.ElideRight; font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm; color: d.message.length ? Theme.danger : Theme.textMuted }
            }
        }
    ]
    buttons: [
        AppButton { text: "Close"; kind: "ghost"; onClicked: d.close() },
        AppButton { id: useBtn; text: "Use this template"; kind: "primary"; enabled: d.current.length > 0
            onClicked: { var n = d.current; var err = Doc.openTemplate(n); if (err.length) d.message = err; else d.close() } }
    ]

    NewTemplateDialog { id: newDlg; onCreated: (n) => { d.close() } }
    AppDialog {
        id: delDlg
        title: "Delete template?"
        body: [ Text { text: "'" + d.current + "' will be removed from the library.\nA backup copy is kept in template_backups."
            wrapMode: Text.Wrap; Layout.preferredWidth: 360; font.family: Theme.fontFamily; font.pixelSize: Theme.fsBase; color: Theme.text } ]
        buttons: [ AppButton { text: "Cancel"; kind: "ghost"; onClicked: delDlg.close() },
                   AppButton { text: "Delete"; kind: "danger"; onClicked: { delDlg.close(); var n = d.current; var e = Lib.delete(n); d.finish(e); d.select(Lib.names.length ? Lib.names[0] : "") } } ]
    }
}
