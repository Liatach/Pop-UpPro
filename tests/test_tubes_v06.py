"""v0.6: tubes on parallel sticking strips (hexagon, box, recessed) and
tethers between tubes or to strip feet. Tabulated hinges must reproduce the
solved geometry through driver curves at every open angle."""
# families: tubes, tethers
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
keep = _add(st, "TUBE")
keep.label, keep.y, keep.depth, keep.front, keep.back = "Keep", 120, 40, 32, 32
gate = _add(st, "TUBE")
gate.label, gate.y, gate.depth, gate.front, gate.back = "Gate", 35, 30, 25, 25  # box ends
gate.height = 40
wl = _add(st, "TETHER")
wl.label, wl.from_uid, wl.from_pt, wl.to, wl.to_uid, wl.to_pt = "Wall L", keep.uid, "FL", "TUBE", gate.uid, "BL"
wr = _add(st, "TETHER")
wr.label, wr.from_uid, wr.from_pt, wr.to, wr.to_uid, wr.to_pt = "Wall R", keep.uid, "FR", "TUBE", gate.uid, "BR"
side = _add(st, "TETHER")
side.label, side.from_uid, side.from_pt, side.to, side.to_y = "Side wall", keep.uid, "BL", "LEFT", 172
br = _add(st, "TETHER")
br.label, br.from_uid, br.from_pt, br.to, br.to_y = "Bridge", keep.uid, "CB", "RIGHT", 196
assert bpy.ops.popup.build() == {"FINISHED"}
assert not st.warnings, st.warnings
model = build.make_model(sc)[0]
assert any(not v["straight"] for v in model.tethers.values()), "expected a creased tether"
print("tethers:", {model.mechs[i]["label"] if False else k: (v["straight"], round(v["length"], 1))
                   for k, v in model.tethers.items()})
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
tables = sum(1 for fc in drv if len(fc.keyframe_points) > 2)
assert worst < 0.1, worst
print(f"rig matches geometry within {worst:.4f} mm; {len(drv)} drivers ({tables} tabulated), "
      f"all simple; closes to {t0:.1f} deg")
files = export_svg.export(sc, os.path.join(OUT, "v06.svg"), **export_svg.settings_from(st))
print("exported", len(files), "sheets")
# the strip-distance rule
gate.x = 20
br.to_y = 196
build.rebuild(sc, force=True)
assert "same Strip Distance" in st.warnings, st.warnings
print("different strip distances refused")
# creases that meet head-on along the fold as the card shuts can't be tethered
gate.x = 25
gate.depth = 28  # gate's back crease now meets the keep's front crease when shut
hd = _add(st, "TETHER")
hd.label, hd.from_uid, hd.from_pt, hd.to, hd.to_uid, hd.to_pt = "Head-on", keep.uid, "CF", "TUBE", gate.uid, "CB"
build.rebuild(sc, force=True)
assert "meet head-on" in st.warnings, st.warnings
print("head-on tether refused")
addon.unregister()
print("V06 OK")
