import QtQuick
import "../theme"

// Flat panel surface with a hairline border on the sides facing the canvas.
Rectangle {
    id: p
    property bool borderLeft: false
    property bool borderRight: false
    property bool borderTop: false
    property bool borderBottom: false
    color: Theme.surface
    Rectangle { visible: p.borderLeft;   width: 1; height: parent.height; color: Theme.border; anchors.left: parent.left }
    Rectangle { visible: p.borderRight;  width: 1; height: parent.height; color: Theme.border; anchors.right: parent.right }
    Rectangle { visible: p.borderTop;    height: 1; width: parent.width; color: Theme.border; anchors.top: parent.top }
    Rectangle { visible: p.borderBottom; height: 1; width: parent.width; color: Theme.border; anchors.bottom: parent.bottom }
}
