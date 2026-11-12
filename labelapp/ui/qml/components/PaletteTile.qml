import QtQuick
import QtQuick.Controls.Basic as C
import "../theme"

// Square "click to add" tile of the insert palette: a small drawn icon (or a glyph) above a short label.
C.AbstractButton {
    id: b
    property string art: ""           // drawn icon key (barcode, qr, line, box, fill_box, ellipse, image, fold, area, field, body)
    property string glyph: ""         // or a text glyph instead of a drawn icon
    property url source: ""           // or a picture (symbol SVG), shown on a small white "label" chip
    property int glyphSize: 20
    property bool glyphBold: false
    property string tip: ""
    implicitWidth: 84; implicitHeight: 70
    hoverEnabled: true
    focusPolicy: Qt.TabFocus

    background: Rectangle {
        radius: Theme.radiusMd
        color: b.down ? Theme.pressed : b.hovered ? Theme.accentSoft : Theme.surface
        border.width: 1; border.color: b.hovered || b.visualFocus ? Theme.accent : Theme.border
        Behavior on color { ColorAnimation { duration: Theme.dFast } }
    }
    contentItem: Item {
        Item {
            id: artBox
            width: 40; height: 26
            anchors.horizontalCenter: parent.horizontalCenter; anchors.top: parent.top; anchors.topMargin: 10
            Rectangle {
                visible: b.source != ""
                anchors.centerIn: parent
                width: 34; height: 30; radius: Theme.radiusSm
                color: "#ffffff"; border.width: 1; border.color: Theme.border
                Image {
                    anchors.centerIn: parent
                    source: b.source
                    sourceSize: Qt.size(24, 24); width: 24; height: 24
                    fillMode: Image.PreserveAspectFit; smooth: true; mipmap: true
                    opacity: b.enabled ? 1 : 0.4
                }
            }
            Text {
                visible: b.glyph.length > 0
                anchors.centerIn: parent
                text: b.glyph
                font.family: Theme.fontFamily; font.pixelSize: b.glyphSize; font.weight: b.glyphBold ? Font.Bold : Font.Normal
                color: b.enabled ? Theme.text : Theme.disabledFg
            }
            Canvas {
                id: cv
                visible: b.glyph.length === 0 && b.source == ""
                anchors.fill: parent
                property color ink: b.enabled ? Theme.text : Theme.disabledFg
                property color acc: Theme.guideFold
                onInkChanged: requestPaint()
                Component.onCompleted: requestPaint()
                onPaint: {
                    var g = getContext("2d"); g.reset()
                    var w = width, h = height
                    g.strokeStyle = ink; g.fillStyle = ink; g.lineWidth = 1.6; g.lineCap = "round"
                    switch (b.art) {
                    case "barcode":
                        var bars = [2, 1, 1, 3, 1, 2, 1, 1, 2, 3, 1, 1, 2, 1, 3, 1]
                        var x = 4
                        for (var i = 0; i < bars.length && x < w - 4; i++) { if (i % 2 === 0) g.fillRect(x, 2, bars[i], h - 4); x += bars[i] + 1 }
                        break
                    case "qr":
                        var s = h - 2, ox = (w - s) / 2, m = s / 7
                        function finder(fx, fy) { g.fillRect(fx, fy, m * 3, m * 3); g.clearRect(fx + m * 0.6, fy + m * 0.6, m * 1.8, m * 1.8); g.fillRect(fx + m, fy + m, m, m) }
                        finder(ox, 1); finder(ox + m * 4, 1); finder(ox, 1 + m * 4)
                        g.fillRect(ox + m * 4.5, 1 + m * 4.5, m, m); g.fillRect(ox + m * 6, 1 + m * 5.5, m, m); g.fillRect(ox + m * 5, 1 + m * 6, m, m)
                        break
                    case "line":
                        g.beginPath(); g.moveTo(4, h / 2); g.lineTo(w - 4, h / 2); g.stroke(); break
                    case "box":
                        g.strokeRect(6, 4, w - 12, h - 8); break
                    case "fill_box":
                        g.fillRect(6, 4, w - 12, h - 8); break
                    case "ellipse":
                        g.beginPath(); g.ellipse(6, 3, w - 12, h - 6); g.stroke(); break
                    case "image":
                        g.strokeRect(6, 2, w - 12, h - 4)
                        g.beginPath(); g.moveTo(8, h - 5); g.lineTo(17, 11); g.lineTo(23, 17); g.lineTo(27, 13); g.lineTo(w - 8, h - 5); g.stroke()
                        g.beginPath(); g.arc(w - 13, 8, 2.5, 0, Math.PI * 2); g.fill(); break
                    case "fold":
                        g.strokeRect(8, 1, w - 16, h - 2)
                        g.strokeStyle = acc; g.lineWidth = 2; g.setLineDash([3, 2])
                        g.beginPath(); g.moveTo(3, h / 2); g.lineTo(w - 3, h / 2); g.stroke(); break
                    case "area":
                        g.setLineDash([3, 2]); g.strokeStyle = Theme.guideArea; g.strokeRect(5, 2, w - 10, h - 4); break
                    case "field":
                        g.font = "600 15px sans-serif"; g.fillText("{ }", 8, h / 2 + 5); break
                    case "body":
                        for (var r = 0; r < 4; r++) g.fillRect(4, 3 + r * 6, r === 3 ? w * 0.5 : w - 8, 2.2)
                        break
                    }
                }
            }
        }
        Text {
            anchors.top: artBox.bottom; anchors.topMargin: 6
            anchors.left: parent.left; anchors.right: parent.right; anchors.leftMargin: 4; anchors.rightMargin: 4
            text: b.text
            horizontalAlignment: Text.AlignHCenter; elide: Text.ElideRight
            font.family: Theme.fontFamily; font.pixelSize: Theme.fsXs; font.weight: Font.Medium
            color: b.enabled ? Theme.textMuted : Theme.disabledFg
        }
    }
    C.ToolTip.visible: hovered && tip.length > 0
    C.ToolTip.text: tip
    C.ToolTip.delay: 600
}
