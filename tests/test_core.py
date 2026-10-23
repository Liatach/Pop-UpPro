"""Kinematics checks: hinge driver formulas match the solved geometry, and
creases and glue lines stay closed at every open angle. Needs mathutils
(run with Blender's Python or `pip install bpy`)."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import bpy  # noqa: F401,E402  (provides mathutils)
from mathutils import Vector  # noqa: E402

from popup_pro.core.model import SAMPLES, Model  # noqa: E402

MECHS = [
    dict(type="VFOLD", uid=1, label="V-fold 1", y=70, phi_l=60, phi_r=60, alpha_l=80,
         alpha_r=80, glue=40, height=50, tab=12, tab_side="IN"),
    dict(type="BOX", style="GLUED", uid=2, label="Box 1", y=130, width=50, height=40,
         depth=30, tab=12),
    dict(type="BOX", style="CUT", uid=3, label="Box layer 1", y=10, width=30, height=25,
         depth=35),
    dict(type="VFOLD", uid=4, label="V-fold 2", y=150, phi_l=50, phi_r=65, alpha_l=70,
         alpha_r=85, glue=30, height=35, tab=10, tab_side="OUT"),
]
STACK = [
    dict(type="BOX", style="CUT", uid=1, label="Layer", y=12, width=62, height=40, depth=50),
    dict(type="BOX", style="CUT", uid=2, label="Step up", y=20, width=25, height=20,
         depth=20, host=1, fold="A"),
    dict(type="BOX", style="CUT", uid=3, label="Inset", y=30, width=20, height=15,
         depth=15, host=1, fold="C"),
    dict(type="BOX", style="CUT", uid=4, label="Step front", y=50, width=20, height=10,
         depth=15, host=1, fold="B"),
    dict(type="BOX", style="GLUED", uid=5, label="Glued", y=92, width=50, height=40,
         depth=35, tab=12),
    dict(type="BOX", style="GLUED", uid=6, label="Glued on top", y=102, width=25,
         height=20, depth=20, tab=8, host=5, fold="A"),
    dict(type="BOX", style="CUT", uid=7, label="Inset in glued", y=107, width=15,
         height=12, depth=12, host=5, fold="C"),
    dict(type="VFOLD", uid=8, label="Beak", y=150, phi_l=60, phi_r=60, alpha_l=72,
         alpha_r=72, glue=22, height=30, tab=8, tab_side="IN", shape="TRI"),
    dict(type="MOUTH", uid=9, label="Mouth", y=192, jaw=22, upper=11, lower=9),
]


def shared_edges(m):
    """Edges two panels of one piece share in the flat pattern."""
    out = []
    for piece in m.pieces.values():
        segs = [(n, Vector(poly[i]), Vector(poly[(i + 1) % len(poly)]))
                for n in piece.panels for poly in m.panels[n].polys for i in range(len(poly))]
        for i, (n1, a1, b1) in enumerate(segs):
            for n2, a2, b2 in segs[i + 1:]:
                L = (b1 - a1).length
                if n1 == n2 or L < 1e-6:
                    continue
                u = (b1 - a1) / L
                nrm = Vector((-u.y, u.x))
                if abs((a2 - a1).dot(nrm)) > 1e-4 or abs((b2 - a1).dot(nrm)) > 1e-4:
                    continue
                t0, t1 = sorted(((a2 - a1).dot(u), (b2 - a1).dot(u)))
                lo, hi = max(0, t0), min(L, t1)
                if hi - lo > 1e-3:
                    out.append((n1, n2, a1 + u * lo, a1 + u * hi))
    return out


for hold in ("RIGHT", "SYM"):
    m = Model(dict(W=148.5, H=210, hold=hold), STACK)
    m.check_fit()
    assert not m.warnings, m.warnings
    folds = slits = 0
    for n1, n2, p, q in shared_edges(m):
        seps = [max((m.panels[n1].asm(t) @ x.to_3d() - m.panels[n2].asm(t) @ x.to_3d()).length
                    for x in (p, q)) for t in SAMPLES]
        tol = 0.2 if "Tab" in n1 + n2 else 1e-3
        if max(seps) < tol:
            folds += 1
        else:
            assert min(seps[3:9]) > tol, (n1, n2, seps)  # a slit, never half-joined
            slits += 1
    print(f"{hold:5s} stacked/inset/beak/mouth: {folds} folds, {slits} slits, consistent")

bad = Model(dict(W=148.5, H=210), STACK[7:8] + [dict(STACK[8], y=165)])
bad.check_fit()
assert any("overlap" in w for w in bad.warnings), bad.warnings
print("overlap warning:", [w for w in bad.warnings if "overlap" in w][0])


def gap(a, b, q):
    return (a.asm(t) @ Vector(q) - b.asm(t) @ Vector(q)).length


for hold in ("RIGHT", "SYM", "LEFT"):
    m = Model(dict(W=148.5, H=210, hold=hold), MECHS)
    m.check_fit()
    err = max(p.hinge.check for p in m.panels.values() if p.hinge)
    assert err < 1e-4, err
    worst = 0.0
    P = m.panels
    for t in SAMPLES:
        for base, L in (("VFold1", 50), ("VFold4", 35)):
            for q in ((0, 0, 0), (0, L, 0)):  # crease stays shared
                worst = max(worst, gap(P[base + ".HalfL"], P[base + ".HalfR"], q))
        worst = max(worst, gap(P["Box2.AC"], P["Box2.CB"], (30, 0, 0)))
        worst = max(worst, gap(P["Box2.CB"], P["Box2.TabB"], (70, 25, 0)) - 0.15)
        worst = max(worst, gap(P["Box3.AC"], P["Box3.CB"], (10, 15, 0)))
        worst = max(worst, gap(P["Box3.CB"], P["Page.R"], (35, 15, 0)))
    assert worst < 1e-3, worst
    print(f"{hold:5s} hinge formula error {err:.1e} rad, closure {worst:.1e} mm")

bad = dict(MECHS[0], alpha_l=45, alpha_r=45)
m = Model(dict(W=148.5, H=210), [bad])
assert any("tears" in w for w in m.warnings), m.warnings
print("tear warning:", m.warnings[0])
print("CORE OK")
