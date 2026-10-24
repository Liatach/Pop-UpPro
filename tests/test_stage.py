"""Stage set kinematics (Birmingham 118, carousel stages): frames pull flat
exactly when the stage is fully open, floors and ceilings lie flat there
too and fold into the stage as it closes, and frames are cut to clear them."""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import bpy  # noqa: F401,E402  (provides mathutils)
from mathutils import Vector  # noqa: E402

from popup_pro.core.model import Model  # noqa: E402


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




MECHS = [dict(type="FRAME", uid=1, label="Staging", x=147.5, tab=8),
         dict(type="FRAME", uid=2, label="Frame 1", x=100, y=10, height=170, tab=8),
         dict(type="FRAME", uid=3, label="Frame 2", x=60, tab=8),
         dict(type="FLOOR", uid=4, label="Floor", depth=148.5, tab=8),
         dict(type="CEILING", uid=5, label="Ceiling", depth=148.5, tab=8)]
for n in (3, 5, 6, 9):
    tmax = 360.0 / n
    m = Model(dict(W=148.5, H=210, hold="SYM", tmax=tmax), MECHS)
    m.check_fit()
    assert not m.warnings, (n, m.warnings)
    err = max(p.hinge.check for p in m.panels.values() if p.hinge)
    assert err < 2e-3, (n, err)
    for n1, n2, p, q in shared_edges(m):
        seps = [max((m.panels[n1].asm(t) @ x.to_3d() - m.panels[n2].asm(t) @ x.to_3d()).length
                    for x in (p, q)) for t in m.samples]
        assert max(seps) < (0.2 if "Tab" in n1 + n2 else 1e-3), (n, n1, n2, seps)
    # frames: halves flat (parallel) at full open, folded back before
    for uid in (1, 2, 3):
        L, R = m.panels[f"Frame{uid}.L"], m.panels[f"Frame{uid}.R"]
        nl = L.asm(tmax).to_3x3() @ Vector((0, 0, 1))
        nr = R.asm(tmax).to_3x3() @ Vector((0, 0, 1))
        assert nl.dot(nr) > 0.9999, (n, uid, nl.dot(nr))
        half = 0.5 * tmax
        nl2 = L.asm(half).to_3x3() @ Vector((0, 0, 1))
        nr2 = R.asm(half).to_3x3() @ Vector((0, 0, 1))
        assert nl2.dot(nr2) < 0.999, (n, uid)
        assert abs(m.frames[uid]["width"] - 2 * m.frames[uid]["depth"] *
                   math.sin(math.radians(half))) < 1e-6
    # floor flat at full open, rising into the stage before; ceiling dropping
    for key, up in (("VFold4", 1.0), ("VFold5", -1.0)):
        c = m.crease(key, tmax)[0]
        assert abs(c.y) < 1e-3, (n, key, c)
        assert up * m.crease(key, 0.5 * tmax)[0].y > 0.1, (n, key)
    # frames stay above the floor and below the ceiling all the way
    worst = 0.0
    for uid in (1, 2, 3):
        F = m.panels[f"Frame{uid}.L"]
        for key, up in (("VFold4.HalfL", 1.0), ("VFold5.HalfL", -1.0)):
            fl = m.panels[key]
            for t in m.samples[1:-1]:
                A, B = F.asm(t), fl.asm(t)
                nf = B.to_3x3() @ Vector((0, 0, 1))
                if nf.y * up < 0:
                    nf = -nf
                # the floor half spans its triangle only: test frame corners over it
                for x, y in F.polys[0]:
                    w = A @ Vector((x, y, 0))
                    loc = B.inverted() @ w
                    tri = [Vector((q[0], q[1], 0)) for q in fl.polys[0]]
                    u = Vector((loc.x, loc.y, 0))
                    inside = all((tri[(i + 1) % 3] - tri[i]).cross(u - tri[i]).z >= -1e-6
                                 for i in range(3)) or all(
                        (tri[(i + 1) % 3] - tri[i]).cross(u - tri[i]).z <= 1e-6 for i in range(3))
                    if inside:
                        worst = min(worst, nf.dot(w - B.translation))
    assert worst > -0.05, (n, worst)
    print(f"{n} stages ({tmax:.0f} deg): frames flat when open, floor and ceiling clear, "
          f"hinge error {err:.0e}")

m = Model(dict(W=148.5, H=210, hold="SYM", tmax=180.0), MECHS[3:4])
assert any("three or more stages" in w for w in m.warnings), m.warnings
print("floor on a two-stage carousel refused")
print("STAGE OK")
