import QtQuick
import QtQuick.Controls.Basic as C
import "../theme"
import "../components"

// The design surface. All coordinates sent to Python are label millimetres, so zoom/pan never touch the document.
//   screen = pan + mm * pxPerMm          (1.0 zoom == real physical size at 96 dpi)
Item {
    id: view
    clip: true
    activeFocusOnTab: true
    Keys.onPressed: (e) => { if (e.key === Qt.Key_Space && !e.isAutoRepeat) { spaceDown = true; e.accepted = true } }
    Keys.onReleased: (e) => { if (e.key === Qt.Key_Space && !e.isAutoRepeat) { spaceDown = false; e.accepted = true } }

    property real zoom: 1.0
    readonly property real pxPerMm: zoom * 96 / 25.4
    property real panX: 0
    property real panY: 0
    property bool spaceDown: false
    property bool showBounds: false
    property bool showRulers: true
    // View-only rotation (0/90/180/270) to preview the label the way it sits on the physical tag. Never touches the
    // document or the print output. Rulers are in unrotated label mm, so they are hidden while rotated.
    property int viewRotation: 0
    readonly property bool rotated: viewRotation !== 0
    readonly property real rulerSize: (showRulers && !rotated) ? 20 : 0
    readonly property bool quarterTurn: viewRotation === 90 || viewRotation === 270
    readonly property var ws: Doc.workspaceRect
    readonly property var paper: Doc.paperRect
    readonly property var ov: Doc.overlay
    property int hoverIndex: -1
    property string hoverRole: ""
    property string dragMode: ""
    property point pressMm: Qt.point(0, 0)
    property point cursorMm: Qt.point(0, 0)

    signal editTextRequested(int index)

    function toScreenX(mm) { return panX + mm * pxPerMm }
    function toScreenY(mm) { return panY + mm * pxPerMm }
    function toMmX(px) { return (px - panX) / pxPerMm }
    function toMmY(px) { return (px - panY) / pxPerMm }

    function paperCenterScreen() {
        var p = view.paper
        return Qt.point(toScreenX(p.x + p.w / 2), toScreenY(p.y + p.h / 2))
    }
    // Overlay canvases are drawn in unrotated screen space (rotating the canvas item itself stops it covering the view
    // once the paper is panned), so the review rotation is applied to points while painting.
    function rotPt(sx, sy) {
        if (viewRotation === 0) return [sx, sy]
        var c = paperCenterScreen(), a = viewRotation * Math.PI / 180, ca = Math.cos(a), sa = Math.sin(a)
        var dx = sx - c.x, dy = sy - c.y
        return [c.x + dx * ca - dy * sa, c.y + dx * sa + dy * ca]
    }
    function rectPath(g, x, y, w, h) {
        var s = pxPerMm, pts = [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]
        g.beginPath()
        for (var k = 0; k < 4; k++) { var q = rotPt(panX + pts[k][0] * s, panY + pts[k][1] * s); if (k === 0) g.moveTo(q[0], q[1]); else g.lineTo(q[0], q[1]) }
        g.closePath()
    }
    function rotateView() { viewRotation = (viewRotation + 90) % 360; Qt.callLater(fit) }
    // screen (view coords) -> label mm, honouring the view rotation
    function viewToMm(vx, vy) {
        var q = content.mapFromItem(view, vx, vy)
        return Qt.point(toMmX(q.x), toMmY(q.y))
    }

    function setZoomAt(z, sx, sy) {
        autoFit = false
        z = Math.max(0.1, Math.min(16, z))
        if (rotated) { var c = paperCenterScreen(); sx = c.x; sy = c.y }   // keep the rotation pivot fixed
        var mx = toMmX(sx), my = toMmY(sy)
        zoom = z
        panX = sx - mx * pxPerMm
        panY = sy - my * pxPerMm
    }
    function zoomBy(f) { setZoomAt(zoom * f, (width + rulerSize) / 2, (height + rulerSize) / 2) }
    function fit() {
        var p = Doc.paperRect
        // Free area: 40 px around the label, plus the floating zoom bar's height kept clear at the bottom.
        var padTop = 40, padBottom = 40 + viewControls.height
        var aw = width - rulerSize - 80, ah = height - rulerSize - padTop - padBottom
        if (aw < 50 || ah < 50 || p.w <= 0 || p.h <= 0) return
        var pw = quarterTurn ? p.h : p.w, ph = quarterTurn ? p.w : p.h
        var z = Math.min(aw / pw, ah / ph) / (96 / 25.4)
        zoom = Math.max(0.1, Math.min(16, z))
        panX = rulerSize + (width - rulerSize - p.w * pxPerMm) / 2 - p.x * pxPerMm
        panY = rulerSize + padTop + (ah - p.h * pxPerMm) / 2 - p.y * pxPerMm
        autoFit = true
    }
    function actualSize() { setZoomAt(1.0, (width + rulerSize) / 2, (height + rulerSize) / 2) }

    onPxPerMmChanged: { Doc.setViewScale(pxPerMm); Qt.callLater(updateSelBox) }
    // The label stays fitted to the view (window resize, panel changes, first layout) until the user zooms or pans;
    // "Fit" / Ctrl+0 turns this back on. Width and height arrive separately at start-up, so both re-arm the fit.
    property bool autoFit: true
    onWidthChanged: if (autoFit) fitTimer.restart()
    onHeightChanged: if (autoFit) fitTimer.restart()
    onRulerSizeChanged: if (autoFit) fitTimer.restart()
    Connections { target: Doc; function onDocChanged() { if (view.autoFit) fitTimer.restart() } }   // paper size edits
    Connections { target: Doc; function onTemplateLoaded() { Qt.callLater(view.fit) } }
    Timer { id: fitTimer; interval: 0; onTriggered: view.fit() }

    Rectangle { anchors.fill: parent; color: Theme.canvas }

    Item {
    id: content
    anchors.fill: parent
    transform: Rotation {
        angle: view.viewRotation
        origin.x: view.toScreenX(view.paper.x + view.paper.w / 2)
        origin.y: view.toScreenY(view.paper.y + view.paper.h / 2)
    }

    // ---- paper shadow + rendered label (physical position) ----
    Rectangle {
        x: view.toScreenX(view.paper.x) - 1; y: view.toScreenY(view.paper.y) + 2
        width: view.paper.w * view.pxPerMm + 2; height: view.paper.h * view.pxPerMm
        color: Theme.shadow; radius: 1
    }
    Rectangle {                     // the physical paper; the render below is transparent where it is blank
        x: view.toScreenX(view.paper.x); y: view.toScreenY(view.paper.y)
        width: view.paper.w * view.pxPerMm; height: view.paper.h * view.pxPerMm
        color: "#ffffff"
    }
    Image {
        id: preview
        x: view.toScreenX(view.ws.x); y: view.toScreenY(view.ws.y)
        width: view.ws.w * view.pxPerMm; height: view.ws.h * view.pxPerMm
        source: Doc.previewSource
        smooth: true; mipmap: true; cache: false
        fillMode: Image.Stretch
    }

    }   // content

    // ---- overlay: element bounds, selection, handles, print area, fold ----
    Canvas {
        id: overlayCanvas
        anchors.fill: parent
        renderStrategy: Canvas.Cooperative   // Threaded could drop repaint requests after many drag/rotate updates -> frame vanished
        onAvailableChanged: if (available) requestPaint()
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        Connections { target: Doc; function onOverlayChanged() { overlayCanvas.requestPaint() } function onGhostChanged() { overlayCanvas.requestPaint() } }
        property var theme: Theme.dark
        onThemeChanged: requestPaint()
        Connections { target: view; function onPanXChanged() { overlayCanvas.requestPaint() } function onPanYChanged() { overlayCanvas.requestPaint() }
            function onPxPerMmChanged() { overlayCanvas.requestPaint() } function onOvChanged() { overlayCanvas.requestPaint() }
            function onHoverIndexChanged() { overlayCanvas.requestPaint() } function onShowBoundsChanged() { overlayCanvas.requestPaint() }
            function onViewRotationChanged() { overlayCanvas.requestPaint() } function onWidthChanged() { overlayCanvas.requestPaint() } function onHeightChanged() { overlayCanvas.requestPaint() } }
        onPaint: {
            var g = getContext("2d")
            g.reset()
            var o = view.ov
            if (!o || !o.elements) return
            var s = view.pxPerMm
            function P(p) { return view.rotPt(view.panX + p[0] * s, view.panY + p[1] * s) }
            function poly(pts) { g.beginPath(); for (var k = 0; k < pts.length; k++) { var q = P(pts[k]); if (k === 0) g.moveTo(q[0], q[1]); else g.lineTo(q[0], q[1]) } g.closePath() }
            var acc = Theme.accent
            // paper outline-less: bounds
            for (var i = 0; i < o.elements.length; i++) {
                var e = o.elements[i]
                if (e.selected) continue
                var hov = (i === view.hoverIndex)
                if (!view.showBounds && !hov) continue
                poly(e.poly)
                g.lineWidth = 1
                g.strokeStyle = hov ? Qt.alpha(acc, 0.9) : Qt.alpha(acc, 0.28)
                if (e.locked) g.strokeStyle = hov ? Qt.alpha(Theme.textMuted, 0.9) : Qt.alpha(Theme.textMuted, 0.3)
                g.setLineDash(hov ? [] : [3, 3])
                g.stroke()
            }
            g.setLineDash([])
            // virtual print area
            if (o.virtual) {
                var v = o.virtual, a = P([v.x, v.y]), b = P([v.x + v.w, v.y + v.h])
                g.strokeStyle = Theme.guideArea; g.lineWidth = 1.5; g.setLineDash([6, 4])
                view.rectPath(g, v.x, v.y, v.w, v.h); g.stroke(); g.setLineDash([])
                g.fillStyle = Theme.guideArea; g.font = "600 10px sans-serif"
                var pa = P([v.x + v.w, v.y]); g.fillText("VÙNG IN", pa[0] - g.measureText("VÙNG IN").width - 4, pa[1] - 5)
                for (var h = 0; h < v.handles.length; h++) {
                    var hp = P([v.handles[h].x, v.handles[h].y])
                    g.fillStyle = Theme.surface; g.strokeStyle = Theme.guideArea; g.lineWidth = 1.5
                    g.fillRect(hp[0] - 4, hp[1] - 4, 8, 8); g.strokeRect(hp[0] - 4, hp[1] - 4, 8, 8)
                }
            }
            // fold line
            if (o.fold) {
                var f1 = P([o.fold.x1, o.fold.y]), f2 = P([o.fold.x2, o.fold.y])
                g.strokeStyle = Theme.guideFold; g.lineWidth = 2.5
                g.beginPath(); g.moveTo(f1[0], f1[1]); g.lineTo(f2[0], f2[1]); g.stroke()
                g.fillStyle = Theme.surface; g.fillRect(f1[0] - 6, f1[1] - 6, 12, 12); g.strokeRect(f1[0] - 6, f1[1] - 6, 12, 12)
                g.fillStyle = Theme.guideFold; g.font = "600 10px sans-serif"; g.fillText("GẬP", f1[0] + 12, f1[1] - 6)
            }
            // selection
            var nSel = 0
            for (var q = 0; q < o.elements.length; q++) if (o.elements[q].selected) nSel++
            for (var j = 0; j < o.elements.length; j++) {
                var se = o.elements[j]
                if (!se.selected) continue
                poly(se.poly)
                g.lineWidth = 2; g.strokeStyle = se.locked ? Theme.textMuted : acc; g.setLineDash([])
                g.fillStyle = Qt.alpha(se.locked ? Theme.textMuted : acc, 0.06); g.fill(); g.stroke()
                if (nSel <= 3) {
                    var lp = P(se.poly[0]); g.fillStyle = se.locked ? Theme.textMuted : acc
                    g.font = "600 10px sans-serif"
                    g.fillText((j + 1) + " " + Doc.typeLabel(se.type) + (se.locked ? "  (đã khoá)" : ""), lp[0] + 1, lp[1] - 6)
                }
            }
            // handles
            var hs = o.handles || []
            for (var k = 0; k < hs.length; k++) {
                var hd = hs[k], p = P([hd.x, hd.y])
                if (hd.role === "rotate") {
                    var ep = P([hd.edge_x, hd.edge_y])
                    g.strokeStyle = acc; g.lineWidth = 1.5; g.beginPath(); g.moveTo(ep[0], ep[1]); g.lineTo(p[0], p[1]); g.stroke()
                    g.beginPath(); g.arc(p[0], p[1], 8, 0, Math.PI * 2); g.fillStyle = Theme.surface; g.fill(); g.lineWidth = 1.5; g.stroke()
                    g.beginPath(); g.arc(p[0], p[1], 3.5, 0.6, Math.PI * 1.9); g.stroke()
                } else {
                    g.fillStyle = Theme.surface; g.strokeStyle = acc; g.lineWidth = 1.5
                    g.fillRect(p[0] - 5, p[1] - 5, 10, 10); g.strokeRect(p[0] - 5, p[1] - 5, 10, 10)
                }
            }
        }
    }

    // ---- ghost: tentative result while dragging ----
    Canvas {
        id: ghostCanvas
        anchors.fill: parent
        renderStrategy: Canvas.Cooperative
        Connections { target: Doc; function onGhostChanged() { ghostCanvas.requestPaint() } }
        Connections { target: view; function onPanXChanged() { ghostCanvas.requestPaint() } function onPanYChanged() { ghostCanvas.requestPaint() } function onPxPerMmChanged() { ghostCanvas.requestPaint() } function onViewRotationChanged() { ghostCanvas.requestPaint() } }
        onPaint: {
            var g = getContext("2d"); g.reset()
            var gh = Doc.ghost
            if (!gh || !gh.mode) return
            var s = view.pxPerMm
            function P(x, y) { return view.rotPt(view.panX + x * s, view.panY + y * s) }
            g.setLineDash([4, 3]); g.lineWidth = 1.5; g.strokeStyle = Theme.accent; g.fillStyle = Qt.alpha(Theme.accent, 0.08)
            var label = gh.text || ""
            var lx = 0, ly = 0
            if (gh.mode === "marquee") {
                view.rectPath(g, gh.rect[0], gh.rect[1], gh.rect[2] - gh.rect[0], gh.rect[3] - gh.rect[1]); g.fill(); g.stroke()
                return
            }
            if (gh.polys) {
                for (var i = 0; i < gh.polys.length; i++) {
                    var pts = gh.polys[i]; g.beginPath()
                    for (var k = 0; k < pts.length; k++) { var q = P(pts[k][0], pts[k][1]); if (k === 0) g.moveTo(q[0], q[1]); else g.lineTo(q[0], q[1]) }
                    g.closePath(); g.fill(); g.stroke()
                    if (i === 0) { var q0 = P(pts[0][0], pts[0][1]); lx = q0[0]; ly = q0[1] }
                }
            }
            if (gh.area) { var a1 = P(gh.area[0], gh.area[1])
                g.strokeStyle = Theme.guideArea; view.rectPath(g, gh.area[0], gh.area[1], gh.area[2], gh.area[3]); g.stroke(); lx = a1[0]; ly = a1[1] }
            if (gh.fold_y !== undefined) { var o = Doc.overlay.fold; if (o) { var f1 = P(o.x1, gh.fold_y), f2 = P(o.x2, gh.fold_y)
                g.strokeStyle = Theme.guideFold; g.lineWidth = 2; g.beginPath(); g.moveTo(f1[0], f1[1]); g.lineTo(f2[0], f2[1]); g.stroke(); lx = f1[0]; ly = f1[1] } }
            if (label.length) {
                g.setLineDash([]); g.font = "600 11px sans-serif"
                var w = g.measureText(label).width + 12
                g.fillStyle = Theme.text; g.fillRect(lx, ly - 24, w, 18)
                g.fillStyle = Theme.surface; g.fillText(label, lx + 6, ly - 11)
            }
        }
    }


    // ---- rulers (millimetres) ----
    Canvas {
        id: rulers
        anchors.fill: parent
        visible: view.showRulers && !view.rotated
        renderStrategy: Canvas.Threaded
        Connections { target: view; function onPanXChanged() { rulers.requestPaint() } function onPanYChanged() { rulers.requestPaint() }
            function onPxPerMmChanged() { rulers.requestPaint() } function onWidthChanged() { rulers.requestPaint() } function onHeightChanged() { rulers.requestPaint() }
            function onCursorMmChanged() { rulers.requestPaint() } }
        property bool dk: Theme.dark
        onDkChanged: requestPaint()
        onPaint: {
            var g = getContext("2d"); g.reset()
            var R = view.rulerSize, s = view.pxPerMm
            g.fillStyle = Theme.surface; g.fillRect(0, 0, width, R); g.fillRect(0, 0, R, height)
            g.strokeStyle = Theme.border; g.lineWidth = 1
            g.beginPath(); g.moveTo(0, R + 0.5); g.lineTo(width, R + 0.5); g.moveTo(R + 0.5, 0); g.lineTo(R + 0.5, height); g.stroke()
            var step = 1
            var steps = [1, 2, 5, 10, 20, 50, 100]
            for (var q = 0; q < steps.length; q++) { step = steps[q]; if (step * s >= 7) break }
            var label = step
            for (var q2 = 0; q2 < steps.length; q2++) { label = steps[q2]; if (label * s >= 46) break }
            g.fillStyle = Theme.textMuted; g.strokeStyle = Theme.borderStrong; g.font = "10px sans-serif"
            var x0 = Math.floor(view.toMmX(R) / step) * step, x1 = view.toMmX(width)
            for (var m = x0; m <= x1; m += step) {
                var sx = Math.round(view.toScreenX(m)) + 0.5
                if (sx < R) continue
                var major = Math.abs(m % label) < 1e-6
                g.beginPath(); g.moveTo(sx, R); g.lineTo(sx, major ? R - 9 : R - 4); g.stroke()
                if (major) g.fillText(String(Math.round(m * 100) / 100), sx + 3, R - 9)
            }
            var y0 = Math.floor(view.toMmY(R) / step) * step, y1 = view.toMmY(height)
            for (var n = y0; n <= y1; n += step) {
                var sy = Math.round(view.toScreenY(n)) + 0.5
                if (sy < R) continue
                var majorY = Math.abs(n % label) < 1e-6
                g.beginPath(); g.moveTo(R, sy); g.lineTo(majorY ? R - 9 : R - 4, sy); g.stroke()
                if (majorY) { g.save(); g.translate(R - 10, sy + 3); g.rotate(-Math.PI / 2); g.fillText(String(Math.round(n * 100) / 100), 0, 0); g.restore() }
            }
            // cursor tracker
            g.strokeStyle = Theme.accent; g.lineWidth = 1
            var cx = view.toScreenX(view.cursorMm.x), cy = view.toScreenY(view.cursorMm.y)
            if (cx > R) { g.beginPath(); g.moveTo(cx + 0.5, 0); g.lineTo(cx + 0.5, R); g.stroke() }
            if (cy > R) { g.beginPath(); g.moveTo(0, cy + 0.5); g.lineTo(R, cy + 0.5); g.stroke() }
            g.fillStyle = Theme.surface; g.fillRect(0, 0, R, R)
            g.fillStyle = Theme.textFaint; g.fillText("mm", 3, R - 6)
        }
    }

    // ---- pointer ----
    MouseArea {
        id: pointer
        anchors.fill: parent
        anchors.topMargin: view.rulerSize; anchors.leftMargin: view.rulerSize
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton | Qt.MiddleButton
        property bool panning: false
        property point panStart
        property point panOrigin
        cursorShape: {
            if (panning || view.spaceDown) return panning ? Qt.ClosedHandCursor : Qt.OpenHandCursor
            var m = view.dragMode, r = view.hoverRole
            if (m === "move") return Qt.SizeAllCursor
            if (m === "element_rotate") return Qt.CrossCursor
            if (m === "fold_move") return Qt.SizeVerCursor
            if (m === "element_resize" || m === "virtual_resize") return Qt.SizeFDiagCursor
            if (m === "marquee") return Qt.CrossCursor
            if (r === "rotate") return Qt.CrossCursor
            if (r.indexOf("resize:") === 0) { var k = r.substring(7); return (k === "ne" || k === "sw") ? Qt.SizeBDiagCursor : Qt.SizeFDiagCursor }
            if (r === "fold") return Qt.SizeVerCursor
            if (r === "move" || r === "virtual") return Qt.SizeAllCursor
            if (r === "locked") return Qt.ForbiddenCursor
            return Qt.ArrowCursor
        }
        function mm(mouse) { return view.viewToMm(mouse.x + view.rulerSize, mouse.y + view.rulerSize) }

        Timer { id: hoverThrottle; interval: 30; property point at; onTriggered: {
                var h = Doc.hover(at.x, at.y); view.hoverIndex = h.element; view.hoverRole = h.role } }

        onPressed: (mouse) => {
            forceActiveFocus()
            if (mouse.button === Qt.MiddleButton || view.spaceDown) {
                panning = true; panStart = Qt.point(mouse.x, mouse.y); panOrigin = Qt.point(view.panX, view.panY); return
            }
            var p = mm(mouse)
            view.pressMm = p
            view.dragMode = Doc.pointerPress(p.x, p.y, (mouse.modifiers & Qt.ShiftModifier) !== 0)
        }
        onPositionChanged: (mouse) => {
            var p = mm(mouse)
            view.cursorMm = p
            if (panning) { view.autoFit = false; view.panX = panOrigin.x + mouse.x - panStart.x; view.panY = panOrigin.y + mouse.y - panStart.y; return }
            if (pressed && view.dragMode.length && view.dragMode !== "select" && view.dragMode !== "none")
                Doc.pointerMove(p.x, p.y, (mouse.modifiers & Qt.ShiftModifier) !== 0)
            else if (!pressed) { hoverThrottle.at = p; if (!hoverThrottle.running) hoverThrottle.start() }
        }
        onReleased: (mouse) => {
            if (panning) { panning = false; return }
            var p = mm(mouse)
            Doc.pointerRelease(p.x, p.y, (mouse.modifiers & Qt.ShiftModifier) !== 0)
            view.dragMode = ""
        }
        onCanceled: { panning = false; Doc.pointerCancel(); view.dragMode = "" }
        onExited: { view.hoverIndex = -1; view.hoverRole = "" }
        onDoubleClicked: (mouse) => {
            var p = mm(mouse)
            var i = Doc.hitElement(p.x, p.y)
            if (i >= 0 && Doc.elementType(i) === "text") view.editTextRequested(i)
        }
        onWheel: (wheel) => {
            if (wheel.modifiers & Qt.ControlModifier) {
                view.setZoomAt(view.zoom * Math.pow(1.0015, wheel.angleDelta.y), wheel.x + view.rulerSize, wheel.y + view.rulerSize)
            } else if (wheel.modifiers & Qt.ShiftModifier) {
                view.autoFit = false
                view.panX += wheel.angleDelta.y !== 0 ? wheel.angleDelta.y : wheel.angleDelta.x
            } else {
                view.autoFit = false
                view.panY += wheel.angleDelta.y
                view.panX += wheel.angleDelta.x
            }
            wheel.accepted = true
        }
    }

    // ---- floating context toolbar over the selection ----
    // Screen box of the selection (rotation aware). Recomputed after overlay / pan / zoom changes settle, not as a
    // binding: overlay updates arrive re-entrantly from Python while the view is still evaluating.
    property var selBox: null
    function updateSelBox() {
        var o = view.ov, s = view.pxPerMm
        if (!o || !o.elements || Doc.selectionCount === 0) { selBox = null; return }
        var x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9, n = 0
        for (var i = 0; i < o.elements.length; i++) {
            var e = o.elements[i]
            if (!e.selected) continue
            for (var k = 0; k < e.poly.length; k++) {
                var q = view.rotPt(view.panX + e.poly[k][0] * s, view.panY + e.poly[k][1] * s)
                x0 = Math.min(x0, q[0]); y0 = Math.min(y0, q[1]); x1 = Math.max(x1, q[0]); y1 = Math.max(y1, q[1]); n++
            }
        }
        selBox = n ? { x: x0, y: y0, w: x1 - x0, h: y1 - y0 } : null
    }
    onOvChanged: Qt.callLater(updateSelBox)
    onPanXChanged: Qt.callLater(updateSelBox)
    onPanYChanged: Qt.callLater(updateSelBox)
    onViewRotationChanged: Qt.callLater(updateSelBox)
    Connections { target: Doc; function onSelectionChanged() { Qt.callLater(view.updateSelBox) } }
    readonly property int selFirst: Doc.selectionCount > 0 ? Doc.selection[0] : -1
    readonly property bool selText: Doc.selectionCount === 1 && Doc.elementType(selFirst) === "text"

    Rectangle {
        id: ctxBar
        objectName: "ctxBar"
        visible: view.selBox !== null && view.dragMode === "" && !pointer.panning
        readonly property real gap: 40                      // clears the rotate knob above the selection
        x: view.selBox ? Math.max(view.rulerSize + 4, Math.min(view.width - width - 4, view.selBox.x + view.selBox.w / 2 - width / 2)) : 0
        y: {
            if (!view.selBox) return 0
            var above = view.selBox.y - height - gap
            if (above >= view.rulerSize + 4) return above
            return Math.min(view.height - height - viewControls.height - Theme.s5, view.selBox.y + view.selBox.h + 14)
        }
        width: ctxRow.implicitWidth + Theme.s1 * 2; height: 38; radius: Theme.radiusLg
        color: Theme.surface; border.width: 1; border.color: Theme.border
        Rectangle { z: -1; anchors.fill: parent; anchors.topMargin: 3; anchors.bottomMargin: -3; radius: parent.radius; color: Theme.shadow; opacity: 0.6 }
        Row {
            id: ctxRow
            anchors.centerIn: parent; spacing: 1
            IconButton { visible: view.selText; text: "✎"; tip: "Sửa chữ (nhấp đúp)"; onClicked: view.editTextRequested(view.selFirst) }
            IconButton { visible: view.selText; text: "A−"; tip: "Giảm cỡ chữ 1 pt"; onClicked: Doc.changeFontSize(-5) }
            IconButton { visible: view.selText; text: "A+"; tip: "Tăng cỡ chữ 1 pt"; onClicked: Doc.changeFontSize(5) }
            IconButton { visible: view.selText; text: "B"; font.bold: true; tip: "In đậm"
                active: { var dep = view.ov; return view.selText && Doc.elementBold(view.selFirst) }   // overlay changes on every commit
                onClicked: Doc.setProp("bold", !Doc.elementBold(view.selFirst)) }
            Separator { visible: view.selText; vertical: true; anchors.verticalCenter: parent.verticalCenter }
            AppButton { visible: Doc.canGroup; text: "Nhóm"; compact: true; anchors.verticalCenter: parent.verticalCenter; onClicked: Doc.groupSelected()
                C.ToolTip.visible: hovered; C.ToolTip.text: "Nhóm các phần tử đang chọn (Ctrl+G)"; C.ToolTip.delay: 500 }
            AppButton { visible: Doc.canUngroup; text: "Bỏ nhóm"; compact: true; anchors.verticalCenter: parent.verticalCenter; onClicked: Doc.ungroupSelected()
                C.ToolTip.visible: hovered; C.ToolTip.text: "Bỏ nhóm (Ctrl+Shift+G)"; C.ToolTip.delay: 500 }
            IconButton { text: "⧉"; tip: "Nhân bản (Ctrl+D)"; onClicked: Doc.duplicateSelected() }
            IconButton { text: "↺"; tip: Doc.selectionCount > 1 ? "Xoay cả khối −90°" : "Xoay −90°"; onClicked: Doc.rotateBy(-90) }
            IconButton { text: "↻"; tip: Doc.selectionCount > 1 ? "Xoay cả khối 90°" : "Xoay 90°"; onClicked: Doc.rotateBy(90) }
            IconButton { text: "⇔"; tip: "Căn giữa theo chiều ngang của tem"; onClicked: Doc.centerOnLabel("h") }
            IconButton { text: "⇕"; tip: "Căn giữa theo chiều dọc của tem"; onClicked: Doc.centerOnLabel("v") }
            IconButton { visible: Doc.selectionCount === 1; text: "▲"; tip: "Đưa lớp lên"; onClicked: Doc.reorder(-1) }
            IconButton { visible: Doc.selectionCount === 1; text: "▼"; tip: "Đưa lớp xuống"; onClicked: Doc.reorder(1) }
            Separator { vertical: true; anchors.verticalCenter: parent.verticalCenter }
            IconButton { text: Doc.selectionLocked ? "🔒" : "🔓"; active: Doc.selectionLocked; tip: Doc.selectionLocked ? "Mở khoá" : "Khoá vị trí"
                onClicked: Doc.setLocked(!Doc.selectionLocked) }
            IconButton { text: "✕"; tip: "Xoá (Del)"; enabled: !Doc.selectionLocked; onClicked: Doc.deleteSelected() }
        }
    }

    // ---- preview error / empty state ----
    Text {
        visible: Doc.previewError.length > 0
        anchors.centerIn: parent
        text: Doc.previewError
        color: Theme.danger; font.family: Theme.fontFamily; font.pixelSize: Theme.fsBase
        width: parent.width * 0.7; wrapMode: Text.Wrap; horizontalAlignment: Text.AlignHCenter
    }

    // ---- review-rotation badge ----
    Rectangle {
        visible: view.rotated
        anchors.left: parent.left; anchors.top: parent.top; anchors.margins: Theme.s4
        width: rotLabel.implicitWidth + Theme.s3 * 2; height: 24; radius: Theme.radiusMd
        color: Theme.surface; border.width: 1; border.color: Theme.border
        Text { id: rotLabel; anchors.centerIn: parent; text: "Đang xem xoay " + view.viewRotation + "° — bản in không đổi"
            font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm; color: Theme.textMuted }
        MouseArea { anchors.fill: parent; onClicked: { view.viewRotation = 0; Qt.callLater(view.fit) } }
    }

    // ---- floating view controls ----
    Rectangle {
        id: viewControls
        anchors.right: parent.right; anchors.bottom: parent.bottom; anchors.margins: Theme.s4
        width: zoomRow.implicitWidth + Theme.s2 * 2; height: 36; radius: Theme.radiusMd
        color: Theme.surface; border.width: 1; border.color: Theme.border
        Row {
            id: zoomRow
            anchors.centerIn: parent; spacing: 2
            IconButton { text: "−"; tip: "Thu nhỏ (Ctrl+−)"; width: 28; height: 28; onClicked: view.zoomBy(1 / 1.25) }
            C.Button {
                id: zoomLabel
                width: 56; height: 28; flat: true; padding: 0
                contentItem: Text { text: Math.round(view.zoom * 100) + "%"; font.family: Theme.fontFamily; font.pixelSize: Theme.fsSm
                    font.weight: Font.Medium; color: Theme.text; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                background: Rectangle { radius: Theme.radiusSm; color: zoomLabel.hovered ? Theme.hover : "transparent" }
                hoverEnabled: true
                onClicked: view.actualSize()
                C.ToolTip.visible: hovered; C.ToolTip.text: "Kích thước thật (100% = đúng milimét)"; C.ToolTip.delay: 500
            }
            IconButton { text: "+"; tip: "Phóng to (Ctrl+=)"; width: 28; height: 28; onClicked: view.zoomBy(1.25) }
            Separator { vertical: true; anchors.verticalCenter: parent.verticalCenter }
            AppButton { text: "Vừa khung"; kind: "ghost"; compact: true; onClicked: view.fit(); anchors.verticalCenter: parent.verticalCenter }
            Separator { vertical: true; anchors.verticalCenter: parent.verticalCenter }
            IconButton { text: "▭"; tip: "Hiện khung bao các phần tử"; active: view.showBounds; width: 28; height: 28; onClicked: view.showBounds = !view.showBounds }
            IconButton { text: "⟳"; tip: view.rotated ? "Xoay góc nhìn 90° (đang " + view.viewRotation + "°; chỉ để xem, bản in không đổi)" : "Xoay góc nhìn 90° (chỉ để xem, bản in không đổi)"
                active: view.rotated; width: 28; height: 28; onClicked: view.rotateView() }
            IconButton { text: "⌗"; tip: "Thước đo"; active: view.showRulers; width: 28; height: 28; onClicked: view.showRulers = !view.showRulers }
        }
    }
}
