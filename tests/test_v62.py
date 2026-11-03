"""v0.62: the rest of Birmingham's 45 degree folds. The double 45 (77): two
arms rising from one point, a top piece twisting round between their tips."""
import os
import math
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
import popup_pro as addon  # noqa: E402
from popup_pro import build, export_svg  # noqa: E402
from popup_pro.core.geom import v3  # noqa: E402
from popup_pro.core.model import Model  # noqa: E402

addon.register()
sc = bpy.context.scene
st = sc.popup
st.live = False


def rig_error(names=None):
    """Worst distance (mm) between the rig's card and the model."""
    rig, card = st.rig, st.card
    if rig.animation_data:
        rig.animation_data.action = None
    model, lay = build.make_model(sc)
    me = card.data
    at = me.attributes["pop_panel"]
    s = 1 / st.mm_per_unit
    t0 = rig["pop_close"]
    worst = 0.0
    for t in (0.0, 33.3, 90.0, 141.7, 180.0):
        rig["pop_open"] = t
        rig.update_tag()
        dg = bpy.context.evaluated_depsgraph_get()
        dg.update()
        ev = card.evaluated_get(dg).data
        real = t0 + t * (180 - t0) / 180
        for poly in me.polygons:
            name = model.order[at.data[poly.index].value]
            if names and not name.startswith(names):
                continue
            P = lay["prints"][model.panels[name].piece].inverted()
            for vi in poly.vertices:
                q = P @ (me.vertices[vi].co / s)
                worst = max(worst, (ev.vertices[vi].co / s - model.point(name, q, real)).length)
    return worst


def shut_spread(model):
    nr = model.panels["Page.R"].asm(0.5).to_3x3() @ Vector((0, 0, 1))
    d = [(p.asm(0.5) @ v3(q)).dot(nr) for p in model.panels.values() for poly in p.polys
         for q in poly]
    return max(d) - min(d)


# ---- the double 45 fold
assert bpy.ops.popup.add(kind="DOUBLE45") == {"FINISHED"}
m = st.mechs[0]
model = build.rebuild(sc, force=True)
assert not st.warnings, st.warnings
P = model.panels
u = m.uid
# the arms: each half on its 45 degree fold, the crease rising out of the card
for t in (150.0, 90.0, 30.0):
    for key in (f"D45{u}.U", f"D45{u}.D"):
        c, uL, uR, ok, P3 = model.crease(key, t)
        assert ok
        assert abs(math.degrees(c.angle(uL)) - 45.0) < 1e-3
        assert abs(math.degrees(c.angle(uR)) - 45.0) < 1e-3
up = model.crease(f"D45{u}.U", 90.0)[0]
dn = model.crease(f"D45{u}.D", 90.0)[0]
assert up.y > 0.2 and dn.y < -0.2, (up, dn)  # one leans up the card, one down
# the top piece: its halves meet at G (shared fold line) at every opening
for t in (179.0, 120.0, 60.0, 5.0):
    for x in (-15.0, 0.0, 15.0):
        a = model.point(f"D45{u}.GF", (x, 0.0), t)
        b = model.point(f"D45{u}.GH", (x, 0.0), t)
        assert (a - b).length < 1e-4, (t, x, (a - b).length)
# F's edge rides its arm's tip: on the upper right half's top edge
for t in (150.0, 60.0):
    for x in (0.0, 7.5, 15.0):
        a = model.point(f"D45{u}.TopF", (x, m.depth / 2), t)
        b = P[f"D45{u}.UR"].asm(t) @ Vector((x, m.height, 0.0))
        assert (a - b).length < 1e-4
# open flat: an exact tent over the arms, G straight above C
G = model.point(f"D45{u}.GF", (0.0, 0.0), 180.0)
assert abs(G.y - m.y) < 0.3 and abs(G.x) < 0.3 and G.z > 20.0, G
print("double 45: arms on 45° folds, top piece hinged on the tips and joined at G")
assert shut_spread(model) < 3.0, shut_spread(model)
err = rig_error()
print("rig error", round(err, 4))
assert err < 0.05, err
out = os.path.join(tempfile.mkdtemp(), "d45.svg")
files = export_svg.export(sc, out)
svg = "".join(open(f).read() for f in files if f.endswith(".svg"))
assert files
print("double 45: lies flat shut, the rig matches, exports")

# ---- Jack in the Box on a V-fold (79): the chest leans back into the V,
# the arms swing round in front, the head rises, all on 45 degree folds
while st.mechs:
    st.active = 0
    bpy.ops.popup.remove()
assert bpy.ops.popup.add(kind="JACK") == {"FINISHED"}
jack = next(x for x in st.mechs if x.kind == "JACK")
body = next(x for x in st.mechs if x.kind == "VFOLD")
assert jack.host_uid == body.uid and jack.on_crease
model = build.rebuild(sc, force=True)
assert not st.warnings, st.warnings
j = jack.uid
for key in (f"Jack{j}.C", f"Jack{j}.H"):
    for t in (150.0, 90.0, 30.0):
        c, uL, uR, ok, P3 = model.crease(key, t)
        Yh = model.joints[key]["host"].dirs(t)[3]
        assert ok and abs(c.dot(Yh)) < 0.95, (key, t)  # risen off its host's fold
        assert abs(math.degrees(c.angle(uL)) - 45.0) < 1e-3
for t in (150.0, 90.0, 30.0):  # nothing through the pages
    for side in ("L", "R"):
        Pg = model.panels[f"Page.{side}"].asm(t)
        n = Pg.to_3x3() @ Vector((0, 0, 1))
        for nm in (f"Jack{j}.Chest{side}", f"Jack{j}.Head{side}"):
            p = model.panels[nm]
            assert min((p.asm(t) @ v3(q) - Pg.to_translation()).dot(n)
                       for poly in p.polys for q in poly) > -0.5, (nm, t)
assert shut_spread(model) < 3.0, shut_spread(model)
err = rig_error()
print("jack rig error", round(err, 4))
assert err < 0.05, err
# not on a V-fold: said, not built
M = Model(st.card_dict(), [dict(uid=1, type="JACK", label="J", y=80.0, height=20.0,
                                depth=20.0, tab=10.0, host=0)])
assert any("V-fold's crease" in w for w in M.warnings) and not any(
    n.startswith("Jack") for n in M.panels)
print("jack in the box: two 45° folds on a V-fold, clear of the pages, the rig matches")

# ---- 45 degree triangles in a box fold's corner (74)
while st.mechs:
    st.active = 0
    bpy.ops.popup.remove()
assert bpy.ops.popup.add(kind="BOX") == {"FINISHED"}
bx = st.mechs[0]
bx.tri45, bx.tri_size = "BOTH", 12.0
model = build.rebuild(sc, force=True)
assert not st.warnings, st.warnings
for tag, sy in (("T", 1.0), ("B", -1.0)):
    key = f"Box{bx.uid}.Tri{tag}"
    c = model.crease(key, 90.0)[0]
    assert c.y * sy > 0.2 and abs(c.dot(Vector((0, 1, 0)))) < 0.95, (tag, c)
    for side in "LR":
        assert f"{key}{side}" in model.panels
# the triangles are cut out of the box's top and front
area = sum(abs(sum(q[0] * r[1] - r[0] * q[1] for q, r in zip(pl, pl[1:] + pl[:1]))) / 2
           for nm in (f"Box{bx.uid}.AC", f"Box{bx.uid}.CB") for pl in model.panels[nm].polys)
full = bx.width * (bx.height + bx.depth)
assert abs(full - area - 4 * 0.5 * 12.0 * 12.0) < 0.5, (full, area)
assert shut_spread(model) < 3.0
err = rig_error()
assert err < 0.05, err
bx.kind = "BOXCUT"
model = build.rebuild(sc, force=True)
assert f"Box{bx.uid}.TriTL" in model.panels and not st.warnings, st.warnings
files = export_svg.export(sc, os.path.join(tempfile.mkdtemp(), "tri.svg"))
print("45° triangles: cut into a box's corner at both ends, rise as it closes")
print("v0.62 OK")
