"""v0.86: rising sheets and cross pieces laid out upright; a rising sheet's
corners and 45° folds as hosts; paste-ons (renamed from pictures); a bite
in steps; an arm swinging behind a mask (Birmingham 75)."""
# families: folds45, vfolds, layout, swing
import math
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
import popup_pro as addon  # noqa: E402
from popup_pro import export_svg, ops, ui  # noqa: E402
from popup_pro.core.geom import v3  # noqa: E402
from popup_pro.core.model import Model  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ui_stub import draw, props_shown  # noqa: E402

addon.register()
sc = bpy.context.scene
st = sc.popup
st.live = False
svg = os.path.join(tempfile.mkdtemp(), "t.svg")


def add(kind, **kw):
    assert bpy.ops.popup.add(kind=kind, **kw) == {"FINISHED"}, (kind, kw)
    return st.mechs[-1]


def model():
    return Model(st.card_dict(), [m.to_dict() for m in st.mechs])


def warns():
    return [w for w in st.warnings.split("\n") if w]


def reset():
    st.mechs.clear()
    st.openings.clear()
    st["pop_next_uid"] = 1


def world(M, name, t):
    p = M.panels[name]
    A = p.asm(t)
    return [A @ v3(q) for poly in p.polys for q in poly]


def clean(M, prefix):
    for n in M.order:
        p = M.panels[n]
        if not n.startswith(prefix) or p.kind != "panel":
            continue
        for t in M.samples:
            l, r, nl, nr = M.dirs(t)
            d = min(min(w.dot(nl), w.dot(nr)) for w in world(M, n, t))
            assert d > -0.5, (n, t, d)


# ---- paste-ons
assert ops.NAMES["PICTURE"] == "Paste-on"
print("paste-ons")

# ---- rising sheets and their cross pieces laid out upright
reset()
r = add("RISER")
add("CROSS", host=r.uid)
M = model()
assert M.pieces["Rise1"].upright == (1.0, 0.0), M.pieces["Rise1"].upright
crosses = [p for p in M.pieces.values() if p.name not in ("Rise1", "Card")]
assert crosses and all(getattr(p, "upright", False) == (1.0, 0.0) for p in crosses)
bpy.ops.popup.build()
export_svg.export(sc, svg)
print("rising sheets laid out upright")

# ---- a rising sheet's corners and 45° folds as hosts
for kind in ("BOX", "VFOLD", "CUBE", "STANDUP"):
    for fold in ("RL", "RR", "RVL", "RVR"):
        reset()
        r = add("RISER")
        r.y, r.width, r.height = 60.0, 90.0, 70.0
        assert bpy.ops.popup.add(kind=kind, host=r.uid, fold=fold) == {"FINISHED"}
        m = st.mechs[-1]
        assert m.side == ("L" if fold in ("RL", "RVL") else "R")
        assert m.on_crease == (fold in ("RVL", "RVR"))
        bpy.ops.popup.build()
        assert not warns(), (kind, fold, warns())
        M = model()
        key = ("V" if m.on_crease else "") + m.side
        assert M.placed[m.uid] is M.hosts[(r.uid, key)], (kind, fold)
        clean(M, "")
print("mechanisms on a rising sheet's corners and 45° folds")

# ---- a bite in steps
reset()
v = add("VFOLD")
v.height, v.glue = 70.0, 45.0
v.bite, v.bite_len = True, 36.0
v.bite_angle, v.bite_steps, v.bite_step_angle = 10.0, 4, 8.0
# (0.86.0's even steps: still built so, until the file's moved on)
bpy.ops.popup.build()
assert not warns(), warns()
M = model()
tags = ["Bite", "Bite2", "Bite3", "Bite4"]
for tg in tags:
    for s in "LR":
        assert f"VFold1.{tg}{s}" in M.panels, (tg, s)
for t in M.samples:
    for i, tg in enumerate(tags):
        L, R = world(M, f"VFold1.{tg}L", t), world(M, f"VFold1.{tg}R", t)
        # each step's two facets meet along its seam
        seam = [w for w in L if min((w - q).length for q in R) < 0.03]
        assert len(seam) >= 2, (tg, t, len(seam))
        if i:  # and carry on from the step before, across its crease
            for s in "LR":
                prev = world(M, f"VFold1.{tags[i - 1]}{s}", t)
                cur = world(M, f"VFold1.{tg}{s}", t)
                shared = [w for w in cur if min((w - q).length for q in prev) < 0.03]
                assert len(shared) >= 2, (tg, s, t)
clean(M, "VFold1")
# each step's facets turn away from the step before's (in the pattern)
P = M.panels


def normal_dir(tg):
    poly = P[f"VFold1.{tg}R"].polys[0]
    return tuple(round(c, 3) for c in poly[0])


assert len({normal_dir(tg) for tg in tags}) == 4
export_svg.export(sc, svg)
v.bite_steps, v.bite_step_angle = 6, 40.0
assert any("run out of paper" in w or "crosses step" in w for w in model().warnings), \
    model().warnings
print("a bite in steps")

# ---- an arm swinging behind a mask
for side in ("R", "L"):
    for dr in ("CW", "CCW"):
        reset()
        s = add("SWING")
        s.swing_side, s.swing_dir = side, dr
        assert {"swing_gap", "swing_at", "swing_dir", "swing_angle"} <= \
            set(props_shown(draw(ui.POPUP_PT_mechs)))
        bpy.ops.popup.build()
        assert not warns(), (side, dr, warns())
        M = model()
        g = s.swing_gap
        base = M.panels["Page.R" if side == "R" else "Page.L"]
        names = ["Swing1.LR", "Swing1.UR", "Swing1.UL", "Swing1.LL", "Swing1.TabD",
                 "Swing1.TabE"]
        prev_dir = None
        turned = []
        for t in M.samples + [M.tmax]:
            pts = {n: world(M, n, t) for n in names}
            # the hinge stays in one piece: neighbours share an edge
            for a, b in zip(names[:4], names[1:4]):
                sh = [w for w in pts[a] if min((w - q).length for q in pts[b]) < 0.05]
                assert len(sh) >= 2, (side, dr, t, a, b)
            for a, b in (("Swing1.LR", "Swing1.TabD"), ("Swing1.LL", "Swing1.TabE")):
                sh = [w for w in pts[a] if min((w - q).length for q in pts[b]) < 0.4]
                assert len(sh) >= 2, (side, dr, t, a, b)
            # C turns about its pivot in the page's plane, a right angle in all
            B = base.asm(t).inverted()
            arm = M.panels["SwArm1.End"]  # (glued on C)
            A = B @ arm.asm(t)
            dv = A.to_3x3() @ v3((1.0, 0.0))
            ang = math.degrees(math.atan2(dv.y, dv.x))
            turned.append(ang)
            # the mask stays parallel to the page, off it by g sin(opening)
            mk = B @ M.panels["Mask1.Mask"].asm(t)
            assert (mk.to_3x3() @ v3((0.0, 0.0, 1.0)) -
                    v3((0.0, 0.0, 1.0))).length < 1e-6
        span = (turned[-1] - turned[0] + 180.0) % 360.0 - 180.0
        assert abs(abs(span) - 90.0) < 3.0, (side, dr, span)
        # clockwise seen from the front as it opens (the left page's pattern
        # runs the same way round as the right's)
        assert (span < 0) == (dr == "CW"), (side, dr, span)
        clean(M, "Swing1")
        clean(M, "Mask1")
        clean(M, "SwArm1")
        export_svg.export(sc, svg)
s.width = 30.0
assert any("doesn't hide the hinge" in w for w in model().warnings)
print("an arm swinging behind a mask")

# ---- 0.86.1: the arm bends at a crease to lie between page and mask, clear
# of its hinge; the mask's fold is a host
from popup_pro.core.swing import _crosses  # noqa: E402

reset()
s = add("SWING")
M = model()
assert not M.warnings, M.warnings
for t in [10.0 * k for k in range(4, 18)]:
    for a in ("SwArm1.Arm", "SwArm1.End"):
        for f in ("LR", "UL", "LL"):
            assert not _crosses(world(M, a, t), world(M, f"Swing1.{f}", t)), (t, a, f)
    # the arm's bent part lies between the page and the mask
    B = M.panels["Page.R"].asm(t).inverted()
    zs = [(B @ q).z for q in world(M, "SwArm1.Arm", t)]
    top = (B @ M.panels["Mask1.Mask"].asm(t)).translation.z
    assert min(zs) > -0.01 and max(zs) < top, (t, zs, top)
s.swing_angle = 60.0
assert any("runs into its hinge" in w for w in model().warnings)
s.swing_angle, s.arm_len = 0.0, 80.0
assert any("back over the fold" in w for w in model().warnings)
s.arm_len = 40.0
for kind in ("BOX", "VFOLD", "STANDUP", "CUBE"):
    for side in ("R", "L"):
        reset()
        s = add("SWING")
        s.swing_side = side
        assert bpy.ops.popup.add(kind=kind, host=s.uid, fold="B") == {"FINISHED"}
        bpy.ops.popup.build()
        assert not warns(), (kind, side, warns())
        M = model()
        m = st.mechs[-1]
        assert M.placed[m.uid] is M.hosts[(s.uid, "B")], (kind, side)
        clean(M, "")
export_svg.export(sc, svg)
print("the arm bends clear of its hinge; things in the mask's corner")

# ---- 0.86.2: each bite step its own length and turn; 0.86.0's even steps
# moved on to them; the book's other hinge, flat shut
from popup_pro.props import migrate_bite  # noqa: E402

reset()
v = add("VFOLD")
v.height, v.glue = 70.0, 45.0
v.bite, v.bite_len, v.bite_angle = True, 42.0, 10.0
st.active = 0
assert bpy.ops.popup.bite_step_add() == {"FINISHED"}
assert len(v.bite_more) == 1 and v.bite_more[0].angle == 10.0
v.bite_more[0].length, v.bite_more[0].angle = 16.0, 10.0
for ln, tn in ((13.0, 12.0), (11.0, 14.0)):
    s = v.bite_more.add()
    s.length, s.angle = ln, tn
assert {"length", "angle"} <= set(props_shown(draw(ui.POPUP_PT_mechs)))
bpy.ops.popup.build()
assert not warns(), warns()
M = model()
assert "VFold1.Bite4R" in M.panels and "VFold1.Bite5R" not in M.panels
clean(M, "VFold1")
# each step carries on from the one before, across its crease
for t in M.samples:
    for a, b in (("Bite", "Bite2"), ("Bite2", "Bite3"), ("Bite3", "Bite4")):
        A_, B_ = world(M, f"VFold1.{a}R", t), world(M, f"VFold1.{b}R", t)
        assert len([w for w in B_ if min((w - q).length for q in A_) < 0.03]) >= 2, (a, b, t)
v.bite_more[2].length = 6.0  # (too short for its turn: its crease crosses)
assert any("crosses step 3's" in w for w in model().warnings), model().warnings
assert bpy.ops.popup.bite_step_remove(index=2) == {"FINISHED"}
assert len(v.bite_more) == 2
v.bite_more.clear()
v.bite_steps, v.bite_step_angle, v.bite_len = 3, 8.0, 36.0
migrate_bite(v)
assert v.bite_steps == 1 and [(round(s.length, 3), s.angle) for s in v.bite_more] == \
    [(12.0, 8.0), (12.0, 8.0)]
for shape in ("TRI", "BEAK_L", "BEAK_R"):  # (on a beak too)
    reset()
    v = add("VFOLD")
    v.shape, v.height, v.glue = shape, 75.0, 45.0
    v.bite, v.bite_len, v.bite_angle = True, 45.0, 10.0
    for ln, tn in ((16.0, 12.0), (13.0, 14.0)):
        s = v.bite_more.add()
        s.length, s.angle = ln, tn
    bpy.ops.popup.build()
    assert not warns(), (shape, warns())
    M = model()
    assert "VFold1.Bite3R" in M.panels and "VFold1.BiteRTab" in M.panels, shape
    clean(M, "VFold1")
    export_svg.export(sc, svg)
print("bite steps of their own, on panels and beaks")

for side in ("R", "L"):
    for dr in ("CW", "CCW"):
        reset()
        s = add("SWING")
        s.swing_side, s.swing_dir, s.swing_hinge = side, dr, "SHUT"
        assert "swing_hinge" in set(props_shown(draw(ui.POPUP_PT_mechs)))
        bpy.ops.popup.build()
        assert not warns(), (side, dr, warns())
        M = model()
        base = M.panels["Page.R" if side == "R" else "Page.L"]
        names = ["Swing1.LR", "Swing1.UR", "Swing1.UL", "Swing1.LL"]
        turned = []
        for t in M.samples + [M.tmax]:
            pts = {n: world(M, n, t) for n in names + ["Swing1.TabD", "Swing1.TabE"]}
            for a, b in zip(names[:3], names[1:]):
                assert len([w for w in pts[a] if min((w - q).length for q in pts[b]) < 0.05]) \
                    >= 2, (side, dr, t, a, b)
            for a, b in (("Swing1.LR", "Swing1.TabD"), ("Swing1.LL", "Swing1.TabE")):
                assert len([w for w in pts[a] if min((w - q).length for q in pts[b]) < 0.4]) \
                    >= 2, (side, dr, t, a, b)
            B = base.asm(t).inverted()
            dv = (B @ M.panels["SwArm1.End"].asm(t)).to_3x3() @ v3((1.0, 0.0))
            turned.append(math.degrees(math.atan2(dv.y, dv.x)))
        # flat shut: C lies in the page's plane shut, folded up open flat
        span = (turned[-1] - turned[0] + 180.0) % 360.0 - 180.0
        assert abs(abs(span) - 90.0) < 3.0 and (span < 0) == (dr == "CW"), (side, dr, span)
        B = base.asm(M.samples[0]).inverted()
        assert max(abs((B @ q).z) for n in names for q in world(M, n, M.samples[0])) < 1.5
        clean(M, "Swing1")
        clean(M, "SwArm1")
        export_svg.export(sc, svg)
print("the book's other hinge, flat shut")

addon.unregister()
print("V86 OK")
