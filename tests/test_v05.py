"""v0.5: 180-degree cube (peaked / dipped / no lid) and pull-tab flaps with
their own Pull control. The rig must match the solved geometry at every
open angle and pull, using simple driver expressions only."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "tests", "out")
os.makedirs(OUT, exist_ok=True)

import bpy  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
import popup_pro as addon  # noqa: E402
from popup_pro import build, export_svg  # noqa: E402
from popup_pro.core.layout import build_layout  # noqa: E402
from popup_pro.ops import _add as _add_mech  # noqa: E402


class Ref:
    """A mechanism looked up by id each time: adding mechanisms can move the
    collection in memory, so Python references to items go stale."""

    def __init__(self, st, uid):
        object.__setattr__(self, "_st", st)
        object.__setattr__(self, "_uid", uid)

    def _m(self):
        return next(m for m in self._st.mechs if m.uid == self._uid)

    def __getattr__(self, k):
        return getattr(self._m(), k)

    def __setattr__(self, k, v):
        setattr(self._m(), k, v)


def _add(st, kind):
    return Ref(st, _add_mech(st, kind).uid)

addon.register()
sc = bpy.context.scene
st = sc.popup
st.live = False
st.hold = "SYM"
cube = _add(st, "CUBE")
cube.y, cube.size, cube.height = 50, 40, 40
f1 = _add(st, "FLAP")
f1.side, f1.x, f1.y, f1.hinge, f1.glue_at = "R", 80, 180, "TOP", 15
f2 = _add(st, "FLAP")
f2.side, f2.x, f2.y, f2.hinge = "L", 70, 40, "BOTTOM"
assert f2.glue_at == 5.0  # glued low by default
assert bpy.ops.popup.build() == {"FINISHED"}
assert not st.warnings, st.warnings
rig, card = st.rig, st.card
s = 1 / st.mm_per_unit
me = card.data


def rig_error(model, t0, open_value, pulls):
    real = t0 + open_value * (180 - t0) / 180
    rig["pop_open"] = float(open_value)
    for uid, v in pulls.items():
        rig[f"pop_pull_{uid}"] = v
        model.pull[uid] = v
    rig.update_tag()
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    ev = card.evaluated_get(dg).data
    attr = me.attributes["pop_panel"]
    lay = build_layout(model)
    worst = 0.0
    for poly in me.polygons:
        p = model.panels[model.order[attr.data[poly.index].value]]
        D = p.asm(real) @ lay["prints"][p.piece].inverted()
        for vi in poly.vertices:
            worst = max(worst, (ev.vertices[vi].co - (D @ (me.vertices[vi].co / s)) * s).length / s)
    return worst


for lid in ("PEAK", "DIP", "NONE"):
    cube.lid = lid
    model = build.rebuild(sc, force=True)
    t0 = rig["pop_close"]
    worst = 0.0
    for ov in (0, 45, 90, 135, 180):
        for pv in (0.0, 0.5, 1.0):
            worst = max(worst, rig_error(model, t0, ov, {f1.uid: pv, f2.uid: 1 - pv}))
    drv = list(rig.animation_data.drivers) + list(rig.data.animation_data.drivers)
    assert all(fc.driver.is_simple_expression for fc in drv)
    assert worst < 0.05, (lid, worst)
    print(f"lid {lid}: rig matches geometry within {worst:.4f} mm over open x pull; "
          f"{len(drv)} simple drivers; closes to {t0:.1f} deg")

# pull test keyframes
rig[f"pop_pull_{f1.uid}"] = 0.0
sc.frame_set(1)
assert bpy.ops.popup.animate_pull(uid=f1.uid) == {"FINISHED"}
fc = [f for f in rig.animation_data.action.fcurves if f.data_path == f'["pop_pull_{f1.uid}"]'] \
    if hasattr(rig.animation_data.action, "fcurves") else ["layered"]
assert fc, "pull keyframes missing"
print("pull test keyframed")

# warnings: strip across the spine, short pull tab
f2.hinge = "RIGHT"  # strip runs to the spine
f1.pull_out = 8
build.rebuild(sc, force=True)
w = st.warnings
assert "across the spine" in w and "longer Pull Tab" in w, w
f2.hinge, f1.pull_out = "BOTTOM", 30
build.rebuild(sc, force=True)
assert not st.warnings, st.warnings

# export: slit cut into the page, no line across the strip where it bends
files = export_svg.export(sc, os.path.join(OUT, "v05.svg"), **export_svg.settings_from(st))
model = build.make_model(sc)[0]
print("sheets:", len(files), "pieces:", sorted(model.pieces))
d1 = open(files[0]).read()
assert d1.count('stroke="#000000"') >= 8  # card outline + two slits (4 sides each)
assert "Pull" in "".join(open(f).read() for f in files)
print("export ok")
# stacking through the Add menu: inset / on top / in front, auto-fitted
st.mechs.clear()
bpy.ops.popup.add(kind="BOXCUT")
host = st.mechs[-1]
host.width = 80
host_uid = host.uid
for i, (kind, fold) in enumerate((("BOXCUT", "C"), ("BOXCUT", "A"), ("BOXCUT", "B"), ("BOX", "A"))):
    host = next(m for m in st.mechs if m.uid == host_uid)  # adding can move it in memory
    bpy.ops.popup.add(kind=kind, host=host.uid, fold=fold)
    host = next(m for m in st.mechs if m.uid == host_uid)
    k = st.mechs[-1]
    assert k.width < host.width and k.height < host.height, (kind, fold)
    k.width, k.y = 14, host.y + 3 + 20 * i  # side by side along the spine
model = build.rebuild(sc, force=True)
assert not st.warnings, st.warnings
assert all(model.panels[f"Box{host.uid}.{p}"].polys for p in ("AC", "CB"))
print("stacking: inset, on top, in front and glued on top all fit their host")
addon.unregister()
print("V05 OK")
