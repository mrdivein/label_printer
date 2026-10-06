"""Workspace state (last template/printer/data source) and the live "working copy" of an unsaved layout.

Uses the same files and keys as the original application (workspace_v20.json, active_working_template.json).
New keys written by the Qt UI are prefixed ``qt_`` so the Tkinter UI keeps working side by side.
"""
import json
import os

from ..core.models import normalize_cfg
from .settings_service import (load_workspace_state, save_workspace_state, working_copy_path)


class Workspace:
    def __init__(self):
        self.state = load_workspace_state()

    def get(self, key, default=None):
        return self.state.get(key, default)

    def set(self, key, value, save=True):
        self.state[key] = value
        if save:
            self.save()

    def update(self, **kv):
        self.state.update(kv)
        self.save()

    def save(self):
        save_workspace_state(self.state)

    # ---- unsaved layout recovery
    def save_working_copy(self, cfg, template_name):
        try:
            with open(working_copy_path(), 'w', encoding='utf-8') as f:
                json.dump(normalize_cfg(cfg), f, ensure_ascii=False, indent=2)
            self.state['working_dirty'] = True
            self.state['working_template'] = template_name or ''
            self.save()
        except Exception:
            pass

    def clear_working_copy(self):
        self.state['working_dirty'] = False
        self.state.pop('working_template', None)
        try:
            if os.path.exists(working_copy_path()):
                os.remove(working_copy_path())
        except Exception:
            pass
        self.save()

    def recover_working_copy(self, template_name):
        """Return the unsaved layout of the previous session for `template_name`, or None."""
        if not self.state.get('working_dirty') or not os.path.exists(working_copy_path()):
            return None
        wanted = self.state.get('working_template', '')
        if wanted and wanted != (template_name or ''):
            return None
        try:
            with open(working_copy_path(), 'r', encoding='utf-8') as f:
                return normalize_cfg(json.load(f))
        except Exception:
            return None
