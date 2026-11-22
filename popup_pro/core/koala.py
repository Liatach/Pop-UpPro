"""The animal face's pattern: one half of a hand-made koala, its creases as
drawn, measured off the flattened card (pixels of the photo, C along the
top, the ear's hinge along the bottom), then stretched to the landmarks.

Only numpy and math here: the pattern, and the face stood up from it open
flat (every facet kept its shape, the middle's corners in the mirror plane,
the ear's hinge on the page).
"""

import math

import numpy as np

# corners of the drawn half (photo pixels)
_PX = {
    "S": (427, 1478), "C1": (563, 1461), "C2": (722, 1441), "E": (805, 1430),
    "N1": (262, 1635), "T": (78, 1805),
    "R1": (440, 1775), "M1": (563, 1778), "Ap": (755, 1775),
    "H0": (298, 2052), "B1": (540, 2055), "B2": (742, 2060),
    "F": (1035, 1555), "P": (918, 1648),
    "Q": (865, 1797), "L1": (957, 1689), "R": (1030, 1603), "S2": (1137, 1718),
    "J4": (1098, 1825), "J5": (1000, 1965),
}
# the ear off its hinge (H0-B2), as cut
_EAR = [(748, 2190), (410, 2445), (258, 2222)]
# the facets as drawn, each round the same way
FACES = [
    ("S", "N1", "R1"), ("T", "H0", "N1"), ("N1", "H0", "R1"),
    ("R1", "H0", "B1", "M1"), ("S", "R1", "M1", "C1"), ("C1", "M1", "Ap", "C2"),
    ("M1", "B1", "B2", "Ap"), ("C2", "Ap", "P", "E"), ("E", "P", "F"),
    ("Ap", "B2", "J5", "Q"), ("Q", "J5", "J4", "L1"), ("L1", "J4", "S2", "R"),
]
C_EDGES = [("S", "C1"), ("C1", "C2"), ("C2", "E")]  # (the nose crease: the halves' fold)
SEAMS = [("Forehead", "S", "N1"), ("Forehead", "N1", "T"), ("Muzzle", "E", "F"),
         ("Chin", "R", "S2")]  # (glued to the other half, in the mirror plane)
MIRROR = ["S", "C1", "C2", "E", "N1", "T", "F", "R", "S2"]
HINGE = ["H0", "B1", "B2"]  # (the ear's hinge: glued down on the page)
_SCALE = 0.1  # (mm a pixel)


def _base():
    """The drawn half in mm: C up the y axis from S (y down it, towards the
    forehead), the half at x < 0."""
    S = np.array(_PX["S"], float)
    c = np.array(_PX["E"], float) - S
    c /= np.linalg.norm(c)
    n = np.array([c[1], -c[0]])
    if n @ (np.array(_PX["H0"], float) - S) < 0:
        n = -n  # (away from C, towards the hinge)

    def mm(p):
        d = np.array(p, float) - S
        return _SCALE * np.array([-(d @ n), -(d @ c)])

    return {k: mm(p) for k, p in _PX.items()}, [mm(p) for p in _EAR]


_K, _KEAR = _base()


def _cross(a, b):
    return float(a[0] * b[1] - a[1] * b[0])


def _ln(a, b):
    return float(np.linalg.norm(_K[a] - _K[b]))


# the koala's own landmarks (the defaults)
DEFAULTS = {
    "nose": _ln("S", "E"), "brow": _ln("S", "T"), "muzzle": _ln("E", "F"),
    "chin": _ln("R", "S2"), "mouth_w": _ln("Ap", "Q"), "mouth_d": _ln("Q", "R"),
    "jaw": _ln("Q", "J5"), "cheek": float(-_K["B1"][0]),
    "ear": float(max(abs(_cross(_K["B2"] - _K["H0"], q - _K["H0"]))
                     / np.linalg.norm(_K["B2"] - _K["H0"]) for q in _KEAR)),
}


def _rot(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s], [s, c]])


def pattern(nose, brow, muzzle, chin, mouth_w, mouth_d, mouth_a, jaw, cheek, ear):
    """The half's corners (mm, C up the y axis from S, the half at x < 0)
    and its ear, the koala's stretched to these landmarks."""
    K, D = _K, DEFAULTS
    sy = nose / D["nose"]
    sx = cheek / D["cheek"]
    p = {}
    for k in ("S", "C1", "C2", "E", "R1", "M1", "Ap", "H0", "B1", "B2"):
        p[k] = K[k] * np.array([sx, sy])
    # (the forehead's seam: its direction kept, its length set)
    p["T"] = K["T"] * (brow / D["brow"])
    p["N1"] = p["T"] * (_ln("S", "N1") / D["brow"])
    # (the muzzle's seam off the nose's tip, then the upper lip back to the
    # mouth's corner)
    p["F"] = p["E"] + (K["F"] - K["E"]) * (muzzle / D["muzzle"])
    fr = float(np.linalg.norm(K["P"] - K["F"]) / np.linalg.norm(K["Ap"] - K["F"]))
    p["P"] = p["F"] + fr * (p["Ap"] - p["F"])
    # (the mouth: its width at the corner, the lower lip, the chin and jaw, all
    # turned about the mouth's corner by its angle)
    Rm = _rot(math.radians(mouth_a))
    p["Q"] = p["Ap"] + Rm @ ((K["Q"] - K["Ap"]) * (mouth_w / D["mouth_w"]))
    p["R"] = p["Q"] + Rm @ ((K["R"] - K["Q"]) * (mouth_d / D["mouth_d"]))
    lr = float(np.linalg.norm(K["L1"] - K["Q"]) / D["mouth_d"])
    p["L1"] = p["Q"] + lr * (p["R"] - p["Q"])
    p["S2"] = p["R"] + Rm @ ((K["S2"] - K["R"]) * (chin / D["chin"]))
    p["J5"] = p["Q"] + Rm @ ((K["J5"] - K["Q"]) * (jaw / D["jaw"]))
    # (the chin's back corner: where it sat between the lip, chin and jaw)
    A0 = np.array([K["R"] - K["L1"], K["J5"] - K["L1"]]).T
    A1 = np.array([p["R"] - p["L1"], p["J5"] - p["L1"]]).T
    p["J4"] = p["L1"] + A1 @ np.linalg.solve(A0, K["J4"] - K["L1"])
    # (C one straight line, the ear's hinge another)
    for k in ("S", "C1", "C2", "E"):
        p[k] = np.array([0.0, p[k][1]])
    hv = (p["B2"] - p["H0"]) / np.linalg.norm(p["B2"] - p["H0"])
    p["B1"] = p["H0"] + hv * float((p["B1"] - p["H0"]) @ hv)
    # (the ear: off its hinge, its depth set)
    h0, h1 = K["H0"], K["B2"]
    ev = (h1 - h0) / np.linalg.norm(h1 - h0)
    nv = np.array([-ev[1], ev[0]])
    if nv @ (K["S"] - h0) > 0:
        nv = -nv
    g0, g1 = p["H0"], p["B2"]
    gv = (g1 - g0) / np.linalg.norm(g1 - g0)
    gn = np.array([-gv[1], gv[0]])
    if gn @ (p["S"] - g0) > 0:
        gn = -gn
    se = ear / D["ear"]
    ln0, ln1 = np.linalg.norm(h1 - h0), np.linalg.norm(g1 - g0)
    earp = []
    for q in _KEAR:
        d = q - h0
        earp.append(g0 + gv * (d @ ev) * (ln1 / ln0) + gn * (d @ nv) * se)
    return p, earp


def edges(p):
    """Every pair of corners of each facet (sides and across): its length."""
    out = {}
    for f in FACES:
        for i in range(len(f)):
            for j in range(i + 1, len(f)):
                out[(f[i], f[j])] = float(np.linalg.norm(p[f[i]] - p[f[j]]))
    return out


def stand(p, clear=0.5):
    """The face stood up open flat: x across (the left page at x < 0), y along
    the fold, z up off the card. Every facet kept its shape, the middle's
    corners at x = 0, the ear's hinge on the card (z = 0), everything else
    above it and left of the middle. Returns (corners, worst edge error)."""
    names = list(p)
    vi = {k: i for i, k in enumerate(names)}
    el = edges(p)
    ea = np.array([vi[a] for a, b in el])
    eb = np.array([vi[b] for a, b in el])
    L0 = np.array(list(el.values()))
    w = 1.0 / np.sqrt(np.maximum(L0, 1e-6))
    # (first guess: the half turned up off the middle, its hinge on the card)
    hx = -float(np.mean([p[k][0] for k in HINGE]))
    ca = 0.55
    sa = math.sqrt(1.0 - ca * ca)
    X = np.array([[p[k][0] * ca, p[k][1], hx * sa + p[k][0] * sa] for k in names])
    X0 = X.copy()
    mi = np.array([vi[k] for k in MIRROR])
    hi = np.array([vi[k] for k in HINGE])
    free = np.array([i for i in range(len(names)) if names[i] not in HINGE])
    side = np.array([i for i in range(len(names)) if names[i] not in MIRROR])
    n = len(names)
    iS = vi["S"]

    def resid(x, lam):
        P = x.reshape(n, 3)
        d = P[ea] - P[eb]
        ln = np.maximum(np.linalg.norm(d, axis=1), 1e-9)
        u = d / ln[:, None]
        rows = []
        J = []
        r1 = w * (ln - L0)
        J1 = np.zeros((len(L0), 3 * n))
        for k in range(3):
            np.add.at(J1, (np.arange(len(L0)), 3 * ea + k), w * u[:, k])
            np.add.at(J1, (np.arange(len(L0)), 3 * eb + k), -w * u[:, k])
        rows.append(r1)
        J.append(J1)
        for idx, comp, sc in ((mi, 0, 10.0), (hi, 2, 10.0)):
            Jx = np.zeros((len(idx), 3 * n))
            Jx[np.arange(len(idx)), 3 * idx + comp] = sc
            rows.append(sc * P[idx, comp])
            J.append(Jx)
        Jy = np.zeros((1, 3 * n))
        Jy[0, 3 * iS + 1] = 10.0
        rows.append(np.array([10.0 * P[iS, 1]]))
        J.append(Jy)
        # (above the card, left of the middle: only those through count)
        lo = free[P[free, 2] < clear]
        Jz = np.zeros((len(lo), 3 * n))
        Jz[np.arange(len(lo)), 3 * lo + 2] = 10.0
        rows.append(10.0 * (P[lo, 2] - clear))
        J.append(Jz)
        rt = side[P[side, 0] > 0.0]
        Jr = np.zeros((len(rt), 3 * n))
        Jr[np.arange(len(rt)), 3 * rt] = 10.0
        rows.append(10.0 * P[rt, 0])
        J.append(Jr)
        rows.append(lam * (x - X0.reshape(-1)))
        J.append(lam * np.eye(3 * n))
        return np.concatenate(rows), np.vstack(J)

    x = X.reshape(-1)
    for lam in (0.05, 0.01, 0.002, 0.0):
        for _ in range(60):
            rv, J = resid(x, lam)
            A = J.T @ J + 1e-6 * np.eye(3 * n)
            step = np.linalg.solve(A, -(J.T @ rv))
            mx = float(np.abs(step).max())
            if mx > 5.0:
                step *= 5.0 / mx
            x = x + step
            if mx < 1e-6:
                break
        X0 = x.reshape(n, 3).copy()
    P = x.reshape(n, 3)
    err = float(np.max(np.abs(np.linalg.norm(P[ea] - P[eb], axis=1) - L0)))
    return {k: P[vi[k]].copy() for k in names}, err
