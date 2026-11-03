"""Run a blocking call (network, printer enumeration, big Excel files) off the UI thread.

Only used for operations that really block. Result callbacks always run on the UI thread.
"""
import itertools

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot


class _Signals(QObject):
    finished = Signal(int, bool, object)        # token, ok, payload


class _Dispatcher(QObject):
    """Lives in the UI thread; the queued signal delivers worker results to `_finish` on that thread."""

    def __init__(self):
        super().__init__()
        self._pending = {}
        self._tokens = itertools.count(1)

    def submit(self, fn, on_ok, on_err):
        token = next(self._tokens)
        sig = _Signals()
        sig.finished.connect(self._finish)          # receiver lives in the UI thread -> queued
        self._pending[token] = (on_ok, on_err, sig)
        QThreadPool.globalInstance().start(_Job(fn, token, sig))

    @Slot(int, bool, object)
    def _finish(self, token, ok, payload):
        on_ok, on_err, _sig = self._pending.pop(token, (None, None, None))
        cb = on_ok if ok else on_err
        if cb:
            cb(payload)


class _Job(QRunnable):
    def __init__(self, fn, token, sig):
        super().__init__()
        self.fn, self.token, self.sig = fn, token, sig

    def run(self):
        try:
            result = self.fn()
        except Exception as e:      # reported to the UI, never raised in the pool thread
            self.sig.finished.emit(self.token, False, str(e) or e.__class__.__name__)
        else:
            self.sig.finished.emit(self.token, True, result)


_dispatcher = None


def run_async(fn, on_ok=None, on_err=None):
    """Call `fn()` in the thread pool, then `on_ok(result)` / `on_err(message)` on the UI thread."""
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = _Dispatcher()
    _dispatcher.submit(fn, on_ok, on_err)
