"""End to end in Blender (`pip install bpy` or `blender -b -P`): build a card,
check the rig's deformation matches the kinematics at several angles, that
every driver is a simple expression, sketch layers survive rebuilds, and the
SVG export runs."""
# families: core, export
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
from popup_pro import art, build, export_svg  # noqa: E402
from popup_pro.core.layout import build_layout  # noqa: E402

addon.register()
sc = bpy.context.scene
st = sc.popup
st.keep_open = False  # this file checks raw kinematics: Open t is exactly t degrees
from popup_pro.ops import _add  # noqa: E402
_add(st, "VFOLD")  # the starter card before 0.27 (now a cube)
_add(st, "BOX")
assert bpy.ops.popup.build() == {"FINISHED"}  # adds a V-fold and a box fold
assert bpy.ops.popup.add(kind="BOXCUT") == {"FINISHED"}
v = st.mechs.add()
v.uid, v.kind, v.label = 9, "VFOLD", "Asymmetric"
v.y, v.symmetric, v.phi_l, v.phi_r, v.alpha_l, v.alpha_r = 150, False, 50, 65, 70, 85
v.glue, v.height, v.tab_side = 30, 35, "OUT"

for hold in ("RIGHT", "SYM"):
    st.hold = hold
    model = build.rebuild(sc, force=True)
    lay = build_layout(model)
    rig, card = st.rig, st.card
    s = 1 / st.mm_per_unit
    me = card.data
    attr = me.attributes["pop_panel"]
    worst = 0.0
    for t in (5, 30, 90, 150, 180):
        rig["pop_open"] = float(t)
        rig.update_tag()
        dg = bpy.context.evaluated_depsgraph_get()
        dg.update()
        ev = card.evaluated_get(dg).data
        for poly in me.polygons:
            p = model.panels[model.order[attr.data[poly.index].value]]
            D = model.shown(p.name, t) @ lay["prints"][p.piece].inverted()
            for vi in poly.vertices:
                want = (D @ (me.vertices[vi].co / s)) * s
                worst = max(worst, (ev.vertices[vi].co - want).length / s)
    drivers = list(rig.animation_data.drivers) + list(rig.data.animation_data.drivers)
    assert all(fc.driver.is_simple_expression for fc in drivers)
    assert worst < 0.5, worst
    print(f"{hold}: {st.status}; rig vs kinematics {worst:.3f} mm; "
          f"{len(drivers)} simple drivers")

st.hold = "RIGHT"
build.rebuild(sc, force=True)
assert bpy.ops.popup.animate(mode="CYCLE") == {"FINISHED"}
assert bpy.ops.popup.add_art(dpi=40) == {"FINISHED"}
sc.render.engine = "BLENDER_EEVEE_NEXT" if hasattr(bpy.types, "EEVEE_NEXT") else sc.render.engine
sc.cycles.samples = 77
engine_before = sc.render.engine
art.bake_art(sc, dpi=20)
assert sc.cycles.samples == 77 and sc.render.engine == engine_before, "bake changed render settings"
obj, layer = art.sketch_layer(sc, "VFold1.HalfL")
dr = layer.current_frame().drawing
dr.add_strokes([16])
for i, p in enumerate(dr.strokes[0].points):
    a = i / 15 * 2 * math.pi
    p.position = (1.0 * math.cos(a), 1.0 * math.sin(a), 0.0)
    p.radius = 0.03
st.mechs[0].height = 55  # rebuild keeps the sketch on its panel
build.rebuild(sc)
assert layer.parent == st.rig and layer.parent_bone == "VFold1.HalfL"
st.layout.data.vertices[3].co.x += 0.2  # hand edit
build.rebuild(sc)
assert st.edited
build.rebuild(sc, force=True)
files = export_svg.export(sc, os.path.join(OUT, "card.svg"))
st.export_content = "CREASE"
st.dashed_folds = False
crease = export_svg.export(sc, os.path.join(OUT, "card.svg"), **export_svg.settings_from(st))
d = open(crease[0]).read()
assert "_crease_sheet1" in crease[0] and "<image" not in d and "dasharray" not in d
st.export_content = "PRINT"

# stacking, inset, beak and mouth through the UI properties
from popup_pro.ops import _add  # noqa: E402
st.live = False
st.mechs.clear()
base = _add(st, "BOXCUT")
base.y, base.width, base.height, base.depth = 12, 62, 40, 50
for fold, y in (("A", 20), ("C", 30), ("B", 50)):
    k = _add(st, "BOXCUT")
    k.host_uid, k.fold, k.y, k.width, k.height, k.depth = base.uid, fold, y, 15, 10, 10
mo = _add(st, "MOUTH")
mo.y = 180
beak = _add(st, "VFOLD")
beak.y, beak.shape, beak.height, beak.glue = 120, "TRI", 30, 22
model = build.rebuild(sc, force=True)
assert not st.warnings, st.warnings
assert any(n.startswith("Mouth") for n in model.order)
assert sum(1 for n in model.order if n.endswith(".AC")) >= 4, model.order
print("stacked:", st.status)
assert layer.parent is None and layer.hide  # its V-fold was deleted
assert min(m.uid for m in st.mechs) > 3  # ids are not reused
for f in files:
    if f.endswith(("_layout.svg", "_reverse.svg")):
        continue  # assembly page and reverse sheets have no art layers
    d = open(f).read()
    print(os.path.basename(f), "valley", d.count("#1d5fbf"), "mountain", d.count("#c0182a"),
          "glue", d.count("#d9d4c7"), "sketch paths", d.split('id="sketch"')[1].split('id="glue"')[0].count("<path"))
assert "<path" in open(files[1]).read().split('id="sketch"')[1].split('id="glue"')[0]
addon.unregister()
print("BLENDER OK")
