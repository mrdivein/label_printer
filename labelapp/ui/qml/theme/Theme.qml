pragma Singleton
import QtQuick

// Design tokens. One set of components; light/dark is only a different palette (Theme.dark).
//
// Colour roles — each colour means one thing everywhere, so it can be read at a glance:
//   blue   (accent)  = what you are editing: selection, focus, active tab, Save
//   green  (print)   = printing: the "In tem" button, printer status
//   violet (data)    = data from Excel / Google Sheet: {{fields}}, row navigator, data badge
//   amber  (warning) = unsaved changes, cautions
//   red    (danger)  = delete, "Không in"
// Everything else is neutral grey, with text kept at WCAG AA contrast or better.
QtObject {
    id: t
    property bool dark: false

    // ---- spacing (4 px grid) ----
    readonly property int s1: 4
    readonly property int s2: 8
    readonly property int s3: 12
    readonly property int s4: 16
    readonly property int s5: 24
    readonly property int s6: 32

    // ---- shape ----
    readonly property int radiusSm: 4
    readonly property int radiusMd: 6
    readonly property int radiusLg: 10
    readonly property int controlH: 32          // standard control height
    readonly property int controlHSm: 26
    readonly property int controlHLg: 40        // the main print button

    // ---- type ----
    readonly property string fontFamily: Qt.platform.os === "windows" ? "Segoe UI" : Qt.application.font.family
    readonly property int fsXs: 11
    readonly property int fsSm: 12
    readonly property int fsBase: 13
    readonly property int fsMd: 14
    readonly property int fsLg: 16
    readonly property int fsXl: 20

    // ---- motion ----
    readonly property int dFast: 120
    readonly property int dBase: 160

    // ---- neutrals ----
    readonly property color bg:          dark ? "#0e1116" : "#eef0f3"   // window chrome (bars, rail)
    readonly property color surface:     dark ? "#171b22" : "#ffffff"   // panels, fields
    readonly property color surfaceAlt:  dark ? "#1e232c" : "#f6f7f9"   // subtle fills, rail
    readonly property color canvas:      dark ? "#06080b" : "#cfd4dc"   // design workspace: darker so the white label stands out
    readonly property color border:      dark ? "#2c323d" : "#dde1e7"   // hairlines between areas
    readonly property color borderStrong:dark ? "#4b5463" : "#a7afbb"   // input outlines, outlined buttons
    readonly property color text:        dark ? "#f2f4f7" : "#0f172a"
    readonly property color textMuted:   dark ? "#c2c8d2" : "#3b4556"   // labels (≈ 9:1 on white)
    readonly property color textFaint:   dark ? "#8b94a3" : "#6a7383"   // hints, units (≈ 4.8:1 on white)
    readonly property color hover:       dark ? "#252b35" : "#e9ecf1"
    readonly property color pressed:     dark ? "#2f3642" : "#dce1e8"
    readonly property color disabledFg:  dark ? "#5a6475" : "#a3abb8"

    // ---- blue: editing / selection ----
    readonly property color accent:      dark ? "#6f9eff" : "#1d4ed8"
    readonly property color accentHover: dark ? "#8db2ff" : "#1e40af"
    readonly property color accentPressed:dark ? "#5585f0" : "#1e3a8a"
    readonly property color onAccent:    dark ? "#06122e" : "#ffffff"
    readonly property color accentSoft:  dark ? "#1b2a4d" : "#e3ebff"
    readonly property color selected:    dark ? "#1f3260" : "#dbe5ff"

    // ---- green: printing ----
    readonly property color printColor:      dark ? "#3fcf86" : "#15803d"
    readonly property color printHover:  dark ? "#5fdc9c" : "#166534"
    readonly property color printPressed:dark ? "#2fb873" : "#14532d"
    readonly property color onPrint:     dark ? "#04210f" : "#ffffff"
    readonly property color printSoft:   dark ? "#123524" : "#dcfce7"

    // ---- violet: data source ----
    readonly property color data:        dark ? "#b49bff" : "#6d28d9"
    readonly property color dataSoft:    dark ? "#2a2147" : "#ede9fe"

    // ---- status ----
    readonly property color danger:      dark ? "#ff8a80" : "#b91c1c"
    readonly property color dangerSoft:  dark ? "#3a1a1a" : "#fee2e2"
    readonly property color warning:     dark ? "#f5b54a" : "#b45309"
    readonly property color warningSoft: dark ? "#3a2a10" : "#fef3c7"
    readonly property color success:     dark ? "#3fcf86" : "#15803d"
    readonly property color shadow:      dark ? "#99000000" : "#33141c30"

    // design-surface overlay colours (also drawn on the paper, so they stay the same in both themes)
    readonly property color guideFold:   "#d97706"
    readonly property color guideArea:   "#15803d"
}
