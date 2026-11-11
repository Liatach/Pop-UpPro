"""v0.4: closing stop, solid paper, Art + Cut export, tab colour, red
creases, bleed, and bakes that leave the user's materials untouched."""
# families: export, paper, bake
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "tests", "out")
os.makedirs(OUT, exist_ok=True)

import bpy  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
import popup_pro as addon  # noqa: E402
from popup_pro import art, build, export_svg  # noqa: E402
from popup_pro.core.layout import build_layout  # noqa: E402
from popup_pro.ops import _add  # noqa: E402

addon.register()
sc = bpy.context.scene
st = sc.popup
st.live = False
assert bpy.ops.popup.build() == {"FINISHED"}  # V-fold + box fold
b = _add(st, "BOXCUT")
b.y, b.width, b.height, b.depth = 150, 40, 30, 30
k = _add(st, "BOX")
k.host_uid, k.fold, k.y, k.width, k.height, k.depth, k.tab = b.uid, "A", 155, 20, 15, 15, 8

# --- closing stop -----------------------------------------------------------
st.keep_open = True
st.paper_thickness = 0.3
model = build.rebuild(sc, force=True)
rig, card = st.rig, st.card
t0 = rig["pop_close"]
assert 0.5 < t0 < 45, t0
lay = build_layout(model)
s = 1 / st.mm_per_unit
me = card.data
attr = me.attributes["pop_panel"]


def rig_error(open_value, real_angle):
    rig["pop_open"] = float(open_value)
    rig.update_tag()
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    ev = card.evaluated_get(dg).data
    attr = me.attributes["pop_panel"]  # re-read: rebuilds replace the mesh data
    worst = 0.0
    for poly in me.polygons:
        p = model.panels[model.order[attr.data[poly.index].value]]
        D = model.shown(p.name, real_angle) @ lay["prints"][p.piece].inverted()
        for vi in poly.vertices:
            worst = max(worst, (ev.vertices[vi].co - (D @ (me.vertices[vi].co / s)) * s).length / s)
    return worst


e0 = rig_error(0, t0)
e90 = rig_error(90, t0 + 90 * (180 - t0) / 180)
e180 = rig_error(180, 180)
assert max(e0, e90, e180) < 0.05, (e0, e90, e180)
drv = list(rig.animation_data.drivers) + list(rig.data.animation_data.drivers)
assert all(fc.driver.is_simple_expression for fc in drv)
# the stop really leaves room: gap at the box stack's outer edge >= layers
l, r, nl, nr = model.dirs(t0)
print(f"closing stop {t0:.2f} deg; rig matches at Open 0/90/180 "
      f"({e0:.4f}/{e90:.4f}/{e180:.4f} mm)")
thick = model.close_angle(1.0)
assert thick > t0, "thicker paper must stop further open"
st.keep_open = False
model2 = build.rebuild(sc, force=True)
assert rig["pop_close"] == 0.0 and rig_error(0, 0.0) < 0.05
print(f"stop off: closes to 0; 1 mm paper would stop at {thick:.1f} deg")

# --- solid paper --------------------------------------------------------------
st.keep_open = True
st.solid_paper = True
build.rebuild(sc, force=True)
mods = [m.type for m in card.modifiers]
assert mods == ["ARMATURE", "SOLIDIFY"], mods
sol = card.modifiers["Pop-up Paper"]
assert abs(sol.thickness - 0.03) < 1e-6 and sol.offset == -1.0
st.solid_paper = False
build.rebuild(sc, force=True)
assert [m.type for m in card.modifiers] == ["ARMATURE"]
print("solid paper: solidify added after the rig, removed when off")

# --- bake leaves materials alone ---------------------------------------------
mat = bpy.data.materials["Pop-up Paper"]
before = (len(mat.node_tree.nodes), mat.node_tree.nodes.active and mat.node_tree.nodes.active.name,
          len(mat.node_tree.links))
n_mats, n_objs, n_meshes = len(bpy.data.materials), len(bpy.data.objects), len(bpy.data.meshes)
sc.cycles.samples = 64
st.bleed = 1.0
art.bake_art(sc, dpi=40)
after = (len(mat.node_tree.nodes), mat.node_tree.nodes.active and mat.node_tree.nodes.active.name,
         len(mat.node_tree.links))
assert before == after, (before, after)
assert (len(bpy.data.materials), len(bpy.data.objects), len(bpy.data.meshes)) == (n_mats, n_objs, n_meshes)
assert sc.cycles.samples == 64
print("bake: material, data blocks and render settings unchanged")

# --- exports ------------------------------------------------------------------
def run(name="v04", **kw):
    for k_, v in kw.items():
        setattr(st, k_, v)
    return export_svg.export(sc, os.path.join(OUT, name + ".svg"), **export_svg.settings_from(st))


files = run(export_content="PRINT", tab_fill=False, bleed=0.0)
d = open(files[1]).read()
glue = d.split('id="glue"')[1].split("</g>")[0]
assert "<path" not in glue, "tabs should be paper white by default"
files = run(tab_fill=True, tab_color=(1.0, 0.0, 0.0))
assert 'fill="#ff0000"' in open(files[1]).read()
files = run(export_content="ART_CUT", tab_fill=False, bleed=1.0)
assert all("_art_sheet" in f for f in files)
d = open(files[1]).read()
assert "<image" in d
for layer in ("mountain", "valley", "guides", "labels"):
    assert "<path" not in d.split(f'id="{layer}"')[1].split("</g>")[0] and \
        "<text" not in d.split(f'id="{layer}"')[1].split("</g>")[0], layer
assert "<path" in d.split('id="cut"')[1].split("</g>")[0]
# bleed: clip paths grow past the cut outline
plain = run("v04_nobleed", export_content="ART_CUT", bleed=0.0)
import re  # noqa: E402


def clip_extent(path):
    nums = [float(x) for x in re.findall(r"-?\d+\.\d+", open(path).read().split("<defs>")[1].split("</defs>")[0])]
    xs = nums[0::2]
    return min(xs), max(xs)


a0, a1 = clip_extent(plain[1])
b0, b1 = clip_extent(files[1])
assert b0 < a0 - 0.5 and b1 > a1 + 0.5, (a0, a1, b0, b1)
files = run(export_content="LINES", dashed_folds=False)
d = open(files[0]).read()
assert "_lines_sheet" in files[0] and 'stroke="#ff0000"' in d and 'stroke="#000000"' in d
assert "<image" not in d and "<text" not in d
creases = d.split('id="valley"')[1].split("</g>")[0] + d.split('id="mountain"')[1].split("</g>")[0]
assert "#000000" not in creases
print("exports: white tabs, colour tabs, Art + Cut (no folds/guides), bleed, red creases")
addon.unregister()
print("V04 OK")
