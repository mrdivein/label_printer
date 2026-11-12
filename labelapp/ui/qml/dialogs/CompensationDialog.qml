import QtQuick
import QtQuick.Layouts
import "../theme"
import "../components"

// Ruler measurements of the printed compare sheet -> width/height scale and X/Y offset for every print.
AppDialog {
    id: d
    title: qsTr("Đo & áp dụng bù sai số")
    signal verifyRequested()
    property var info: ({})
    property string error: ""
    onAboutToShow: {
        info = Printing.compareInfo(); error = ""
        mx.text = ""; my.text = ""; ml.text = ""; mt.text = ""
        sx.value = Doc.doc.scale_x_pct; sy.value = Doc.doc.scale_y_pct; ox.value = Doc.doc.offset_x_mm; oy.value = Doc.doc.offset_y_mm
    }
    function calc() {
        var r = Printing.computeCompensation({mx: mx.text, my: my.text, ml: ml.text, mt: mt.text})
        if (!r.ok) { error = r.error; return false }
        error = ""
        sx.value = r.scale_x_pct; sy.value = r.scale_y_pct; ox.value = r.offset_x_mm; oy.value = r.offset_y_mm
        return true
    }
    function apply() { Doc.setDocMany({scale_x_pct: sx.value, scale_y_pct: sy.value, offset_x_mm: ox.value, offset_y_mm: oy.value}) }

    body: [
        ColumnLayout {
            Layout.preferredWidth: 520; spacing: Theme.s3
            Text { Layout.fillWidth: true; wrapMode: Text.Wrap; font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm; color: Theme.textMuted
                text: d.info.hasSheet ? qsTr("Theo tờ so sánh in gần nhất (") + (d.info.compensated ? qsTr("có bù") : qsTr("gốc")) + ")."
                                     : qsTr("In tờ so sánh trước (In ▾ → In thử), đo trên giấy rồi quay lại đây.") }
            SectionHeader { text: qsTr("Số đo trên giấy (mm)"); Layout.fillWidth: true }
            PropertyRow { label: qsTr("Đường ngang"); labelWidth: 150; AppTextField { id: mx; Layout.fillWidth: true; placeholderText: qsTr("chuẩn ") + d.info.refX } }
            PropertyRow { label: qsTr("Đường dọc"); labelWidth: 150; AppTextField { id: my; Layout.fillWidth: true; placeholderText: qsTr("chuẩn ") + d.info.refY } }
            PropertyRow { label: qsTr("Mép trái → khung"); labelWidth: 150; AppTextField { id: ml; Layout.fillWidth: true; placeholderText: qsTr("chuẩn ") + d.info.inset } }
            PropertyRow { label: qsTr("Mép trên → khung"); labelWidth: 150; AppTextField { id: mt; Layout.fillWidth: true; placeholderText: qsTr("chuẩn ") + d.info.inset } }
            AppButton { text: qsTr("Tính từ số đo"); enabled: d.info.hasSheet === true; onClicked: d.calc() }
            Text { visible: d.error.length > 0; text: I18n.tr(d.error); color: Theme.danger; Layout.fillWidth: true; wrapMode: Text.Wrap; font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm }
            Separator { Layout.fillWidth: true }
            SectionHeader { text: qsTr("Bù sai số áp dụng cho mọi lần in"); Layout.fillWidth: true }
            GridLayout {
                columns: 4; columnSpacing: Theme.s2; rowSpacing: Theme.s2; Layout.fillWidth: true
                Text { text: qsTr("Tỉ lệ rộng"); color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm }
                NumberField { id: sx; Layout.fillWidth: true; unit: "%"; step: 0.1; from: 50; to: 150 }
                Text { text: qsTr("Tỉ lệ cao"); color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm }
                NumberField { id: sy; Layout.fillWidth: true; unit: "%"; step: 0.1; from: 50; to: 150 }
                Text { text: qsTr("Lệch X (+ sang phải)"); color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm }
                NumberField { id: ox; Layout.fillWidth: true; unit: "mm"; step: 0.1 }
                Text { text: qsTr("Lệch Y (+ xuống)"); color: Theme.textMuted; font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm }
                NumberField { id: oy; Layout.fillWidth: true; unit: "mm"; step: 0.1 }
            }
            Text { text: qsTr("Lưu mẫu để giữ bù sai số."); font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm; color: Theme.textFaint }
        }
    ]
    buttons: [
        AppButton { text: qsTr("Đặt lại"); kind: "ghost"; onClicked: { sx.value = 100; sy.value = 100; ox.value = 0; oy.value = 0 } },
        Item { Layout.fillWidth: true },
        AppButton { text: qsTr("Huỷ"); kind: "ghost"; onClicked: d.close() },
        AppButton { text: qsTr("Áp dụng + in kiểm tra"); onClicked: { d.apply(); d.close(); d.verifyRequested() } },
        AppButton { text: qsTr("Áp dụng"); kind: "primary"; onClicked: { d.apply(); d.close() } }
    ]
}
