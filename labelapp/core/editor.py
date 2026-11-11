"""Label editor: document state, selection, undo/redo, edit commands and pointer interaction.

Everything the Tk designer dialog did *to the template* lives here, with no UI toolkit involved. All coordinates
are label millimetres (display space for pointer input), so nothing depends on the current zoom level.

Usage pattern (see labelapp.bridge.document_controller):
    note = editor.some_command(...)      # returns a short status note when the document changed, else None
"""
import copy
import math

from .designer_geometry import (display_box_mm, display_to_source_box, element_is_rotated, element_outline,
                                first_fold, flip_point, fold_at, fold_for_element, frame_corners,
                                line_display_endpoints, outline_bbox, point_near_poly, source_box, virtual_area,
                                visual_frame, element_in_fold_region)
from .geometry import _element_angle, element_rotation_center, rotate_point_cw
from .models import is_printed, normalize_cfg
from .profiles import apply_profile

FONT_CHOICES = ('Arial', 'Arial Narrow', 'Segoe UI', 'Segoe UI Light', 'Tahoma', 'Verdana')
UNDO_LIMIT = 60
HANDLE_PX = 6               # handle half-size in view pixels
HIT_PAD_PX = 4              # hit padding around elements in view pixels
ROTATE_KNOB_PX = 26         # distance of the rotate knob from the element edge

DRAWABLE = {'text', 'barcode', 'qr', 'image', 'line', 'box', 'fill_box', 'ellipse'}
ALL = DRAWABLE

# key, label, kind, element types it applies to, extra
# kind: number | text | bool | choice | path ; extra: unit / choices (+ choice_labels shown instead of the stored value)
INSPECTOR_FIELDS = [
    {'key': 'x', 'label': 'X', 'kind': 'number', 'group': 'Vị trí', 'types': ALL, 'unit': 'mm'},
    {'key': 'y', 'label': 'Y', 'kind': 'number', 'group': 'Vị trí', 'types': ALL, 'unit': 'mm'},
    {'key': 'w', 'label': 'Rộng', 'kind': 'number', 'group': 'Vị trí', 'types': ALL - {'line'}, 'unit': 'mm'},
    {'key': 'h', 'label': 'Cao', 'kind': 'number', 'group': 'Vị trí', 'types': ALL - {'line'}, 'unit': 'mm'},
    {'key': 'x2', 'label': 'X cuối', 'kind': 'number', 'group': 'Vị trí', 'types': {'line'}, 'unit': 'mm'},
    {'key': 'y2', 'label': 'Y cuối', 'kind': 'number', 'group': 'Vị trí', 'types': {'line'}, 'unit': 'mm'},
    {'key': 'angle', 'label': 'Xoay', 'kind': 'number', 'group': 'Vị trí', 'types': ALL, 'unit': '°'},
    {'key': 'text', 'label': 'Nội dung', 'kind': 'text', 'group': 'Nội dung', 'types': {'text'}},
    {'key': 'value', 'label': 'Giá trị', 'kind': 'text', 'group': 'Nội dung', 'types': {'barcode', 'qr'}},
    {'key': 'path', 'label': 'Tệp ảnh', 'kind': 'path', 'group': 'Nội dung', 'types': {'image'}},
    {'key': 'font', 'label': 'Phông chữ', 'kind': 'choice', 'group': 'Chữ', 'types': {'text', 'barcode'}, 'choices': list(FONT_CHOICES)},
    {'key': 'font_size', 'label': 'Cỡ chữ', 'kind': 'number', 'group': 'Chữ', 'types': {'text'}, 'unit': 'pt'},
    {'key': 'bold', 'label': 'In đậm', 'kind': 'bool', 'group': 'Chữ', 'types': {'text'}},
    {'key': 'align', 'label': 'Căn lề', 'kind': 'choice', 'group': 'Chữ', 'types': {'text'}, 'choices': ['left', 'center', 'right'],
     'choice_labels': ['Trái', 'Giữa', 'Phải']},
    {'key': 'auto_fit', 'label': 'Tự thu nhỏ cho vừa khung', 'kind': 'bool', 'group': 'Chữ', 'types': {'text'}},
    {'key': 'min_font_size', 'label': 'Cỡ nhỏ nhất', 'kind': 'number', 'group': 'Chữ', 'types': {'text'}, 'unit': 'pt'},
    {'key': 'wrap', 'label': 'Xuống dòng', 'kind': 'bool', 'group': 'Chữ', 'types': {'text'}},
    {'key': 'symbology', 'label': 'Loại mã', 'kind': 'choice', 'group': 'Mã vạch', 'types': {'barcode'},
     'choices': ['code128', 'ean13', 'ean8', 'upca', 'code39', 'itf'],
     'choice_labels': ['Code 128', 'EAN-13', 'EAN-8', 'UPC-A', 'Code 39', 'ITF (2 of 5)']},
    {'key': 'crop_height', 'label': 'Cắt chiều cao vạch', 'kind': 'bool', 'group': 'Mã vạch', 'types': {'barcode'}},
    {'key': 'barcode_height_mm', 'label': 'Cao vạch', 'kind': 'number', 'group': 'Mã vạch', 'types': {'barcode'}, 'unit': 'mm'},
    {'key': 'show_text', 'label': 'Hiện số dưới vạch', 'kind': 'bool', 'group': 'Mã vạch', 'types': {'barcode'}},
    {'key': 'ecc', 'label': 'Mức sửa lỗi', 'kind': 'choice', 'group': 'QR', 'types': {'qr'}, 'choices': ['L', 'M', 'Q', 'H'],
     'choice_labels': ['L · 7%', 'M · 15%', 'Q · 25%', 'H · 30%']},
    {'key': 'fit', 'label': 'Co giãn', 'kind': 'choice', 'group': 'Ảnh', 'types': {'image'}, 'choices': ['contain', 'stretch'],
     'choice_labels': ['Giữ tỉ lệ', 'Kéo giãn']},
    {'key': 'dither', 'label': 'Chấm mịn (ảnh màu / xám)', 'kind': 'bool', 'group': 'Ảnh', 'types': {'image'}},
    {'key': 'thickness', 'label': 'Độ dày nét', 'kind': 'number', 'group': 'Nét', 'types': {'line', 'box', 'ellipse'}, 'unit': 'mm'},
    {'key': 'transform', 'label': 'Kiểu chữ', 'kind': 'choice', 'group': 'Dữ liệu', 'types': {'text'}, 'choices': ['', 'upper', 'lower', 'title'],
     'choice_labels': ['Giữ nguyên', 'IN HOA', 'in thường', 'Hoa Đầu Từ']},
    {'key': 'prefix', 'label': 'Thêm trước', 'kind': 'text', 'group': 'Dữ liệu', 'types': {'text'}},
    {'key': 'suffix', 'label': 'Thêm sau', 'kind': 'text', 'group': 'Dữ liệu', 'types': {'text'}},
    {'key': 'show_if', 'label': 'Chỉ in khi có', 'kind': 'text', 'group': 'Dữ liệu', 'types': ALL},
    {'key': 'print', 'label': 'In phần này', 'kind': 'bool', 'group': 'In', 'types': ALL},
]
# Vietnamese names of element types (lists, titles, canvas tags)
TYPE_LABELS = {'text': 'Chữ', 'barcode': 'Mã vạch', 'qr': 'QR', 'image': 'Ảnh', 'line': 'Đường kẻ', 'box': 'Khung',
               'fill_box': 'Khối tô', 'ellipse': 'Elip'}
FIELD_BY_KEY = {f['key']: f for f in INSPECTOR_FIELDS}
# Setting one value on every member would collapse a group's layout, so these are edited member by member.
GROUP_HIDDEN_KEYS = {'x', 'y', 'w', 'h', 'x2', 'y2', 'angle', 'text', 'value', 'path'}
DEFAULTS = {'font': 'Arial', 'bold': False, 'align': 'left', 'auto_fit': False, 'wrap': False, 'transform': '',
            'prefix': '', 'suffix': '', 'show_if': '', 'thickness': 0.2, 'symbology': 'code128', 'show_text': False,
            'ecc': 'M', 'path': '', 'fit': 'contain', 'min_font_size': 4, 'font_size': 8, 'angle': 0.0,
            'print': True, 'dither': True}

DOC_NUMBER_KEYS = ('width_mm', 'height_mm', 'dpi', 'offset_x_mm', 'offset_y_mm', 'rotation_deg', 'scale_x_pct',
                   'scale_y_pct', 'threshold', 'oversample', 'copies')
DOC_CHOICE_KEYS = {'orientation': ('portrait', 'landscape'), 'render_mode': ('thermal_crisp', 'standard')}

def _etype(e):
    return str(e.get('type', '')).lower()


def _set_angle(e, value):
    a = ((float(value) + 180.0) % 360.0) - 180.0
    if abs(a) < 0.0001:
        e.pop('angle', None)
    else:
        e['angle'] = round(a, 2)


def _shift(e, dx, dy, nd=3):
    for k in ('x', 'x2'):
        if k in e:
            e[k] = round(float(e[k]) + dx, nd)
    for k in ('y', 'y2'):
        if k in e:
            e[k] = round(float(e[k]) + dy, nd)


class LabelEditor:
    def __init__(self, cfg=None):
        self.cfg = normalize_cfg(cfg)
        self.selected = set()
        self.primary = None
        self.undo_stack = []
        self.redo_stack = []
        self.clipboard = []
        self.snap_mm = 0.1
        self.view_mm_per_px = 0.26          # updated by the view whenever zoom changes
        self.dirty = False
        self._drag = None

    # ------------------------------------------------------------------ document
    def load(self, cfg):
        self.cfg = normalize_cfg(cfg)
        self.selected = set()
        self.primary = None
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.dirty = False
        self._drag = None
        if self.cfg.get('elements'):
            self.set_selection({0}, 0)

    def snapshot(self):
        return copy.deepcopy(self.cfg)

    def push_undo(self, snap=None):
        self.undo_stack.append(copy.deepcopy(snap if snap is not None else self.cfg))
        if len(self.undo_stack) > UNDO_LIMIT:
            self.undo_stack = self.undo_stack[-UNDO_LIMIT:]
        self.redo_stack.clear()

    def _drop_undo(self):
        if self.undo_stack:
            self.undo_stack.pop()

    @property
    def can_undo(self):
        return bool(self.undo_stack)

    @property
    def can_redo(self):
        return bool(self.redo_stack)

    def undo(self):
        if not self.undo_stack:
            return None
        self.redo_stack.append(self.snapshot())
        self.cfg = self.undo_stack.pop()
        self.sanitize_selection()
        return 'Undo'

    def redo(self):
        if not self.redo_stack:
            return None
        self.undo_stack.append(self.snapshot())
        self.cfg = self.redo_stack.pop()
        self.sanitize_selection()
        return 'Redo'

    # ------------------------------------------------------------------ selection
    @property
    def elements(self):
        return self.cfg['elements']

    def sanitize_selection(self):
        n = len(self.elements)
        self.selected = {i for i in self.selected if 0 <= i < n}
        if self.primary not in self.selected:
            self.primary = min(self.selected) if self.selected else None

    def set_selection(self, indices, primary=None):
        n = len(self.elements)
        self.selected = {int(i) for i in indices if 0 <= int(i) < n}
        self.primary = primary if primary in self.selected else (min(self.selected) if self.selected else None)

    def select_all(self):
        if self.elements:
            self.set_selection(set(range(len(self.elements))), 0)

    def _unlocked(self):
        return [i for i in sorted(self.selected) if not self.elements[i].get('locked')]

    def selection_types(self):
        return {_etype(self.elements[i]) for i in self.selected}

    # ------------------------------------------------------------------ groups
    # A group is the elements sharing a 'group_id'. Canvas clicks and the marquee take the whole group; the layer
    # list still picks a single member, which is how a member is edited on its own.
    def with_groups(self, indices):
        """`indices` plus every other member of the groups they belong to."""
        out = {int(i) for i in indices}
        gids = {self.elements[i].get('group_id') for i in out} - {None}
        out.update(i for i, e in enumerate(self.elements) if e.get('group_id') in gids)
        return out

    def _selected_groups(self):
        return {self.elements[i].get('group_id') for i in self.selected} - {None}

    @property
    def can_group(self):
        return len(self.selected) >= 2 and not self.selection_is_group

    @property
    def can_ungroup(self):
        return bool(self._selected_groups())

    @property
    def selection_is_group(self):
        """The selection is exactly one complete group."""
        gids = {self.elements[i].get('group_id') for i in self.selected}
        return len(self.selected) >= 2 and len(gids) == 1 and None not in gids and self.with_groups(self.selected) == self.selected

    def _new_group_id(self):
        used = {e.get('group_id') for e in self.elements}
        n = 1
        while f'g{n}' in used:
            n += 1
        return f'g{n}'

    def _prune_groups(self):
        """A group of one is no group: drop the id left on the last member."""
        counts = {}
        for e in self.elements:
            if e.get('group_id') is not None:
                counts[e['group_id']] = counts.get(e['group_id'], 0) + 1
        for e in self.elements:
            if counts.get(e.get('group_id')) == 1:
                del e['group_id']

    def _regroup_copies(self, indices):
        """Copies must not join the originals' groups: give them groups of their own."""
        fresh = {}
        for i in indices:
            e = self.elements[i]
            gid = e.get('group_id')
            if gid is not None:
                if gid not in fresh:
                    fresh[gid] = self._new_group_id()
                e['group_id'] = fresh[gid]             # written at once, so the next new id differs
        self._prune_groups()

    def group_selected(self):
        if not self.can_group:
            return None
        self.push_undo()
        gid = self._new_group_id()
        for i in self.selected:
            self.elements[i]['group_id'] = gid
        self._prune_groups()
        return 'Grouped'

    def ungroup_selected(self):
        gids = self._selected_groups()
        if not gids:
            return None
        self.push_undo()
        for e in self.elements:
            if e.get('group_id') in gids:
                del e['group_id']
        return 'Ungrouped'

    # ------------------------------------------------------------------ inspector
    def inspector_fields(self):
        """Fields applicable to the current selection (schema + current value; None = mixed values)."""
        if not self.selected:
            return []
        types = self.selection_types()
        grouped = len(self.selected) > 1 and bool(self._selected_groups())
        out = []
        for f in INSPECTOR_FIELDS:
            if not types & f['types'] or (grouped and f['key'] in GROUP_HIDDEN_KEYS):
                continue
            vals = []
            for i in sorted(self.selected):
                e = self.elements[i]
                if _etype(e) not in f['types']:
                    continue
                vals.append(self._field_value(e, f['key']))
            same = all(v == vals[0] for v in vals) if vals else True
            item = {k: (sorted(v) if isinstance(v, set) else v) for k, v in f.items() if k != 'types'}
            item['value'] = vals[0] if (vals and same) else None
            item['mixed'] = not same
            out.append(item)
        return out

    @staticmethod
    def _field_value(e, key):
        if key == 'angle':
            return round(_element_angle(e), 3)
        if key in e:
            v = e[key]
            return round(v, 4) if isinstance(v, float) else v
        return DEFAULTS.get(key, '' if FIELD_BY_KEY[key]['kind'] in ('text', 'path', 'choice') else 0)

    def set_prop(self, key, value):
        """Set one property on every selected, unlocked element it applies to. Returns a status note or None."""
        f = FIELD_BY_KEY.get(key)
        if f is None:
            return None
        if key == 'print':
            return self.set_print(sorted(self.selected), bool(value))
        ids = [i for i in self._unlocked() if _etype(self.elements[i]) in f['types']]
        if not ids:
            return None
        kind = f['kind']
        try:
            if kind == 'number':
                if str(value).strip() == '':
                    return None
                new = float(str(value).replace(',', '.'))
            elif kind == 'bool':
                new = bool(value)
            else:
                new = str(value) if value is not None else ''
                if key not in ('prefix', 'suffix'):
                    new = new.strip() if key != 'text' else new
        except (TypeError, ValueError):
            return None
        snap = self.snapshot()
        changed = False
        for i in ids:
            e = self.elements[i]
            if key == 'angle':
                old = _element_angle(e)
                _set_angle(e, new)
                changed = changed or abs(_element_angle(e) - old) > 1e-9
            elif kind in ('choice', 'text', 'path') and new == '' and key not in ('font', 'text', 'value'):
                if key in e:
                    del e[key]
                    changed = True
            elif e.get(key) != new:
                e[key] = new
                changed = True
        if not changed:
            return None
        self.push_undo(snap)
        return f"{f['label']} changed"

    def apply_profile(self, profile):
        """Apply a printer profile (paper, compensation, quality, print-area guide) to the document."""
        snap = self.snapshot()
        apply_profile(self.cfg, profile)
        if self.cfg == snap:
            return None
        self.push_undo(snap)
        return 'Printer profile loaded'

    def set_doc(self, **vals):
        """Document level settings (paper, DPI, compensation, print quality)."""
        snap = self.snapshot()
        changed = False
        for k, v in vals.items():
            if k in DOC_NUMBER_KEYS:
                try:
                    nv = float(str(v).replace(',', '.'))
                except (TypeError, ValueError):
                    continue
                if k in ('dpi', 'oversample', 'threshold', 'copies'):
                    nv = int(round(nv))
                if k in ('width_mm', 'height_mm', 'dpi') and nv <= 0:
                    continue
                if k == 'copies':
                    nv = max(1, nv)
                if self.cfg.get(k) != nv:
                    self.cfg[k] = nv
                    changed = True
            elif k in DOC_CHOICE_KEYS and v in DOC_CHOICE_KEYS[k]:
                if self.cfg.get(k) != v:
                    self.cfg[k] = v
                    changed = True
            elif k == 'virtual_area_show':
                a = virtual_area(self.cfg)
                if a.get('show') != bool(v):
                    a['show'] = bool(v)
                    self.cfg['virtual_print_area'] = a
                    changed = True
        if not changed:
            return None
        self.push_undo(snap)
        return 'Paper settings changed'

    # ------------------------------------------------------------------ edit commands
    def _snap(self, v):
        step = float(self.snap_mm or 0)
        if step <= 0:
            return round(float(v), 3)
        return round(round(float(v) / step) * step, 3)

    def _default_add_xy(self):
        a = virtual_area(self.cfg)
        return float(a.get('x', 0)) + 2, float(a.get('y', 0)) + 2

    def _append(self, elements, note):
        self.push_undo()
        new = []
        for e in elements:
            self.elements.append(e)
            new.append(len(self.elements) - 1)
        self.set_selection(set(new), new[-1])
        return note

    def add_text(self, text='New text', font_size=5.0, bold=False, w=25.0, h=4.0):
        x, y = self._default_add_xy()
        return self._append([{'type': 'text', 'text': text, 'x': x, 'y': y, 'w': float(w), 'h': float(h), 'font': 'Segoe UI',
                              'font_size': float(font_size), 'bold': bool(bold), 'align': 'left', 'wrap': False, 'auto_fit': False}],
                            'Free text added')

    def add_fields(self, fields, as_barcode=False):
        fields = [str(f).strip() for f in fields if str(f).strip()]
        if not fields:
            return None
        x, y = self._default_add_xy()
        els = []
        for n, field in enumerate(fields):
            yy = y + n * 5.0
            if as_barcode:
                els.append({'type': 'barcode', 'value': '{{' + field + '}}', 'x': x, 'y': yy, 'w': 30.0, 'h': 7.0, 'symbology': 'code128',
                            'barcode_height_mm': 6.5, 'module_width': 0.22, 'quiet_zone': 1.2, 'show_text': False})
            else:
                els.append({'type': 'text', 'text': '{{' + field + '}}', 'x': x, 'y': yy, 'w': 25.0, 'h': 4.0, 'font': 'Segoe UI',
                            'font_size': 5.0, 'bold': False, 'align': 'left', 'wrap': False, 'auto_fit': True, 'min_font_size': 3.0})
        return self._append(els, 'Dynamic field(s) added')

    def add_special(self, kind, path=None):
        x, y = self._default_add_xy()
        if kind == 'qr':
            e = {'type': 'qr', 'value': '{{Barcode}}', 'x': x, 'y': y, 'w': 14.0, 'h': 14.0, 'ecc': 'M'}
        elif kind == 'barcode':
            e = {'type': 'barcode', 'value': '{{Barcode}}', 'x': x, 'y': y, 'w': 30.0, 'h': 9.0, 'symbology': 'code128',
                 'barcode_height_mm': 6.5, 'module_width': 0.25, 'quiet_zone': 1.0, 'show_text': True, 'text_size': 6.0}
        elif kind == 'image':
            if not path:
                return None
            e = {'type': 'image', 'path': path, 'x': x, 'y': y, 'w': 16.0, 'h': 8.0, 'fit': 'contain'}
        else:
            return None
        return self._append([e], 'Element added')

    def add_shape(self, kind):
        x, y = self._default_add_xy()
        if kind == 'line':
            e = {'type': 'line', 'x': x, 'y': y, 'x2': x + 20, 'y2': y, 'thickness': 0.15}
        elif kind in ('box', 'fill_box', 'ellipse'):
            e = {'type': kind, 'x': x, 'y': y, 'w': 20.0, 'h': 8.0, 'thickness': 0.15}
        else:
            return None
        return self._append([e], 'Shape added')

    def delete_selected(self):
        ids = [i for i in sorted(self.selected, reverse=True) if not self.elements[i].get('locked')]
        if not ids:
            return None
        self.push_undo()
        for i in ids:
            self.elements.pop(i)
        self._prune_groups()
        self.selected = set()
        self.primary = None
        return 'Element(s) deleted'

    def duplicate_selected(self):
        if not self.selected:
            return None
        self.push_undo()
        new = []
        for i in sorted(self.selected):
            e = copy.deepcopy(self.elements[i])
            e['locked'] = False
            e['x'] = round(float(e.get('x', 0)) + 1, 3)
            e['y'] = round(float(e.get('y', 0)) + 1, 3)
            if 'x2' in e: e['x2'] = round(float(e.get('x2', 0)) + 1, 3)
            if 'y2' in e: e['y2'] = round(float(e.get('y2', 0)) + 1, 3)
            self.elements.append(e)
            new.append(len(self.elements) - 1)
        self._regroup_copies(new)
        self.set_selection(set(new), new[-1] if new else None)
        return 'Duplicated'

    def copy_selected(self):
        if not self.selected:
            return None
        self.clipboard = [copy.deepcopy(self.elements[i]) for i in sorted(self.selected)]
        return f'Copied {len(self.clipboard)} element(s)'

    def paste(self):
        if not self.clipboard:
            return None
        self.push_undo()
        new = []
        for e0 in self.clipboard:
            e = copy.deepcopy(e0)
            e['locked'] = False
            _shift(e, 2, 2)
            self.elements.append(e)
            new.append(len(self.elements) - 1)
        self._regroup_copies(new)
        self.clipboard = [copy.deepcopy(self.elements[i]) for i in new]     # next paste cascades
        self.set_selection(set(new), new[-1])
        return 'Pasted'

    def center_on_label(self, axis):
        ids = self._unlocked()
        if not ids:
            return None
        self.push_undo()
        pw = float(self.cfg.get('width_mm', 50)); ph = float(self.cfg.get('height_mm', 68))
        boxes = [source_box(self.elements[i]) for i in ids]
        minx = min(b[0] for b in boxes); maxx = max(b[0] + b[2] for b in boxes)
        miny = min(b[1] for b in boxes); maxy = max(b[1] + b[3] for b in boxes)
        dx = (pw - (maxx - minx)) / 2 - minx if axis == 'h' else 0.0
        dy = (ph - (maxy - miny)) / 2 - miny if axis == 'v' else 0.0
        for i in ids:
            _shift(self.elements[i], dx, dy)
        return 'Centered'

    def align_selected(self, mode):
        ids = self._unlocked()
        if len(ids) < 2:
            return None
        boxes = {i: source_box(self.elements[i]) for i in ids}
        self.push_undo()
        if mode == 'left': target = min(b[0] for b in boxes.values())
        elif mode == 'top': target = min(b[1] for b in boxes.values())
        elif mode == 'hcenter': target = sum(b[0] + b[2] / 2 for b in boxes.values()) / len(boxes)
        else: target = sum(b[1] + b[3] / 2 for b in boxes.values()) / len(boxes)
        for i in ids:
            e = self.elements[i]
            x, y, w, h = boxes[i]
            if mode == 'left': dx, dy = target - x, 0
            elif mode == 'top': dx, dy = 0, target - y
            elif mode == 'hcenter': dx, dy = target - (x + w / 2), 0
            else: dx, dy = 0, target - (y + h / 2)
            e['x'] = self._snap(float(e.get('x', 0)) + dx); e['y'] = self._snap(float(e.get('y', 0)) + dy)
            if 'x2' in e: e['x2'] = self._snap(float(e.get('x2', 0)) + dx)
            if 'y2' in e: e['y2'] = self._snap(float(e.get('y2', 0)) + dy)
        return 'Aligned'

    def nudge(self, sx, sy, big=False):
        ids = self._unlocked()
        if not ids:
            return None
        step = float(self.snap_mm or 0.1) * (10 if big else 1)
        self.push_undo()
        for i in ids:
            e = self.elements[i]
            sign = -1 if fold_for_element(self.cfg, e) is not None else 1
            dx = sx * step * sign; dy = sy * step * sign
            e['x'] = self._snap(float(e.get('x', 0)) + dx); e['y'] = self._snap(float(e.get('y', 0)) + dy)
            if 'x2' in e: e['x2'] = self._snap(float(e.get('x2', 0)) + dx)
            if 'y2' in e: e['y2'] = self._snap(float(e.get('y2', 0)) + dy)
        return 'Moved'

    def reorder(self, delta):
        if len(self.selected) != 1:
            return None
        i = self.primary
        ni = i + delta
        if ni < 0 or ni >= len(self.elements):
            return None
        self.push_undo()
        els = self.elements
        els[i], els[ni] = els[ni], els[i]
        self.set_selection({ni}, ni)
        return 'Layer order changed'

    def rotate_selected(self, delta):
        """Rotate by `delta` degrees: one element about its centre, several as one rigid block. None resets angles."""
        ids = self._unlocked()
        if not ids:
            return None
        self.push_undo()
        if delta is not None and len(ids) > 1:
            self._rotate_block(ids, float(delta))
            return 'Rotated'
        for i in ids:
            e = self.elements[i]
            _set_angle(e, 0.0 if delta is None else _element_angle(e) + float(delta))
        return 'Rotated'

    def _rotate_block(self, ids, delta):
        """Turn the elements about the centre of their common box, working in display space: a member may cross a
        fold band, where its source position is the mirror of what is shown and its angle carries the 180 degrees."""
        boxes = [outline_bbox(element_outline(self.cfg, self.elements[i])) for i in ids]
        px = (min(b[0] for b in boxes) + max(b[2] for b in boxes)) / 2
        py = (min(b[1] for b in boxes) + max(b[3] for b in boxes)) / 2
        for i in ids:
            e = self.elements[i]
            old_fold = fold_for_element(self.cfg, e) is not None
            sx, sy = element_rotation_center(e)
            cx, cy = visual_frame(self.cfg, e)[:2]
            nx, ny = rotate_point_cw(cx, cy, px, py, delta)
            fr = fold_at(self.cfg, ny)
            tx, ty = flip_point(fr, nx, ny) if fr is not None else (nx, ny)
            _shift(e, tx - sx, ty - sy)
            _set_angle(e, _element_angle(e) + delta + (180.0 if old_fold else 0.0) - (180.0 if fr is not None else 0.0))

    def set_element_text(self, index, text):
        """Edit one element's text by index (double click): the selection may be a whole group."""
        if not 0 <= index < len(self.elements):
            return None
        e = self.elements[index]
        if _etype(e) != 'text' or e.get('locked') or e.get('text') == text:
            return None
        self.push_undo()
        e['text'] = text
        return f"{FIELD_BY_KEY['text']['label']} changed"

    def change_font_size(self, direction, step=0.2):
        ids = [i for i in self._unlocked() if _etype(self.elements[i]) == 'text']
        if not ids:
            return None
        self.push_undo()
        for i in ids:
            e = self.elements[i]
            e['font_size'] = round(max(1.0, float(e.get('font_size', 8)) + direction * float(step)), 2)
        return 'Font size changed'

    def set_lock_selected(self, value):
        if not self.selected:
            return None
        self.push_undo()
        for i in self.selected:
            self.elements[i]['locked'] = bool(value)
        return 'Locked' if value else 'Unlocked'

    def set_print(self, ids, value):
        """Switch elements on/off for printing. They stay on the template (and in the designer) either way; locking
        only fixes the position, so locked elements can be switched too. "print" is stored only when off."""
        ids = [i for i in ids if 0 <= i < len(self.elements) and is_printed(self.elements[i]) != bool(value)]
        if not ids:
            return None
        self.push_undo()
        for i in ids:
            if value:
                self.elements[i].pop('print', None)
            else:
                self.elements[i]['print'] = False
        return 'Print on' if value else 'Print off'

    def toggle_print(self, index):
        if not 0 <= index < len(self.elements):
            return None
        return self.set_print([index], not is_printed(self.elements[index]))

    def unlock_all(self):
        if not any(e.get('locked') for e in self.elements):
            return None
        self.push_undo()
        for e in self.elements:
            e['locked'] = False
        return 'All elements unlocked'

    def show_virtual_area(self):
        a = virtual_area(self.cfg)
        a['show'] = True
        self.push_undo()
        self.cfg['virtual_print_area'] = a
        return 'Virtual area visible'

    def ensure_fold_line(self):
        if first_fold(self.cfg) is not None:
            return None
        self.push_undo()
        pw = float(self.cfg.get('width_mm', 56)); ph = float(self.cfg.get('height_mm', 83)); y = ph / 2
        self.cfg.setdefault('fold_regions', []).append(
            {'name': 'LOWER_FACE', 'x': 0.0, 'y': y, 'w': pw, 'h': ph - y, 'angle': 180, 'enabled': True})
        return 'Fold region added'

    # ------------------------------------------------------------------ overlay (what the view draws)
    def overlay(self):
        """Everything the canvas draws on top of the rendered label, in display millimetres."""
        cfg = self.cfg
        mpp = self.view_mm_per_px
        els = []
        for i, e in enumerate(cfg.get('elements', [])):
            try:
                pts = element_outline(cfg, e)
            except Exception:
                try:   # never drop an element's frame: fall back to its unrotated box
                    x, y, w, h = display_box_mm(cfg, e)
                    pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
                except Exception:
                    continue
            els.append({'index': i, 'type': _etype(e), 'locked': bool(e.get('locked')), 'printed': is_printed(e),
                        'selected': i in self.selected, 'rotated': element_is_rotated(e),
                        'poly': [[p[0], p[1]] for p in pts]})
        a = virtual_area(cfg)
        va = None
        if a.get('show', True):
            va = {'x': float(a['x']), 'y': float(a['y']), 'w': float(a['w']), 'h': float(a['h']),
                  'handles': self._virtual_handles(a)}
        fold = None
        fr = first_fold(cfg)
        if fr:
            fold = {'x1': float(fr.get('x', 0)), 'x2': float(fr.get('x', 0)) + float(fr.get('w', 0)), 'y': float(fr.get('y', 0))}
        return {'elements': els, 'handles': self.element_handles(), 'virtual': va, 'fold': fold,
                'handle_mm': HANDLE_PX * mpp}

    @staticmethod
    def _virtual_handles(a):
        if not a.get('show', True):
            return []
        x, y, w, h = float(a['x']), float(a['y']), float(a['w']), float(a['h'])
        return [{'role': r, 'x': hx, 'y': hy} for r, (hx, hy) in
                {'nw': (x, y), 'ne': (x + w, y), 'sw': (x, y + h), 'se': (x + w, y + h)}.items()]

    def element_handles(self):
        """Resize / rotate handles for exactly one unlocked selected element ([] otherwise)."""
        if len(self.selected) != 1:
            return []
        i = next(iter(self.selected))
        e = self.elements[i]
        if e.get('locked'):
            return []
        cfg = self.cfg
        t = _etype(e)
        handles = []
        rotated = element_is_rotated(e)
        if rotated:
            pts = frame_corners(visual_frame(cfg, e))
            if t != 'line':
                for role, (hx, hy) in zip(('nw', 'ne', 'se', 'sw'), pts):
                    handles.append({'role': role, 'x': hx, 'y': hy})
        elif t == 'line':
            (x1, y1), (x2, y2) = line_display_endpoints(cfg, e)
            handles += [{'role': 'line_start', 'x': x1, 'y': y1}, {'role': 'line_end', 'x': x2, 'y': y2}]
            pts = element_outline(cfg, e)
        else:
            x, y, w, h = display_box_mm(cfg, e)
            pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
            for role, (hx, hy) in {'nw': (x, y), 'ne': (x + w, y), 'sw': (x, y + h), 'se': (x + w, y + h)}.items():
                handles.append({'role': role, 'x': hx, 'y': hy})
        fcx, fcy, _fw, _fh, _th = visual_frame(cfg, e)
        mx = (pts[0][0] + pts[1][0]) / 2; my = (pts[0][1] + pts[1][1]) / 2
        ux = mx - fcx; uy = my - fcy; ul = math.hypot(ux, uy)
        if ul < 1e-6:
            ux, uy, ul = 0.0, -1.0, 1.0
        k = ROTATE_KNOB_PX * self.view_mm_per_px
        handles.append({'role': 'rotate', 'x': mx + ux / ul * k, 'y': my + uy / ul * k, 'edge_x': mx, 'edge_y': my,
                        'cx': fcx, 'cy': fcy})
        return handles

    # ------------------------------------------------------------------ hit testing
    def hit_element(self, x, y, pad_mm=None):
        pad = HIT_PAD_PX * self.view_mm_per_px if pad_mm is None else pad_mm
        for i in range(len(self.elements) - 1, -1, -1):
            e = self.elements[i]
            try:
                pts = element_outline(self.cfg, e)
            except Exception:
                continue
            if element_is_rotated(e):
                if point_near_poly(pts, x, y, pad):
                    return i
            else:
                x1, y1, x2, y2 = outline_bbox(pts)
                if x1 - pad <= x <= x2 + pad and y1 - pad <= y <= y2 + pad:
                    return i
        return None

    def _hit_handle(self, handles, x, y):
        r = HANDLE_PX * self.view_mm_per_px
        for h in handles:
            pad = (r + 1 * self.view_mm_per_px) if h['role'] != 'rotate' else 9 * self.view_mm_per_px
            if abs(x - h['x']) <= pad and abs(y - h['y']) <= pad:
                return h['role']
        return None

    def _hit_virtual_border(self, x, y):
        a = virtual_area(self.cfg)
        if not a.get('show', True):
            return False
        x1, y1 = float(a['x']), float(a['y'])
        x2, y2 = x1 + float(a['w']), y1 + float(a['h'])
        p = 6 * self.view_mm_per_px
        return ((x1 - p <= x <= x2 + p and (abs(y - y1) <= p or abs(y - y2) <= p)) or
                (y1 - p <= y <= y2 + p and (abs(x - x1) <= p or abs(x - x2) <= p)))

    def _hit_fold(self, x, y):
        fr = first_fold(self.cfg)
        if not fr:
            return False
        x1 = float(fr.get('x', 0)); x2 = x1 + float(fr.get('w', 0)); yy = float(fr.get('y', 0))
        return min(x1, x2) - 8 * self.view_mm_per_px <= x <= max(x1, x2) + 8 * self.view_mm_per_px and abs(y - yy) <= 7 * self.view_mm_per_px

    def hover(self, x, y):
        """What is under the pointer: {'element': index|-1, 'role': handle/fold/virtual role or ''} (cursor + hover feedback)."""
        role = self._hit_handle(self.element_handles(), x, y) if len(self.selected) == 1 else None
        if role:
            return {'element': -1, 'role': 'rotate' if role == 'rotate' else 'resize:' + role}
        vrole = self._hit_handle(self._virtual_handles(virtual_area(self.cfg)), x, y)
        if vrole:
            return {'element': -1, 'role': 'resize:' + vrole}
        if self._hit_fold(x, y):
            return {'element': -1, 'role': 'fold'}
        idx = self.hit_element(x, y)
        if idx is not None:
            return {'element': idx, 'role': 'move' if not self.elements[idx].get('locked') else 'locked'}
        if self._hit_virtual_border(x, y):
            return {'element': -1, 'role': 'virtual'}
        return {'element': -1, 'role': ''}

    # ------------------------------------------------------------------ pointer interaction
    def press(self, x, y, shift=False):
        """Start an interaction at display point (x, y) mm. Returns the mode: move | element_resize |
        element_rotate | virtual_move | virtual_resize | fold_move | marquee | select | none."""
        d = {'start': (x, y), 'before': self.snapshot(), 'original': None, 'role': None, 'mode': None}
        self._drag = d
        handles = self.element_handles()
        role = self._hit_handle(handles, x, y)
        if role and len(self.selected) == 1:
            e0 = self.elements[self.primary]
            d['role'] = role
            d['original'] = copy.deepcopy(e0)
            if role == 'rotate':
                hr = next(h for h in handles if h['role'] == 'rotate')
                d['center'] = (hr['cx'], hr['cy'])
                d['mode'] = 'element_rotate'
            else:
                d['mode'] = 'element_resize'
            return d['mode']
        va = virtual_area(self.cfg)
        vrole = self._hit_handle(self._virtual_handles(va), x, y)
        if vrole:
            d.update(mode='virtual_resize', role=vrole, original=copy.deepcopy(va))
            return d['mode']
        if self._hit_fold(x, y):
            fr0 = copy.deepcopy(first_fold(self.cfg))
            members = {i: copy.deepcopy(e) for i, e in enumerate(self.elements) if element_in_fold_region(e, fr0)}
            d.update(mode='fold_move', original={'fold': fr0, 'members': members})
            return d['mode']
        idx = self.hit_element(x, y)
        if idx is not None:
            if shift:
                ns = set(self.selected)
                members = self.with_groups({idx})
                if idx in ns: ns -= members
                else: ns |= members
                self.set_selection(ns, idx if idx in ns else (min(ns) if ns else None))
                d['mode'] = None
                return 'select'
            if idx not in self.selected:
                self.set_selection(self.with_groups({idx}), idx)
            else:
                self.primary = idx
            movable = [i for i in self.selected if not self.elements[i].get('locked', False)]
            if movable:
                d.update(mode='move', original={i: copy.deepcopy(self.elements[i]) for i in movable})
                return 'move'
            d['mode'] = None
            return 'select'
        if self._hit_virtual_border(x, y):
            d.update(mode='virtual_move', original=copy.deepcopy(va))
            return d['mode']
        if not shift:
            self.set_selection(set(), None)
        d['mode'] = 'marquee'
        return 'marquee'

    def _drag_delta(self, x, y):
        d = self._drag
        return x - d['start'][0], y - d['start'][1]

    def _rotate_angle(self, x, y, shift):
        d = self._drag
        e = d['original']
        ccx, ccy = d['center']
        view = math.degrees(math.atan2(y - ccy, x - ccx)) + 90.0
        if _etype(e) == 'line':
            base = math.degrees(math.atan2(float(e.get('y2', e.get('y', 0))) - float(e.get('y', 0)),
                                           float(e.get('x2', e.get('x', 0))) - float(e.get('x', 0))))
        else:
            base = 0.0
        if fold_for_element(self.cfg, e) is not None:
            base += 180.0
        ang = view - base
        step = 15.0 if shift else 1.0
        ang = round(ang / step) * step
        return ((ang + 180.0) % 360.0) - 180.0

    def _apply_drag(self, cfg, x, y, shift):
        """Apply the current drag to `cfg` (the real document on release, a scratch copy while dragging)."""
        d = self._drag
        mode = d['mode']
        dxm, dym = self._drag_delta(x, y)
        els = cfg['elements']
        orig = d['original']
        if mode == 'move':
            for i, o in orig.items():
                e = els[i]
                sx, sy = (-dxm, -dym) if fold_for_element(cfg, o) is not None else (dxm, dym)
                ox = float(o.get('x', 0)); oy = float(o.get('y', 0))
                e['x'] = self._snap(ox + sx); e['y'] = self._snap(oy + sy)
                if 'x2' in o: e['x2'] = self._snap(float(o.get('x2', ox)) + sx)
                if 'y2' in o: e['y2'] = self._snap(float(o.get('y2', oy)) + sy)
            return True
        if mode == 'element_rotate':
            _set_angle(els[self.primary], self._rotate_angle(x, y, shift))
            return True
        if mode == 'element_resize':
            e = els[self.primary]
            role = d['role']
            t = _etype(orig)
            if t == 'line':
                sx, sy = (-dxm, -dym) if fold_for_element(cfg, orig) is not None else (dxm, dym)
                if role == 'line_start':
                    e['x'] = self._snap(float(orig.get('x', 0)) + sx); e['y'] = self._snap(float(orig.get('y', 0)) + sy)
                else:
                    e['x2'] = self._snap(float(orig.get('x2', orig.get('x', 0))) + sx)
                    e['y2'] = self._snap(float(orig.get('y2', orig.get('y', 0))) + sy)
                return True
            bx, by, bw, bh = display_box_mm(cfg, orig)
            nx, ny, nw, nh = bx, by, bw, bh
            minsz = .5
            th = visual_frame(cfg, orig)[4] if abs(_element_angle(orig)) > 0.0001 else 0.0
            if th:
                dxm, dym = rotate_point_cw(dxm, dym, 0, 0, -th)      # pointer delta in the element's own frame
            if 'w' in role: nx = bx + dxm; nw = bw - dxm
            if 'e' in role: nw = bw + dxm
            if 'n' in role: ny = by + dym; nh = bh - dym
            if 's' in role: nh = bh + dym
            if nw < minsz:
                if 'w' in role: nx -= minsz - nw
                nw = minsz
            if nh < minsz:
                if 'n' in role: ny -= minsz - nh
                nh = minsz
            if th:
                # keep the opposite corner fixed on the page although the centre (rotation pivot) moves
                ax = bx if 'e' in role else bx + bw
                ay = by if 's' in role else by + bh
                oc = (bx + bw / 2, by + bh / 2); nc = (nx + nw / 2, ny + nh / 2)
                wa = rotate_point_cw(ax, ay, oc[0], oc[1], th); wb = rotate_point_cw(ax, ay, nc[0], nc[1], th)
                nx += wa[0] - wb[0]; ny += wa[1] - wb[1]
            sx, sy, sw, sh = display_to_source_box(cfg, orig, (nx, ny, nw, nh))
            e['x'] = self._snap(sx); e['y'] = self._snap(sy); e['w'] = self._snap(sw); e['h'] = self._snap(sh)
            return True
        if mode == 'virtual_move':
            a = orig
            cfg['virtual_print_area'] = {'show': True, 'x': self._snap(float(a.get('x', 0)) + dxm), 'y': self._snap(float(a.get('y', 0)) + dym),
                                         'w': float(a.get('w', 1)), 'h': float(a.get('h', 1))}
            return True
        if mode == 'virtual_resize':
            a = orig
            vx = float(a.get('x', 0)); vy = float(a.get('y', 0)); vw = float(a.get('w', 1)); vh = float(a.get('h', 1))
            nx, ny, nw, nh = vx, vy, vw, vh
            r = d['role']
            minsz = 1.0
            if 'w' in r: nx = vx + dxm; nw = vw - dxm
            if 'e' in r: nw = vw + dxm
            if 'n' in r: ny = vy + dym; nh = vh - dym
            if 's' in r: nh = vh + dym
            nw = max(nw, minsz); nh = max(nh, minsz)
            cfg['virtual_print_area'] = {'show': True, 'x': self._snap(nx), 'y': self._snap(ny), 'w': self._snap(nw), 'h': self._snap(nh)}
            return True
        if mode == 'fold_move':
            fr = first_fold(cfg)
            orig_fold = orig.get('fold')
            if fr and orig_fold:
                oldy = float(orig_fold.get('y', 0)); bottom = oldy + float(orig_fold.get('h', 0))
                newy = min(self._snap(oldy + dym), bottom - 1.0)
                delta = newy - oldy
                fr['y'] = newy; fr['h'] = round(bottom - newy, 3)
                # keep back-face elements visually fixed: compensate in source coordinates
                for i, e0 in (orig.get('members') or {}).items():
                    if 0 <= i < len(els):
                        e = els[i]
                        if 'y' in e0: e['y'] = self._snap(float(e0.get('y', 0)) + delta)
                        if 'y2' in e0: e['y2'] = self._snap(float(e0.get('y2', e0.get('y', 0))) + delta)
                return True
            return False
        return False

    def drag_ghost(self, x, y, shift=False):
        """Lightweight description of the tentative result while the pointer is down (nothing is committed)."""
        d = self._drag
        if not d or not d['mode']:
            return None
        mode = d['mode']
        if mode == 'marquee':
            return {'mode': 'marquee', 'rect': [d['start'][0], d['start'][1], x, y]}
        scratch = copy.deepcopy(self.cfg)
        if not self._apply_drag(scratch, x, y, shift):
            return None
        ghost = {'mode': mode, 'polys': [], 'text': ''}
        if mode in ('move', 'element_resize', 'element_rotate'):
            ids = list(d['original'].keys()) if mode == 'move' else [self.primary]
            for i in ids:
                ghost['polys'].append([[p[0], p[1]] for p in element_outline(scratch, scratch['elements'][i])])
            dxm, dym = self._drag_delta(x, y)
            ghost['text'] = (f'Rotate {scratch["elements"][self.primary].get("angle", 0):g}°' if mode == 'element_rotate'
                             else f'Δ {dxm:+.1f}, {dym:+.1f} mm')
        elif mode in ('virtual_move', 'virtual_resize'):
            a = scratch['virtual_print_area']
            ghost['area'] = [a['x'], a['y'], a['w'], a['h']]
            ghost['text'] = f"Print area {a['w']:g} × {a['h']:g} mm"
        elif mode == 'fold_move':
            fr = first_fold(scratch)
            ghost['fold_y'] = float(fr['y'])
            ghost['text'] = f"Fold at {float(fr['y']):g} mm"
        return ghost

    def marquee_select(self, x1, y1, x2, y2, additive=False):
        lx, hx = sorted((x1, x2)); ly, hy = sorted((y1, y2))
        hits = set(self.selected) if additive else set()
        for i, e in enumerate(self.elements):
            bx1, by1, bx2, by2 = outline_bbox(element_outline(self.cfg, e))
            if not (bx2 < lx or bx1 > hx or by2 < ly or by1 > hy):
                hits.add(i)
        hits = self.with_groups(hits)
        self.set_selection(hits, min(hits) if hits else None)

    def release(self, x, y, shift=False):
        """Finish the interaction. Returns a status note when the document changed, else None."""
        d = self._drag
        if not d or not d['mode']:
            self._drag = None
            return None
        mode = d['mode']
        try:
            dx, dy = self._drag_delta(x, y)
            tiny = abs(dx) < self.view_mm_per_px and abs(dy) < self.view_mm_per_px
            if mode == 'marquee':
                if not tiny:
                    self.marquee_select(d['start'][0], d['start'][1], x, y, additive=shift)
                return None
            if mode != 'element_rotate' and tiny:
                return None
            if not self._apply_drag(self.cfg, x, y, shift):
                return None
        finally:
            self._drag = None
        self.push_undo(d['before'])
        self.sanitize_selection()
        return {'move': 'Moved', 'element_resize': 'Resized', 'element_rotate': 'Rotated', 'virtual_move': 'Print area moved',
                'virtual_resize': 'Print area resized', 'fold_move': 'Fold moved'}.get(mode, 'Changed')

    def cancel_drag(self):
        self._drag = None
