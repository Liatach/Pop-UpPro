"""v0.7: pyramid and ridge roofs (Birmingham 52), standing on the strips or
capping a tube. The rig must follow the solved geometry at every angle."""
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
st.size = "A4"
tower = _add(st, "TUBE")
tower.label, tower.y, tower.depth, tower.front, tower.back = "Tower", 100, 30, 30, 30
tower.height, tower.roof, tower.roof_height = 45, "POINTED", 32
house = _add(st, "TUBE")
house.label, house.y, house.depth, house.front, house.back = "House", 25, 24, 18, 18
house.x = 18
house.height, house.roof, house.roof_height, house.ridge = 28, "POINTED", 22, 20
keep = _add(st, "TUBE")
keep.label, keep.y, keep.x, keep.depth, keep.front, keep.back = "Keep", 195, 32, 26, 34, 34
keep.height, keep.roof, keep.eave = 34, "FLAT", 6
pyr = _add(st, "PYRAMID")
pyr.label, pyr.y, pyr.x, pyr.depth, pyr.height = "Pyramid", 275, 10, 10, 14
pyr.front = pyr.back = 10
assert bpy.ops.popup.build() == {"FINISHED"}
assert not st.warnings, st.warnings
model = build.make_model(sc)[0]
names = set(model.panels)
for want in ("Roof1.SL", "Roof1.FR", "Roof2.SR", "Roof2.BL", "Roof3.L", "Tube3.TopR",
             "Pyramid4.FL", "Pyramid4.TabR"):
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
print(f"roofs: rig matches geometry within {worst:.4f} mm; {len(drv)} drivers; "
      f"closes to {t0:.1f} deg")
files = export_svg.export(sc, os.path.join(OUT, "v07.svg"), **export_svg.settings_from(st))
rev = [f for f in files if f.endswith("_reverse.svg")]
assert rev and any(f.endswith("_layout.svg") for f in files), files
r = open(rev[0]).read()
assert "REVERSE OF SHEET" in r and "BACK of" in r and "glue" in r
lay_svg = open(next(f for f in files if f.endswith("_layout.svg"))).read()
for name in ("Tower", "House", "Keep roof", "Pyramid"):
    assert name in lay_svg, name
print("exported", len(files), "files:", ", ".join(os.path.basename(f) for f in files))
# a roof that lies further out than the page when shut is flagged
tower.roof_height = 150
build.rebuild(sc, force=True)
assert any("sticks out" in w for w in st.warnings.split("\n")) or "sticks out" in st.warnings, st.warnings
print("over-tall roof flagged")
addon.unregister()
print("V07 OK")
