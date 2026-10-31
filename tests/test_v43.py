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
v.y, v.height = 60, 60
v.shape = "FAN"
assert v.pleat == 45.0 and v.fan_pleats == 3


def ang(m, n, t):
    p = m.panels[n]
    M = m.panels[p.parent].asm(t).inverted() @ p.asm(t)
    return math.degrees(math.acos(max(-1.0, min(1.0, M[2][2]))))


for alpha in (60.0, 90.0):
    d = dict(v.to_dict(), alpha_l=alpha, alpha_r=alpha)
    m = Model(dict(st.card_dict(), thickness=0.3), [d])
    m.check_fit()
    m.solve_hinges()
    assert not m.warnings, m.warnings
    folds = [n for n in m.order if ".Fold" in n]
    assert len(folds) == 6
    for a, b in zip(folds[:3], folds[3:]):
        assert abs(ang(m, a, 90) - ang(m, b, 90)) < 0.5, "both halves alike"
    assert all(ang(m, n, 90) > 10 for n in folds), "every pleat folds"
    assert all(ang(m, n, 180) < 0.5 for n in folds), "flat when the card is"
    half = next(n for n in m.order if n.endswith(".HalfL"))
    outline = [q for n in [half] + folds[:3] for poly in m.panels[n].polys for q in poly]
    r = max(math.hypot(*q) for q in outline)
    assert abs(r - 60.0) < 0.5, r
    print(f"fan at {alpha:.0f}°: six pleats, halves alike, flat open; radius {r:.1f} mm")

st.live = True
build.rebuild(sc, force=True)
assert not st.warnings, st.warnings
print("the fan builds in Blender")

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
