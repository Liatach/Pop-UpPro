"""v0.36: pieces too big for the piece paper get a sheet they fit (no more
spilling onto the next sheet, e.g. an A4 carousel's frames); Done Drawing
leaves the layout drawing mode and puts the view back."""
# families: export, drawing
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
import popup_pro as addon  # noqa: E402
from popup_pro import build, carousel  # noqa: E402

addon.register()
sc = bpy.context.scene


def check_layout(scene):
    model, lay = build.make_model(scene)
    boxes = []
    for name, piece in model.pieces.items():
        if not piece.panels:
            continue
        M = lay["prints"][name]
        pts = [(M @ Vector((q[0], q[1], 0.0))) for n in piece.panels
               for poly in model.panels[n].polys for q in poly]
        bb = (min(v.x for v in pts), min(v.y for v in pts), max(v.x for v in pts),
              max(v.y for v in pts))
        sh = lay["sheets"][lay["on_sheet"][name]]
        x0, y0 = sh.origin
        w, h = sh.size
        assert bb[0] >= x0 - 1e-3 and bb[2] <= x0 + w + 1e-3, (name, bb, sh.origin, sh.size)
        assert bb[1] >= y0 - 1e-3 and bb[3] <= y0 + h + 1e-3, (name, bb, sh.origin, sh.size)
        boxes.append((name, bb))
    for i, (a, ba) in enumerate(boxes):
        for b, bb in boxes[i + 1:]:
            ox = min(ba[2], bb[2]) - max(ba[0], bb[0])
            oy = min(ba[3], bb[3]) - max(ba[1], bb[1])
            assert ox <= 0.01 or oy <= 0.01, (a, b, ba, bb)
    for i, s in enumerate(lay["sheets"][1:], 1):
        p = lay["sheets"][i - 1]
        assert s.origin[0] >= p.origin[0] + p.size[0], "sheets overlap"
    return model


for size in ("A4", "A5", "A3"):
    addon.unregister()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon.register()
    sc = bpy.context.scene
    sc.popup.size = size
    assert bpy.ops.popup.make_carousel(count=5) == {"FINISHED"}
    for stage in carousel.stages(sc):
        check_layout(stage)
    print(size, "carousel: every piece inside its own sheet, nothing overlapping")

# ---- Done Drawing: back to Object Mode, the view and the active object
addon.unregister()
bpy.ops.wm.read_factory_settings(use_empty=True)
addon.register()
sc = bpy.context.scene
assert bpy.ops.popup.build() == {"FINISHED"}
card = sc.popup.card
bpy.context.view_layer.objects.active = card
assert bpy.ops.popup.draw_holes() == {"FINISHED"}
assert "pop_active_before" in sc
from popup_pro import ops  # noqa: E402
assert bpy.ops.popup.done_drawing() == {"FINISHED"}
assert bpy.context.mode == "OBJECT"
assert bpy.context.view_layer.objects.active == card
assert "pop_active_before" not in sc and "pop_view_before" not in sc
assert not ops.drawing(bpy.context)
print("Done Drawing goes back")
print("all v36 checks pass")
