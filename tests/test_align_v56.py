"""v0.56: Align (line mechanisms up along their fold or across the card,
space them evenly) and the Plan View (squashed flat along the view,
see-through, a colour per mechanism)."""
# families: align, view
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
import popup_pro as addon  # noqa: E402
from popup_pro import arrange, build, carousel, debug  # noqa: E402
from popup_pro.carousel import in_scene  # noqa: E402
from popup_pro.core import align as A  # noqa: E402

addon.register()
sc = bpy.context.scene
st = sc.popup
st.live = False


def add(kind, **kw):
    assert bpy.ops.popup.add(kind=kind, **kw) == {"FINISHED"}
    return st.mechs[-1].uid


def M(u):
    return next(m for m in st.mechs if m.uid == u)


def pick(*uids, active):
    for m in st.mechs:
        m.selected = m.uid in uids
    st.active = next(i for i, m in enumerate(st.mechs) if m.uid == active)


def fold(u):
    return A.fold_extent(arrange._model(st), u)


def close(a, b, tol=0.15):
    return abs(a - b) <= tol


# ---- along the spine: three different kinds line up with the active one
box, cube, vf = add("BOX"), add("CUBE"), add("VFOLD")
M(box).y, M(box).width = 60, 30
M(cube).y, M(vf).y = 95, 150
pick(box, cube, vf, active=box)
ref = fold(box)
for how, f in (("START", 0), ("END", 1)):
    assert bpy.ops.popup.align(how=how, scope="FOLD", relative="ACTIVE") == {"FINISHED"}
    assert fold(box) == ref  # the active one stays put
    for u in (cube, vf):
        assert close(fold(u)[f], ref[f]), (how, u, fold(u), ref)
bpy.ops.popup.align(how="CENTRE", scope="FOLD", relative="ACTIVE")
for u in (cube, vf):
    e = fold(u)
    assert close(0.5 * (e[0] + e[1]), 0.5 * (ref[0] + ref[1])), (u, e)
print("along the spine: start, end and centre line up with the active one")

# distribute: equal gaps between the outermost two, which stay put
M(box).y, M(cube).y, M(vf).y = 10, 70, 150
outer = sorted((fold(u) for u in (box, cube, vf)))
bpy.ops.popup.align(how="DISTRIBUTE", scope="FOLD", relative="SELECTION")
es = sorted(fold(u) for u in (box, cube, vf))
assert close(es[0][0], outer[0][0]) and close(es[-1][1], outer[-1][1])
g = [es[i + 1][0] - es[i][1] for i in range(2)]
assert close(g[0], g[1]), g
# along the whole fold: the ends get the same gap too
bpy.ops.popup.align(how="DISTRIBUTE", scope="FOLD", relative="HOST")
es = sorted(fold(u) for u in (box, cube, vf))
H = st.card_dict()["H"]
g = [es[0][0]] + [es[i + 1][0] - es[i][1] for i in range(2)] + [H - es[-1][1]]
assert max(g) - min(g) < 0.3, g
print("distribute: even gaps, between the outer two or along the whole fold")

# ---- on a V-fold half: measured along that fold (the glue line), not the
# spine; each fold's mechanisms line up on their own
c1 = add("CUBE", host=vf, fold="FR")
c2 = add("STANDUP", host=vf, fold="FR")
M(c2).y = 4
mdl = arrange._model(st)
span = A.fold_span(mdl, mdl.placed[c1])
assert span is not None and close(span[0], 0.0) and close(span[1], M(vf).glue), span
pick(c1, c2, box, cube, active=c1)
bpy.ops.popup.align(how="END", scope="FOLD", relative="ACTIVE")
assert close(fold(c2)[1], fold(c1)[1])
# the spine's two (box and cube) lined up among themselves meanwhile
assert close(fold(box)[1], fold(cube)[1])
bpy.ops.popup.align(how="END", scope="FOLD", relative="HOST")
assert close(fold(c1)[1], span[1]) and close(fold(c2)[1], span[1])
print("on a V-fold half: along its glue line, to its end")

# a host that moves takes what stands on it along; things placed by what
# they stand in are never moved
before = (M(c1).y, M(c2).y)
pick(vf, box, active=box)
bpy.ops.popup.align(how="START", scope="FOLD", relative="ACTIVE")
assert (M(c1).y, M(c2).y) == before
assert close(fold(vf)[0], fold(box)[0])
print("children ride along with their host")

# Same Fold picks everything on the active one's fold
st.active = next(i for i, m in enumerate(st.mechs) if m.uid == c1)
assert bpy.ops.popup.select_mechs(action="FOLD") == {"FINISHED"}
assert {m.uid for m in st.mechs if m.selected} == {c1, c2}
st.active = next(i for i, m in enumerate(st.mechs) if m.uid == box)
bpy.ops.popup.select_mechs(action="FOLD")
assert {m.uid for m in st.mechs if m.selected} == {box, cube, vf}
bpy.ops.popup.select_mechs(action="NONE")
assert not any(m.selected for m in st.mechs)

# ---- whole card: up the card, and flaps across their pages (mirrored)
f1, f2 = add("FLAP"), add("FLAP")
M(f1).y, M(f1).x = 120, 70
M(f2).side, M(f2).x, M(f2).y = "L", 40, 150
pick(f1, f2, cube, active=f1)


def card(u, ax):
    return A.card_extent(arrange._model(st), M(u).to_dict(), ax)


bpy.ops.popup.align(how="BOTTOM", scope="CARD", relative="ACTIVE")
assert close(card(f2, "Y")[0], card(f1, "Y")[0]) and close(card(cube, "Y")[0],
                                                            card(f1, "Y")[0])
bpy.ops.popup.align(how="OUTER", scope="CARD", relative="ACTIVE")
assert close(card(f2, "X")[1], card(f1, "X")[1])  # the same distance out
assert close(M(f2).x, M(f1).x)  # so mirror images either side of the spine
bpy.ops.popup.align(how="TOP", scope="CARD", relative="HOST")
for u in (f1, f2, cube):
    assert close(card(u, "Y")[1], H), (u, card(u, "Y"))
mdl = arrange._model(st)
assert not [w for w in mdl.warnings if "Flap" in w], mdl.warnings  # still on the page
print("whole card: up the card, to the top edge; flaps mirror across the spine")

# ---- one rebuild, after the lot; the card follows
bpy.ops.popup.build()
n = {"n": 0}
real = build.rebuild


def counting(scene, force=False):
    n["n"] += 1
    return real(scene, force)


build.rebuild = counting
pick(box, cube, vf, active=box)
st.live = True
bpy.ops.popup.align(how="CENTRE", scope="FOLD", relative="ACTIVE")
build.rebuild = real
assert n["n"] == 1, n
assert st.live
st.live = False
print("one rebuild")

# ---- plan view ------------------------------------------------------------
st.rig["pop_open"] = 130.0
st.plan_angle = 70.0
st.plan_view = True
card_ob = st.card
mod = card_ob.modifiers[debug.MOD]
assert card_ob.modifiers[-1] == mod and not mod.show_render
assert st.rig["pop_open"] == 70.0


def depth(t):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = card_ob.evaluated_get(dg)
    me = ev.to_mesh()
    ax = debug.view_axis(st.hold, t)
    ds = [v.co.dot(ax) for v in me.vertices]
    mats = {me.materials[p.material_index].name for p in me.polygons if me.materials}
    keys = set()
    a = me.attributes.get("pop_mech")
    if a is not None:
        vals = [0] * len(me.polygons)
        a.data.foreach_get("value", vals)
        keys = set(vals)
    ev.to_mesh_clear()
    return max(ds) - min(ds), mats, keys


d, mats, keys = depth(70.0)
st.plan_view = False
d0 = depth(70.0)[0]
st.plan_view = True
assert d < 0.05 * d0 and d0 > 1.0, (d, d0)
assert 0 not in keys  # the card's own pages: outlines only
assert all(k.startswith("Pop-up Plan") for k in mats) and len(mats) >= 3, mats
# turning the angle turns the squash with it
st.plan_angle = 120.0
assert st.rig["pop_open"] == 120.0
assert depth(120.0)[0] < 0.05 * d0
# a rebuild (which adds modifiers of its own) leaves it last
bpy.ops.popup.build()
assert st.card.modifiers[-1].name == debug.MOD
# colour by panel
st.plan_colour = "PANEL"
assert len(depth(120.0)[1]) >= 3
# following the card's own Open
st.plan_use_open = True
st.rig["pop_open"] = 45.0
debug._follow_open(sc)
assert abs(sc["pop_plan_t"] - 45.0) < 1e-6
st.plan_use_open = False
# off: the opening comes back, the modifier goes
st.plan_view = False
assert debug.MOD not in st.card.modifiers
assert st.rig["pop_open"] == 130.0
assert debug.SAVED not in sc
print("plan view: squashed flat along the view, a colour per mechanism, put back after")

# ---- on a carousel stage
addon.unregister()
bpy.ops.wm.read_factory_settings(use_empty=True)
addon.register()
sc = bpy.context.scene
assert bpy.ops.popup.make_carousel(count=4) == {"FINISHED"}
S = carousel.stages(sc)
s0 = S[0]
with in_scene(s0):
    p = s0.popup
    was = carousel.open_value(sc)
    p.plan_angle = 60.0  # more than a quarter turn: held to 90
    p.plan_view = True
    assert abs(debug.angle(s0) - 60.0) < 1e-6
    assert s0.popup.card.modifiers[-1].name == debug.MOD
    assert abs(carousel.open_value(sc) - 240.0) < 1e-6  # 60 degrees a stage
    p.plan_angle = 150.0
    assert abs(debug.angle(s0) - 90.0) < 1e-6
    p.plan_view = False
    assert debug.MOD not in s0.popup.card.modifiers
    assert abs(carousel.open_value(sc) - was) < 1e-6
print("plan view on a carousel stage")
print("v0.56 OK")
