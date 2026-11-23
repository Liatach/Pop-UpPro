"""The animal face's patterns: one half of each hand-made face (a koala, a
goblin), its creases as drawn, measured off the flattened card (pixels of
the photo, C along one edge of the drawn half, the ear's hinge along the
other), then stretched to the landmarks.

Only numpy and math here: the pattern, and the face stood up from it open
flat (every facet kept its shape, the middle's corners in the mirror plane,
the ear's hinge on the page).
"""

import math

import numpy as np

_SCALE = 0.1  # (mm a pixel)

# Each base: its corners (photo pixels), the ear off its hinge (H0-B2), the
# facets as drawn (each round the same way), C's corners in order, the seams
# (glued to the other half, in the mirror plane) and the other corners on the
# mirror plane. Shared names mean the same landmark in each: S and E the ends
# of C (between the eyes, the nose's tip), T the top of the head, Ap the
# mouth's corner, Q the slot's inner corner below it, R the lower lip's end,
# S2 the chin's, J5 the jaw's, H0-B1-B2 the ear's hinge.
BASES = {
    "KOALA": dict(
        px={
            "S": (427, 1478), "C1": (563, 1461), "C2": (722, 1441), "E": (805, 1430),
            "N1": (262, 1635), "T": (78, 1805),
            "R1": (440, 1775), "M1": (563, 1778), "Ap": (755, 1775),
            "H0": (298, 2052), "B1": (540, 2055), "B2": (742, 2060),
            "F": (1035, 1555), "P": (918, 1648),
            "Q": (865, 1797), "L1": (957, 1689), "R": (1030, 1603), "S2": (1137, 1718),
            "J4": (1098, 1825), "J5": (1000, 1965),
        },
        ear=[(748, 2190), (410, 2445), (258, 2222)],
        faces=[
            ("S", "N1", "R1"), ("T", "H0", "N1"), ("N1", "H0", "R1"),
            ("R1", "H0", "B1", "M1"), ("S", "R1", "M1", "C1"), ("C1", "M1", "Ap", "C2"),
            ("M1", "B1", "B2", "Ap"), ("C2", "Ap", "P", "E"), ("E", "P", "F"),
            ("Ap", "B2", "J5", "Q"), ("Q", "J5", "J4", "L1"), ("L1", "J4", "S2", "R"),
        ],
        cpath=["S", "C1", "C2", "E"],
        seams=[("Forehead", "S", "N1"), ("Forehead", "N1", "T"), ("Muzzle", "E", "F"),
               ("Chin", "R", "S2")],
        mirror=["N1", "T", "F", "R", "S2"],
        band=["R1", "M1", "Ap", "H0", "B1", "B2"],
        brow=["N1"],  # (corners carried with the forehead)
    ),
    "GOBLIN": dict(
        px={
            "S": (370, 1342), "C0": (442, 1335), "C1": (545, 1324), "C2": (610, 1318),
            "E": (737, 1305),
            "N1": (313, 1466), "K": (253, 1652), "T": (163, 1499),
            "R1": (390, 1567), "M1": (503, 1600), "A3": (613, 1607), "Ap": (893, 1530),
            "H0": (300, 1718), "B1": (474, 1769), "B2": (623, 1813), "V": (913, 1742),
            "Q": (985, 1492), "L1": (955, 1440), "R": (902, 1357), "S2": (1135, 1337),
            "J4": (1135, 1492), "J5": (1072, 1568),
        },
        ear=[(453, 2127)],
        faces=[
            ("S", "C0", "R1", "N1"), ("S", "N1", "K", "T"), ("N1", "R1", "H0", "K"),
            ("C0", "C1", "M1", "R1"), ("C1", "C2", "A3", "M1"), ("C2", "E", "Ap", "A3"),
            ("R1", "M1", "B1", "H0"), ("M1", "A3", "B2", "B1"), ("A3", "Ap", "V", "B2"),
            ("Ap", "Q", "J5", "V"), ("Q", "L1", "J4", "J5"), ("L1", "R", "S2", "J4"),
        ],
        cpath=["S", "C0", "C1", "C2", "E"],
        seams=[("Forehead", "S", "T"), ("Chin", "R", "S2")],
        mirror=["T", "R", "S2"],
        band=["R1", "M1", "A3", "Ap", "H0", "B1", "B2", "V"],
        brow=["N1", "K"],
    ),
}
LABELS = {"KOALA": "Koala", "GOBLIN": "Goblin"}
HINGE = ["H0", "B1", "B2"]  # (the ear's hinge: glued down on the page)


def _cross(a, b):
    return float(a[0] * b[1] - a[1] * b[0])


def _rot(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s], [s, c]])


def _mm(B):
    """The drawn half in mm: C up the y axis from S (y down it, towards the
    forehead), the half at x < 0."""
    px = B["px"]
    S = np.array(px["S"], float)
    c = np.array(px["E"], float) - S
    c /= np.linalg.norm(c)
    n = np.array([c[1], -c[0]])
    if n @ (np.array(px["H0"], float) - S) < 0:
        n = -n  # (away from C, towards the hinge)

    def mm(p):
        d = np.array(p, float) - S
        return _SCALE * np.array([-(d @ n), -(d @ c)])

    return {k: mm(p) for k, p in px.items()}, [mm(p) for p in B["ear"]]


_K = {}
DEFAULTS = {}
for _b, _B in BASES.items():
    K_, E_ = _mm(_B)
    _K[_b] = (K_, E_)

    def _ln(a, b, K_=K_):
        return float(np.linalg.norm(K_[a] - K_[b]))

    DEFAULTS[_b] = {
        "nose": _ln("S", "E"), "brow": _ln("S", "T"),
        "muzzle": _ln("E", "F") if "F" in K_ else 0.0,
        "chin": _ln("R", "S2"), "mouth_w": _ln("Ap", "Q"), "mouth_d": _ln("Q", "R"),
        "jaw": _ln("Q", "J5"), "cheek": float(-K_["B1"][0]),
        "ear": float(max(abs(_cross(K_["B2"] - K_["H0"], q - K_["H0"]))
                         / np.linalg.norm(K_["B2"] - K_["H0"]) for q in E_)),
    }
_MZ_LEAN = 20.0  # (a muzzle added to a base drawn without one: its lean off C's line)


def _aff(src, dst, q):
    """q carried by the affine map taking triangle src onto dst."""
    A0 = np.array([src[1] - src[0], src[2] - src[0]]).T
    A1 = np.array([dst[1] - dst[0], dst[2] - dst[0]]).T
    return dst[0] + A1 @ np.linalg.solve(A0, q - src[0])


def pattern(nose, brow, muzzle, chin, mouth_w, mouth_d, mouth_a, jaw, cheek, ear,
            base="KOALA"):
    """The half's corners (mm, C up the y axis from S, the half at x < 0),
    its ear and its topology, the base's stretched to these landmarks.
    Muzzle under 1 mm: none (the upper lip straight off the nose's tip)."""
    B = BASES[base]
    K, KE = _K[base]
    D = DEFAULTS[base]
    sy = nose / D["nose"]
    sx = cheek / D["cheek"]
    p = {}
    for k in B["cpath"] + B["band"]:
        p[k] = K[k] * np.array([sx, sy])
    # (the forehead's seam: its direction kept, its length set; what lies
    # between it and the hinge carried with it)
    p["T"] = K["T"] * (brow / D["brow"])
    for k in B["brow"]:
        p[k] = _aff((K["S"], K["T"], K["H0"]), (p["S"], p["T"], p["H0"]), K[k])
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
    p["J4"] = _aff((K["L1"], K["R"], K["J5"]), (p["L1"], p["R"], p["J5"]), K["J4"])
    # (C one straight line, the ear's hinge another)
    for k in B["cpath"]:
        p[k] = np.array([0.0, p[k][1]])
    hv = (p["B2"] - p["H0"]) / np.linalg.norm(p["B2"] - p["H0"])
    p["B1"] = p["H0"] + hv * float((p["B1"] - p["H0"]) @ hv)
    faces = [tuple(f) for f in B["faces"]]
    seams = list(B["seams"])
    mirror = list(B["cpath"]) + list(B["mirror"])
    # (the muzzle: the seam off the nose's tip, the upper lip back from its
    # end to the mouth's corner)
    has_mz = "F" in K
    if muzzle >= 1.0 and has_mz:
        p["F"] = p["E"] + (K["F"] - K["E"]) * (muzzle / D["muzzle"])
        fr = float(np.linalg.norm(K["P"] - K["F"]) / np.linalg.norm(K["Ap"] - K["F"]))
        p["P"] = p["F"] + fr * (p["Ap"] - p["F"])
    elif muzzle >= 1.0:
        # (straight on down C's line, turned a little towards the half)
        cv = (p["E"] - p["S"]) / np.linalg.norm(p["E"] - p["S"])
        tv = np.array([-1.0, 0.0])
        a_ = math.radians(_MZ_LEAN)
        p["F"] = p["E"] + muzzle * (math.cos(a_) * cv + math.sin(a_) * tv)
        faces.append(("E", "F", "Ap"))
        seams.insert(1, ("Muzzle", "E", "F"))
        mirror.append("F")
    elif has_mz:
        # (none: the lip straight from the nose's tip to the mouth's corner)
        faces = [f for f in faces if f != ("E", "P", "F")]
        faces = [("C2", "Ap", "E") if f == ("C2", "Ap", "P", "E") else f for f in faces]
        seams = [s for s in seams if s[0] != "Muzzle"]
        mirror.remove("F")
    p = {k: v for k, v in p.items() if any(k in f for f in faces)}
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
    for q in KE:
        d = q - h0
        earp.append(g0 + gv * (d @ ev) * (ln1 / ln0) + gn * (d @ nv) * se)
    cp = B["cpath"]
    topo = dict(faces=faces, seams=seams, mirror=mirror, hinge=list(HINGE),
                c_edges=list(zip(cp, cp[1:])))
    return p, earp, topo


def edges(p, faces):
    """Every pair of corners of each facet (sides and across): its length."""
    out = {}
    for f in faces:
        for i in range(len(f)):
            for j in range(i + 1, len(f)):
                out[(f[i], f[j])] = float(np.linalg.norm(p[f[i]] - p[f[j]]))
    return out


def stand(p, topo, clear=0.5):
    """The face stood up open flat: x across (the left page at x < 0), y along
    the fold, z up off the card. Every facet kept its shape, the middle's
    corners at x = 0, the ear's hinge on the card (z = 0), everything else
    above it and left of the middle. Returns (corners, worst edge error)."""
    names = list(p)
    vi = {k: i for i, k in enumerate(names)}
    el = edges(p, topo["faces"])
    ea = np.array([vi[a] for a, b in el])
    eb = np.array([vi[b] for a, b in el])
    L0 = np.array(list(el.values()))
    w = 1.0 / np.sqrt(np.maximum(L0, 1e-6))
    hinge, mirror = topo["hinge"], topo["mirror"]
    # (first guess: the half turned up off the middle, its hinge on the card)
    hx = -float(np.mean([p[k][0] for k in hinge]))
    ca = 0.55
    sa = math.sqrt(1.0 - ca * ca)
    X = np.array([[p[k][0] * ca, p[k][1], hx * sa + p[k][0] * sa] for k in names])
    X0 = X.copy()
    mi = np.array([vi[k] for k in mirror])
    hi = np.array([vi[k] for k in hinge])
    free = np.array([i for i in range(len(names)) if names[i] not in hinge])
    side = np.array([i for i in range(len(names)) if names[i] not in mirror])
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
