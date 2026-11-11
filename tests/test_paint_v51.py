"""v0.51: a mechanism added after the paint texture gets its own tile
(a UDIM image renders a missing tile magenta), keeping the painted art."""
# families: paint
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402
import numpy as np  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
import popup_pro as addon  # noqa: E402
from popup_pro import build, live  # noqa: E402

addon.register()
sc = bpy.context.scene
st = sc.popup
bpy.ops.popup.build()
st.mechs.clear()
bpy.ops.popup.add(kind="VFOLD")
build.rebuild(sc, force=True)
bpy.ops.popup.add_art(dpi=60)
img = bpy.data.images["Pop-up Art"]
w, h = img.size
px = np.zeros((h, w, 4), np.float32)
px[..., 2] = 1.0
px[..., 3] = 1.0
img.pixels.foreach_set(px.ravel())  # the card's tile, painted blue
img.update()
n0 = len(img.tiles)
bpy.ops.popup.add(kind="CUBE")
build.rebuild(sc, force=True)
img = bpy.data.images["Pop-up Art"]
meta = live.meta(st.rig)
have = {t.number for t in img.tiles}
need = {1001 + p["slot"] for p in meta["pieces"].values()}
assert need <= have, (need - have)
assert len(img.tiles) == n0 + 1
got = np.array(img.pixels[:]).reshape(-1, 4)
assert abs(got[:, 2].mean() - 1.0) < 0.01 and got[:, 0].max() < 0.01, "the painting is kept"
mat = bpy.data.materials["Pop-up Paper"]
assert any(n.type == "TEX_IMAGE" and n.image == img for n in mat.node_tree.nodes)
print("v51 ok")
