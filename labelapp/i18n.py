"""Interface language (Vietnamese / English).

The source language of every UI string is Vietnamese. QML marks its strings with qsTr("…"); Python marks the
strings it shows with tr("…") / trf("… {} …", value). English text comes from ``i18n_en.EN`` (keyed by the
Vietnamese source), so no .ts/.qm build step is needed: a QTranslator subclass answers QML from that table and
switching language calls QQmlEngine.retranslate(), which refreshes every qsTr binding live.

Keys may hold ``{}`` slots: trf() formats the English template, and tr() also recognises an already formatted
Vietnamese message (e.g. a status line built with an f-string) by matching it against those templates.
"""
import re

from .i18n_en import EN

LANGUAGES = (("vi", "Tiếng Việt"), ("en", "English"))
DEFAULT_LANGUAGE = "vi"

_lang = DEFAULT_LANGUAGE
_patterns = None


def language():
    return _lang


def set_language(lang):
    """Set the process-wide language ('vi' | 'en'); unknown values fall back to Vietnamese."""
    global _lang
    _lang = lang if lang in dict(LANGUAGES) else DEFAULT_LANGUAGE
    return _lang


def _compiled():
    global _patterns
    if _patterns is None:
        pats = []
        for vi, en in EN.items():
            if "{}" not in vi:
                continue
            parts = vi.split("{}")
            rx = re.compile("(.+?)".join(re.escape(p) for p in parts), re.S)
            pats.append((len(vi) - 2 * (len(parts) - 1), rx, en))
        pats.sort(key=lambda p: -p[0])           # most specific (longest fixed text) first
        _patterns = [(rx, en) for _, rx, en in pats]
    return _patterns


def tr(text, lang=None):
    """English for a Vietnamese UI string when the language is English; the text itself otherwise."""
    if (lang or _lang) != "en" or not text:
        return text
    s = str(text)
    hit = EN.get(s)
    if hit is not None:
        return hit
    for rx, en in _compiled():
        m = rx.fullmatch(s)
        if m:
            return en.format(*(tr(g, "en") for g in m.groups()))
    return s


def trf(template, *args):
    """tr() for a template with {} slots, then format: trf('Đã mở mẫu: {}', name)."""
    t = template if _lang != "en" else EN.get(template, template)
    return t.format(*args)


try:                                                     # Qt pieces are optional so core code imports without Qt
    from PySide6.QtCore import Property, QObject, QTranslator, Signal, Slot

    class TableTranslator(QTranslator):
        """Answers qsTr() from the EN table. Installed only while English is active."""

        def translate(self, context, source_text, disambiguation=None, n=-1):
            hit = EN.get(source_text)
            return hit if hit is not None else source_text

        def isEmpty(self):
            return False

    class I18nBridge(QObject):
        """Exposed to QML as ``I18n``: the current language, a switch, and tr() for strings that come from Python."""
        languageChanged = Signal()

        def __init__(self, workspace=None, parent=None):
            super().__init__(parent)
            self.workspace = workspace
            self.engine = None
            self._translator = None
            saved = workspace.get("qt_language", DEFAULT_LANGUAGE) if workspace is not None else DEFAULT_LANGUAGE
            set_language(saved)

        def attach(self, app, engine):
            """Install the translator for the saved language once the QML engine exists."""
            self.engine = engine
            self._app = app
            self._apply(initial=True)

        def _apply(self, initial=False):
            app = getattr(self, "_app", None)
            if app is not None:
                if language() == "en":
                    if self._translator is None:
                        self._translator = TableTranslator(app)
                    app.installTranslator(self._translator)
                elif self._translator is not None:
                    app.removeTranslator(self._translator)
            if not initial and self.engine is not None:
                self.engine.retranslate()

        def _get_language(self):
            return language()

        def _set_language(self, lang):
            if lang == language():
                return
            set_language(lang)
            if self.workspace is not None:
                self.workspace.set("qt_language", language())
            self._apply()
            self.languageChanged.emit()          # AppBridge re-describes Python-made texts

        language = Property(str, _get_language, _set_language, notify=languageChanged)

        @Slot(str)
        def setLanguage(self, lang):
            self._set_language(lang)

        @Slot()
        def toggle(self):
            self._set_language("vi" if language() == "en" else "en")

        @Slot(str, result=str)
        def tr(self, text):
            return tr(text)

        def _get_languages(self):
            return [{"code": c, "name": n} for c, n in LANGUAGES]

        languages = Property("QVariantList", _get_languages, constant=True)
except ImportError:                                      # pragma: no cover
    pass
