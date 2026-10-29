"""v0.30: a strap zig-zags into several peaks (one strip, glued only at its
ends) with pop-ups in its valleys; faster rebuilds; the interface tidied:
the same words for where things stand, Checks second and red when there's
anything to fix, the movement test folded to a play button."""
import math
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
import popup_pro as addon  # noqa: E402
from popup_pro import build, ui  # noqa: E402
from popup_pro.core.model import Model  # noqa: E402

CARD = dict(W=148.5, H=210.0, hold="SYM")


def P(m, n, q, t):
    return m.panels[n].asm(t) @ Vector((q[0], q[1], 0))


# ---- peaks: one strip, its creases joined at every opening, flat when open
for npk, sl, a, b in ((2, 0.0, 35.0, 35.0), (3, 0.0, 40.0, 30.0), (3, 20.0, 35.0, 35.0)):
    S = dict(type="BOX", style="GLUED", uid=1, label="Strap", y=70, width=50, height=a,
             depth=b, tab=8, peaks=npk, slant=sl)
    m = Model(CARD, [S])
    m.check_fit()
    assert not m.warnings, m.warnings
    names = [n for n in m.order if n.startswith("Box1.") and m.panels[n].kind == "panel"]
    assert len(names) == 2 * npk and [p for p in m.pieces if p.startswith("Box")] == ["Box1"]
    L = a + b
    ub = [0.0]
    for i in range(npk):
        ub += [i * L / npk + b / npk, (i + 1) * L / npk]
    kk = math.tan(math.radians(sl))
    for t in (20.0, 70.0, 120.0, 170.0):
        for j in range(len(names) - 1):
            q = (ub[j + 1], kk * (ub[j + 1] - a))
            assert (P(m, names[j], q, t) - P(m, names[j + 1], q, t)).length < 1e-3
    assert max(abs(P(m, n, q, 179.9).z) for n in names
               for poly in m.panels[n].polys for q in poly) < 0.5
    assert all((1, f"V{i}") in m.hosts for i in range(1, npk))
    # shown resting on its glue tabs: above them (and the page) when flat
    # (v0.35: the rig lifts the whole strip off its page near flat)
    assert abs(m.panels[names[0]].lift - 0.3) < 1e-9, m.panels[names[0]].lift
print("strap peaks: one strip, joined at every crease, flat when open")

# a cube in each valley, where it lies when flat
S = dict(type="BOX", style="GLUED", uid=1, label="Strap", y=70, width=60, height=40,
         depth=40, tab=8, peaks=3)
for g in (1, 2):
    kid = dict(type="CUBE", uid=2, label="c", y=82, size=8, height=8, tab=5, host=1,
               fold="V", gully=g, lid="PEAK", tab_side="IN")
    m = Model(CARD, [S, kid])
    m.check_fit()
    assert not m.warnings, m.warnings
    pts = [P(m, n, q, 179.9) for n in m.order if n.startswith("Cube2")
           for poly in m.panels[n].polys for q in poly]
    x = sum(p.x for p in pts) / len(pts)
    assert abs(x - (-40 + g * 80 / 3)) < 1.0, (g, x)
print("pop-ups stand in the valleys")

# ---- a strap with a cube and a tube rebuilds quickly
S1 = dict(type="BOX", style="GLUED", uid=1, label="Strap", y=70, width=70, height=35,
          depth=35, tab=10)
kids = [dict(type="CUBE", uid=2, label="c", y=75, size=15, height=15, tab=6, host=1,
             fold="A", lid="PEAK", tab_side="IN"),
        dict(type="TUBE", uid=3, label="t", y=75, x=5, depth=25, height=15, front=8, back=8,
             tab=6, host=1, fold="B", front_style="OUT", back_style="OUT", tab_side="IN",
             roof="NONE")]
t0 = time.time()
m = Model(CARD, [S1] + kids)
assert time.time() - t0 < 2.0
print(f"strap with a cube and a tube: {time.time() - t0:.2f} s")

# ---- the interface
assert ui.POPUP_PT_card.bl_order < ui.POPUP_PT_checks.bl_order < ui.POPUP_PT_mechs.bl_order
assert "DEFAULT_CLOSED" not in getattr(ui.POPUP_PT_checks, "bl_options", set())
addon.register()
sc = bpy.context.scene
st = sc.popup
assert st.bl_rna.properties.get("images") is not None
from popup_pro.props import PopupMech  # noqa: E402
P_ = PopupMech.bl_rna.properties
assert P_["tab"].name == "Tab Size" and P_["tab_side"].name == "Tab Side"
assert P_["fold"].name == P_["vside"].name == P_["wall"].name == "Fold"
assert bpy.ops.popup.build() == {"FINISHED"}
st.live = False
assert bpy.ops.popup.add(kind="BOX", variant="STRAP") == {"FINISHED"}
strap = st.mechs[-1]
strap.peaks = 2
assert bpy.ops.popup.add(kind="CUBE", host=strap.uid, fold="VAL") == {"FINISHED"}
cube = st.mechs[-1]
assert cube.fold == "V"
assert bpy.ops.popup.build() == {"FINISHED"}
m, _ = build.make_model(sc)
assert any(n.startswith(f"Cube{cube.uid}.") for n in m.order), m.warnings
addon.unregister()
print("V30 OK")
