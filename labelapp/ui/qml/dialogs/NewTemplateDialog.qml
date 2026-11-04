import QtQuick
import QtQuick.Controls.Basic as C
import QtQuick.Layouts
import "../theme"
import "../components"

// New template: pick a kind of label (card), then a common size for it, or type any size.
AppDialog {
    id: d
    title: "Tạo tem mới"
    subtitle: "Chọn loại tem và khổ giấy — sau này vẫn đổi được ở bảng bên phải."
    signal created(string name)
    property string error: ""
    property int kind: 0
    property int sizeIndex: 0
    property bool nameEdited: false

    // fold: add a 180° fold region at half height (tem gập 2 mặt). Sizes in mm.
    readonly property var kinds: [
        { name: "Tem dán", desc: "Nhãn sản phẩm, giá, mã vạch trên cuộn tem nhiệt", icon: "box", fold: false, prefix: "Tem_dan",
          sizes: [[30, 20], [40, 25], [40, 30], [50, 30], [60, 40], [70, 40], [100, 50], [100, 70]] },
        { name: "Tem gập (treo)", desc: "Tem 2 mặt gập đôi, mặt sau tự in lật 180°", icon: "fold", fold: true, prefix: "Tem_gap",
          sizes: [[50, 68], [56, 83], [40, 60], [50, 90]] },
        { name: "Tem vận chuyển", desc: "Phiếu giao hàng, thùng carton, kho", icon: "barcode", fold: false, prefix: "Tem_van_chuyen",
          sizes: [[100, 150], [100, 100], [101.6, 152.4], [80, 50]] },
        { name: "Tem trang sức", desc: "Tem đuôi chuột / tem dài hẹp cho nhẫn, dây chuyền", icon: "line", fold: false, prefix: "Tem_trang_suc",
          sizes: [[68, 12], [72, 10], [90, 12]] },
        { name: "Tuỳ chỉnh", desc: "Tự nhập chiều rộng và chiều cao", icon: "area", fold: false, prefix: "Tem_moi", sizes: [] }
    ]
    readonly property var k: kinds[kind]

    function sizeText(s) { return (s[0] === 101.6 && s[1] === 152.4) ? "4×6 inch" : (s[0] + "×" + s[1] + " mm") }
    function applySize() {
        var s = k.sizes[sizeIndex]
        if (s) { w.value = s[0]; h.value = s[1] }
        if (!nameEdited) nm.text = k.prefix + "_" + Math.round(w.value) + "x" + Math.round(h.value)
    }
    function pickKind(i) { kind = i; sizeIndex = 0; applySize() }

    onAboutToShow: { error = ""; nameEdited = false; kind = 0; sizeIndex = 0; dpi.currentIndex = 1; applySize() }

    body: [
        RowLayout {
            Layout.preferredWidth: 720; spacing: Theme.s5

            // ---- kind cards ----
            ColumnLayout {
                Layout.preferredWidth: 300; Layout.alignment: Qt.AlignTop; spacing: Theme.s2
                Repeater {
                    model: d.kinds
                    delegate: Rectangle {
                        required property var modelData
                        required property int index
                        readonly property bool on: d.kind === index
                        Layout.fillWidth: true; implicitHeight: 58
                        radius: Theme.radiusMd
                        color: on ? Theme.accentSoft : (kma.containsMouse ? Theme.hover : Theme.surface)
                        border.width: on ? 2 : 1; border.color: on ? Theme.accent : Theme.border
                        PaletteTile { id: ic; focusPolicy: Qt.NoFocus; art: modelData.icon; text: ""; width: 44; height: 40
                            anchors.left: parent.left; anchors.leftMargin: Theme.s2; anchors.verticalCenter: parent.verticalCenter }
                        Column {
                            anchors.left: ic.right; anchors.leftMargin: Theme.s2; anchors.right: parent.right; anchors.rightMargin: Theme.s2
                            anchors.verticalCenter: parent.verticalCenter; spacing: 1
                            Text { text: modelData.name; font.family: Theme.fontFamily; font.pixelSize: Theme.fsBase; font.weight: Font.DemiBold
                                color: on ? Theme.accent : Theme.text }
                            Text { text: modelData.desc; width: parent.width; elide: Text.ElideRight
                                font.family: Theme.fontFamily; font.pixelSize: Theme.fsXs; color: Theme.textMuted }
                        }
                        MouseArea { id: kma; anchors.fill: parent; hoverEnabled: true; onClicked: d.pickKind(index) }
                    }
                }
            }

            // ---- size + name ----
            ColumnLayout {
                Layout.fillWidth: true; Layout.alignment: Qt.AlignTop; spacing: Theme.s3
                SectionHeader { text: "Khổ tem"; Layout.fillWidth: true; visible: d.k.sizes.length > 0 }
                Flow {
                    Layout.fillWidth: true; spacing: Theme.s2; visible: d.k.sizes.length > 0
                    Repeater {
                        model: d.k.sizes
                        delegate: C.AbstractButton {
                            id: chip
                            required property var modelData
                            required property int index
                            readonly property bool on: d.sizeIndex === index
                            implicitWidth: chipText.implicitWidth + Theme.s4 * 2; implicitHeight: 32
                            hoverEnabled: true
                            background: Rectangle { radius: 16; color: chip.on ? Theme.accent : chip.hovered ? Theme.hover : Theme.surface
                                border.width: 1; border.color: chip.on ? Theme.accent : Theme.borderStrong }
                            contentItem: Text { id: chipText; text: d.sizeText(chip.modelData); horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                                font.family: Theme.fontFamily; font.pixelSize: Theme.fsBase; font.weight: Font.Medium
                                color: chip.on ? Theme.onAccent : Theme.text }
                            onClicked: { d.sizeIndex = index; d.applySize() }
                        }
                    }
                }
                PropertyRow { label: "Rộng × cao"
                    NumberField { id: w; Layout.fillWidth: true; value: 50; unit: "mm"; from: 1
                        onEdited: { d.sizeIndex = -1; if (!d.nameEdited) d.applySize() } }
                    NumberField { id: h; Layout.fillWidth: true; value: 30; unit: "mm"; from: 1
                        onEdited: { d.sizeIndex = -1; if (!d.nameEdited) d.applySize() } } }
                PropertyRow { label: "DPI máy in"
                    ComboField { id: dpi; Layout.fillWidth: true; model: ["203", "300", "600"]; currentIndex: 1 } }
                PropertyRow { label: "Tên mẫu"; AppTextField { id: nm; Layout.fillWidth: true; onTextEdited: d.nameEdited = true; onAccepted: ok.clicked() } }
                Text { visible: d.k.fold; Layout.fillWidth: true; wrapMode: Text.Wrap
                    text: "Đường gập được đặt ở giữa tem; kéo đường màu cam để đổi vị trí gập."
                    font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm; color: Theme.textMuted }
                Text { visible: d.error.length > 0; text: d.error; color: Theme.danger; Layout.fillWidth: true; wrapMode: Text.Wrap
                    font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm }
            }
        }
    ]
    buttons: [
        AppButton { text: "Huỷ"; kind: "ghost"; onClicked: d.close() },
        AppButton { id: ok; text: "Tạo tem"; kind: "primary"
            onClicked: {
                var e = Lib.createTemplate(nm.text, w.value, h.value, parseInt(dpi.currentText))
                if (e.length) { d.error = e; return }
                if (d.k.fold) { Doc.ensureFoldLine(); Doc.saveTemplate() }
                d.close(); d.created(nm.text)
            } }
    ]
}
