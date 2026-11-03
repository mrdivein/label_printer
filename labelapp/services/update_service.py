"""OTA updates from the public releases repository (no UI toolkit; used by bridge/update_controller).

Each GitHub Release of ``UPDATE_REPO`` carries the installer and a ``latest.json`` manifest:
    {"version": "22.1.0", "file": "Label-Printer-Setup-22.1.0.exe", "sha256": "<hex>", "size": 12345}
``releases/latest/download/latest.json`` always points at the newest release and is not subject to the
GitHub API rate limit. The installer is downloaded into %LOCALAPPDATA%, its size and SHA-256 are checked,
and only then is it offered for install. Installing runs it silently; it closes and restarts the app.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request

from ..version import UPDATE_REPO, __version__

USER_AGENT = "label-printer-updater/" + __version__
_FILE_RE = re.compile(r"^[A-Za-z0-9._-]+\.exe$")


class UpdateError(Exception):
    pass


def parse_version(v):
    """'v22.1.0' -> (22, 1, 0). Missing parts count as 0; anything unparsable as (0,)."""
    nums = re.findall(r"\d+", str(v or "").split("-")[0].split("+")[0])
    t = tuple(int(n) for n in nums[:4]) or (0,)
    while len(t) > 1 and t[-1] == 0:
        t = t[:-1]
    return t


def is_newer(remote, local=__version__):
    return parse_version(remote) > parse_version(local)


def manifest_url(repo=UPDATE_REPO):
    return os.environ.get("LABEL_PRINTER_UPDATE_MANIFEST") or \
        "https://github.com/%s/releases/latest/download/latest.json" % repo


def installer_url(manifest, repo=UPDATE_REPO):
    base = os.environ.get("LABEL_PRINTER_UPDATE_BASE") or "https://github.com/%s/releases/download" % repo
    return "%s/v%s/%s" % (base.rstrip("/"), manifest["version"], manifest["file"])


def updates_supported():
    """Only the installed Windows build updates itself; a source checkout is updated with git."""
    return bool(getattr(sys, "frozen", False)) and sys.platform.startswith("win")


def updates_dir():
    base = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
    path = os.path.join(base, "LabelPrinter", "updates")
    os.makedirs(path, exist_ok=True)
    return path


def _open(url, timeout):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Cache-Control": "no-cache"})
    return urllib.request.urlopen(req, timeout=timeout)


def validate_manifest(m):
    if not isinstance(m, dict):
        raise UpdateError("Update manifest is not an object")
    ver, name, digest = str(m.get("version") or ""), str(m.get("file") or ""), str(m.get("sha256") or "").lower()
    if not re.fullmatch(r"\d+(\.\d+){0,3}", ver):
        raise UpdateError("Update manifest has no valid version")
    if not _FILE_RE.match(name):
        raise UpdateError("Update manifest has no valid installer name")
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise UpdateError("Update manifest has no SHA-256")
    size = m.get("size")
    return {"version": ver, "file": name, "sha256": digest, "size": int(size) if size else 0,
            "notes": str(m.get("notes") or "")}


def fetch_manifest(url=None, timeout=15):
    try:
        with _open(url or manifest_url(), timeout) as r:
            data = json.loads(r.read(256 * 1024).decode("utf-8"))
    except UpdateError:
        raise
    except Exception as e:
        raise UpdateError("Could not read update information: %s" % (getattr(e, "reason", None) or e))
    return validate_manifest(data)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verified_installer(manifest, folder=None):
    """Path of an already downloaded installer that matches the manifest, else None."""
    p = os.path.join(folder or updates_dir(), manifest["file"])
    try:
        if os.path.isfile(p) and sha256_file(p) == manifest["sha256"]:
            return p
    except OSError:
        pass
    return None


def download(manifest, folder=None, progress=None, url=None, timeout=30):
    """Download the installer, check size and SHA-256, return its path. Old installers are removed."""
    folder = folder or updates_dir()
    done = verified_installer(manifest, folder)
    if done:
        return done
    final = os.path.join(folder, manifest["file"])
    part = final + ".part"
    h = hashlib.sha256()
    got = 0
    try:
        with _open(url or installer_url(manifest), timeout) as r, open(part, "wb") as out:
            total = manifest["size"] or int(r.headers.get("Content-Length") or 0)
            while True:
                chunk = r.read(256 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                h.update(chunk)
                got += len(chunk)
                if progress and total:
                    progress(min(100.0, got * 100.0 / total))
    except Exception as e:
        _remove(part)
        raise UpdateError("Download failed: %s" % (getattr(e, "reason", None) or e))
    if manifest["size"] and got != manifest["size"]:
        _remove(part)
        raise UpdateError("Download incomplete (%d of %d bytes)" % (got, manifest["size"]))
    if h.hexdigest() != manifest["sha256"]:
        _remove(part)
        raise UpdateError("Downloaded installer failed the checksum; it was deleted")
    os.replace(part, final)
    for name in os.listdir(folder):                 # keep only the installer that is about to be used
        if name != manifest["file"]:
            _remove(os.path.join(folder, name))
    return final


def installer_command(path, relaunch=True):
    """Silent Inno Setup install. The installer closes the running app and, unless told not to, restarts it."""
    cmd = [path, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS"]
    if not relaunch:
        cmd.append("/NORELAUNCH=1")
    return cmd


def launch_installer(path, relaunch=True):
    flags = 0
    if sys.platform.startswith("win"):
        flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen(installer_command(path, relaunch), close_fds=True, creationflags=flags)


def _remove(p):
    try:
        os.remove(p)
    except OSError:
        pass
