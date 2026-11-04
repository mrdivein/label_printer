import QtQuick
import QtQuick.Controls.Basic as C
import QtQuick.Layouts
import QtQuick.Dialogs
import "theme"
import "components"
import "panels"
import "dialogs"

C.ApplicationWindow {
    id: win
    width: App.windowState.w || 1480
    height: App.windowState.h || 900
    x: App.windowState.x !== undefined ? App.windowState.x : 80
    y: App.windowState.y !== undefined ? App.windowState.y : 60
    minimumWidth: 1060
    minimumHeight: 640
    visible: true
    title: App.appName + (Doc.templateName.length ? "  —  " + Doc.templateName.replace(/\.json$/i, "") : "") + (Doc.dirty ? "  •" : "")
    color: Theme.bg
    font.family: Theme.fontFamily
    font.pixelSize: Theme.fsBase

    Binding { target: Theme; property: "dark"; value: App.darkMode }
    Component.onCompleted: if (App.windowState.maximized) win.visibility = Window.Maximized
    onClosing: App.saveWindow(win.x, win.y, win.width, win.height, win.visibility === Window.Maximized)

    readonly property bool typing: activeFocusItem !== null && activeFocusItem !== undefined && activeFocusItem.hasOwnProperty("cursorPosition")

    // ------------------------------------------------------------------ layout
    header: TopBar {
        id: top
        onSaveAs: textPrompt.openFor("Lưu mẫu thành", Doc.templateName.replace(/\.json$/i, "") || "Tem", function(n) {
            var e = Doc.saveTemplateAs(n); if (e.length) msg.show("Lưu mẫu", e); else Lib.refresh() }, "Lưu", "Mẫu được lưu vào thư viện mẫu.")
        onOpenLibrary: library.open()
        onOpenExcel: excelDialog.open()
        onOpenGoogle: googleDlg.open()
        onAddField: fieldPicker.open()
        onNewTemplate: newTpl.open()
    }
    footer: BottomBar {
        onPrintRequested: win.doPrint("current")
        onPrintSelected: win.openQueue("selected")
        onPrintAll: win.openQueue("all")
        onBatchScanRequested: batchScan.open()
        onProofRequested: Printing.pdfProof()
        onDriverRequested: win.doPrint("driver")
        onTestRequested: (kind) => win.doPrint("test:" + kind)
        onCompensationRequested: compDlg.open()
        onProfilesRequested: profilesDlg.open()
        onPrinterInfoRequested: msg.show("Thông tin máy in", Printing.printerSummary())
    }

    C.SplitView {
        anchors.fill: parent
        orientation: Qt.Horizontal
        handle: Rectangle { implicitWidth: 1; color: C.SplitHandle.hovered || C.SplitHandle.pressed ? Theme.accent : Theme.border }

        LeftPanel {
            id: left
            objectName: "left"
            C.SplitView.preferredWidth: 340
            C.SplitView.minimumWidth: 300
            C.SplitView.maximumWidth: 560
            onOpenExcel: excelDialog.open()
            onOpenGoogle: googleDlg.open()
            onAddFieldRequested: fieldPicker.open()
            onAddImageRequested: { imageDialog.forProperty = false; imageDialog.open() }
            onPrintQueue: (scope) => win.openQueue(scope)
            onOpenBatchScan: batchScan.open()
            onOpenTemplateRequested: (n) => top.switchTo(n)
            onNewTemplateRequested: newTpl.open()
            onOpenLibraryRequested: library.open()
        }
        CanvasView {
            id: canvas
            objectName: "canvas"
            C.SplitView.fillWidth: true
            C.SplitView.minimumWidth: 360
            focus: true
            onEditTextRequested: (i) => textPrompt.openFor("Sửa chữ", Doc.elementText(i), function(t) { Doc.setElementText(i, t) }, "Áp dụng", "Dùng {{TênCột}} để chèn dữ liệu.")
        }
        InspectorPanel {
            C.SplitView.preferredWidth: 330
            C.SplitView.minimumWidth: 290
            C.SplitView.maximumWidth: 520
            onPickImage: { imageDialog.forProperty = true; imageDialog.open() }
        }
    }

    // ------------------------------------------------------------------ actions
    function doPrint(mode) {
        var r = mode.indexOf("test:") === 0 ? Printing.prepareTest(mode.substring(5)) : Printing.preparePrint()
        printConfirm.show(r, mode)
    }
    function openQueue(scope) { if (Printing.openQueue(scope)) queueDlg.open() }

    // ------------------------------------------------------------------ shortcuts
    Shortcut { sequences: ["Ctrl+S"]; onActivated: top.save() }
    Shortcut { sequences: ["Ctrl+Shift+S"]; onActivated: top.saveAs() }
    Shortcut { sequences: ["Ctrl+P"]; onActivated: win.doPrint("current") }
    Shortcut { sequences: ["Ctrl+O"]; onActivated: excelDialog.open() }
    Shortcut { sequences: ["F8"]; onActivated: batchScan.open() }
    Shortcut { sequences: ["Ctrl+L"]; onActivated: left.focusScan() }
    Shortcut { sequences: ["F5"]; onActivated: Data.reload() }
    Shortcut { sequences: ["Ctrl+Z"]; enabled: !win.typing; onActivated: Doc.undo() }
    Shortcut { sequences: ["Ctrl+Y", "Ctrl+Shift+Z"]; enabled: !win.typing; onActivated: Doc.redo() }
    Shortcut { sequences: ["Ctrl+C"]; enabled: !win.typing; onActivated: Doc.copySelected() }
    Shortcut { sequences: ["Ctrl+V"]; enabled: !win.typing; onActivated: Doc.paste() }
    Shortcut { sequences: ["Ctrl+A"]; enabled: !win.typing; onActivated: Doc.selectAll() }
    Shortcut { sequences: ["Ctrl+D"]; enabled: !win.typing; onActivated: Doc.duplicateSelected() }
    Shortcut { sequences: ["Ctrl+G"]; enabled: !win.typing; onActivated: Doc.groupSelected() }
    Shortcut { sequences: ["Ctrl+Shift+G"]; enabled: !win.typing; onActivated: Doc.ungroupSelected() }
    Shortcut { sequences: ["Delete"]; enabled: !win.typing; onActivated: Doc.deleteSelected() }
    Shortcut { sequences: ["Escape"]; enabled: !win.typing; onActivated: Doc.clearSelection() }
    Shortcut { sequences: ["Left"]; enabled: !win.typing; onActivated: Doc.nudge(-1, 0, false) }
    Shortcut { sequences: ["Right"]; enabled: !win.typing; onActivated: Doc.nudge(1, 0, false) }
    Shortcut { sequences: ["Up"]; enabled: !win.typing && left.tab !== left.tabData; onActivated: Doc.nudge(0, -1, false) }
    Shortcut { sequences: ["Down"]; enabled: !win.typing && left.tab !== left.tabData; onActivated: Doc.nudge(0, 1, false) }
    Shortcut { sequences: ["Shift+Left"]; enabled: !win.typing; onActivated: Doc.nudge(-1, 0, true) }
    Shortcut { sequences: ["Shift+Right"]; enabled: !win.typing; onActivated: Doc.nudge(1, 0, true) }
    Shortcut { sequences: ["Shift+Up"]; enabled: !win.typing; onActivated: Doc.nudge(0, -1, true) }
    Shortcut { sequences: ["Shift+Down"]; enabled: !win.typing; onActivated: Doc.nudge(0, 1, true) }
    Shortcut { sequences: ["Ctrl+0"]; onActivated: canvas.fit() }
    Shortcut { sequences: ["Ctrl+1"]; onActivated: canvas.actualSize() }
    Shortcut { sequences: ["Ctrl+=", "Ctrl++"]; onActivated: canvas.zoomBy(1.25) }
    Shortcut { sequences: ["Ctrl+-"]; onActivated: canvas.zoomBy(1 / 1.25) }
    Shortcut { sequences: ["PgDown"]; enabled: !win.typing; onActivated: Data.step(1) }
    Shortcut { sequences: ["PgUp"]; enabled: !win.typing; onActivated: Data.step(-1) }

    // ------------------------------------------------------------------ dialogs
    MessageDialog { id: msg }
    TextPromptDialog { id: textPrompt }
    ConfirmPrintDialog { id: printConfirm; objectName: "printConfirm" }
    ProfilesDialog { id: profilesDlg }
    CompensationDialog { id: compDlg; onVerifyRequested: win.doPrint("test:compare_comp") }
    PrintQueueDialog { id: queueDlg; objectName: "queueDlg"; onExportRequested: pdfDialog.open() }
    BatchScanDialog { id: batchScan; objectName: "batchScan" }
    BatchDialog { id: batch; objectName: "batch" }
    GoogleSheetDialog { id: googleDlg; objectName: "googleDlg" }
    FieldPickerDialog { id: fieldPicker; objectName: "fieldPicker" }
    NewTemplateDialog { id: newTpl; objectName: "newTpl"; onCreated: left.tab = 1 }
    TemplateLibraryDialog {
        id: library
        objectName: "library"
        onImportRequested: importDialog.open()
        onExportRequested: (name) => { exportDialog.templateName = name; exportDialog.currentFile = "file:///" + name; exportDialog.open() }
        onPromptRequested: (ttl, initial, action, name) => textPrompt.openFor(ttl, initial, function(n) {
            var e = action === "rename" ? Lib.rename(name, n) : Lib.duplicate(name, n)
            library.finish(e); if (!e.length) library.select(n.toLowerCase().endsWith(".json") ? n : n + ".json") }, "OK")
    }
    AppDialog {
        id: existsDlg
        property string srcUrl: ""
        title: "Mẫu đã tồn tại"
        body: [ Text { text: "Thư viện đã có một mẫu trùng tên."; Layout.preferredWidth: 380; wrapMode: Text.Wrap
            font.family: Theme.fontFamily; font.pixelSize: Theme.fsBase; color: Theme.text } ]
        buttons: [
            AppButton { text: "Huỷ"; kind: "ghost"; onClicked: existsDlg.close() },
            AppButton { text: "Lưu với tên khác…"; onClicked: { existsDlg.close(); textPrompt.openFor("Nhập với tên", "Mau_nhap", function(n) {
                var e = Lib.importTemplate(existsDlg.srcUrl, n, false); if (e.length && e.indexOf("exists:") !== 0) msg.show("Nhập mẫu", e) }, "Nhập") } },
            AppButton { text: "Thay thế"; kind: "danger"; onClicked: { existsDlg.close(); var e = Lib.importTemplate(existsDlg.srcUrl, "", true); if (e.length) msg.show("Nhập mẫu", e) } }
        ]
    }

    FileDialog {
        id: excelDialog
        title: "Mở tệp Excel"
        nameFilters: ["Tệp Excel (*.xlsx *.xlsm)", "Tất cả tệp (*)"]
        onAccepted: Data.loadExcel(App.toLocalPath(selectedFile))
    }
    FileDialog {
        id: importDialog
        title: "Mở mẫu từ tệp"
        nameFilters: ["Mẫu JSON (*.json)", "Tất cả tệp (*)"]
        onAccepted: { var e = Lib.importTemplate(selectedFile, "", false)
            if (e.indexOf("exists:") === 0) { existsDlg.srcUrl = selectedFile; existsDlg.open() }
            else if (e.length) { msg.show("Mở mẫu", e) }
            else { library.close() } }
    }
    FileDialog {
        id: exportDialog
        property string templateName: ""
        title: "Xuất mẫu"
        fileMode: FileDialog.SaveFile
        defaultSuffix: "json"
        nameFilters: ["Mẫu JSON (*.json)"]
        onAccepted: { var e = Lib.exportTemplate(templateName, selectedFile); if (e.length) msg.show("Xuất mẫu", e) }
    }
    FileDialog {
        id: imageDialog
        property bool forProperty: false
        title: "Chọn ảnh / logo"
        nameFilters: ["Ảnh (*.png *.jpg *.jpeg *.bmp *.gif)", "Tất cả tệp (*)"]
        onAccepted: { var p = App.toLocalPath(selectedFile); if (forProperty) Doc.setProp("path", p); else Doc.addImage(p) }
    }
    FileDialog {
        id: pdfDialog
        title: "Xuất tem ra PDF"
        fileMode: FileDialog.SaveFile
        defaultSuffix: "pdf"
        nameFilters: ["PDF (*.pdf)"]
        onAccepted: { var e = Printing.exportQueuePdf(selectedFile); msg.show("Xuất PDF", e.length ? e : "Đã lưu " + Printing.queueSummary.split("·").pop().trim() + " thành các trang PDF.") }
    }

    Connections { target: App; function onErrorRaised(t, m) { msg.show(t, m) } }
    Connections { target: Updates; function onQuitRequested() { win.close() } }   // window state is saved, then the installer restarts the app
}
