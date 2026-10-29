"""v0.26: images placed on pieces, front or back, fitted and moved like a UV
transform; shown through the paper material, exported at full size (backs
on the reverse sheet), and cut to shape where they are transparent."""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402
import numpy as np  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
import popup_pro as addon  # noqa: E402
from popup_pro import build, export_svg, holes, images, live  # noqa: E402
from popup_pro.build import art_uv  # noqa: E402
from popup_pro.naming import N  # noqa: E402

OUT = tempfile.mkdtemp(prefix="v26_")
addon.register()
sc = bpy.context.scene
st = sc.popup
st.live = False
assert bpy.ops.popup.build() == {"FINISHED"}
meta = live.meta(st.rig)
model = build.make_model(sc)[0]

# a 64 x 32 image: red, with a see-through hole in the middle
W_, H_ = 64, 32
px = np.zeros((H_, W_, 4), np.float32)
px[..., 0], px[..., 3] = 0.9, 1.0
yy, xx = np.mgrid[0:H_, 0:W_]
px[(xx - 32) ** 2 + (yy - 16) ** 2 < 8 ** 2, 3] = 0.0
img = bpy.data.images.new("logo", W_, H_, alpha=True)
img.pixels.foreach_set(px.ravel())

card = next(k for k, v in meta["pieces"].items() if v["is_card"])
mech = next(k for k, v in meta["pieces"].items() if not v["is_card"])

# ---- placement maths: the face's centre is the image's centre, any piece
for piece, side in ((card, "FRONT"), (mech, "BACK")):
    pl = images.add(sc, img, piece, side)
    pl.fit = "FIT"  # (a cube's piece wraps round by default)
    b = meta["pieces"][piece]["bounds"]
    c = (0.5 * (b[0] + b[2]), 0.5 * (b[1] + b[3]))
    u, v = art_uv(model, piece, c)
    (su, sv, s0), (tu, tv, t0) = images.uv_affine(pl, meta)
    s, t = su * u + sv * v + s0, tu * u + tv * v + t0
    assert abs(s - 0.5) < 1e-6 and abs(t - 0.5) < 1e-6, (piece, s, t)
    # fit: the whole image inside the face, touching it on one axis
    L, _ = images.placement(pl, meta)
    w, h = abs(L[0][0]), abs(L[1][1])
    assert abs(w / h - 2.0) < 1e-6
    assert (abs(w - (b[2] - b[0])) < 1e-6) or (abs(h - (b[3] - b[1])) < 1e-6)
    if side == "BACK":
        assert L[0][0] < 0  # mirrored: reads right way round from behind
pl_card, pl_mech = st.images[0], st.images[1]
# moving and turning: values only, no new nodes
mat = bpy.data.materials[N(sc, "Pop-up Paper")]
n_nodes = len(mat.node_tree.nodes)
pl_card.offset_x, pl_card.rotation, pl_card.scale = 10.0, 0.3, 0.5
assert len(mat.node_tree.nodes) == n_nodes
bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
assert bsdf.inputs["Base Color"].links[0].from_node.name.startswith(images.PREFIX)
print("placements fit, move and turn; material updates in place")

# ---- cut where transparent: the hole is cut out of the card
import math  # noqa: E402


def paper_area():
    me = st.layout.data
    return sum(p.area for p in me.polygons) * meta["mm_per_unit"] ** 2


area0 = paper_area()
pl_card.offset_x, pl_card.rotation, pl_card.scale = 0.0, 0.0, 0.5
pl_card.cut = True
n = holes.trace_painted(sc)
assert n == 1, n
build.rebuild(sc, force=True)
m1, lay1 = build.make_model(sc)
assert len(holes.collect(sc, m1, lay1)[card]) == 1
L, c = images.placement(pl_card, meta)
r_mm = 8 / W_ * abs(L[0][0])  # the hole's radius on the card
lost = area0 - paper_area()
assert abs(lost - math.pi * r_mm ** 2) < 0.15 * math.pi * r_mm ** 2, (lost, r_mm)
print(f"transparent middle cut out (radius {r_mm:.1f} mm, {lost:.0f} mm2 of paper)")
# turning the cut off takes the hole away again
pl_card.cut = False
holes.cut_painted(sc, force=True)
assert abs(paper_area() - area0) < 1.0
print("cut off: paper back")

# ---- export: front image in the art layer, back image on the reverse sheet
st.export_content = "PRINT"
files = export_svg.export(sc, os.path.join(OUT, "v26.svg"), **export_svg.settings_from(st))
sheets = [f for f in files if "_sheet" in f and "_reverse" not in f]
revs = [f for f in files if "_reverse" in f]
front = "".join(open(f).read() for f in sheets)
art_layers = [d.split('id="art"')[1].split('id="sketch"')[0] for d in
              (open(f).read() for f in sheets)]
assert any('<image width="1" height="1"' in a for a in art_layers), "front image missing"
mech_sheet = meta["pieces"][mech]["sheet"]
rv = [f for f in revs if f"_sheet{mech_sheet + 1}_reverse" in f]
assert rv and '<image width="1" height="1"' in open(rv[0]).read(), "back image missing"
# lines-only files carry no images
st.export_content = "CUT"
files = export_svg.export(sc, os.path.join(OUT, "v26c.svg"), **export_svg.settings_from(st))
assert not any("<image" in open(f).read() for f in files)
print("export: front in the art, back on the reverse sheet, none in cutter files")

# ---- removing the images puts the material back
while len(st.images):
    st.active_image = 0
    bpy.ops.popup.remove_image()
assert not any(n.name.startswith(images.PREFIX) for n in mat.node_tree.nodes)
assert not bsdf.inputs["Base Color"].is_linked
addon.unregister()
print("V26 OK")
