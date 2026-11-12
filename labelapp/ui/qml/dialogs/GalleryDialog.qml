import QtQuick
import QtQuick.Controls.Basic as C
import QtQuick.Layouts
import "../theme"
import "../components"

// Ready-made template gallery: category chips, search, a grid of cards; a card opens a large preview that
// switches between sample data and the original template ({{fields}} visible).
AppDialog {
    id: d
    title: qsTr("Kho mẫu tem")
    subtitle: qsTr("Mẫu dựng sẵn theo ngành hàng — chọn một mẫu, sửa nội dung rồi in.")
    contentPadding: 0
    width: Math.min(parent ? parent.width - 60 : 1180, 1180)
    height: Math.min(parent ? parent.height - 60 : 780, 780)

    property string category: ""            // "" = all, "popular", or a category id
    property string query: ""
    property var hits: null                 // ids matching the search (null = no search)
    readonly property bool en: I18n.language === "en"
    function loc(o) { return o ? (d.en ? (o.en || o.vi) : (o.vi || o.en)) : "" }

    readonly property var shown: {
        var out = []
        var items = Gallery.items
        for (var i = 0; i < items.length; i++) {
            var it = items[i]
            if (d.category === "popular" && !it.popular) continue
            if (d.category.length && d.category !== "popular" && it.category !== d.category) continue
            if (d.hits !== null && d.hits.indexOf(it.id) < 0) continue
            out.push(it)
        }
        return out
    }
    onOpened: { Gallery.loadThumbs(); search.forceActiveFocus() }

    body: [
        ColumnLayout {
            Layout.fillWidth: true; Layout.fillHeight: true
            spacing: 0

            // ---- category chips
            C.ScrollView {
                Layout.fillWidth: true; Layout.preferredHeight: 66
                Layout.leftMargin: Theme.s4; Layout.rightMargin: Theme.s4; Layout.topMargin: Theme.s3
                clip: true
                C.ScrollBar.vertical.policy: C.ScrollBar.AlwaysOff
                Row {
                    spacing: Theme.s2
                    Repeater {
                        model: [{ id: "", name: { vi: "Tất cả mẫu", en: "All templates" }, icon: "▦", count: Gallery.total },
                                { id: "popular", name: { vi: "Phổ biến", en: "Popular" }, icon: "☆", count: -1 }].concat(Gallery.categories)
                        delegate: C.AbstractButton {
                            id: chip
                            required property var modelData
                            readonly property bool on: d.category === modelData.id
                            height: 52; width: Math.max(128, chipRow.implicitWidth + Theme.s3 * 2)
                            hoverEnabled: true
                            onClicked: d.category = modelData.id
                            background: Rectangle {
                                radius: Theme.radiusLg
                                color: chip.on ? Theme.accentSoft : chip.hovered ? Theme.hover : Theme.surface
                                border.width: chip.on ? 2 : 1; border.color: chip.on ? Theme.accent : Theme.border
                            }
                            contentItem: Item {
                                Row {
                                    id: chipRow
                                    anchors.verticalCenter: parent.verticalCenter; x: Theme.s3
                                    spacing: Theme.s2
                                    Rectangle {
                                        width: 30; height: 30; radius: 8; anchors.verticalCenter: parent.verticalCenter
                                        color: chip.on ? Theme.accent : Theme.surfaceAlt
                                        Text { anchors.centerIn: parent; text: chip.modelData.icon; font.pixelSize: 15
                                            color: chip.on ? Theme.onAccent : Theme.textMuted }
                                    }
                                    Column {
                                        anchors.verticalCenter: parent.verticalCenter
                                        Text { text: d.loc(chip.modelData.name); font.family: Theme.fontFamily; font.pixelSize: Theme.fsBase
                                            font.weight: Font.DemiBold; color: chip.on ? Theme.accent : Theme.text }
                                        Text { text: chip.modelData.count >= 0 ? chip.modelData.count : qsTr("Mẫu gợi ý")
                                            font.family: Theme.fontFamily; font.pixelSize: Theme.fsXs; color: Theme.textMuted }
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // ---- search
            RowLayout {
                Layout.fillWidth: true; Layout.margins: Theme.s4; Layout.topMargin: Theme.s2; Layout.bottomMargin: Theme.s3
                spacing: Theme.s2
                AppTextField {
                    id: search
                    Layout.fillWidth: true
                    placeholderText: qsTr("Tìm theo tên mẫu, kích thước, loại mã, mô tả…")
                    onTextChanged: { d.query = text.trim(); d.hits = d.query.length ? Gallery.search(d.query) : null }
                }
                Text { text: d.shown.length + " / " + Gallery.total; font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm; color: Theme.textMuted }
            }
            Separator { Layout.fillWidth: true }

            // ---- cards
            GridView {
                id: grid
                Layout.fillWidth: true; Layout.fillHeight: true
                clip: true
                leftMargin: Theme.s4; rightMargin: Theme.s4; topMargin: Theme.s4; bottomMargin: Theme.s4
                readonly property int cols: Math.max(1, Math.floor((width - Theme.s4 * 2) / 260))
                cellWidth: Math.floor((width - Theme.s4 * 2) / cols); cellHeight: 330
                model: d.shown
                boundsBehavior: Flickable.StopAtBounds
                C.ScrollBar.vertical: C.ScrollBar {}
                delegate: Item {
                    id: cell
                    required property var modelData
                    width: grid.cellWidth; height: grid.cellHeight
                    Rectangle {
                        id: card
                        anchors.fill: parent; anchors.margins: Theme.s2
                        radius: Theme.radiusLg; color: Theme.surface
                        border.width: 1; border.color: cardMa.containsMouse ? Theme.accent : Theme.border
                        MouseArea { id: cardMa; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: detail.openFor(cell.modelData) }
                        ColumnLayout {
                            anchors.fill: parent; anchors.margins: Theme.s3
                            spacing: Theme.s1
                            Rectangle {
                                Layout.fillWidth: true; Layout.preferredHeight: 150
                                radius: Theme.radiusMd; color: Theme.canvas
                                Image {
                                    anchors.fill: parent; anchors.margins: Theme.s3
                                    fillMode: Image.PreserveAspectFit; smooth: true; mipmap: true; cache: false
                                    source: Gallery.thumbs[cell.modelData.id] ? "image://preview/g_" + cell.modelData.id + "?v=" + Gallery.thumbs[cell.modelData.id] : ""
                                }
                                BusyIndicator2 { anchors.centerIn: parent; visible: !Gallery.thumbs[cell.modelData.id] }
                                Text { visible: cell.modelData.popular; text: "★"; anchors.right: parent.right; anchors.top: parent.top
                                    anchors.margins: Theme.s2; color: Theme.warning; font.pixelSize: 14 }
                            }
                            Text { text: d.loc(cell.modelData.name); Layout.fillWidth: true; Layout.topMargin: Theme.s1; elide: Text.ElideRight
                                font.family: Theme.fontFamily; font.pixelSize: Theme.fsMd; font.weight: Font.DemiBold; color: Theme.text }
                            Text { text: d.loc(cell.modelData.description); Layout.fillWidth: true; Layout.preferredHeight: 34
                                wrapMode: Text.Wrap; elide: Text.ElideRight; maximumLineCount: 2
                                font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm; color: Theme.textMuted }
                            Flow {
                                Layout.fillWidth: true; spacing: Theme.s1
                                Repeater {
                                    model: [cell.modelData.size].concat(cell.modelData.codes.length ? cell.modelData.codes : [qsTr("Không mã")])
                                    delegate: Rectangle {
                                        required property var modelData
                                        required property int index
                                        height: 20; width: tag.implicitWidth + 12; radius: 4
                                        color: index === 0 ? Theme.surfaceAlt : Theme.accentSoft
                                        border.width: 1; border.color: Theme.border
                                        Text { id: tag; anchors.centerIn: parent; text: parent.modelData
                                            font.family: Theme.fontFamily; font.pixelSize: Theme.fsXs; color: index === 0 ? Theme.textMuted : Theme.accent }
                                    }
                                }
                            }
                            Item { Layout.fillHeight: true }
                            AppButton { text: qsTr("Dùng mẫu"); Layout.fillWidth: true; kind: "secondary"
                                onClicked: d.use(cell.modelData.id) }
                        }
                    }
                }
                Text { visible: grid.count === 0; anchors.centerIn: parent; text: qsTr("Không có mẫu phù hợp.")
                    font.family: Theme.fontFamily; font.pixelSize: Theme.fsBase; color: Theme.textFaint }
            }
        }
    ]
    buttons: [ AppButton { text: qsTr("Đóng"); kind: "ghost"; onClicked: d.close() } ]

    function use(id) {
        var e = Gallery.useTemplate(id)
        if (e.length) App.errorRaised(qsTr("Mẫu có sẵn"), e)
        else { detail.close(); d.close() }
    }

    // ---- detail: large preview, sample data vs original template
    AppDialog {
        id: detail
        property var item: null
        property bool original: false
        function openFor(it) { item = it; original = false; Gallery.showPreview(it.id, true); open() }
        onOriginalChanged: if (item) Gallery.showPreview(item.id, !original)
        title: item ? d.loc(item.name) : ""
        subtitle: item ? item.size + "  ·  " + d.loc(item.description) : ""
        width: Math.min(d.width - 40, 900)
        height: Math.min(d.height - 20, 720)
        body: [
            RowLayout {
                Layout.fillWidth: true; Layout.fillHeight: true; spacing: Theme.s4
                Rectangle {
                    Layout.fillWidth: true; Layout.fillHeight: true; radius: Theme.radiusMd; color: Theme.canvas
                    Image { anchors.fill: parent; anchors.margins: Theme.s5; fillMode: Image.PreserveAspectFit; smooth: true; mipmap: true
                        cache: false; source: detail.item ? Gallery.previewSource : "" }
                }
                ColumnLayout {
                    Layout.preferredWidth: 240; Layout.fillHeight: true; spacing: Theme.s2
                    Row {
                        spacing: 0
                        AppButton { text: qsTr("Xem với dữ liệu mẫu"); compact: true; kind: detail.original ? "ghost" : "primary"; onClicked: detail.original = false }
                        AppButton { text: qsTr("Xem mẫu gốc"); compact: true; kind: detail.original ? "primary" : "ghost"; onClicked: detail.original = true }
                    }
                    Text { Layout.fillWidth: true; wrapMode: Text.Wrap; font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm; color: Theme.textMuted
                        text: detail.original ? qsTr("Mẫu gốc: các ô {{…}} được thay bằng dữ liệu của bạn khi in.") : qsTr("Dữ liệu mẫu chỉ để minh hoạ.") }
                    SectionHeader { text: qsTr("Các trường dữ liệu"); Layout.fillWidth: true; Layout.topMargin: Theme.s2 }
                    Flow {
                        Layout.fillWidth: true; spacing: Theme.s1
                        Repeater {
                            model: detail.item ? detail.item.fields : []
                            delegate: Rectangle {
                                required property var modelData
                                height: 22; width: ft.implicitWidth + 12; radius: 4; color: Theme.surfaceAlt; border.width: 1; border.color: Theme.border
                                Text { id: ft; anchors.centerIn: parent; text: "{{" + parent.modelData + "}}"; font.family: "Consolas"; font.pixelSize: Theme.fsXs; color: Theme.text }
                            }
                        }
                    }
                    Item { Layout.fillHeight: true }
                }
            }
        ]
        buttons: [
            AppButton { text: qsTr("Đóng"); kind: "ghost"; onClicked: detail.close() },
            AppButton { text: qsTr("Dùng mẫu này"); kind: "primary"; onClicked: d.use(detail.item.id) }
        ]
    }
}
