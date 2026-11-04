"""LabelEditor: selection, edits, undo/redo and pointer interaction — all in millimetres, independent of zoom."""
import copy

import pytest

from labelapp.core.designer_geometry import element_outline, outline_bbox
from labelapp.core.editor import LabelEditor


@pytest.fixture
def ed(templates):
    e = LabelEditor(templates["Hang_Tag_50x68.json"])
    e.view_mm_per_px = 0.25
    return e


def centre(ed, i):
    poly = [p for p in ed.overlay()["elements"] if p["index"] == i][0]["poly"]
    return (sum(p[0] for p in poly) / 4, sum(p[1] for p in poly) / 4)


def test_move_commits_snapped_delta_and_undo_redo(ed):
    x0, y0 = ed.elements[1]["x"], ed.elements[1]["y"]
    cx, cy = centre(ed, 1)
    assert ed.press(cx, cy) == "move"
    assert ed.release(cx + 3.04, cy + 2.0) == "Moved"
    assert ed.elements[1]["x"] == pytest.approx(x0 + 3.0) and ed.elements[1]["y"] == pytest.approx(y0 + 2.0)
    ed.undo()
    assert ed.elements[1]["x"] == x0
    ed.redo()
    assert ed.elements[1]["x"] == pytest.approx(x0 + 3.0)


def test_move_result_does_not_depend_on_zoom(templates):
    results = []
    for mpp in (0.05, 0.26, 1.2):                       # very different zoom levels
        e = LabelEditor(templates["Hang_Tag_50x68.json"])
        e.view_mm_per_px = mpp
        cx, cy = centre(e, 1)
        e.press(cx, cy)
        e.release(cx + 5, cy + 4)
        results.append((e.elements[1]["x"], e.elements[1]["y"]))
    assert results[0] == results[1] == results[2]


def test_view_scale_never_changes_document(ed):
    before = copy.deepcopy(ed.cfg)
    for mpp in (0.01, 0.5, 3):
        ed.view_mm_per_px = mpp
        ed.overlay()
    assert ed.cfg == before


def test_resize_handle_and_minimum_size(ed):
    ed.set_selection({1}, 1)
    h = next(h for h in ed.element_handles() if h["role"] == "se")
    w0 = ed.elements[1]["w"]
    ed.press(h["x"], h["y"])
    ed.release(h["x"] + 2, h["y"] + 1)
    assert ed.elements[1]["w"] == pytest.approx(w0 + 2)
    h = next(h for h in ed.element_handles() if h["role"] == "se")
    ed.press(h["x"], h["y"])
    ed.release(h["x"] - 500, h["y"] - 500)
    assert ed.elements[1]["w"] >= 0.5 and ed.elements[1]["h"] >= 0.5


def test_rotate_handle_sets_angle_with_shift_snapping(ed):
    ed.set_selection({1}, 1)
    r = next(h for h in ed.element_handles() if h["role"] == "rotate")
    ed.press(r["x"], r["y"])
    assert ed.release(r["cx"] + 10, r["cy"] + 0.0, shift=True) == "Rotated"
    assert ed.elements[1]["angle"] == pytest.approx(90.0)


def test_marquee_selects_intersecting_elements(ed):
    ed.set_selection(set(), None)
    assert ed.press(-3, -3) == "marquee"
    ed.release(30, 9)
    assert {0, 1, 2}.issubset(ed.selected)


def test_shift_click_toggles_selection(ed):
    ed.set_selection({1}, 1)
    cx, cy = centre(ed, 2)
    ed.press(cx, cy, shift=True)
    assert ed.selected == {1, 2}
    ed.press(cx, cy, shift=True)
    assert ed.selected == {1}


def test_fold_move_keeps_back_face_visually_fixed(ed):
    fold = ed.overlay()["fold"]
    members = [i for i, e in enumerate(ed.elements) if e.get("y", 0) > fold["y"]]
    before = {i: [round(c, 3) for c in ed.overlay()["elements"][i]["poly"][0]] for i in members}
    ed.press(fold["x1"] + 0.5, fold["y"])
    assert ed.release(fold["x1"] + 0.5, fold["y"] - 3) == "Fold moved"
    after_fold = ed.overlay()["fold"]["y"]
    assert after_fold == pytest.approx(fold["y"] - 3)
    # back-face members are mirrored about the fold region centre: their final positions must not jump
    for i in members:
        assert [round(c, 3) for c in ed.overlay()["elements"][i]["poly"][0]] == before[i]


def test_locked_elements_do_not_move(ed):
    ed.set_selection({1}, 1)
    ed.set_lock_selected(True)
    x0 = ed.elements[1]["x"]
    cx, cy = centre(ed, 1)
    assert ed.press(cx, cy) == "select"
    assert ed.release(cx + 5, cy + 5) is None and ed.elements[1]["x"] == x0
    assert ed.nudge(1, 0) is None


def test_set_prop_applies_to_all_selected_and_respects_types(ed):
    ed.set_selection({1, 2}, 1)                             # two text elements
    assert ed.set_prop("font_size", "9,5")
    assert ed.elements[1]["font_size"] == 9.5 and ed.elements[2]["font_size"] == 9.5
    assert ed.set_prop("thickness", 1) is None              # not applicable to text
    ed.set_prop("prefix", "€")
    assert ed.elements[1]["prefix"] == "€"
    ed.set_prop("prefix", "")
    assert "prefix" not in ed.elements[1]                   # empty removes optional keys, like the Tk style tab


def test_inspector_reports_mixed_values(ed):
    ed.set_selection({1, 2}, 1)
    ed.set_prop("font_size", 8)
    ed.elements[2]["font_size"] = 9
    f = {x["key"]: x for x in ed.inspector_fields()}
    assert f["font_size"]["mixed"] is True and f["font_size"]["value"] is None
    assert f["y"]["mixed"] is True


def test_add_delete_duplicate_copy_paste(ed):
    n = len(ed.elements)
    assert ed.add_text("Hello") and len(ed.elements) == n + 1 and ed.primary == n
    assert ed.add_fields(["Brand", "Model"]) and len(ed.elements) == n + 3
    ed.set_selection({n}, n)
    assert ed.duplicate_selected() and len(ed.elements) == n + 4
    ed.copy_selected()
    assert ed.paste() and len(ed.elements) == n + 5
    assert ed.delete_selected() and len(ed.elements) == n + 4
    assert ed.add_special("image") is None                  # needs a path
    assert ed.add_special("qr") and ed.elements[-1]["type"] == "qr"


def test_align_center_reorder(ed):
    ed.set_selection({1, 2}, 1)
    ed.align_selected("left")
    assert ed.elements[1]["x"] == ed.elements[2]["x"]
    ed.set_selection({1}, 1)
    ed.center_on_label("h")
    e = ed.elements[1]
    assert e["x"] + e["w"] / 2 == pytest.approx(25.0)
    ed.reorder(1)
    assert ed.primary == 2


def test_doc_settings_validate(ed):
    assert ed.set_doc(width_mm="60", height_mm=40, dpi=203) and ed.cfg["width_mm"] == 60.0 and ed.cfg["dpi"] == 203
    assert ed.set_doc(width_mm=-1, dpi=0) is None           # invalid values are ignored
    assert ed.set_doc(orientation="landscape") and ed.cfg["orientation"] == "landscape"
    assert ed.set_doc(orientation="sideways") is None


def test_undo_stack_is_bounded(ed):
    ed.set_selection({1}, 1)
    for _ in range(80):
        ed.nudge(1, 0)
    assert len(ed.undo_stack) == 60

def test_group_click_selects_all_and_moves_together(ed):
    ed.set_selection({1, 2}, 1)
    assert ed.can_group and ed.group_selected() == "Grouped"
    assert ed.selection_is_group and not ed.can_group and ed.can_ungroup
    ed.set_selection(set(), None)
    x1, x2 = ed.elements[1]["x"], ed.elements[2]["x"]
    cx, cy = centre(ed, 2)
    assert ed.press(cx, cy) == "move" and ed.selected == {1, 2}
    ed.release(cx + 2.0, cy)
    assert ed.elements[1]["x"] == pytest.approx(x1 + 2) and ed.elements[2]["x"] == pytest.approx(x2 + 2)
    ed.undo()
    assert ed.ungroup_selected() == "Ungrouped"
    assert not any("group_id" in e for e in ed.elements)
    ed.undo()
    assert ed.elements[1]["group_id"] == ed.elements[2]["group_id"]


def test_marquee_takes_whole_group_and_list_pick_stays_single(ed):
    ed.set_selection({1, 2}, 1)
    ed.group_selected()
    ed.set_selection(set(), None)
    cx, cy = centre(ed, 1)
    ed.marquee_select(cx - 0.1, cy - 0.1, cx + 0.1, cy + 0.1)
    assert {1, 2} <= ed.selected
    ed.set_selection({2}, 2)                                 # the layer list edits one member
    assert ed.selected == {2} and ed.can_ungroup and not ed.can_group


def test_group_hides_fields_that_would_collapse_its_layout(ed):
    ed.set_selection({1, 2}, 1)
    assert "x" in [f["key"] for f in ed.inspector_fields()]
    ed.group_selected()
    keys = [f["key"] for f in ed.inspector_fields()]
    assert "x" not in keys and "text" not in keys and "font_size" in keys


def test_copies_of_a_group_get_their_own_group(ed):
    ed.set_selection({1, 2}, 1)
    ed.group_selected()
    gid = ed.elements[1]["group_id"]
    ed.duplicate_selected()
    a, b = ed.elements[-2], ed.elements[-1]
    assert a["group_id"] == b["group_id"] != gid
    ed.set_selection({1, 2}, 1)
    ed.copy_selected()
    ed.paste()
    assert ed.elements[-1]["group_id"] not in (gid, a["group_id"])


def test_deleting_down_to_one_member_dissolves_the_group(ed):
    ed.set_selection({1, 2}, 1)
    ed.group_selected()
    ed.set_selection({2}, 2)
    ed.delete_selected()
    assert not any("group_id" in e for e in ed.elements)


def test_double_click_edit_changes_one_member_only(ed):
    ed.set_selection({1, 2}, 1)
    ed.group_selected()
    other = ed.elements[2]["text"]
    assert ed.set_element_text(1, "Mới")
    assert ed.elements[1]["text"] == "Mới" and ed.elements[2]["text"] == other


def test_block_rotation_is_rigid_across_a_fold(ed):
    from labelapp.core.designer_geometry import visual_frame
    from labelapp.core.geometry import rotate_point_cw
    ed.select_all()
    ed.group_selected()
    before = [visual_frame(ed.cfg, e) for e in ed.elements]
    boxes = [outline_bbox(element_outline(ed.cfg, e)) for e in ed.elements]
    px = (min(b[0] for b in boxes) + max(b[2] for b in boxes)) / 2
    py = (min(b[1] for b in boxes) + max(b[3] for b in boxes)) / 2
    assert ed.rotate_selected(90) == "Rotated"
    for f0, f1 in zip(before, [visual_frame(ed.cfg, e) for e in ed.elements]):
        tx, ty = rotate_point_cw(f0[0], f0[1], px, py, 90)
        assert (f1[0], f1[1]) == pytest.approx((tx, ty), abs=0.01)
        assert (f1[4] - f0[4] - 90) % 360 == pytest.approx(0, abs=0.02) or (f1[4] - f0[4] - 90) % 360 == pytest.approx(360, abs=0.02)


def test_four_quarter_turns_restore_the_block(ed):
    ed.select_all()
    before = copy.deepcopy(ed.elements)
    for _ in range(4):
        ed.rotate_selected(90)
    for a, b in zip(before, ed.elements):
        assert float(b["x"]) == pytest.approx(float(a["x"]), abs=0.02) and float(b["y"]) == pytest.approx(float(a["y"]), abs=0.02)
        assert float(b.get("angle", 0)) % 360 == pytest.approx(float(a.get("angle", 0)) % 360, abs=0.02)
