import QtQuick
import "../theme"

// Small, calm activity indicator (no animation unless visible).
Item {
    implicitWidth: 16; implicitHeight: 16
    Rectangle {
        anchors.fill: parent; radius: width / 2; color: "transparent"
        border.width: 2; border.color: Theme.border
    }
    Canvas {
        id: arc
        anchors.fill: parent
        rotation: 0
        onPaint: { var g = getContext("2d"); g.reset(); g.strokeStyle = Theme.accent; g.lineWidth = 2; g.lineCap = "round"
            g.beginPath(); g.arc(8, 8, 6.5, 0, Math.PI * 0.6); g.stroke() }
        RotationAnimator on rotation { running: arc.visible && arc.parent.visible; from: 0; to: 360; duration: 900; loops: Animation.Infinite }
    }
}
