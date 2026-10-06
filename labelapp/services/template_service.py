"""Template library: list / load / save / save-as / new / duplicate / rename / delete / import / export.

The library lives in the persistent user-data folder (see settings_service) and is seeded from the bundled
``templates/`` folder without overwriting user files. Template files are plain JSON with an unchanged schema.
"""
import json
import os
import shutil

from ..core.binding import bind_row_to_template
from ..core.label_engine import render_preview_with_guides
from ..core.models import normalize_cfg
from .settings_service import backup_template_file, ensure_persistent_library, safe_filename

LABEL_PRESETS = {
    "50 x 68 mm (ECG tag)": (50, 68), "56 x 83 mm (thermal tag)": (56, 83), "40 x 30 mm": (40, 30),
    "50 x 30 mm": (50, 30), "60 x 40 mm": (60, 40), "100 x 50 mm": (100, 50), "100 x 150 mm (shipping)": (100, 150),
}


class TemplateError(Exception):
    pass


def _json_name(name):
    name = safe_filename(name)
    return name if name.lower().endswith('.json') else name + '.json'


def write_template(path, cfg):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
        f.write('\n')


class TemplateService:
    def __init__(self, library_dir=None):
        self._dir = library_dir

    @property
    def library_dir(self):
        return self._dir or ensure_persistent_library()

    def path_for(self, name):
        return os.path.join(self.library_dir, name)

    def is_in_library(self, path):
        return bool(path) and os.path.dirname(os.path.abspath(path)) == os.path.abspath(self.library_dir)

    def list_templates(self):
        return sorted((f for f in os.listdir(self.library_dir) if f.lower().endswith('.json')), key=str.lower)

    def load_path(self, path):
        with open(path, 'r', encoding='utf-8') as f:
            return normalize_cfg(json.load(f))

    def load(self, name):
        return self.load_path(self.path_for(name))

    def save(self, name, cfg):
        """Overwrite a library template (keeping a backup of the previous version)."""
        path = self.path_for(name)
        backup_template_file(path)
        write_template(path, cfg)
        return path

    def save_as(self, name, cfg):
        name = _json_name(name)
        write_template(self.path_for(name), cfg)
        return name

    def create(self, name, width_mm, height_mm, dpi=300):
        name = _json_name(name or 'New_Label')
        if os.path.exists(self.path_for(name)):
            raise TemplateError('That name already exists.')
        w, h = float(width_mm), float(height_mm)
        if w <= 0 or h <= 0:
            raise TemplateError('Width and height must be greater than 0.')
        cfg = normalize_cfg({'width_mm': w, 'height_mm': h, 'dpi': int(dpi), 'orientation': 'portrait', 'copies': 1, 'elements': [
            {'type': 'box', 'x': 0, 'y': 0, 'w': w, 'h': h, 'thickness': 0.18},
            {'type': 'text', 'text': 'New text', 'x': 2, 'y': 2, 'w': max(5, w - 4), 'h': 5, 'font': 'Arial', 'font_size': 9,
             'bold': True, 'align': 'left', 'wrap': False, 'auto_fit': True, 'min_font_size': 4}]})
        write_template(self.path_for(name), cfg)
        return name

    def duplicate(self, name, new_name):
        nn = _json_name(new_name)
        if os.path.exists(self.path_for(nn)):
            raise TemplateError('That name already exists.')
        shutil.copy2(self.path_for(name), self.path_for(nn))
        return nn

    def rename(self, name, new_name):
        nn = _json_name(new_name)
        if nn == name:
            return name
        if os.path.exists(self.path_for(nn)):
            raise TemplateError('That name already exists.')
        os.rename(self.path_for(name), self.path_for(nn))
        return nn

    def delete(self, name):
        p = self.path_for(name)
        backup_template_file(p, keep=20)
        os.remove(p)

    def export(self, name, dest):
        shutil.copy2(self.path_for(name), dest)

    def import_file(self, src, name=None, overwrite=False):
        """Copy an external JSON template into the library. Raises TemplateError if it exists and not overwrite."""
        try:
            cfg = self.load_path(src)
        except Exception as e:
            raise TemplateError(f'Invalid JSON template:\n{e}')
        name = _json_name(name or os.path.basename(src))
        dest = self.path_for(name)
        if os.path.exists(dest) and os.path.abspath(dest) != os.path.abspath(src) and not overwrite:
            raise TemplateError(f"'{name}' already exists in your template library.")
        write_template(dest, cfg)
        return name

    def preview_image(self, name, row=None, scale=2):
        cfg = self.load(name)
        if row:
            cfg = bind_row_to_template(cfg, row)
        return cfg, render_preview_with_guides(cfg, scale=scale, show_guides=False, show_fold=False)
