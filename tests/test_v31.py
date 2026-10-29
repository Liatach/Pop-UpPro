"""v0.31: with Solid Paper a strap rests on top of its tabs' thickness;
images wrap round a cube's or tube's walls (Repeat for a copy per wall);
images go straight onto the card; the card camera becomes the scene camera
(a new file's own Camera no longer wins)."""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402
import numpy as np  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=False)  # with its own Camera
import popup_pro as addon  # noqa: E402
from popup_pro import export_svg, images, live, scene_setup  # noqa: E402
from popup_pro.core.model import Model  # noqa: E402

addon.register()
sc = bpy.context.scene
st = sc.popup
assert bpy.ops.popup.build() == {"FINISHED"}
assert sc.camera.name == scene_setup.CAMERA, sc.camera.name
print("the card camera is the scene camera")

# ---- a strap clears its tabs' thickness
m = Model(dict(W=148.5, H=210.0, hold="SYM", thickness=0.3),
          [dict(type="BOX", style="GLUED", uid=1, label="S", y=70, width=50, height=35,
                depth=35, tab=8)])
z = [m.panels["Box1.AC"].lift]  # v0.35: lifted by the rig near flat, the whole strip
assert all(abs(v - (0.15 + 0.6 + 0.05)) < 1e-9 for v in z), z  # tab top 0.45, strip 0.3 thick
print("strap rests on its tabs' thickness")

# ---- images wrap round a cube
meta = live.meta(st.rig)
cp = next(k for k in meta["pieces"] if k.startswith("Cube"))
wrap = meta["pieces"][cp]["wrap"]
img = bpy.data.images.new("F", 60, 80, alpha=True)
img.pixels.foreach_set(np.ones(60 * 80 * 4, np.float32))
pl = images.add(sc, img, cp)
assert pl.fit == "WRAP"
L, c = images.placement(pl, meta)
assert abs(abs(L[0][0]) - (wrap[2] - wrap[0])) < 1e-6 and abs(L[1][1] - (wrap[3] - wrap[1])) < 1e-6
assert abs(c[0] - 0.5 * (wrap[0] + wrap[2])) < 1e-6
pl.repeat = 4
mat = bpy.data.materials["Pop-up Paper"]
assert mat.node_tree.nodes[f"{images.PREFIX}.{pl.uid}.rep"].inputs[1].default_value == 4.0
# four copies in the export, side by side, together the walls' width
files = export_svg.export(sc, os.path.join(tempfile.mkdtemp(), "w.svg"),
                          **export_svg.settings_from(st))
svg = "".join(open(f).read() for f in files if "_sheet" in f and "_reverse" not in f)
assert svg.count('<image width="1" height="1"') == 4, svg.count('<image width="1" height="1"')
ms = [images.svg_matrix(pl, meta, k) for k in range(4)]
assert all(abs(ms[k + 1][4] - ms[k][4] - ms[0][0]) < 1e-6 for k in range(3))
print("images wrap round the cube's walls, one copy per wall")

# ---- straight onto the card
assert bpy.ops.popup.add_image.get_rna_type().properties.get("to_card") is not None
card = next(k for k, v in meta["pieces"].items() if v["is_card"])
pc = images.add(sc, img, card, "BACK")  # the outside cover
assert pc.fit == "FIT" and pc.piece == card
addon.unregister()
print("V31 OK")
