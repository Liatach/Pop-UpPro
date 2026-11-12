"""v0.71: gabled tower roofs with eaves (Birmingham 49: gables, a rib between
their tips, a roof stuck only to the rib), tubes and castles in two strips,
balconies on arches with open railings, balconies outside a castle's towers."""
# families: towers, roofs, tubes, balconies
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
import popup_pro as addon  # noqa: E402
from popup_pro import build, export_svg, live  # noqa: E402
from popup_pro.core.geom import v3  # noqa: E402

addon.register()
sc = bpy.context.scene
st = sc.popup
st.live = False
svg = os.path.join(tempfile.mkdtemp(), "t.svg")


def warns():
    return [w for w in st.warnings.split("\n") if w]


def faces_in_mesh(prefix):
    bpy.ops.popup.build()
    names = [p["name"] for p in live.meta(st.rig)["panels"]]
    me = st.card.data
    vals = [0] * len(me.polygons)
    me.attributes["pop_panel"].data.foreach_get("value", vals)
    have = set(vals)
    missing = [n for i, n in enumerate(names) if n.startswith(prefix) and i not in have]
    assert not missing, missing


def flat_shut(model, names):
    nr = model.panels["Page.R"].asm(0.5).to_3x3() @ Vector((0, 0, 1))
    d = [(model.panels[n].asm(0.5) @ v3(q)).dot(nr) for n in names
         for poly in model.panels[n].polys for q in poly]
    return max(d) - min(d)


# ---- a castle with gabled tower roofs
st.mechs.clear()
assert bpy.ops.popup.add(kind="TUBE", variant="CASTLE") == {"FINISHED"}
castle = st.mechs[0]
cu = castle.uid
castle.x = castle.front = castle.back = 40.0
castle.depth = 70.0
towers = [m.uid for m in st.mechs if m.kind == "BOX"]
assert len(towers) == 4
for m in st.mechs:
    if m.kind == "BOX":
        m.roof, m.eave, m.roof_height = "GABLE", 4.0, 10.0
        m.height = m.depth = 18.0
build.rebuild(sc, force=True)
assert not [w for w in warns() if "print sheet" not in w], warns()
model = build.make_model(sc)[0]
for u in towers:
    rib, ra, rb = f"Rib{u}.Rib", f"GRoof{u}.A", f"GRoof{u}.B"
    assert rib in model.panels and ra in model.panels and rb in model.panels
    assert model.panels[ra].parent == rib and model.panels[rb].parent == ra
    # glued to nothing but the rib (and its tabs)
    kids = [n for n, p in model.panels.items() if p.parent in (ra, rb)]
    assert all(n.startswith(f"Rib{u}.Top") or n == rb for n in kids), kids
    # the roof overhangs: wider than the gap between the gables, open flat
    L = model.panels[rib].polys[0]
    span = max(x for x, y in L) - min(x for x, y in L)
    ra_x = [x for x, y in model.panels[ra].polys[0]]
    assert max(ra_x) - min(ra_x) > span + 7.9, (span, ra_x)
    # roof halves lean up from the ridge open flat
    up = model.panels["Page.R"].asm(179.0).to_3x3() @ Vector((0, 0, 1))
    for h in (ra, rb):
        n = model.panels[h].asm(179.0).to_3x3() @ Vector((0, 0, 1))
        assert n.dot(up) > 0.2, (h, n)
gab = [n for n in model.panels if n.startswith(("Rib", "GRoof"))]
assert flat_shut(model, gab) < 1.0, flat_shut(model, gab)
faces_in_mesh("GRoof")
faces_in_mesh("Rib")
# the gables: a point on the wall and on the tower's inner face
tw0 = next(m for m in st.mechs if m.uid == towers[0])
pts = [q for poly in model.panels[f"Box{towers[0]}.CB"].polys for q in poly]
assert any(abs(q[1] - (tw0.width + 10.0)) < 1e-3 for q in pts), pts
print("gabled tower roofs: rib, overhanging roof, flat shut")

# turned: the ridge runs the other way
for m in st.mechs:
    if m.kind == "BOX":
        m.gable_turn = True
build.rebuild(sc, force=True)
assert not [w for w in warns() if "print sheet" not in w], warns()
print("turned gables")

# a gabled roof on a tube is refused
castle.roof = "GABLE"
build.rebuild(sc, force=True)
assert any("gabled roofs go on towers" in w for w in warns()), warns()
castle.roof = "NONE"

# ---- two strips: the big castle fits the sheet
castle.strips = 1
build.rebuild(sc, force=True)
assert any("bigger than the print sheet" in w and "Strips: 2" in w for w in warns()), warns()
castle.strips = 2
build.rebuild(sc, force=True)
assert not warns(), warns()
model = build.make_model(sc)[0]
pc = {n: model.panels[n].piece for n in model.panels if n.startswith(f"Tube{cu}.")}
assert pc[f"Tube{cu}.FL_"] == pc[f"Tube{cu}.GFL"] == pc[f"Tube{cu}.GFR"] == \
    pc[f"Tube{cu}.Join"] == f"Tube{cu}"
assert pc[f"Tube{cu}.FR_"] == pc[f"Tube{cu}.GBR"] == pc[f"Tube{cu}.GBL"] == \
    pc[f"Tube{cu}.Close"] == pc[f"Tube{cu}.TabR"] == f"Tube{cu}b"
assert model.panels[f"Tube{cu}.Join"].parent == f"Tube{cu}.FR_"
faces_in_mesh(f"Tube{cu}.")
export_svg.export(sc, svg)
print("two strips, joined by a tab")

# ---- balconies outside the towers
st.active = 0
assert bpy.ops.popup.add(kind="BOX", host=cu, variant="TOWER_BALCONIES") == {"FINISHED"}
castle = next(m for m in st.mechs if m.uid == cu)  # (the list moved in memory)
bal = [m for m in st.mechs if m.label.endswith("tower balcony")]
assert len(bal) == 4, [m.label for m in st.mechs]
for m in bal:
    assert m.wall in ("L", "R") and m.support == "ARCHES" and m.rail > 0
    assert abs(m.height - castle.height) < 0.05 and abs(m.width - 18.0) < 0.05
assert sorted(m.y for m in bal) == [0.0, 0.0, 52.0, 52.0], [m.y for m in bal]
build.rebuild(sc, force=True)
assert not warns(), warns()
model = build.make_model(sc)[0]
for m in bal:
    cb = model.panels[f"Box{m.uid}.CB"]
    assert len(cb.polys) > 4, len(cb.polys)  # band, sill, pillars, spandrels
    rp = model.panels[f"Rail{m.uid}.Rail"]
    assert len(rp.polys) > 3  # open: posts
faces_in_mesh("Rail")
faces_in_mesh("Box")
export_svg.export(sc, svg)
print("balconies outside the towers, on arches, with open railings")

# ---- arches too small: left solid, with a warning
m = bal[0]
m.bays = 12
build.rebuild(sc, force=True)
assert any("too small for 12 arches" in w for w in warns()), warns()

addon.unregister()
print("V71 OK")
