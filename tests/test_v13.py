"""v0.13: one set of hole tools for every mechanism. Erasing paint to a
piece's edge trims its outline in the print (cut on export), openings can be
cut in any piece (roofs and ribs included), and holes that cut a fold right
through are flagged."""
import math
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "tests", "out")
os.makedirs(OUT, exist_ok=True)

import bpy  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
import numpy as np  # noqa: E402
import popup_pro as addon  # noqa: E402
from popup_pro import art, build, export_svg, holes, live  # noqa: E402
from popup_pro.build import TILE_MM  # noqa: E402

addon.register()
sc = bpy.context.scene
st = sc.popup
st.live = False
assert bpy.ops.popup.add(kind="VFOLD") == {"FINISHED"}
uid = st.mechs[0].uid
assert bpy.ops.popup.add(kind="TUBE") == {"FINISHED"}
tube = st.mechs[1]
tube.roof, tube.y, tube.x = "POINTED", 120, 25
assert bpy.ops.popup.build() == {"FINISHED"}
assert not st.warnings, st.warnings

# erase a round bite off the outer top corner of the V-fold's left half
img = art.add_art_texture(sc, dpi=100)
meta = live.meta(st.rig)
info = meta["pieces"][f"VFold{uid}"]
model, layout = build.make_model(sc)
half = model.panels[f"VFold{uid}.HalfL"].polys[0]
cx, cy = min(q[0] for q in half), max(q[1] for q in half)
tmp = tempfile.mkdtemp()
tiles = export_svg._tile_pngs(img, tmp)
t = bpy.data.images.load(tiles[1001 + info["slot"]])
w, h = t.size
ax, ay = info["anchor"]
A = np.empty(w * h * 4, np.float32)
t.pixels.foreach_get(A)
A = A.reshape(h, w, 4)
ys = ay - TILE_MM / 2 + (np.arange(h) + 0.5) * TILE_MM / h
xs = ax - TILE_MM / 2 + (np.arange(w) + 0.5) * TILE_MM / w
X, Y = np.meshgrid(xs, ys)
A[..., 3][(X - cx) ** 2 + (Y - cy) ** 2 < 18 ** 2] = 0.0
t.pixels.foreach_set(A.ravel())
t.save()
bpy.data.images.remove(t)
new = bpy.data.images.load(tiles[1001])
new.source = "TILED"
new.filepath = os.path.join(tmp, "tile.<UDIM>.png")
new.reload()
new.pack()
new.filepath = ""
name = img.name
img.user_remap(new)
bpy.data.images.remove(img)
new.name = name

# exporting cuts what the paint shows (Cut Painted Areas is on by default)
assert st.auto_holes
path = os.path.join(OUT, "v13.svg")
assert bpy.ops.popup.export_svg(filepath=path) == {"FINISHED"}
assert len(holes.painted(st)[f"VFold{uid}"]) == 1
model, layout = build.make_model(sc)
cuts = holes.collect(sc, model, layout)
me = st.layout.data
attr = me.attributes["pop_panel"]
pi = model.order.index(f"VFold{uid}.HalfL")
P = layout["prints"][f"VFold{uid}"].inverted()
s_ = 1 / st.mm_per_unit
corner_gone = all(((P @ (me.vertices[v].co / s_)).to_2d() - __import__("mathutils").Vector((cx, cy))).length > 17
                  for poly in me.polygons if attr.data[poly.index].value == pi
                  for v in poly.vertices)
assert corner_gone
assert not st.warnings, st.warnings
print("erased corner trimmed off the V-fold half, cut on export")

# an opening on the tube's roof piece (a piece of its own, same id as the tube)
o = st.openings.add()
o.on_piece = f"Roof{tube.uid}"
o.shape, o.x, o.y, o.width, o.height = "OVAL", -12.0, 100.0, 8.0, 8.0
build.rebuild(sc, force=True)
model, layout = build.make_model(sc)
assert f"Roof{tube.uid}" in holes.collect(sc, model, layout)
print("opening cut in a roof")

# a hole right across a glue line is flagged
o = st.openings.add()
o.on_piece = f"VFold{uid}"
o.shape, o.x, o.y, o.width, o.height = "RECT", -20.0, -5.0, 60.0, 14.0
build.rebuild(sc, force=True)
assert "cuts it free" in st.warnings, st.warnings
print("hole cutting a half free of its tab flagged")
addon.unregister()
print("V13 OK")
