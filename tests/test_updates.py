"""OTA updates: version compare, manifest checks, verified download, controller flow (local HTTP server)."""
import hashlib
import http.server
import json
import os
import threading
import time

import pytest

from labelapp.services import update_service as us

PAYLOAD = b"MZ fake installer " * 5000


def _manifest(version="99.0.0", payload=PAYLOAD, **over):
    m = {"version": version, "file": "Temly-Setup-%s.exe" % version,
         "sha256": hashlib.sha256(payload).hexdigest(), "size": len(payload)}
    m.update(over)
    return m


@pytest.fixture
def server(tmp_path):
    """Serves tmp_path/www like a GitHub release: latest.json and v<ver>/<file>."""
    www = tmp_path / "www"
    www.mkdir()

    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(www), **k)

        def log_message(self, *a):
            pass

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = "http://127.0.0.1:%d" % httpd.server_address[1]

    def publish(m, payload=PAYLOAD):
        (www / "latest.json").write_text(json.dumps(m))
        d = www / ("v" + m["version"])
        d.mkdir(exist_ok=True)
        (d / m["file"]).write_bytes(payload)

    yield base, publish
    httpd.shutdown()


@pytest.fixture
def env(server, tmp_path, monkeypatch):
    base, publish = server
    monkeypatch.setenv("TEMLY_UPDATE_MANIFEST", base + "/latest.json")
    monkeypatch.setenv("TEMLY_UPDATE_BASE", base)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    return publish


def test_version_compare():
    assert us.parse_version("v22.1.0") == (22, 1)
    assert us.is_newer("22.10.0", "22.9.3")
    assert us.is_newer("23", "22.99.99")
    assert not us.is_newer("22.1.0", "22.1")
    assert not us.is_newer("22.0.9", "22.1.0")
    assert not us.is_newer("garbage", "22.1.0")


def test_manifest_validation_rejects_bad_names_and_digests():
    assert us.validate_manifest(_manifest())["size"] == len(PAYLOAD)
    for bad in (_manifest(file="..\\evil.exe"), _manifest(file="setup.bat"), _manifest(sha256="abc"),
                _manifest(version="latest"), []):
        with pytest.raises(us.UpdateError):
            us.validate_manifest(bad)


def test_download_verifies_checksum_and_keeps_only_new_installer(env, tmp_path):
    env(_manifest())
    m = us.fetch_manifest()
    old = os.path.join(us.updates_dir(), "Temly-Setup-1.0.0.exe")
    open(old, "wb").write(b"old")
    seen = []
    p = us.download(m, progress=seen.append)
    assert open(p, "rb").read() == PAYLOAD
    assert seen and seen[-1] == 100.0
    assert os.listdir(us.updates_dir()) == [m["file"]]
    assert us.download(m) == p                                   # already there: no second download


def test_tampered_installer_is_rejected_and_deleted(env):
    m = _manifest()
    env(m, payload=b"X" * len(PAYLOAD))
    with pytest.raises(us.UpdateError, match="checksum"):
        us.download(us.fetch_manifest())
    assert os.listdir(us.updates_dir()) == []


def test_missing_manifest_is_a_clean_error(monkeypatch, server):
    base, _ = server
    monkeypatch.setenv("TEMLY_UPDATE_MANIFEST", base + "/nothing.json")
    with pytest.raises(us.UpdateError):
        us.fetch_manifest()


def test_installer_command_is_silent_and_can_skip_relaunch():
    assert us.installer_command("s.exe")[:3] == ["s.exe", "/VERYSILENT", "/SUPPRESSMSGBOXES"]
    assert "/NORELAUNCH=1" not in us.installer_command("s.exe")
    assert us.installer_command("s.exe", relaunch=False)[-1] == "/NORELAUNCH=1"


def _wait(qapp, cond, timeout=8.0):
    end = time.time() + timeout
    while not cond() and time.time() < end:
        qapp.processEvents()
        time.sleep(0.005)
    assert cond(), "timed out"


def test_controller_downloads_then_installs_and_quits(env, qapp, monkeypatch):
    from labelapp.bridge.update_controller import UpdateController
    env(_manifest())
    launched, quits = [], []
    monkeypatch.setattr(us, "launch_installer", lambda p, relaunch=True: launched.append((p, relaunch)))
    c = UpdateController(supported=True)
    c.quitRequested.connect(lambda: quits.append(1))
    c.check()
    _wait(qapp, lambda: c.state in ("ready", "error"))
    assert c.state == "ready", c.text
    assert c.newVersion == "99.0.0"
    c.installNow()
    assert launched and launched[0][1] is True and quits == [1]
    c.install_on_quit()                                          # already handed over: nothing runs twice
    assert len(launched) == 1


def test_controller_up_to_date_and_install_on_quit(env, qapp, monkeypatch):
    from labelapp.bridge.update_controller import UpdateController
    from labelapp.version import __version__
    env(_manifest(version=__version__))
    c = UpdateController(supported=True)
    c.check()
    _wait(qapp, lambda: c.state in ("current", "error"))
    assert c.state == "current"

    env(_manifest())
    launched = []
    monkeypatch.setattr(us, "launch_installer", lambda p, relaunch=True: launched.append(relaunch))
    c.check()
    _wait(qapp, lambda: c.state == "ready")
    c.install_on_quit()
    assert launched == [False]


def test_source_checkout_never_updates(qapp):
    from labelapp.bridge.update_controller import UpdateController
    c = UpdateController(supported=False)
    c.check()
    assert c.state == "dev"
