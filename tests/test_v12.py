"""v0.12: stage floors and ceilings with a pointed lead past the stage front,
printed side into the stage, and mechanisms standing in the corners where a
floor or ceiling meets a wall."""
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
from popup_pro import build, carousel, export_svg  # noqa: E402
from popup_pro.core.model import Model  # noqa: E402

# ---- the model: lead limit, printed sides, corner hosts
for n in (3, 5, 8):
    tmax = 360.0 / n
    al = math.radians(tmax / 2)
    m = Model(dict(W=148.5, H=210, hold="SYM", tmax=tmax),
              [dict(type="FLOOR", uid=1, label="Floor", depth=148.5, tab=8, lead=500)])
    lim = min(148.5 / math.cos(al), 210 / math.sin(al)) - 0.5
    assert any("shortened" in w for w in m.warnings), m.warnings
    m = Model(dict(W=148.5, H=210, hold="SYM", tmax=tmax),
              [dict(type="FLOOR", uid=1, label="Floor", depth=148.5, tab=8,
                    lead=lim - 148.5 * math.cos(al) - 1)])
    m.check_fit()
    assert not m.warnings, (n, m.warnings)
    # printed side of the floor faces up into the stage
    fn = m.panels["VFold1.HalfL"].asm(0.5 * tmax).to_3x3() @ Vector((0, 0, 1))
    assert fn.y > 0.1, fn
    assert {(1, "L"), (1, "R")} <= set(m.hosts)
    print(f"{n} stages: floor point reaches {lim - 148.5 * math.cos(al):.0f} mm past the front")

addon.register()
sc = bpy.context.scene
sc.name = "Carousel"
sc.popup.size = "A5"
assert bpy.ops.popup.make_carousel(count=5) == {"FINISHED"}
s1 = carousel.stages(sc)[0]
st = s1.popup
with carousel.in_scene(s1):
    st.live = False
    assert bpy.ops.popup.add(kind="FLOOR") == {"FINISHED"}
    next(m for m in st.mechs if m.kind == "FLOOR").lead = 40
    fuid = next(m for m in st.mechs if m.kind == "FLOOR").uid
    assert bpy.ops.popup.add(kind="CEILING") == {"FINISHED"}
    cuid = next(m for m in st.mechs if m.kind == "CEILING").uid
    for kind, host, side in (("BOX", fuid, "L"), ("VFOLD", cuid, "R"), ("BOX", fuid, "R")):
        assert bpy.ops.popup.add(kind=kind, host=host, side=side) == {"FINISHED"}
    carousel.rebuild_stage(s1)
assert not st.warnings, st.warnings
model, layout = build.make_model(s1)
boxes = [m for m in st.mechs if m.host_uid == fuid]
assert len(boxes) == 2 and {m.side for m in boxes} == {"L", "R"}
for b in boxes:
    assert f"Box{b.uid}.AC" in model.panels
assert any(n.startswith("VFold") and n.endswith("HalfL") for n in model.panels
           if n.split(".")[0] not in (f"VFold{fuid}", f"VFold{cuid}"))
print("box folds on both floor corners and a V-fold in a ceiling corner")

# the rig follows the geometry
rig, card = st.rig, st.card
c = carousel.ctrl(sc)
s_ = 1 / st.mm_per_unit
me = card.data
worst = 0.0
for T in (30.0, 180.0, 340.0):
    c[carousel.OPEN] = T
    c.update_tag()
    rig.update_tag()
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    ev = card.evaluated_get(dg).data
    attr = me.attributes["pop_panel"]
    for poly in me.polygons:
        p = model.panels[model.order[attr.data[poly.index].value]]
        D = p.asm(T / 5) @ layout["prints"][p.piece].inverted()
        for vi in poly.vertices:
            worst = max(worst, (ev.vertices[vi].co - (D @ (me.vertices[vi].co / s_)) * s_).length / s_)
assert worst < 0.1, worst
print(f"rig matches geometry within {worst:.4f} mm")
files = export_svg.export(s1, os.path.join(OUT, "v12.svg"), **export_svg.settings_from(st))
print("exported", len(files), "files")
addon.unregister()
print("V12 OK")
