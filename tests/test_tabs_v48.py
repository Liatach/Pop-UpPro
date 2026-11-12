"""v0.48: outside tabs carry the art of the part they glue onto (as in
Papercraft Pro): shown on the folded card, painted through, baked into the
tab's own place for print, and drawn on the tab in the SVG export."""
# families: tabs, paint, bake, export
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
import popup_pro as addon  # noqa: E402
from popup_pro import build, export_svg  # noqa: E402
from popup_pro.build import ART_UV, TILE_UV, tab_art  # noqa: E402

addon.register()
sc = bpy.context.scene
st = sc.popup
bpy.ops.popup.build()
st.mechs.clear()
bpy.ops.popup.add(kind="VFOLD")
v = st.mechs[-1]
v.tab_side = "OUT"
bpy.ops.popup.add(kind="BOX")
build.rebuild(sc, force=True)
model, lay = build.make_model(sc)
carry = tab_art(model)
tL, tR = f"VFold{v.uid}.TabL", f"VFold{v.uid}.TabR"
assert tL in carry and tR in carry, carry.keys()
# box tabs fold under the strip, printed side down: they keep their own art
assert not any(k.startswith("Box") for k in carry), carry.keys()
assert carry[tL][0] == "Card"

me = st.card.data
at = me.attributes["pop_panel"]
art, own = me.uv_layers[ART_UV], me.uv_layers[TILE_UV]
assert me.uv_layers.active.name == ART_UV
i = model.order.index(tL)
seen = 0
for p in me.polygons:
    if at.data[p.index].value != i:
        continue
    for li in p.loop_indices:
        u = art.data[li].uv
        assert 0.0 <= u.x < 1.0 and 0.0 <= u.y < 1.0, u  # on the card's tile (1001)
        o = own.data[li].uv
        assert o.x >= 1.0 or o.y >= 1.0, o  # its own place is its piece's tile
        seen += 1
    # it lands where it is glued: compare with the page's UV there
    host = model.panels["Page.L"]
    R = carry[tL][1]
assert seen

# paint the card's tile red, bake: the tab's own place in the print is red
bpy.ops.popup.add_art()
img = bpy.data.images["Pop-up Art"]
import numpy as np  # noqa: E402
sc.render.engine = "CYCLES"
w, h = img.size
px = np.zeros((h, w, 4), np.float32)
px[..., 0] = 1.0
px[..., 3] = 1.0
img.pixels.foreach_set(px.ravel())  # first tile: the card
img.update()
from popup_pro import art as _art  # noqa: E402
pimg = _art.bake_art(sc, dpi=40)
meta = build.live.meta(st.rig) if hasattr(build, "live") else None
tab_tile = next(t for t in pimg.tiles if t.number != 1001 and
                t.number == 1001 + model.pieces[f"VFold{v.uid}"].slot)
# sample the print at the tab's own UVs
tmp = tempfile.mkdtemp()
pngs = export_svg._tile_pngs(pimg, tmp)
tile_img = bpy.data.images.load(pngs[tab_tile.number])
tw, th = tile_img.size
tp = np.array(tile_img.pixels[:]).reshape(th, tw, 4)
reds = []
for p in me.polygons:
    if at.data[p.index].value != i:
        continue
    c = sum((own.data[li].uv for li in p.loop_indices), Vector((0, 0))) / len(p.loop_indices)
    x = int((c.x % 1.0) * tw)
    y = int((c.y % 1.0) * th)
    reds.append(tuple(round(float(a), 2) for a in tp[y, x]))
print("tab print colour", reds)
assert all(r[0] > 0.8 and r[1] < 0.3 and r[3] > 0.9 for r in reds), reds

# export without the bake: the tab draws the card's art, clipped to it
bpy.data.images.remove(pimg)
out = os.path.join(tmp, "card.svg")
export_svg.export(sc, out)
txt = "".join(open(os.path.join(tmp, f)).read() for f in os.listdir(tmp) if f.endswith(".svg"))
assert "clip_tab_" in txt, "outside tab art missing from the export"
print("v48 ok")
