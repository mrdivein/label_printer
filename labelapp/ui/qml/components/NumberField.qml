import QtQuick
import QtQuick.Controls.Basic as C
import "../theme"

// Numeric field with a unit suffix. Up/Down adjusts by `step` (Shift = x10). Commits on Enter / focus loss.
Item {
    id: n
    property real value: 0
    property bool mixed: false
    property string unit: ""
    property real step: 0.1
    property int decimals: 2
    property real from: -100000
    property real to: 100000
    signal edited(real v)
    implicitHeight: Theme.controlH
    implicitWidth: 96

    function fmt(v) { return Number(v).toFixed(decimals).replace(/\.?0+$/, "") === "" ? "0" : Number(v).toFixed(decimals).replace(/(\.\d*?)0+$/, "$1").replace(/\.$/, "") }
    function commit() {
        var t = input.text.replace(",", ".").trim()
        if (t === "") { input.text = mixed ? "" : fmt(value); return }
        var v = parseFloat(t)
        if (isNaN(v)) { input.text = mixed ? "" : fmt(value); return }
        v = Math.max(from, Math.min(to, v))
        edited(v)
        input.text = fmt(v)
    }
    onValueChanged: if (!input.activeFocus) input.text = mixed ? "" : fmt(value)
    onMixedChanged: if (!input.activeFocus) input.text = mixed ? "" : fmt(value)

    AppTextField {
        id: input
        anchors.fill: parent
        mixed: n.mixed
        rightPadding: unitText.visible ? unitText.implicitWidth + Theme.s3 : Theme.s2 + 2
        text: n.mixed ? "" : n.fmt(n.value)
        inputMethodHints: Qt.ImhFormattedNumbersOnly
        horizontalAlignment: TextInput.AlignLeft
        onEditingFinished: n.commit()
        Keys.onPressed: (e) => {
            if (e.key === Qt.Key_Up || e.key === Qt.Key_Down) {
                var s = n.step * ((e.modifiers & Qt.ShiftModifier) ? 10 : 1) * (e.key === Qt.Key_Up ? 1 : -1)
                var base = isNaN(parseFloat(text.replace(",", "."))) ? n.value : parseFloat(text.replace(",", "."))
                text = n.fmt(Math.round((base + s) * 1000) / 1000)
                n.commit()
                e.accepted = true
            }
        }
        Text {
            id: unitText
            visible: n.unit.length > 0
            anchors.right: parent.right; anchors.rightMargin: Theme.s2
            anchors.verticalCenter: parent.verticalCenter
            text: n.unit
            font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm
            color: Theme.textFaint
        }
    }
}
