"""Align: line mechanisms up along the fold they share, or across the card,
and space them evenly.

Everything is measured from the built model, never from per-kind sliders:
a mechanism's extent along its fold is where its panels lie in its host's
virtual (spine-style) frame at the set-up angle, so it is right for every
kind and every host. Positions are then moved by changing `y` (and a flap's
`x`); the caller rebuilds the model and calls `measure` again to mop up
anything that did not move one-for-one (a mechanism riding on another that
moved too, say).
"""

import math
import re

from mathutils import Vector

from .geom import v3

# placed by what they stand in or join: never moved by Align
FIXED = ("TETHER", "ROOF", "FRAME", "FLOOR", "CEILING", "PICTURE")
_UID = re.compile(r"^(?:D45|[A-Za-z]+?)(\d+)[.a-z]")  # (D45: the double 45 fold)

SLIT_MARGIN = 2.0  # mm of page kept past a flap's pull slit
FOLD_HOW = ("START", "CENTRE", "END", "DISTRIBUTE")
CARD_HOW = ("INNER", "HCENTRE", "OUTER", "BOTTOM", "VCENTRE", "TOP", "DIST_H", "DIST_V")


def uid_of(name):
    m = _UID.match(name)
    return int(m.group(1)) if m else None


def _points(model, uid, t):
    """World points of a mechanism's own panels (glue tabs only if that is
    all it has) at opening t."""
    body, tabs = [], []
    for name in model.order:
        if uid_of(name) != uid:
            continue
        p = model.panels[name]
        if p.outside:
            continue
        A = p.asm(t)
        pts = [A @ v3(q) for poly in p.polys for q in poly]
        (tabs if p.kind == "tab" else body).extend(pts)
    return body or tabs


def fold_extent(model, uid, t=None):
    """(lo, hi) of a mechanism along the fold it stands on, in the host's
    virtual frame (y up the fold), or None."""
    host = model.placed.get(uid)
    if host is None:
        return None
    t = model.t_ref if t is None else t
    pts = _points(model, uid, t)
    if not pts:
        return None
    Li = host.L(t).inverted()
    ys = [(Li @ p).y for p in pts]
    return min(ys), max(ys)


def fold_span(model, host):
    """(lo, hi) of the fold itself in its virtual frame: where the fold line
    (virtual x = 0) runs across both of its panels."""
    spans = []
    for pn, T in ((host.p1, host.T1), (host.p2, host.T2)):
        p = model.panels.get(pn)
        if p is None:
            return None
        Ti = T.inverted()
        ys = []
        for poly in p.polys:
            q = [Ti @ v3(c) for c in poly]
            for i in range(len(q)):
                a, b = q[i], q[(i + 1) % len(q)]
                if abs(a.x) < 0.05:
                    ys.append(a.y)
                if (a.x < -0.05 and b.x > 0.05) or (a.x > 0.05 and b.x < -0.05):
                    ys.append(a.y + (b.y - a.y) * (-a.x) / (b.x - a.x))
        if not ys:
            return None
        spans.append((min(ys), max(ys)))
    lo = max(s[0] for s in spans)
    hi = min(s[1] for s in spans)
    return (lo, hi) if hi > lo else None


def flap_rect(m, W):
    """A flap on the card (the flap, its hinge tab and pull slit), in card pattern
    (x across, y up), as the model lays it out."""
    left = m.get("side", "R") == "L"
    hx = -float(m["x"]) if left else float(m["x"])
    hy = float(m["y"])
    uu = {"TOP": (0, -1), "BOTTOM": (0, 1), "LEFT": (1, 0), "RIGHT": (-1, 0)}[
        m.get("hinge", "TOP")]
    U = Vector((uu[0], uu[1], 0.0))
    Hd = Vector((0.0, 0.0, 1.0)).cross(U)
    Wf, Lf = float(m["width"]), float(m["length"])
    # behind the hinge: its glued tab, then the slit the pull strip runs
    # through (which must stay on the page, with a little paper past it)
    sl = min(float(m.get("tab", 10.0)), 30.0) + float(m.get("gap", 4.0)) + SLIT_MARGIN
    cs = [Vector((hx, hy, 0.0)) + a * U + b * Hd for a in (-sl, Lf)
          for b in (-Wf / 2, Wf / 2)]
    return (min(c.x for c in cs), max(c.x for c in cs),
            min(c.y for c in cs), max(c.y for c in cs))


def card_extent(model, m, axis):
    """(lo, hi) of a mechanism up the card (axis "Y", along the spine), or
    a flap's out across its page (axis "X": distance from the spine, so a
    flap on the left page lines up with its mirror image on the right), or
    None."""
    if m["type"] == "FLAP":
        x0, x1, y0, y1 = flap_rect(m, model.W)
        if axis == "Y":
            return y0, y1
        return (-x1, -x0) if m.get("side", "R") == "L" else (x0, x1)
    if axis == "X":
        return None  # only flaps move across a page
    pts = _points(model, m["uid"], model.t_ref)
    if not pts:
        return None
    ys = [p.y for p in pts]  # the pages turn about the spine (world Y)
    return min(ys), max(ys)


def y_sense(model, m):
    """How a mechanism's `y` moves it up the card: +1 or -1 when its fold
    runs along the spine, 0 when it doesn't (on a V-fold's crease, say)."""
    if m["type"] == "FLAP":
        return 1.0
    host = model.placed.get(m["uid"])
    if host is None:
        return 0.0
    Y = host.dirs(model.t_ref)[3]
    d = Y.normalized().dot(Vector((0.0, 1.0, 0.0)))
    return math.copysign(1.0, d) if abs(d) > 0.99 else 0.0


def feature(lo, hi, how):
    if how in ("START", "INNER", "BOTTOM", "DISTRIBUTE", "DIST_H", "DIST_V"):
        return lo
    if how in ("END", "OUTER", "TOP"):
        return hi
    return 0.5 * (lo + hi)


def targets(ext, how, ref, ref_uid=None, bounds=None):
    """Where each mechanism's aligned feature should go.

    ext: {uid: (lo, hi)} measured; ref: "ACTIVE", "SELECTION" or "HOST"
    (the fold's ends, or the card's edges: `bounds` (lo, hi), per uid when
    a dict). Returns {uid: target value of feature(lo, hi, how)}."""
    if not ext:
        return {}
    dist = how in ("DISTRIBUTE", "DIST_H", "DIST_V")
    if dist:
        order = sorted(ext, key=lambda u: 0.5 * (ext[u][0] + ext[u][1]))
        sizes = [ext[u][1] - ext[u][0] for u in order]
        if ref == "HOST" and bounds is not None:
            b = bounds if not isinstance(bounds, dict) else bounds[order[0]]
            gap = (b[1] - b[0] - sum(sizes)) / (len(order) + 1)
            at = b[0] + gap
        else:
            if len(order) < 3:
                return {u: ext[u][0] for u in order}
            span = ext[order[-1]][1] - ext[order[0]][0]
            gap = (span - sum(sizes)) / (len(order) - 1)
            at = ext[order[0]][0]
        out = {}
        for u, s in zip(order, sizes):
            out[u] = at
            at += s + gap
        return out
    if ref == "ACTIVE" and ref_uid in ext:
        v = feature(*ext[ref_uid], how)
        return {u: v for u in ext}
    if ref == "HOST" and bounds is not None:
        out = {}
        for u in ext:
            b = bounds[u] if isinstance(bounds, dict) else bounds
            out[u] = feature(b[0], b[1], how)
        return out
    lo = min(e[0] for e in ext.values())
    hi = max(e[1] for e in ext.values())
    v = feature(lo, hi, how)
    return {u: v for u in ext}
