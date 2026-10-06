pragma Singleton
import QtQuick

// Design tokens. One set of components; light/dark is only a different palette (Theme.dark).
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
    readonly property int controlH: 30          // standard control height
    readonly property int controlHSm: 24

    // ---- type ----
    readonly property string fontFamily: Qt.platform.os === "windows" ? "Segoe UI Variable Text, Segoe UI" : Qt.application.font.family
    readonly property int fsXs: 11
    readonly property int fsSm: 12
    readonly property int fsBase: 13
    readonly property int fsMd: 14
    readonly property int fsLg: 16
    readonly property int fsXl: 20

    // ---- motion ----
    readonly property int dFast: 120
    readonly property int dBase: 160

    // ---- palette ----
    readonly property color bg:          dark ? "#14171c" : "#f4f5f8"   // window
    readonly property color surface:     dark ? "#1b1f26" : "#ffffff"   // panels, fields
    readonly property color surfaceAlt:  dark ? "#222731" : "#f8f9fb"   // subtle fills
    readonly property color canvas:      dark ? "#0f1115" : "#e6e9ef"   // design workspace
    readonly property color border:      dark ? "#2b313c" : "#e0e4ea"
    readonly property color borderStrong:dark ? "#3a4250" : "#c8cfda"
    readonly property color text:        dark ? "#e8eaee" : "#1b2130"
    readonly property color textMuted:   dark ? "#9aa3b2" : "#5c6678"
    readonly property color textFaint:   dark ? "#6d7686" : "#8b94a5"
    readonly property color accent:      dark ? "#7b97ff" : "#2f5bea"
    readonly property color accentHover: dark ? "#93aaff" : "#2549c4"
    readonly property color accentPressed:dark ? "#6683f0" : "#1d3ba0"
    readonly property color onAccent:    dark ? "#0d1226" : "#ffffff"
    readonly property color accentSoft:  dark ? "#232c4d" : "#e8eeff"
    readonly property color hover:       dark ? "#262c37" : "#eef0f4"
    readonly property color pressed:     dark ? "#2e3541" : "#e2e6ed"
    readonly property color selected:    dark ? "#26335e" : "#e3eaff"
    readonly property color disabledFg:  dark ? "#566071" : "#aab1bf"
    readonly property color danger:      dark ? "#ff8a80" : "#c9372c"
    readonly property color warning:     dark ? "#f2b45a" : "#b86e00"
    readonly property color success:     dark ? "#5fd39a" : "#12805c"
    readonly property color shadow:      dark ? "#80000000" : "#26141c30"
    // design-surface overlay colours
    readonly property color guideFold:   "#e18200"
    readonly property color guideArea:   "#159447"
}
