"""v0.9: the basic box (Birmingham 67): a tube with a dipped flat roof held up
by a centre rib, and mechanisms standing on the roof's crease as on a spine."""
"""v0.6: tubes on parallel sticking strips (hexagon, box, recessed) and
tethers between tubes or to strip feet. Tabulated hinges must reproduce the
solved geometry through driver curves at every open angle."""
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
box = _add(st, "TUBE")
box.label, box.y, box.x, box.depth, box.front, box.back = "Box", 60, 30, 60, 30, 30
box.height, box.roof, box.roof_fold, box.rib = 35, "FLAT", "DIP", 24
tree = _add(st, "VFOLD")
tree.label = "Tree"
tree.host = str(box.uid)
assert tree.host_uid == box.uid
tree.y, tree.height, tree.glue = 62, 18, 14
step = _add(st, "BOX")
step.label = "Step"
step.host = str(box.uid)
step.y, step.width = 92, 24
assert bpy.ops.popup.build() == {"FINISHED"}
assert not st.warnings, st.warnings
model = build.make_model(sc)[0]
names = set(model.panels)
for want in ("Roof1.L", "Rib1.W1", "Rib1.W2", "Rib1.CR", "VFold2.HalfL", "Box3.AC"):
    assert want in names, (want, sorted(names))
rig, card = st.rig, st.card
s = 1 / st.mm_per_unit
me = card.data
t0 = rig["pop_close"]
lay = build_layout(model)
worst = 0.0
for ov in (0, 10, 30, 60, 90, 120, 150, 170, 180):
    real = t0 + ov * (180 - t0) / 180
    rig["pop_open"] = float(ov)
    rig.update_tag()
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    ev = card.evaluated_get(dg).data
    attr = me.attributes["pop_panel"]
    for poly in me.polygons:
        p = model.panels[model.order[attr.data[poly.index].value]]
        D = p.asm(real) @ lay["prints"][p.piece].inverted()
        for vi in poly.vertices:
            worst = max(worst, (ev.vertices[vi].co - (D @ (me.vertices[vi].co / s)) * s).length / s)
drv = list(rig.animation_data.drivers) + (list(rig.data.animation_data.drivers)
                                           if rig.data.animation_data else [])
assert all(fc.driver.is_simple_expression for fc in drv)
assert worst < 0.1, worst
print(f"basic box: rig matches geometry within {worst:.4f} mm; {len(drv)} drivers; "
      f"closes to {t0:.1f} deg")
files = export_svg.export(sc, os.path.join(OUT, "v08.svg"), **export_svg.settings_from(st))
print("exported", len(files), "files")
# the roof is only a spine when it dips
box.roof_fold = "PEAK"
build.rebuild(sc, force=True)
assert "its host is missing" in st.warnings, st.warnings
print("peaked roof refused as a host")
addon.unregister()
print("V08 OK")
