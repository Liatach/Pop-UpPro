"""Roof kinematics (Birmingham 52): every fold stays shut, every glue join
stays glued, end tabs sit on their slope, and nets never overlap
themselves, for pyramids, hexagonal pyramids, tents, hips and tube caps."""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import bpy  # noqa: F401,E402  (provides mathutils)
from mathutils import Vector  # noqa: E402

from popup_pro.core.model import SAMPLES, Model  # noqa: E402


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



CASES = {
    "pyramid": dict(type="PYRAMID", x=25, y=80, depth=50, height=40, front=25, back=25),
    "hexagonal": dict(type="PYRAMID", x=25, y=80, depth=40, height=40, front=32, back=32),
    "recessed": dict(type="PYRAMID", x=25, y=80, depth=50, height=40, front=30, back=25,
                     front_style="IN"),
    "tent": dict(type="PYRAMID", x=25, y=60, depth=80, height=30, ridge=80, front=25,
                 back=25),
    "hip": dict(type="PYRAMID", x=25, y=60, depth=60, height=30, ridge=30, front=35,
                back=35),
    "tower cap": dict(type="TUBE", x=25, y=80, depth=40, height=50, front=32, back=32,
                      roof=True, roof_height=30),
    "house cap": dict(type="TUBE", x=25, y=60, depth=60, height=30, front=25, back=25,
                      roof=True, roof_height=25, ridge=40),
}
for name, mech in CASES.items():
    mech = dict(mech, uid=1, label=name, tab=10)
    for hold in ("RIGHT", "SYM"):
        m = Model(dict(W=148.5, H=210, hold=hold), [mech])
        m.check_fit()
        assert not m.warnings, (name, m.warnings)
        err = max(p.hinge.check for p in m.panels.values() if p.hinge)
        assert err < 5e-4, (name, err)
        folds = 0
        for n1, n2, p, q in shared_edges(m):
            if n1.startswith("Tube1.") and n2.startswith("Tube1."):
                continue  # the tube itself is tested elsewhere
            seps = [max((m.panels[n1].asm(t) @ x.to_3d() - m.panels[n2].asm(t) @ x.to_3d()).length
                        for x in (p, q)) for t in SAMPLES]
            assert max(seps) < (0.2 if "Tab" in n1 + n2 else 1e-3), (name, n1, n2, seps)
            folds += 1
        pre = next(k for k in m.pieces if k.startswith(("Pyramid", "Roof")))
        P = m.panels
        # each end's right half meets the right slope along its sloping edge
        glue = 0.0
        for end in "FB":
            hr, sr = P[f"{pre}.{end}R"], P[f"{pre}.SR"]
            for t in SAMPLES:
                pts = [sr.asm(t).inverted() @ (hr.asm(t) @ Vector((x, y, 0))) for x, y in hr.polys[0]]
                glue = max(glue, sorted(abs(v.z) for v in pts)[1])
        assert glue < 1e-3, (name, glue)
        # ends crease the same way front and back (a symmetric roof)
        if mech.get("front_style", "OUT") == mech.get("back_style", "OUT") and \
                mech["front"] == mech["back"]:
            def foot_out(end, t=30.0):
                p = P[f"{pre}.{end}L"]
                ys = [(p.asm(t) @ Vector((x, y, 0))).y for x, y in p.polys[0]]
                return min(ys) if end == "F" else max(ys)
            y0, y1 = mech["y"], mech["y"] + mech["depth"]
            assert abs((y0 - foot_out("F")) - (foot_out("B") - y1)) < 1e-2, name
        # nets don't overlap themselves
        for pc in m.pieces.values():
            ps = [(n, q) for n in pc.panels for q in P[n].polys]
            for i, (n1, q1) in enumerate(ps):
                for n2, q2 in ps[i + 1:]:
                    assert Model._overlap(q1, q2) < 0.5, (name, n1, n2)
    print(f"{name:10s} {folds:2d} folds shut, glue joins {glue:.0e} mm, hinge error {err:.0e} rad")

# a roof taller than the page is wide sticks out when shut
m = Model(dict(W=148.5, H=210), [dict(CASES["tower cap"], uid=1, label="Tall", tab=10,
                                      roof_height=90)])
assert any("sticks out" in w for w in m.warnings), m.warnings
print("ROOFS OK")
