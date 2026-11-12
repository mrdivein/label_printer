"""Qt Quick (QML) entry point:  python -m labelapp   or   python labelapp/main.py"""
import os
import sys


def main(argv=None):
    argv = list(sys.argv if argv is None else argv)
    if __package__ in (None, ""):                         # started as a script: make `labelapp` importable
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from PySide6.QtCore import QTimer, QUrl
    from PySide6.QtGui import QGuiApplication, QIcon
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuickControls2 import QQuickStyle

    from labelapp.bridge.app_bridge import APP_NAME, AppBridge
    from labelapp.paths import qml_dir

    QQuickStyle.setStyle("Basic")                         # fully themed by our own components
    app = QGuiApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("LabelPrinter")
    icon = os.path.join(qml_dir(), "..", "resources", "app.ico" if sys.platform == "win32" else "app.svg")
    if os.path.exists(icon):
        app.setWindowIcon(QIcon(icon))

    bridge = AppBridge()
    engine = QQmlApplicationEngine()
    engine.addImageProvider("preview", bridge.provider)
    engine.addImportPath(qml_dir())
    ctx = engine.rootContext()
    ctx.setContextProperty("App", bridge)
    ctx.setContextProperty("Doc", bridge.document)
    ctx.setContextProperty("Lib", bridge.library)
    ctx.setContextProperty("Data", bridge.data)
    ctx.setContextProperty("Printing", bridge.printing)
    ctx.setContextProperty("Scan", bridge.scan)
    ctx.setContextProperty("Profiles", bridge.profiles)
    ctx.setContextProperty("Updates", bridge.updates)
    engine.load(QUrl.fromLocalFile(os.path.join(qml_dir(), "Main.qml")))
    if not engine.rootObjects():
        return 1
    app.aboutToQuit.connect(bridge.shutdown)
    QTimer.singleShot(0, bridge.start)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
