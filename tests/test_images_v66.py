"""v0.66: widths grow one way (pictures, stand-up pictures, flaps), pictures
on the 45 degree triangles laid along the crease by default, and Align
relative to the fold or card by default."""
# families: images, standups, align
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
import popup_pro as addon  # noqa: E402
from popup_pro.core.geom import v3  # noqa: E402
from popup_pro.core.model import Model  # noqa: E402

addon.register()
sc = bpy.context.scene
st = sc.popup
st.live = False
assert st.align_to == "HOST"  # Align: to the fold / card unless you pick otherwise
card = st.card_dict()


def flat_span(model, names, axis):
    """Min and max of the panels' points, open flat, along a card axis."""
    vals = [(model.panels[n].asm(180.0) @ v3(q))[axis] for n in names
            for poly in model.panels[n].polys for q in poly]
    return min(vals), max(vals)


# ---- a stand-up's picture grows up the fold from its bridge's start
for stand in ("UPRIGHT", "TAIL", "FLAT"):
    spans = []
    for w in (40.0, 80.0):
        m = dict(uid=1, type="STANDUP", label="S", y=50.0, width=30.0, height=25.0,
                 depth=20.0, img_w=w, img_h=60.0, tab=10.0, host=0, stand=stand)
        M = Model(card, [m])
        pic = "Stand1.AC" if stand == "FLAT" else "Stand1.CB"
        spans.append(flat_span(M, [pic], 1))
    assert abs(spans[0][0] - 50.0) < 1e-3 and abs(spans[1][0] - 50.0) < 1e-3, (stand, spans)
    assert abs(spans[1][1] - spans[0][1] - 40.0) < 1e-3, (stand, spans)
print("stand-up pictures grow up the fold from the bridge's start")

# ---- a flap's width runs on from where its hinge starts
for side, hinge, axis in (("R", "TOP", 0), ("L", "BOTTOM", 0), ("R", "LEFT", 1)):
    spans = []
    for w in (30.0, 60.0):
        m = dict(uid=1, type="FLAP", label="F", y=120.0, x=30.0, width=w, length=30.0,
                 tab=8.0, host=0, side=side, hinge=hinge, angle=150.0, strip=10.0,
                 glue_at=15.0, gap=4.0, pull_out=30.0)
        M = Model(card, [m])
        spans.append(flat_span(M, ["Flap1.Flap"], axis))
    if axis == 0:
        sgn = -1.0 if side == "L" else 1.0
        near = [min(abs(a), abs(b)) for a, b in spans]
        far = [max(abs(a), abs(b)) for a, b in spans]
        assert abs(near[0] - 30.0) < 1e-3 and abs(near[1] - 30.0) < 1e-3, spans
        assert abs(far[1] - far[0] - 30.0) < 1e-3, spans
    else:
        assert abs(spans[0][0] - 120.0) < 1e-3 and abs(spans[1][0] - 120.0) < 1e-3, spans
        assert abs(spans[1][1] - spans[0][1] - 30.0) < 1e-3, spans
print("flaps grow from where their hinge starts")

# ---- a picture grows from its bottom left corner
spans = []
for w in (20.0, 50.0):
    M = Model(card, [dict(uid=1, type="PICTURE", label="P", host=0, face="Page.R", x=10.0,
                          y=30.0, img_w=w, img_h=25.0, turn=0.0)])
    spans.append(flat_span(M, ["Pic1.Face"], 0))
assert abs(spans[0][0] - spans[1][0]) < 1e-3 and abs(spans[1][1] - spans[0][1] - 30.0) < 1e-3
print("pictures grow from their corner")
print("v0.66 OK")
