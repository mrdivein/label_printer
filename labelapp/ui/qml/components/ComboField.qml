import QtQuick
import QtQuick.Controls.Basic as C
import "../theme"

C.ComboBox {
    id: c
    property bool mixed: false
    implicitHeight: Theme.controlH
    hoverEnabled: true
    font.family: Theme.fontFamily; font.pixelSize: Theme.fsBase
    leftPadding: Theme.s2 + 2; rightPadding: 28; topPadding: 0; bottomPadding: 0

    background: Rectangle {
        radius: Theme.radiusMd
        color: c.enabled ? Theme.surface : Theme.surfaceAlt
        border.width: 1
        border.color: c.visualFocus || c.popup.visible ? Theme.accent : c.hovered ? Theme.borderStrong : Theme.border
        Behavior on border.color { ColorAnimation { duration: Theme.dFast } }
    }
    contentItem: Text {
        leftPadding: 0
        text: c.mixed ? qsTr("Nhiều giá trị") : c.displayText
        font: c.font
        color: c.mixed ? Theme.textFaint : (c.enabled ? Theme.text : Theme.disabledFg)
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
    indicator: Canvas {
        x: c.width - width - Theme.s2; y: (c.height - height) / 2; width: 10; height: 6
        property color col: Theme.textMuted
        onColChanged: requestPaint()
        onPaint: { var g = getContext("2d"); g.reset(); g.strokeStyle = col; g.lineWidth = 1.5; g.lineCap = "round"; g.lineJoin = "round"
            g.beginPath(); g.moveTo(1, 1); g.lineTo(5, 5); g.lineTo(9, 1); g.stroke() }
    }
    delegate: C.ItemDelegate {
        id: d
        width: c.width
        height: 30
        leftPadding: Theme.s3; rightPadding: Theme.s3
        highlighted: c.highlightedIndex === index
        contentItem: Text {
            text: c.textRole ? (Array.isArray(c.model) ? modelData[c.textRole] : model[c.textRole]) : modelData
            font: c.font; elide: Text.ElideRight; verticalAlignment: Text.AlignVCenter
            color: Theme.text
        }
        background: Rectangle { color: d.highlighted ? Theme.hover : "transparent"; radius: Theme.radiusSm
            anchors.fill: parent; anchors.margins: 2 }
    }
    popup: C.Popup {
        y: c.height + 2; width: c.width; padding: 2
        implicitHeight: Math.min(contentItem.implicitHeight + 4, 260)
        contentItem: ListView {
            clip: true
            implicitHeight: contentHeight
            model: c.popup.visible ? c.delegateModel : null
            currentIndex: c.highlightedIndex
            C.ScrollIndicator.vertical: C.ScrollIndicator {}
        }
        background: Rectangle { radius: Theme.radiusMd; color: Theme.surface; border.width: 1; border.color: Theme.borderStrong }
    }
}
