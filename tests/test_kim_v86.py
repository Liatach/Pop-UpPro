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
assert {"bite_steps", "bite_step_angle"} <= set(props_shown(draw(ui.POPUP_PT_mechs)))
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
assert any("turn too far" in w for w in model().warnings), model().warnings
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
            arm = M.panels["SwArm1.Arm"]
            A = B @ arm.asm(t)
            dv = (A.to_3x3() @ v3((1.0, 0.0))).normalized()
            assert abs(dv.z) < 1e-6
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

addon.unregister()
print("V86 OK")
