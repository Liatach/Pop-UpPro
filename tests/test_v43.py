"""v0.43: the Fan V-fold shape (a semicircle pleated by creases fanning from
the V point); Fan and Concertina pleat presets; creases, cuts and holes in
one panel; painting shows both shapes."""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
import popup_pro as addon  # noqa: E402
from popup_pro import build, ui  # noqa: E402
from popup_pro.core.model import Model  # noqa: E402
import types  # noqa: E402

addon.register()
sc = bpy.context.scene
st = sc.popup
assert bpy.ops.popup.build() == {"FINISHED"}
st.mechs.clear()
assert bpy.ops.popup.add(kind="VFOLD") == {"FINISHED"}
v = st.mechs[-1]
st.live = False
v.y, v.height = 40, 80
v.shape = "FAN"
assert v.fan_pleats == 5 and v.fan_spread == 180.0 and v.fan_stand == 60.0
from mathutils import Vector  # noqa: E402


def normal(m, n, t):
    return m.panels[n].asm(t).to_3x3() @ Vector((0, 0, 1))


for phi in (30.0, 60.0):
    d = dict(v.to_dict(), phi_l=phi, phi_r=phi)
    m = Model(dict(st.card_dict(), thickness=0.3), [d])
    m.check_fit()
    m.solve_hinges()
    assert not m.warnings, m.warnings
    fan = [n for n in m.order if ".Fan" in n]
    assert len(fan) == 10
    # shut: every sector flat against the next
    for a, b in zip(fan, fan[1:]):
        c = abs(normal(m, a, 1.0).dot(normal(m, b, 1.0)))
        assert c > math.cos(math.radians(2.0)), (a, b, math.degrees(math.acos(min(1, c))))
    # open: pleated, never flat (more paper than room), and standing up
    for t in (90.0, 180.0):
        angs = [math.degrees(math.acos(min(1.0, abs(normal(m, a, t).dot(normal(m, b, t))))))
                for a, b in zip(fan, fan[1:])]
        assert min(angs) > 15, (t, angs)
        assert all(abs(x - y) < 1.0 for x, y in zip(angs, angs[::-1])), "both sides alike"
    top = max((m.panels[n].asm(180.0) @ Vector((q[0], q[1], 0.0))).z
              for n in fan for poly in m.panels[n].polys for q in poly)
    assert top > 0.6 * 80.0, top
    d0 = dict(d, fan_stand=0.0)
    m0 = Model(dict(st.card_dict(), thickness=0.3), [d0])
    top0 = max((m0.panels[n].asm(180.0) @ Vector((q[0], q[1], 0.0))).z
               for n in fan for poly in m0.panels[n].polys for q in poly)
    assert top0 < 0.5 * top, (top0, top)
    # the radius, and the ends glued on their glue lines
    r = max(math.hypot(*q) for n in fan for poly in m.panels[n].polys for q in poly)
    assert abs(r - 80.0) < 0.5, r
    print(f"fan, glue angle {phi:.0f}: shut flat pleat on pleat; open it stands "
          f"{top:.0f} mm tall (Stand 0: {top0:.0f} mm)")

d = dict(v.to_dict(), phi_l=60, phi_r=60, fan_spread=100.0)
m = Model(dict(st.card_dict(), thickness=0.3), [d])
assert any("not enough Spread" in w for w in m.warnings)
print("too little Spread is flagged")

st.live = True
build.rebuild(sc, force=True)
assert not st.warnings, st.warnings
model, lay = build.make_model(sc)
rig, card = st.rig, st.card
if rig.animation_data:
    rig.animation_data.action = None  # the movement test would drive Open
s_ = 1 / st.mm_per_unit
me = card.data
attr = me.attributes["pop_panel"]
worst = 0.0
for t in (10, 60, 120, 180):
    rig["pop_open"] = float(t)
    rig.update_tag()
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    ev = card.evaluated_get(dg).data
    real = rig.get("pop_close", 0.0) + t * (180 - rig.get("pop_close", 0.0)) / 180
    for poly in me.polygons:
        p = model.panels[model.order[attr.data[poly.index].value]]
        D = model.shown(p.name, real) @ lay["prints"][p.piece].inverted()
        for vi in poly.vertices:
            worst = max(worst, (ev.vertices[vi].co - (D @ (me.vertices[vi].co / s_)) * s_).length / s_)
assert worst < 0.5, worst
print(f"the fan builds in Blender; the rig follows it to {worst:.3f} mm")

# ---- the pleat presets
v.shape = "QUAD"
v.pleat = 0.0
v.lines.clear()
st.active = 0
for pre in ("FAN", "PLEATS"):
    n0 = len(v.lines)
    assert bpy.ops.popup.add_line(preset=pre) == {"FINISHED"}
    assert len(v.lines) - n0 == 3 and all(ln.mirror for ln in v.lines[n0:])
    assert v.pleat == 45.0
print("Fan Pleats and Concertina Pleats presets")

# ---- one panel: openings, creases and cuts on the mechanism or the card, drawn


class Lay:
    def __init__(self, seen):
        self.seen = seen

    def __getattr__(self, k):
        def f(*a, **kw):
            if k in ("prop", "prop_enum"):
                self.seen.append(a[1] if len(a) > 1 else k)
            if k in ("operator", "operator_menu_enum"):
                self.seen.append(a[0])
                return types.SimpleNamespace()
            if k == "panel":
                return Lay(self.seen), Lay(self.seen)
            return Lay(self.seen) if k in ("row", "column", "box", "split") else None
        return f


seen = []
stub = types.SimpleNamespace(layout=Lay(seen))
for st.lines_on in ("MECH", "CARD"):
    ui.POPUP_PT_openings.draw(stub, bpy.context)
assert "popup.add_line" in seen and "pleat" in seen and "popup.add_card_line" in seen
assert "popup.draw_holes" in seen and "popup.take_lines" in seen and "popup.add_opening" in seen
assert "popup.trace_holes" not in seen, "painted holes live under Paint now"
seen.clear()
ui._paint_controls(Lay(seen), bpy.context, big=True)
assert "popup.trace_holes" in seen and "auto_holes" in seen
print("creases, cuts and holes in one panel; painted holes under Paint")
print("all v43 checks pass")
