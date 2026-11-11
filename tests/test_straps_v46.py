"""v0.46: a V-fold standing on a strap or box fold, with one half on the
page and one on the strip, keeps its crease closed as the strip is raised
onto its tabs near flat (no slit along the crease); the rig follows."""
# families: straps, vfolds
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
import popup_pro as addon  # noqa: E402
from popup_pro import build  # noqa: E402

addon.register()
sc = bpy.context.scene
st = sc.popup
bpy.ops.popup.build()


def check(fold, shape, kind="VFOLD"):
    st.mechs.clear()
    bpy.ops.popup.add(kind="BOX")
    box = st.mechs[-1]
    st.active = 0
    bpy.ops.popup.add(kind=kind, host=box.uid, fold=fold)
    v = st.mechs[-1]
    if kind == "VFOLD":
        v.y = 90
        v.shape = shape
        v.height = 45
        v.glue = v.glue_r = 30
        v.symmetric = False
        v.phi_l, v.phi_r, v.fold_flat, v.lean = 100, 130, True, 30
    st.solid_paper = False
    build.rebuild(sc, force=True)
    model, lay = build.make_model(sc)
    rig, card = st.rig, st.card
    if rig.animation_data:
        rig.animation_data.action = None
    me = card.data
    at = me.attributes["pop_panel"]
    s = 1 / st.mm_per_unit
    t0 = rig["pop_close"]
    halves = [n for n in model.order if n.startswith(f"VFold{v.uid}.Half")] or \
        [n for n in model.order if n.startswith(f"Cube{v.uid}.") and n[-2:] in (".B", ".C")]
    worst_gap = worst_rig = 0.0
    for t in (60.0, 121.7, 150.3, 170.0, 180.0):
        rig["pop_open"] = t
        rig.update_tag()
        dg = bpy.context.evaluated_depsgraph_get()
        dg.update()
        ev = card.evaluated_get(dg).data
        real = t0 + t * (180 - t0) / 180
        pos = {}
        for poly in me.polygons:
            name = model.order[at.data[poly.index].value]
            D = model.shown(name, real) @ lay["prints"][model.panels[name].piece].inverted()
            for vi in poly.vertices:
                e = (ev.vertices[vi].co - (D @ (me.vertices[vi].co / s)) * s).length / s
                worst_rig = max(worst_rig, e)
                if name in halves:
                    key = tuple(round(x, 4) for x in me.vertices[vi].co[:2])
                    pos.setdefault(key, {})[name] = ev.vertices[vi].co.copy()
        for d in pos.values():
            if len(d) == 2:
                a, b = d.values()
                worst_gap = max(worst_gap, (a - b).length / s)
    print(fold, shape, kind, "crease gap", round(worst_gap, 4), "rig", round(worst_rig, 4))
    assert worst_gap < 0.01, (fold, shape, worst_gap)
    assert worst_rig < 0.05, (fold, shape, worst_rig)


for fold in ("A", "C", "B"):
    for shape in ("BEAK_R", "QUAD"):
        check(fold, shape)
for fold in ("A", "B"):
    check(fold, "", "CUBE")
print("v46 ok")
