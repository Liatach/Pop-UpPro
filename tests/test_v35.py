"""v0.35: door flaps (an opening cut on every side but a hinge crease),
names never reused, preset shapes grouped in the list, duplicate."""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
import popup_pro as addon  # noqa: E402
from popup_pro import build, holes  # noqa: E402
from popup_pro.core.model import Model  # noqa: E402

addon.register()
sc = bpy.context.scene
st = sc.popup

# ---- model: doors on a glued box's front, the card and a box layer's front
doors = [dict(id=0, piece="Box1", face="Box1.CB", shape="ARCH", x=0, y=4, width=16,
              height=24, turn=0, cut="DOOR", hinge="LEFT", open=60),
         dict(id=1, piece="Card", face="", shape="RECT", x=60, y=120, width=20, height=30,
              turn=0, cut="DOOR", hinge="TOP", open=45),
         dict(id=2, piece="Card", face="Box2.CB", shape="RECT", x=0, y=3, width=12,
              height=15, turn=0, cut="DOOR", hinge="RIGHT", open=80),
         dict(id=3, piece="Cube3", face="", shape="RECT", x=10, y=5, width=8, height=8,
              turn=0, cut="DOOR", hinge="LEFT", open=60)]
m = Model(dict(W=148.5, H=210.0, hold="SYM", doors=doors),
          [dict(type="BOX", style="GLUED", uid=1, label="B", y=40, width=50, height=40,
                depth=30, tab=8),
           dict(type="BOX", style="CUT", uid=2, label="L", y=150, width=40, height=25,
                depth=25),
           dict(type="CUBE", uid=3, label="C", y=100, x=0, size=20, height=20)])
m.solve_hinges()
assert m.doors_done == {0, 1, 2}, m.doors_done
assert any("Door flap on Cube3" in w for w in m.warnings), m.warnings
want = {"Box1.Door1": 60, "Card.Door1": 45, "Box2.Door1": 80}
for name, deg in want.items():
    p = m.panels[name]
    for t, f in ((0, 0.0), (90, 0.25), (180, 1.0)):
        M = m.panels[p.parent].asm(t).inverted() @ p.asm(t)
        a = math.degrees(math.acos(max(-1.0, min(1.0, M[2][2]))))
        assert abs(a - deg * f) < 0.05, (name, t, a)
    # it swings out of the printed side
    M = m.panels[p.parent].asm(180).inverted() @ p.asm(180)
    from mathutils import Vector
    pts = [q for poly in p.polys for q in poly]
    c = Vector((sum(q[0] for q in pts) / len(pts), sum(q[1] for q in pts) / len(pts), 0))
    assert (M @ c).z > 0.5, (name, (M @ c).z)
print("doors hinge, open with the card, swing out of the printed side")

# ---- in Blender: the door is not also cut as a hole; the rig follows it
assert bpy.ops.popup.build() == {"FINISHED"}
st.mechs.clear()
assert bpy.ops.popup.add(kind="BOX") == {"FINISHED"}
box = st.mechs[0]
st.active = 0
assert bpy.ops.popup.add_opening() == {"FINISHED"}
o = st.openings[0]
o.cut, o.y, o.hinge = "DOOR", 4.0, "LEFT"
model = build.rebuild(sc, force=True)
model, _ = build.make_model(sc)
assert 0 in model.doors_done
assert not holes._openings(sc, model, st), "a door is not a hole"
assert f"Box{box.uid}.Door1" in model.panels
print("door built, not cut out")

# ---- names: never reused
assert bpy.ops.popup.add(kind="CUBE") == {"FINISHED"}
assert bpy.ops.popup.add(kind="CUBE") == {"FINISHED"}
labels = [x.label for x in st.mechs]
assert labels[-2:] == ["Cube 1", "Cube 2"], labels
st.active = len(st.mechs) - 2
bpy.ops.popup.remove()
assert bpy.ops.popup.add(kind="CUBE") == {"FINISHED"}
assert st.mechs[-1].label == "Cube 3", [x.label for x in st.mechs]
assert len({x.label for x in st.mechs}) == len(st.mechs)
print("names count on")

# ---- preset shapes group; a collapsed group is removed whole
st.active = 0
bpy.ops.popup.add_line(preset="BATTLEMENTS")
n = len(box.lines)
assert n >= 2 and all(ln.shape_name == "Battlements" for ln in box.lines)
box.active_line = 0
box.lines[0].expanded = True
assert all(ln.expanded for ln in box.lines)
bpy.ops.popup.remove_line()
assert len(box.lines) == n - 1
box.lines[0].expanded = False
bpy.ops.popup.remove_line()
assert len(box.lines) == 0
print("shapes collapse, expand and go together")

# ---- duplicate: settings, lines and its openings come along
bpy.ops.popup.add_line(preset="TOWER")
box.width, box.height = 44.0, 33.0
n_open = len(st.openings)
assert bpy.ops.popup.duplicate() == {"FINISHED"}
cp = st.mechs[st.active]
assert cp.uid != box.uid and cp.kind == "BOX"
assert (cp.width, cp.height) == (44.0, 33.0)
assert abs(cp.y - box.y - 15.0) < 1e-6
assert len(cp.lines) == len(box.lines)
assert cp.label == "Box fold 2", cp.label
assert len(st.openings) == n_open + 1
o2 = st.openings[-1]
assert o2.face == f"Box{cp.uid}.CB" and o2.cut == "DOOR", (o2.face, o2.on_piece)
model, _ = build.make_model(sc)
assert f"Box{cp.uid}.Door1" in model.panels or any(
    n.startswith(f"Box{cp.uid}.Door") for n in model.panels), [
    n for n in model.panels if "Door" in n]
print("duplicated with its lines and door")

# ---- a glued box fold never pokes through the page behind it as it folds
# (it is lifted onto its tabs only near flat)
from popup_pro import live  # noqa: E402
st.mechs.clear()
st.openings.clear()
assert bpy.ops.popup.add(kind="BOX", variant="STRAP") == {"FINISHED"}
st.mechs[0].peaks, st.mechs[0].slant = 2, 30.0
st.solid_paper = True
build.rebuild(sc, force=True)
card, rig, mmu = st.card, st.rig, st.mm_per_unit
names = [p["name"] for p in live.meta(rig)["panels"]]


def below_back(t):
    rig["pop_open"] = float(t)
    rig.update_tag()
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    ev = card.evaluated_get(dg)
    em = ev.to_mesh()
    W = ev.matrix_world
    pn = [names[em.attributes["pop_panel"].data[p.index].value] for p in em.polygons]
    worst = 0.0
    for pg in ("Page.L", "Page.R"):
        polys = [p for p in em.polygons if pn[p.index] == pg]
        n0 = len(card.data.polygons)  # Solid Paper's own faces come after the card's
        big = max((p for p in polys if p.index < n0), key=lambda p: p.area)
        n = (W.to_3x3() @ big.normal).normalized()
        o = W @ em.vertices[big.vertices[0]].co
        P = [W @ em.vertices[i].co for p in polys for i in p.vertices]
        dmin = min((x - o).dot(n) for x in P)
        for p in em.polygons:
            if pn[p.index].startswith("Box") and ".Tab" not in pn[p.index]:
                for i in p.vertices:
                    worst = min(worst, ((W @ em.vertices[i].co - o).dot(n) - dmin) * mmu)
    ev.to_mesh_clear()
    return worst


for t in (5, 20, 45):
    w = below_back(t)
    assert w > -0.05, (t, w)
print("the strap stays in front of the pages as it folds")
print("all v35 checks pass")
