"""v0.40 Grease Pencil check: a sketch on any panel (V-fold half, box front,
cube wall, stand-up picture, the card page) stays on that panel's face as
the card opens and closes, through rebuilds, and prints on its piece."""
# families: drawing
import math
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
import popup_pro as addon  # noqa: E402
from popup_pro import art, build, export_svg, live  # noqa: E402

addon.register()
sc = bpy.context.scene
st = sc.popup
assert bpy.ops.popup.build() == {"FINISHED"}
st.mechs.clear()
for k, y in (("VFOLD", 150), ("BOX", 20), ("STANDUP", 75)):  # (its picture runs up from 75, v0.66)
    assert bpy.ops.popup.add(kind=k) == {"FINISHED"}
    st.mechs[-1].y = y
assert bpy.ops.popup.add(kind="CUBE") == {"FINISHED"}
st.mechs[-1].y = 70
st.mechs[-1].size = 22
build.rebuild(sc, force=True)
assert not st.warnings, st.warnings
rig, card, mmu = st.rig, st.card, st.mm_per_unit
names = [p["name"] for p in live.meta(rig)["panels"]]
uid = {m.kind: m.uid for m in st.mechs}
panels = [f"VFold{uid['VFOLD']}.HalfL", f"Box{uid['BOX']}.CB", f"Cube{uid['CUBE']}.B",
          f"Stand{uid['STANDUP']}.CB", "Page.R"]
for p in panels:
    assert p in names, (p, names)


def pose(t):
    rig["pop_open"] = float(t)
    rig.update_tag()
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    return dg


def layer_world(layer, dg):
    pb = rig.evaluated_get(dg).pose.bones[layer.parent_bone]
    return rig.matrix_world @ pb.matrix @ layer.matrix_parent_inverse @ layer.matrix_local


def face(panel, dg):
    """The panel's printed face in the folded card: centre, normal, points."""
    ev = card.evaluated_get(dg)
    me = ev.data
    attr = me.attributes["pop_panel"]
    i = names.index(panel)
    n0 = len(card.data.polygons)  # Solid Paper's own faces come after the card's
    polys = [p for p in me.polygons[:n0] if attr.data[p.index].value == i]
    big = max(polys, key=lambda p: p.area)
    n = (ev.matrix_world.to_3x3() @ big.normal).normalized()
    pb = rig.evaluated_get(dg).pose.bones[panel]
    if n.dot((rig.matrix_world @ pb.matrix).to_3x3() @ Vector((0, 0, 1))) < 0:
        n = -n  # the printed side, not the back of a solid page
    pts = [ev.matrix_world @ me.vertices[v].co for p in polys for v in p.vertices]
    top = max(pts, key=lambda q: q.dot(n)).dot(n)  # the printed side (Solid Paper)
    c = sum(pts, Vector()) / len(pts)
    return c + n * (top - c.dot(n)), n


# ---- draw a small ring on each panel at 90 degrees, as Surface placement does
dg = pose(90)
obj = None
for p in panels:
    obj, layer = art.sketch_layer(sc, p)
    assert layer.parent == rig and layer.parent_bone == p
    c, n = face(p, dg)
    W = layer_world(layer, dg)
    ax = W.to_3x3() @ Vector((1, 0, 0))
    ax = (ax - n * ax.dot(n)).normalized()  # along the face
    ay = n.cross(ax).normalized()
    r = 4.0 / mmu
    dr = layer.current_frame().drawing
    dr.add_strokes([12])
    s = dr.strokes[len(dr.strokes) - 1]
    for i, q in enumerate(s.points):
        a = 2 * math.pi * i / 12
        w = c + n * (0.2 / mmu) + ax * (r * math.cos(a)) + ay * (r * math.sin(a))
        q.position = W.inverted() @ w
        q.radius = 0.01


def check(when):
    """Each ring keeps the same height off its panel and the same place on
    it, whatever the open angle: it rides on the panel."""
    seen = {}
    for t in (5, 45, 90, 135, 180):
        dg = pose(t)
        for layer in obj.data.layers:
            if layer.parent_bone not in panels:
                continue
            c, n = face(layer.parent_bone, dg)
            W = layer_world(layer, dg)
            for s in layer.current_frame().drawing.strokes:
                for k, q in enumerate(s.points):
                    w = W @ Vector(q.position)
                    d = (w - c).dot(n) * mmu  # off the face
                    r = (w - c - n * (w - c).dot(n)).length * mmu  # from its centre
                    seen.setdefault((layer.name, k), []).append((d, r))
    worst = max(max(abs(a[0] - b[0]) + abs(a[1] - b[1]) for a in v for b in v)
                for v in seen.values())
    assert worst < 0.05, (when, worst)
    assert all(0.0 < d < 0.6 for v in seen.values() for d, _ in v), "on the printed side"
    print(f"{when}: every sketch rides on its panel (moves {worst:.4f} mm at most)")


check("drawn")
# rebuilds (sizes changed, a mechanism added) keep them on their panels
st.mechs[0].height += 10
st.mechs[1].width += 8
build.rebuild(sc, force=True)
assert bpy.ops.popup.add(kind="VFOLD") == {"FINISHED"}
st.mechs[-1].y = 185
build.rebuild(sc, force=True)
names = [p["name"] for p in live.meta(rig)["panels"]]
for layer in obj.data.layers:
    if layer.parent_bone in panels:
        assert layer.parent == rig
check("rebuilt")

# ---- the Sketch on Panel button makes and selects the layer
st.sketch_panel = panels[0]
assert bpy.ops.popup.sketch(panel="") == {"FINISHED"}
assert obj.data.layers.active.name == panels[0]
assert bpy.context.view_layer.objects.active == obj
assert sc.tool_settings.gpencil_stroke_placement_view3d == "SURFACE"
from popup_pro import ops  # noqa: E402
if bpy.context.mode == "PAINT_GREASE_PENCIL":
    assert ops.sketching(bpy.context) == panels[0] and ops.drawing(bpy.context)
assert bpy.ops.popup.done_drawing() == {"FINISHED"}
assert bpy.context.mode == "OBJECT" and not ops.sketching(bpy.context)
print("Sketch on Panel picks the panel's layer, Surface placement")

# ---- export: each ring prints inside its own piece
out = tempfile.mkdtemp()
files = export_svg.export(sc, os.path.join(out, "gp.svg"))
svg = "".join(open(f).read() for f in files)
n_paths = svg.count('id="sketch"') and sum(
    part.split('id="glue"')[0].count("<path") for part in svg.split('id="sketch"')[1:])
assert n_paths >= len(panels), n_paths
print(f"exported: {n_paths} sketch paths")

# ---- a deleted mechanism's sketch is kept, unparented and hidden
st.active = 0
vf = f"VFold{st.mechs[0].uid}.HalfL"
bpy.ops.popup.remove()
build.rebuild(sc, force=True)
lay = next(layer for layer in obj.data.layers if layer.name.startswith(vf))
assert lay.parent is None and lay.hide
print("a deleted mechanism's sketch is kept, hidden")
print("all v40 checks pass")
