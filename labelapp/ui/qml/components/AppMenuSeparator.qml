import QtQuick
import QtQuick.Controls.Basic as C
import "../theme"

C.MenuSeparator {
    padding: 0; topPadding: 3; bottomPadding: 3
    contentItem: Rectangle { implicitHeight: 1; color: Theme.border }
}
