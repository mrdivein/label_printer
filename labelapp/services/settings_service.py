"""Persistent per-user data (%APPDATA%\\LabelPrinter): template library, profiles, workspace, saved sources.

File formats are unchanged from earlier versions; an earlier data folder is copied over on first start.
"""
import datetime
import json
import os
import re

from .datasource_service import extract_google_sheet_id
from ..paths import app_root

def create_session_dir():
    now = datetime.datetime.now()
    p = os.path.join(app_data_dir(), now.strftime("%Y-%m-%d"), "session_" + now.strftime("%H%M%S"))
    os.makedirs(p, exist_ok=True)
    return p


def safe_filename(s):
    s = re.sub(r'[<>:"/\\|?*]+', "_", str(s or "").strip())
    s = re.sub(r"\s+", "_", s)
    return s[:80] or "label"


DATA_DIR_NAME = "LabelPrinter"


def _looks_like_data_dir(path):
    """A user-data folder of an earlier version: it holds the workspace file and a template library."""
    return os.path.isfile(os.path.join(path, "workspace_v20.json")) and os.path.isdir(os.path.join(path, "templates"))


def _migrate_previous_data_dir(base, path):
    """Copy the data folder of an earlier version (found by its contents, not its name) into the new one, once."""
    try:
        names = sorted(os.listdir(base))
    except OSError:
        return
    for name in names:
        old = os.path.join(base, name)
        if name != DATA_DIR_NAME and os.path.isdir(old) and _looks_like_data_dir(old):
            try:
                import shutil
                shutil.copytree(old, path)
            except Exception:
                pass
            return


def app_data_dir():
    """Persistent user data that survives replacing/updating the application folder."""
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".label_printer")
    path = os.path.join(base, DATA_DIR_NAME)
    if not os.path.isdir(path):
        _migrate_previous_data_dir(base, path)
    os.makedirs(path, exist_ok=True)
    return path

def persistent_template_dir():
    path = os.path.join(app_data_dir(), "templates")
    os.makedirs(path, exist_ok=True)
    return path

def bundled_template_dir():
    return os.path.join(app_root(), "templates")

def ensure_persistent_library():
    """Seed the bundled example templates into an empty library (first run), and migrate a legacy profile file.

    Examples are copied only while the library holds no template at all, so one the user deleted does not come
    back at the next start. User files are never overwritten.
    """
    td = persistent_template_dir()
    src = bundled_template_dir()
    if os.path.isdir(src) and not any(n.lower().endswith(".json") for n in os.listdir(td)):
        for name in os.listdir(src):
            if not name.lower().endswith(".json"):
                continue
            sp = os.path.join(src, name)
            dp = os.path.join(td, name)
            if not os.path.exists(dp):
                try:
                    import shutil
                    shutil.copy2(sp, dp)
                except Exception:
                    pass
    # Migrate a legacy profile file from an older portable app folder if present.
    legacy = os.path.join(app_root(), "printer_profiles.json")
    target = os.path.join(app_data_dir(), "printer_profiles.json")
    if os.path.exists(legacy) and not os.path.exists(target):
        try:
            import shutil
            shutil.copy2(legacy, target)
        except Exception:
            pass
    return td

def profiles_path():
    ensure_persistent_library()
    return os.path.join(app_data_dir(), "printer_profiles.json")

def load_profiles():
    p = profiles_path()
    if not os.path.exists(p):
        return {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def save_profiles(data):
    with open(profiles_path(), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def workspace_path():
    return os.path.join(app_data_dir(), "workspace_v20.json")

def working_copy_path():
    return os.path.join(app_data_dir(), "active_working_template.json")

def load_workspace_state():
    p = workspace_path()
    if not os.path.exists(p):
        return {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def save_workspace_state(data):
    try:
        with open(workspace_path(), "w", encoding="utf-8") as f:
            json.dump(data or {}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def sources_path():
    return os.path.join(app_data_dir(), "data_sources.json")

def load_sources():
    """Saved Google Sheets + recent Excel files. Lives in the persistent app-data folder."""
    base = {"sheets": [], "excel": []}
    try:
        with open(sources_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            base["sheets"] = [x for x in data.get("sheets", []) if isinstance(x, dict) and x.get("url")]
            base["excel"] = [x for x in data.get("excel", []) if isinstance(x, str)]
    except Exception:
        pass
    return base

def save_sources(data):
    try:
        with open(sources_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def _sheet_key(url):
    try:
        return extract_google_sheet_id(url)
    except Exception:
        return str(url).strip()

def default_sheet_name(url, tab):
    sid = _sheet_key(url)
    return f"{tab or 'Sheet'} · …{str(sid)[-6:]}"

def remember_google_source(url, tab, name=None):
    """Insert/refresh a saved sheet (keyed by sheet id + tab), most recently used first."""
    data = load_sources()
    sid = _sheet_key(url)
    keep = []
    old_name = None
    for it in data["sheets"]:
        if _sheet_key(it["url"]) == sid and (it.get("tab") or "") == (tab or ""):
            old_name = it.get("name")
        else:
            keep.append(it)
    entry = {"name": (name or old_name or default_sheet_name(url, tab)), "url": url, "tab": tab or "",
             "last_used": datetime.datetime.now().isoformat(timespec="seconds")}
    data["sheets"] = [entry] + keep
    save_sources(data)
    return entry

def remember_excel_source(path):
    data = load_sources()
    data["excel"] = [path] + [p for p in data["excel"] if p != path][:11]
    save_sources(data)

def backup_template_file(path, keep=5):
    if not path or not os.path.exists(path):
        return
    try:
        import shutil
        stem = os.path.splitext(os.path.basename(path))[0]
        bdir = os.path.join(app_data_dir(), "template_backups", stem)
        os.makedirs(bdir, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        shutil.copy2(path, os.path.join(bdir, stamp + ".json"))
        files = sorted([os.path.join(bdir,n) for n in os.listdir(bdir) if n.lower().endswith('.json')], reverse=True)
        for old in files[int(keep):]:
            try: os.remove(old)
            except Exception: pass
    except Exception:
        pass
