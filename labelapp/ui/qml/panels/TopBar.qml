import QtQuick
import QtQuick.Controls.Basic as C
import QtQuick.Layouts
import "../theme"
import "../components"
import "../dialogs"

Toolbar {
    id: bar
    signal saveAs()
    signal openLibrary()
    signal openExcel()
    signal openGoogle()
    signal importTemplate()

    Text {
        text: "ECG Label Tool"
        font.family: Theme.fontFamily; font.pixelSize: Theme.fsMd; font.weight: Font.DemiBold; color: Theme.text
        Layout.rightMargin: Theme.s2
    }
    Separator { vertical: true }

    // template selector
    ComboField {
        id: tpl
        Layout.preferredWidth: 230
        model: Lib.names
        currentIndex: Math.max(0, Lib.names.indexOf(Doc.templateName))
        displayText: Doc.templateName.length ? Doc.templateName.replace(/\.json$/i, "") : "No template"
        onActivated: (i) => { var n = Lib.names[i]; if (n === Doc.templateName) return
            if (Doc.dirty) confirmSwitch.openFor(n); else Doc.openTemplate(n) }
        C.ToolTip.visible: hovered && !popup.visible; C.ToolTip.text: "Template"; C.ToolTip.delay: 700
    }
    Rectangle { visible: Doc.dirty; width: 8; height: 8; radius: 4; color: Theme.warning
        C.ToolTip.visible: dirtyHover.hovered; C.ToolTip.text: "Unsaved changes (live for printing)"
        HoverHandler { id: dirtyHover } }
    AppButton { text: "Save"; compact: false; kind: Doc.dirty ? "primary" : "secondary"; onClicked: bar.save() }
    AppButton { text: "Save as…"; kind: "ghost"; onClicked: bar.saveAs() }
    AppButton { text: "Library"; kind: "ghost"; onClicked: bar.openLibrary() }
    Separator { vertical: true }
    IconButton { text: "↶"; tip: "Undo (Ctrl+Z)"; enabled: Doc.canUndo; onClicked: Doc.undo() }
    IconButton { text: "↷"; tip: "Redo (Ctrl+Y)"; enabled: Doc.canRedo; onClicked: Doc.redo() }

    Item { Layout.fillWidth: true }

    // data source
    AppButton {
        text: Data.hasData ? "Data  ▾" : "Load data  ▾"
        kind: Data.hasData ? "secondary" : "primary"
        onClicked: dataMenu.popup(0, height + 4)
        AppMenu {
            id: dataMenu
            AppMenuItem { text: "Open Excel file…"; hint: "Ctrl+O"; onTriggered: bar.openExcel() }
            AppMenuItem { text: "Google Sheet…"; onTriggered: bar.openGoogle() }
            AppMenuSeparator {}
            Repeater { model: Data.savedSheets
                AppMenuItem { required property var modelData; required property int index
                    text: "Sheet · " + modelData.name + (modelData.tab ? "  [" + modelData.tab + "]" : "")
                    onTriggered: Data.loadSavedGoogle(index) } }
            AppMenuSeparator { visible: Data.savedSheets.length > 0 }
            Repeater { model: Data.recentExcel
                AppMenuItem { required property var modelData
                    text: "Excel · " + modelData.name
                    onTriggered: Data.loadExcel(modelData.path) } }
            AppMenuSeparator { visible: Data.recentExcel.length > 0 }
            AppMenuItem { text: "Reload data"; hint: "F5"; enabled: Data.hasData; onTriggered: Data.reload() }
            AppMenuItem { text: "Add data field to label…"; enabled: Data.hasData; onTriggered: bar.addField() }
            AppMenuSeparator { visible: App.legacyAvailable }
            AppMenuItem { visible: App.legacyAvailable; height: visible ? implicitHeight : 0; text: "Open legacy app (batch scan, history)…"; onTriggered: App.launchLegacy() }
        }
    }
    signal addField()
    Text { text: Data.hasData ? Data.rowLabel : ""; visible: Data.hasData
        font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm; color: Theme.textMuted }
    Separator { vertical: true }
    IconButton { text: App.darkMode ? "☀" : "☾"; tip: "Toggle light / dark theme"; onClicked: App.darkMode = !App.darkMode }

    function save() {
        var r = Doc.saveTemplate()
        if (r === "needs_name") bar.saveAs()
        else if (r.length) App.errorRaised("Save template", r)
    }

    AppDialog {
        id: confirmSwitch
        property string target: ""
        function openFor(n) { target = n; open() }
        title: "Discard unsaved changes?"
        body: [ Text { text: "The current layout has changes that are live for printing but not saved to the template file.\n\nSwitching template discards them."
            Layout.preferredWidth: 380; wrapMode: Text.Wrap; font.family: Theme.fontFamily; font.pixelSize: Theme.fsBase; color: Theme.text } ]
        buttons: [
            AppButton { text: "Cancel"; kind: "ghost"; onClicked: { confirmSwitch.close(); tpl.currentIndex = Math.max(0, Lib.names.indexOf(Doc.templateName)) } },
            AppButton { text: "Save, then switch"; onClicked: { bar.save(); Doc.openTemplate(confirmSwitch.target); confirmSwitch.close() } },
            AppButton { text: "Discard"; kind: "danger"; onClicked: { Doc.openTemplate(confirmSwitch.target); confirmSwitch.close() } }
        ]
    }
}
