"""Data binding: {{Column}} placeholders, per-element text options, and row -> template resolution."""
import copy

from .models import PLACEHOLDER_RE, normalize_cfg

def format_binding_value(key, v):
    if v is None:
        return ""
    if key.lower() == "price":
        if isinstance(v, (int, float)):
            return f"{int(round(v)):,} VNĐ"
        s = str(v).strip()
        if not s:
            return ""
        compact = s.replace(",", "").replace(".", "").replace(" ", "")
        if compact.isdigit():
            return f"{int(compact):,} VNĐ"
        return s
    if key.lower() == "barcode":
        if isinstance(v, float) and v.is_integer():
            return str(int(v))
        return str(v).strip()
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)

def resolve_row_value(row, column_name):
    """Resolve a source column dynamically. Exact header wins; trimmed/case-insensitive is fallback."""
    if column_name in row:
        return row.get(column_name, "")
    wanted = str(column_name).strip().casefold()
    for k, v in row.items():
        if str(k).strip().casefold() == wanted:
            return v
    return ""

def replace_placeholders(value, row, bindings):
    if not isinstance(value, str):
        return value
    def repl(m):
        key = m.group(1).strip()
        col = bindings.get(key, key)
        return format_binding_value(key, resolve_row_value(row, col))
    return PLACEHOLDER_RE.sub(repl, value)

def apply_text_options(e, text):
    """Per-element text formatting: transform (upper/lower/title), prefix, suffix. Skipped when the text is empty."""
    text = str(text)
    if not text.strip():
        return text
    mode = str(e.get("transform", "") or "").lower()
    if mode == "upper":
        text = text.upper()
    elif mode == "lower":
        text = text.lower()
    elif mode == "title":
        text = text.title()
    return f"{e.get('prefix', '') or ''}{text}{e.get('suffix', '') or ''}"

def bind_row_to_template(template_cfg, row):
    cfg = copy.deepcopy(normalize_cfg(template_cfg))
    bindings = dict(cfg.get("data_bindings", {}))
    for e in cfg["elements"]:
        if "text" in e:
            e["text"] = apply_text_options(e, replace_placeholders(e["text"], row, bindings))
        if "value" in e:
            e["value"] = replace_placeholders(e["value"], row, bindings)
        if "path" in e:
            e["path"] = replace_placeholders(e["path"], row, bindings)
    # "show_if": "{{Field}}" -> element is dropped for rows where that field is empty.
    cfg["elements"] = [e for e in cfg["elements"]
                       if not e.get("show_if") or replace_placeholders(str(e["show_if"]), row, bindings).strip()]
    copies_col = bindings.get("Copies", "Copies")
    if row.get(copies_col) not in (None, ""):
        try:
            cfg["copies"] = max(1, int(float(row[copies_col])))
        except Exception:
            pass
    return cfg
