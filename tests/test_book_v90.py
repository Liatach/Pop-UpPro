"""v0.90 (v0.92): the animal face as a mirrored low-poly mesh on the fold, the
koala's pattern."""
# families: tubes
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
import popup_pro as addon  # noqa: E402
from popup_pro.core.layout import build_layout  # noqa: E402
from popup_pro import build  # noqa: E402
from popup_pro import export_svg, ui  # noqa: E402
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


# ---- a mirrored low-poly face on the fold, facet for facet a hand-made
# koala's: laid out flat in one piece, crushed flat as the card closes
reset()
f = add("HEAD")
assert f.label.startswith("Face")
shown = set(props_shown(draw(ui.POPUP_PT_mechs)))
assert {"head_brow", "head_nose", "head_muzzle", "head_chin", "mouth_w", "mouth_d",
        "mouth_a", "head_jaw", "ear_base", "ear_size", "head_base"} <= shown, shown
assert "ear_clock" not in shown and "height" not in shown, shown
bpy.ops.popup.build()
assert not warns(), warns()
M = model()
L = sorted(n for n in M.panels if n.startswith("Head1.L"))
assert len(L) == 20 and all(n.replace(".L", ".R") in M.panels for n in L), L
tabs = [n for n in M.panels if n.startswith("Head1.") and n.endswith("Tab")]
assert {"Forehead", "Muzzle", "Chin"} <= {n[6:].rstrip("0123456789Tab") for n in tabs}, tabs
assert "Head1.EarL" in M.panels and "Head1.EarR" in M.panels
# (each tab folds off its facet along the whole seam: its fold a crease, not a cut)
for n in tabs:
    k_ = next(k for k in M.fold_kind if n in k)
    o_ = next(x for x in k_ if x != n)
    po = [v3(q) for q in M.panels[o_].polys[0]]
    on = [q for q in M.panels[n].polys[0]
          if min(((v3(q) - a_).cross(b_ - a_)).length / max((b_ - a_).length, 1e-9)
                 for a_, b_ in zip(po, po[1:] + po[:1])) < 1e-3]
    assert len(on) >= 2, n


def corners(n, t):
    return world(M, n, t)


def gaps(t):
    """How far apart the facets' shared corners come (each facet's a rigid
    piece of card)."""
    pts = {}
    for n in L:
        P_ = M.panels[n]
        A = P_.asm(t)
        for q in P_.polys[0]:
            pts.setdefault((round(q[0], 3), round(q[1], 3)), []).append(A @ v3(q))
    return max(max((a_ - b_).length for a_ in v for b_ in v) for v in pts.values())


for t in M.samples + [M.tmax, 12.0, 6.0, 3.0]:
    # the halves meet down the middle: every left corner on the mirror plane
    # has its right twin there too
    for n in L:
        wl, wr = corners(n, t), corners(n.replace(".L", ".R"), t)
        for w in wl:
            if abs(w.x) < 0.05 and t >= 5.0:  # (near shut, everything's near the middle)
                assert min((w - v).length for v in wr) < 0.3, (t, n, w)
        # (and never crosses it: the left half stays left)
        assert max(w.x for w in wl) < 0.3, (t, n)
    # the facets stay joined (a hair apart at most)
    assert gaps(t) < 0.5, (t, gaps(t))
    # every facet is a true turn and shift of its pattern (no stretch, no
    # mirror: the rig can follow it)
    for n in L:
        A = M.panels[n].asm(t).to_3x3()
        assert abs(A.determinant() - 1.0) < 1e-4, (t, n)
clean(M, "Head1")
# the seams down the middle stay ridges all the way shut: the facets off each
# fall away towards the card (the nose's tip and the chin never cave in)
from popup_pro.core import koala as KO  # noqa: E402


def ridges(M, f):
    pk, _, tp = KO.pattern(f.head_nose, f.head_brow, f.head_muzzle, f.head_chin, f.mouth_w,
                           f.mouth_d, f.mouth_a, f.head_jaw, f.ear_base, f.ear_size,
                           base=f.head_base)
    L = sorted(n for n in M.panels if n.startswith("Head1.L"))
    for _, a_, b_ in tp["seams"]:
        pa_, pb_ = v3(pk[a_]), v3(pk[b_])
        for n in L:
            P_ = M.panels[n]
            qs = [v3(q) for q in P_.polys[0]]
            if min((q - pa_).length for q in qs) > 0.05 or min((q - pb_).length for q in qs) > 0.05:
                continue
            for t in (150.0, 90.0, 60.0, 40.0, 20.0, 10.0):
                l_, r_, nl_, nr_ = M.dirs(t)
                e_ = (l_ + r_).normalized()
                A = P_.asm(t)
                wa, wb = A @ pa_, A @ pb_
                u_ = (wb - wa).normalized()
                c_ = sum((A @ q for q in qs), v3((0, 0))) / len(qs) - wa
                c_ -= c_.dot(u_) * u_
                assert c_.dot(e_ - e_.dot(u_) * u_) < 0.0, (a_, b_, n, t)


def folds_ok(M, f, worst=-10.0):
    """No crease goes valley more than a few degrees on the way shut: left to
    themselves, card's creases sit a little mountain."""
    import numpy as np
    pk, _, tp = KO.pattern(f.head_nose, f.head_brow, f.head_muzzle, f.head_chin, f.mouth_w,
                           f.mouth_d, f.mouth_a, f.head_jaw, f.ear_base, f.ear_size,
                           base=f.head_base)
    _, _, out = KO.stand(pk, tp)
    names = list(pk)
    cr = KO.creases(pk, tp["faces"])
    vi = {k: i for i, k in enumerate(names)}
    idx = tuple(np.array([vi[c[k]] for c in cr]) for k in range(4)) + \
        (np.array([c[4] for c in cr]),)
    L = sorted(n for n in M.panels if n.startswith("Head1.L"))
    for t in (150.0, 120.0, 90.0, 60.0, 40.0, 25.0, 12.0):
        P = np.zeros((len(names), 3))
        for k, q in pk.items():
            for n in L:
                P_ = M.panels[n]
                if min((v3(c) - v3(q)).length for c in P_.polys[0]) < 0.05:
                    P[vi[k]] = list(P_.asm(t) @ v3(q))
                    break
        ph = np.degrees(KO.fold_angles(P, idx, out))
        assert ph.min() > worst, (f.head_base, t, [(c[:2], round(a)) for c, a in zip(cr, ph)
                                                   if a <= worst])


ridges(M, f)
folds_ok(M, f)
# open, it stands up; shut, it lies flat between the pages
top = max(w.z for n in L for w in corners(n, M.tmax))
assert top > 40.0, top
assert max(abs(w.x) for n in L for w in corners(n, 0.0)) < 1.0
# the pattern: one piece, the left half on the left of C, the right its mirror
for n in L:
    assert all(q[0] <= 0.05 for q in M.panels[n].polys[0]), n
export_svg.export(sc, svg)
# the rig follows it
st.keep_open = False
mdl = build.rebuild(sc, force=True)
rig, card = st.rig, st.card
lay = build_layout(mdl)
s_ = 1 / st.mm_per_unit
me = card.data


def rig_error(ov):
    rig["pop_open"] = float(ov)
    rig.update_tag()
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    ev = card.evaluated_get(dg).data
    attr = me.attributes["pop_panel"]
    worst = 0.0
    for poly in me.polygons:
        p_ = mdl.panels[mdl.order[attr.data[poly.index].value]]
        D = mdl.shown(p_.name, ov) @ lay["prints"][p_.piece].inverted()
        for vi in poly.vertices:
            worst = max(worst, (ev.vertices[vi].co - (D @ (me.vertices[vi].co / s_)) * s_).length
                        / s_)
    return worst


for ov in (180.0, 120.0, 60.0, 10.0):
    assert rig_error(ov) < 0.05, (ov, rig_error(ov))
# the landmarks move it: each stretches its own part of the pattern
M = model()


wide0 = max(abs(q[0]) for n in L for q in M.panels[n].polys[0])
f.ear_base = 70.0
M = model()
assert max(abs(q[0]) for n in L for q in M.panels[n].polys[0]) > wide0 + 8.0
f.ear_base = 59.0
for k, v in (("mouth_a", 15.0), ("mouth_a", -15.0), ("mouth_w", 16.0), ("mouth_d", 32.0),
             ("head_jaw", 28.0), ("head_brow", 35.0), ("head_brow", 60.0), ("head_chin", 22.0),
             ("head_nose", 30.0), ("head_nose", 46.0), ("head_muzzle", 20.0), ("ear_base", 50.0),
             ("ear_size", 0.0)):
    old = getattr(f, k)
    setattr(f, k, v)
    bpy.ops.popup.build()
    assert not warns(), (k, v, warns())
    M = model()
    assert gaps(60.0) < 0.6 and gaps(12.0) < 0.6, (k, v, gaps(60.0), gaps(12.0))
    setattr(f, k, old)
f.ear_size = 0.0
assert "Head1.EarL" not in model().panels
f.ear_size = 39.0
# the goblin: its own pattern (a frown, no muzzle), its own landmarks set on
# choosing it; a muzzle can be added, and the koala's taken away
f.head_base = "GOBLIN"
assert round(f.head_muzzle) == 0 and round(f.head_nose) == 37, (f.head_muzzle, f.head_nose)
for k, v in ((None, None), ("head_muzzle", 12.0), ("mouth_a", -15.0), ("head_brow", 35.0),
             ("head_chin", 30.0)):
    if k:
        old = getattr(f, k)
        setattr(f, k, v)
    bpy.ops.popup.build()
    assert not warns(), (k, v, warns())
    M = model()
    L = sorted(n for n in M.panels if n.startswith("Head1.L"))
    assert gaps(60.0) < 0.6 and gaps(12.0) < 0.6, (k, v, gaps(60.0), gaps(12.0))
    assert max(abs(w.x) for n in L for w in corners(n, 0.0)) < 1.0
    ridges(M, f)
    if k is None:
        folds_ok(M, f)
    if k:
        setattr(f, k, old)
M = model()
assert any(n.startswith("Head1.Muzzle") for n in model().panels) is False
f.head_base = "KOALA"
assert round(f.head_muzzle) == 26
f.head_muzzle = 0.0
bpy.ops.popup.build()
assert not warns(), warns()
M = model()
L = sorted(n for n in M.panels if n.startswith("Head1.L"))
assert not any("Muzzle" in n for n in M.panels) and gaps(40.0) < 0.6
ridges(M, f)
f.head_muzzle = 26.0
# pictures go on its facets
from popup_pro import props  # noqa: E402
p = add("PICTURE")
p.host_uid = 1
items = [i[0] for i in props.pic_face_items(p, bpy.context)]
assert "Head1.L1" in items, items
print("an animal face: a hand-made koala's pattern on the fold")

addon.unregister()
print("V90 OK")
