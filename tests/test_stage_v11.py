"""v0.11: a stage set standing in an ordinary card (Birmingham 118 mounted as a
V-fold), with frames and a ceiling inside it and an opening carried through
to its background."""
# families: stage, holes
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "tests", "out")
os.makedirs(OUT, exist_ok=True)

import bpy  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
import popup_pro as addon  # noqa: E402
from mathutils import Vector  # noqa: E402
from popup_pro import build, export_svg, holes  # noqa: E402

addon.register()
sc = bpy.context.scene
st = sc.popup
st.live = False


def refused(**kw):
    try:
        return bpy.ops.popup.add(**kw) == {"CANCELLED"}
    except RuntimeError:  # reported as an error
        return True


assert refused(kind="FLOOR")  # no stage to stand in yet (frames go on a plain card, v0.64)
assert bpy.ops.popup.add(kind="STAGE") == {"FINISHED"}
assert [m.kind for m in st.mechs] == ["STAGE", "FRAME", "FRAME"], [m.kind for m in st.mechs]
stage = st.mechs[0]
assert all(m.host_uid == stage.uid for m in st.mechs[1:])
assert st.mechs[1].label.endswith("staging frame") and st.mechs[1].x == stage.glue - 1
assert bpy.ops.popup.add(kind="CEILING", host=stage.uid) == {"FINISHED"}
assert refused(kind="CEILING", host=stage.uid)  # one only
assert bpy.ops.popup.build() == {"FINISHED"}
assert not st.warnings, st.warnings
model, layout = build.make_model(sc)
uid = stage.uid
h = model.hosts[(uid, "S")]
assert h.open_max == 2 * stage.phi_l and h.lift == (1.0, 1.0)
print(f"stage set opens to {h.open_max:.0f} deg; frames {[round(f['width'], 1) for f in model.frames.values()]}")

# frames pull flat exactly when the card is flat; the ceiling lies flat then too
for fu, f in model.frames.items():
    L, R = model.panels[f"Frame{fu}.L"], model.panels[f"Frame{fu}.R"]
    d = (L.asm(180.0).to_3x3() @ Vector((0, 0, 1))).dot(R.asm(180.0).to_3x3() @ Vector((0, 0, 1)))
    assert d > 0.9999, d
    assert abs(f["width"] - 2 * f["depth"] * math.sin(math.radians(stage.phi_l))) < 1e-6
ceil = next(m for m in st.mechs if m.kind == "CEILING")
c = model.crease(f"VFold{ceil.uid}", 180.0)
nl = model.panels[f"VFold{uid}.HalfR"].asm(180.0).to_3x3() @ Vector((0, 1, 0))
assert abs(c[0].dot(nl)) < 1e-3
print("frames and ceiling flat when the card is flat")

# the background's printed side faces into the stage (art is seen from inside)
for t in (60.0, 120.0, 180.0):
    S_, l, r, Y, n1, n2 = h.dirs(t)
    assert n1.dot(r) > 0 and n2.dot(l) > 0
print("background art faces into the stage")

# an opening on the back frame carried through to the background
fr = st.mechs[2]
o = st.openings.add()
o.on_uid, o.shape, o.x, o.y, o.width, o.height, o.through = fr.uid, "ARCH", 0.0, 10.0, 24.0, 40.0, "BEHIND"
st.live = False
build.rebuild(sc, force=True)
assert not st.warnings, st.warnings
model, layout = build.make_model(sc)
hs = holes.collect(sc, model, layout)
assert len(hs[f"Frame{fr.uid}"]) == 1 and len(hs[f"VFold{uid}"]) == 2, {k: len(v) for k, v in hs.items()}
print("opening carried through to the stage's background")

# the rig follows the geometry
rig, card = st.rig, st.card
s_ = 1 / st.mm_per_unit
me = card.data
t0 = rig["pop_close"]
worst = 0.0
for ov in (0, 30, 90, 150, 180):
    real = t0 + ov * (180 - t0) / 180
    rig["pop_open"] = float(ov)
    rig.update_tag()
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    ev = card.evaluated_get(dg).data
    attr = me.attributes["pop_panel"]
    for poly in me.polygons:
        p = model.panels[model.order[attr.data[poly.index].value]]
        D = p.asm(real) @ layout["prints"][p.piece].inverted()
        for vi in poly.vertices:
            worst = max(worst, (ev.vertices[vi].co - (D @ (me.vertices[vi].co / s_)) * s_).length / s_)
assert worst < 0.1, worst
print(f"rig matches geometry within {worst:.4f} mm")
files = export_svg.export(sc, os.path.join(OUT, "v11.svg"), **export_svg.settings_from(st))
print("exported", len(files), "files")
# too low on the card: it would stick out of the bottom when shut
stage.y = 30
build.rebuild(sc, force=True)
assert "move it at least that far up" in st.warnings, st.warnings
print("stage set too low flagged")
addon.unregister()
print("V11 OK")
