"""v0.84: Slotted Cross Pieces are mechanisms of their own, standing on a
rising sheet: each sized and placed on its own, its feet growing with its
width, on one page or both. Older files' riser-own cross pieces become them."""
# families: folds45
import math
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
import popup_pro as addon  # noqa: E402
from popup_pro import export_svg, props, ui  # noqa: E402
from popup_pro.core.geom import v3  # noqa: E402
from popup_pro.core.model import Model  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ui_stub import adds_offered, draw, props_shown  # noqa: E402

addon.register()
sc = bpy.context.scene
st = sc.popup
st.live = False


def model():
    return Model(st.card_dict(), [m.to_dict() for m in st.mechs])


def warns():
    return [w for w in st.warnings.split("\n") if w]


def world(M, name, t):
    p = M.panels[name]
    A = p.asm(t)
    return [A @ v3(q) for poly in p.polys for q in poly]


def by(uid):
    return next(x for x in st.mechs if x.uid == uid)


assert bpy.ops.popup.add(kind="RISER") == {"FINISHED"}
ru = st.mechs[-1].uid
r = by(ru)
r.height, r.width = 60.0, 90.0
# offered on the + menu and in the sheet's panel, with the sheet selected
st.active = 0
offered = adds_offered(draw(ui.POPUP_MT_add))
assert {"kind": "CROSS", "host": ru, "fold": "A"} in offered, offered
assert {"kind": "CROSS", "host": ru, "fold": "A"} in adds_offered(draw(ui.POPUP_PT_mechs))
assert "brace_size" in props_shown(draw(ui.POPUP_PT_mechs))  # (its own folds, alone)

assert bpy.ops.popup.add(kind="CROSS", host=ru, fold="A") == {"FINISHED"}
c1 = st.mechs[-1].uid
assert bpy.ops.popup.add(kind="CROSS", host=ru, fold="A") == {"FINISHED"}
c2 = st.mechs[-1].uid
assert by(c1).cross_pos == 0.0 and by(c2).cross_pos > 15.0  # (beside the first)
assert by(c1).label == "Rising sheet 1: cross piece 1", by(c1).label
st.active = len(st.mechs) - 1
shown = props_shown(draw(ui.POPUP_PT_mechs))
assert {"host", "cross_pos", "cross_height", "cross_width", "foot_size", "feet",
        "slot_height"} <= set(shown), shown
st.active = 0
assert "brace_size" not in props_shown(draw(ui.POPUP_PT_mechs))  # (the crosses hold it)

# each sized on its own: one tall and wide, one small with one foot
a, b = by(c1), by(c2)
a.cross_width, a.cross_height, a.cross_pos = 40.0, 90.0, -15.0
b = by(c2)
b.cross_width, b.cross_height, b.cross_pos, b.feet = 16.0, 40.0, 25.0, "LEFT"
bpy.ops.popup.build()
assert not warns(), warns()
export_svg.export(sc, os.path.join(tempfile.mkdtemp(), "t.svg"))
M = model()
assert not [n for n in M.order if n.startswith(f"Rise{ru}.") and "Fold" in n]  # no own folds
for uid, cw, hc, feet in ((c1, 40.0, 90.0, "LR"), (c2, 16.0, 40.0, "L")):
    x = f"Cross{uid}"
    assert set(n[len(x) + 1:] for n in M.order if n.startswith(x + ".")) == \
        {"Cross"} | {f"Foot{s}" for s in feet} | {f"Tab{s}" for s in feet}
    polys = M.panels[f"{x}.Cross"].polys
    ys = [abs(q[1]) for p in polys for q in p]
    xs = [q[0] for p in polys for q in p]
    assert abs(max(ys) - 0.5 * cw) < 1e-6 and abs(max(xs) - hc) < 1e-6
    # the base grows with the width: the feet reach half of it
    g = max(abs(q[1]) for q in M.panels[f"{x}.FootL"].polys[0])
    assert abs(g - 0.5 * cw) < 1e-6, (uid, g)
    t = M.tmax
    for tt in M.samples:  # in its slot, and its feet's far edges on their pages
        S = M.panels[f"Rise{ru}.Sheet"].asm(tt)
        yc = 0.5 * r.width + by(uid).cross_pos
        for h_ in (0.0, 20.0):
            p = M.panels[f"{x}.Cross"].asm(tt) @ v3((h_, 0.0))
            assert (p - S @ v3((h_, yc))).length < 0.02, (uid, tt)
        l, rr, nl, nr = M.dirs(tt)
        for s_, nrm in (("L", nl), ("R", nr)):
            if s_ in feet:
                f = M.panels[f"{x}.Foot{s_}"]
                on = [f.asm(tt) @ v3(q) for q in f.polys[0] if abs(q[0]) < 1e-6]
                assert all(abs(w.dot(nrm)) < 0.02 for w in on), (uid, s_, tt)
    tops = [w.z for w in world(M, f"{x}.Cross", t)]
    assert abs(max(tops) - hc) < 0.05
# a set foot size still wins (the step at its top stays)
by(c1).foot_size = 12.0
M = model()
assert abs(max(abs(q[1]) for q in M.panels[f"Cross{c1}.FootL"].polys[0]) - 12.0) < 1e-6
# feet that overlap on a page are flagged
by(c2).feet, by(c2).cross_pos, by(c1).cross_pos = "BOTH", 0.0, -5.0
assert any("feet overlap" in w for w in model().warnings), model().warnings
by(c2).host_uid = 0
assert any("stands on a rising sheet" in w for w in model().warnings)
print("cross pieces of their own: sized, placed, one foot or two")

# ---- an older file's riser with its own cross pieces becomes these
st.mechs.clear()
st["pop_next_uid"] = 1
assert bpy.ops.popup.add(kind="RISER") == {"FINISHED"}
r = st.mechs[-1]
r.slotted, r.cross_count, r.cross_gap, r.cross_pos = True, 2, 30.0, 4.0
r.cross_height, r.cross_width, r.brace_size, r.slot_height = 100.0, 50.0, 18.0, 20.0
M0 = model()
before = {n: [w.copy() for w in world(M0, n, 120.0)] for n in M0.order
          if n.startswith(("Rise1x", "Rise1x2")) and n.endswith(".Cross")}
props.sync_folds(sc)  # (what loading the file does)
r = st.mechs[0]
assert not r.slotted
cs = [m for m in st.mechs if m.kind == "CROSS"]
assert len(cs) == 2 and all(c.host_uid == r.uid for c in cs)
assert sorted(c.cross_pos for c in cs) == [-11.0, 19.0]
assert all(c.label.startswith("Rising sheet 1: cross piece") for c in cs), [c.label for c in cs]
M1 = model()
assert not M1.warnings, M1.warnings
after = [world(M1, f"Cross{c.uid}.Cross", 120.0) for c in sorted(cs, key=lambda c: c.cross_pos)]
for old, new in zip(before.values(), after):  # (built just where they were)
    assert max((p - q).length for p, q in zip(old, new)) < 1e-4
print("older files' cross pieces become mechanisms of their own")

addon.unregister()
print("V84 OK")
_ = math
