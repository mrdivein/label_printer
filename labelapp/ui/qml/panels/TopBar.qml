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
    signal newTemplate()
    signal openGallery()

    // Open a library template, asking first when the current layout has unsaved changes.
    function switchTo(n) {
        if (n === Doc.templateName) return
        if (Doc.dirty) confirmSwitch.openFor(n); else Doc.openTemplate(n)
    }

    Image {
        source: Qt.resolvedUrl("../../resources/app.svg")
        sourceSize: Qt.size(26, 26); Layout.preferredWidth: 26; Layout.preferredHeight: 26
        smooth: true; mipmap: true
    }
    Text {
        text: App.appName
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
        displayText: Doc.templateName.length ? Doc.templateName.replace(/\.json$/i, "") : qsTr("Chưa có mẫu")
        onActivated: (i) => { var n = Lib.names[i]; if (n === Doc.templateName) return
            if (Doc.dirty) confirmSwitch.openFor(n); else Doc.openTemplate(n) }
        C.ToolTip.visible: hovered && !popup.visible; C.ToolTip.text: qsTr("Mẫu đang mở"); C.ToolTip.delay: 700
    }
    // unsaved-changes chip (amber): visible and readable, not just a dot
    Rectangle {
        visible: Doc.dirty
        Layout.preferredHeight: 24; Layout.preferredWidth: dirtyText.implicitWidth + 22
        radius: 12; color: Theme.warningSoft; border.width: 1; border.color: Qt.alpha(Theme.warning, 0.5)
        Rectangle { width: 6; height: 6; radius: 3; color: Theme.warning; anchors.left: parent.left; anchors.leftMargin: 8; anchors.verticalCenter: parent.verticalCenter }
        Text { id: dirtyText; text: qsTr("Chưa lưu"); anchors.left: parent.left; anchors.leftMargin: 18; anchors.verticalCenter: parent.verticalCenter
            font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm; font.weight: Font.DemiBold; color: Theme.warning }
        C.ToolTip.visible: dirtyHover.hovered; C.ToolTip.text: qsTr("Có thay đổi chưa lưu (vẫn được dùng khi in)")
        HoverHandler { id: dirtyHover }
    }
    AppButton { text: qsTr("Lưu"); kind: Doc.dirty ? "primary" : "secondary"; onClicked: bar.save()
        C.ToolTip.visible: hovered; C.ToolTip.text: qsTr("Lưu mẫu (Ctrl+S)"); C.ToolTip.delay: 600 }
    // everything else about templates lives in one menu (and in the "Mẫu" tab on the left)
    AppButton {
        text: qsTr("Mẫu") + "  ▾"; kind: "ghost"
        onClicked: tplMenu.popup(0, height + 4)
        AppMenu {
            id: tplMenu
            AppMenuItem { text: qsTr("＋ Tạo mới"); onTriggered: bar.newTemplate() }
            AppMenuItem { text: qsTr("Mẫu có sẵn…"); onTriggered: bar.openGallery() }
            AppMenuItem { text: qsTr("Quản lý thư viện mẫu…"); onTriggered: bar.openLibrary() }
            AppMenuSeparator {}
            AppMenuItem { text: qsTr("Lưu thành…"); hint: "Ctrl+Shift+S"; onTriggered: bar.saveAs() }
        }
    }
    Separator { vertical: true }
    IconButton { text: "↶"; font.pixelSize: Theme.fsLg; tip: qsTr("Hoàn tác (Ctrl+Z)"); enabled: Doc.canUndo; onClicked: Doc.undo() }
    IconButton { text: "↷"; font.pixelSize: Theme.fsLg; tip: qsTr("Làm lại (Ctrl+Y)"); enabled: Doc.canRedo; onClicked: Doc.redo() }

    Item { Layout.fillWidth: true }

    // data source
    AppButton {
        text: Data.hasData ? qsTr("Dữ liệu  ▾") : qsTr("Mở dữ liệu  ▾")
        glyph: "☷"
        kind: "data"
        onClicked: dataMenu.popup(0, height + 4)
        AppMenu {
            id: dataMenu
            AppMenuItem { text: qsTr("Mở tệp Excel…"); hint: "Ctrl+O"; onTriggered: bar.openExcel() }
            AppMenuItem { text: "Google Sheet…"; onTriggered: bar.openGoogle() }
            AppMenuSeparator {}
            Repeater { model: Data.savedSheets
                AppMenuItem { required property var modelData; required property int index
                    text: "Google Sheet · " + modelData.name + (modelData.tab ? "  [" + modelData.tab + "]" : "")
                    onTriggered: Data.loadSavedGoogle(index) } }
            AppMenuSeparator { visible: Data.savedSheets.length > 0 }
            Repeater { model: Data.recentExcel
                AppMenuItem { required property var modelData
                    text: "Excel · " + modelData.name
                    onTriggered: Data.loadExcel(modelData.path) } }
            AppMenuSeparator { visible: Data.recentExcel.length > 0 }
            AppMenuItem { text: qsTr("Tải lại dữ liệu"); hint: "F5"; enabled: Data.hasData; onTriggered: Data.reload() }
            AppMenuItem { text: qsTr("Chèn trường dữ liệu vào tem…"); enabled: Data.hasData; onTriggered: bar.addField() }
            AppMenuSeparator { visible: App.legacyAvailable }
            AppMenuItem { visible: App.legacyAvailable; height: visible ? implicitHeight : 0; text: qsTr("Mở ứng dụng cũ (quét hàng loạt, lịch sử)…"); onTriggered: App.launchLegacy() }
        }
    }
    signal addField()
    // row navigator: which data row the preview (and "In tem") uses
    Rectangle {
        visible: Data.hasData
        Layout.preferredHeight: Theme.controlH; Layout.preferredWidth: navRow.implicitWidth + 4
        radius: Theme.radiusMd; color: Theme.dataSoft
        Row {
            id: navRow; anchors.centerIn: parent; spacing: 0
            IconButton { text: "‹"; font.pixelSize: Theme.fsLg; width: 28; height: 28; tip: qsTr("Dòng trước") + " (PgUp)"; onClicked: Data.step(-1) }
            Text { text: Data.rowLabel; anchors.verticalCenter: parent.verticalCenter; leftPadding: 4; rightPadding: 4
                font.family: Theme.fontFamily; font.pixelSize: Theme.fsBase; font.weight: Font.DemiBold; color: Theme.data }
            IconButton { text: "›"; font.pixelSize: Theme.fsLg; width: 28; height: 28; tip: qsTr("Dòng sau") + " (PgDn)"; onClicked: Data.step(1) }
        }
    }
    Separator { vertical: true }
    // OTA update: progress while downloading, a "Restart to update" button once the new version is ready
    Text { visible: Updates.state === "downloading" || Updates.state === "error"; text: Updates.text
        Layout.maximumWidth: 260; elide: Text.ElideRight
        font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm; color: Updates.state === "error" ? Theme.warning : Theme.textMuted
        C.ToolTip.visible: updHover.hovered; C.ToolTip.text: Updates.text; HoverHandler { id: updHover } }
    AppButton { visible: Updates.state === "ready"; text: qsTr("Khởi động lại để cập nhật ") + Updates.newVersion; kind: "primary"
        onClicked: Updates.installNow() }
    IconButton { text: "⟳"; visible: Updates.supported && Updates.state !== "ready"; enabled: Updates.state !== "checking" && Updates.state !== "downloading"
        tip: qsTr("Kiểm tra cập nhật · phiên bản ") + Updates.currentVersion + (Updates.text.length ? "\n" + Updates.text : "")
        onClicked: Updates.check() }
    AppButton {
        objectName: "langButton"
        text: I18n.language === "en" ? "EN" : "VI"; compact: true; kind: "secondary"
        onClicked: langMenu.popup(0, height + 4)
        C.ToolTip.visible: hovered && !langMenu.visible; C.ToolTip.text: qsTr("Đổi ngôn ngữ giao diện (Tiếng Việt / English)"); C.ToolTip.delay: 500
        AppMenu {
            id: langMenu
            Repeater { model: I18n.languages
                AppMenuItem { required property var modelData
                    text: (I18n.language === modelData.code ? "✓  " : "     ") + modelData.name
                    onTriggered: I18n.setLanguage(modelData.code) } }
        }
    }
    IconButton { text: App.darkMode ? "☀" : "☾"; tip: qsTr("Đổi giao diện sáng / tối"); onClicked: App.darkMode = !App.darkMode }

    function save() {
        var r = Doc.saveTemplate()
        if (r === "needs_name") bar.saveAs()
        else if (r.length) App.errorRaised(qsTr("Lưu mẫu"), r)
    }

    AppDialog {
        id: confirmSwitch
        property string target: ""
        function openFor(n) { target = n; open() }
        title: qsTr("Bỏ các thay đổi chưa lưu?")
        body: [ Text { text: qsTr("Bố cục hiện tại có thay đổi đang được dùng khi in nhưng chưa lưu vào tệp mẫu.\n\nChuyển sang mẫu khác sẽ bỏ các thay đổi này.")
            Layout.preferredWidth: 380; wrapMode: Text.Wrap; font.family: Theme.fontFamily; font.pixelSize: Theme.fsBase; color: Theme.text } ]
        buttons: [
            AppButton { text: qsTr("Huỷ"); kind: "ghost"; onClicked: { confirmSwitch.close(); tpl.currentIndex = Math.max(0, Lib.names.indexOf(Doc.templateName)) } },
            AppButton { text: qsTr("Lưu rồi chuyển"); onClicked: { bar.save(); Doc.openTemplate(confirmSwitch.target); confirmSwitch.close() } },
            AppButton { text: qsTr("Bỏ thay đổi"); kind: "danger"; onClicked: { Doc.openTemplate(confirmSwitch.target); confirmSwitch.close() } }
        ]
    }
}
