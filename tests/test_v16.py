"""v0.16: true colours while painting. In Texture Paint the paper shows its
art unlit with the Standard view transform (so colours picked off the screen
match the art), and everything is put back afterwards."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
import popup_pro as addon  # noqa: E402
from popup_pro import art, colours  # noqa: E402

addon.register()
sc = bpy.context.scene
st = sc.popup
st.live = False
assert bpy.ops.popup.build() == {"FINISHED"}
art.add_art_texture(sc, dpi=20)
sc.view_settings.view_transform = "AgX"
mat = st.card.data.materials[0]
out = next(n for n in mat.node_tree.nodes if n.type == "OUTPUT_MATERIAL")
before = out.inputs["Surface"].links[0].from_node.name
n_nodes = len(mat.node_tree.nodes)

assert colours.enter(sc)
assert not colours.enter(sc)  # once only
assert sc.view_settings.view_transform == "Standard"
src = out.inputs["Surface"].links[0].from_node
assert src.name == colours.MIX
emit = mat.node_tree.nodes[colours.EMIT]
assert emit.inputs["Color"].links[0].from_node.name == "Pop-up Back"  # art front, paper back
colours.leave(sc)
assert sc.view_settings.view_transform == "AgX"
assert out.inputs["Surface"].links[0].from_node.name == before
assert len(mat.node_tree.nodes) == n_nodes
print("true colours on and off")

st.true_colours = False
assert not colours.enter(sc)
assert sc.view_settings.view_transform == "AgX"
print("can be turned off")
st.true_colours = True

# ---- drawn hole strokes stay on their piece when the layout is packed again
from mathutils import Vector  # noqa: E402
from popup_pro import build, holes  # noqa: E402

assert bpy.ops.popup.add(kind="STANDUP") == {"FINISHED"}
su = st.mechs[-1]
su.y = 120
model = build.rebuild(sc, force=True)
model, layout = build.make_model(sc)
piece = f"Stand{su.uid}"
P = layout["prints"][piece]
obj, layer = holes.hole_sketch(sc)
mmu = st.mm_per_unit
L = obj.matrix_world.inverted() @ st.layout.matrix_world
dr = layer.current_frame().drawing
ring = [(10 * __import__("math").cos(a / 8 * 6.283), 40 + 10 * __import__("math").sin(a / 8 * 6.283))
        for a in range(8)]
dr.add_strokes([len(ring)])
for pt, (x, y) in zip(dr.strokes[0].points, ring):
    pt.position = L @ ((P @ Vector((x, y, 0))) / mmu)
dr.strokes[0].cyclic = True
build.rebuild(sc, force=True)
assert [p for p, _ in holes.drawn(sc, *build.make_model(sc))] == [piece]
# a new piece packed in first moves the stand-up along the sheet
box = next(m for m in st.mechs if m.kind == "BOX")  # an earlier piece grows
box.height, box.depth = 60, 70
build.rebuild(sc, force=True)
model, layout = build.make_model(sc)
assert layout["prints"][piece] != P, "layout did not move the piece (test setup)"
got = holes.drawn(sc, model, layout)
assert [p for p, _ in got] == [piece], got
c = Vector((sum(x for x, _ in got[0][1]) / 8, sum(y for _, y in got[0][1]) / 8))
assert (c - Vector((0, 40))).length < 0.5, c
print("drawn holes move with their piece")

# a rebuild never moves the pen off the layer being drawn on
obj, layer = holes.line_layer(sc, "CUT")
assert obj.data.layers.active.name == "slit"
build.rebuild(sc, force=True)
assert obj.data.layers.active.name == "slit"
print("drawing layer kept across rebuilds")

# ---- highlight: the selected mechanism's panels, on the card and layout
from popup_pro import highlight  # noqa: E402
st.active = next(i for i, m in enumerate(st.mechs) if m.uid == su.uid)
want = highlight._panels(sc, su.uid)
names = [model.order[i] for i in want]
assert names and all(n.startswith(f"Stand{su.uid}.") for n in names), names
assert not highlight._panels(sc, 999)
dg = bpy.context.evaluated_depsgraph_get()
tris = highlight._tris(st.card, dg, want) + highlight._tris(st.layout, dg, want)
assert tris and len(tris) % 3 == 0
for n in ("VFold1.HalfL", "Box12.AC", "Stand5.TabC", "Tube3.TopL", "Page.L"):
    print(n, highlight._uid_of(n))
assert highlight._uid_of("Box12.AC") == 12 and highlight._uid_of("Page.L") is None
print("highlight finds", len(tris) // 3, "triangles")

addon.unregister()
print("V16 OK")
