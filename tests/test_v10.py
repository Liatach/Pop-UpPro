"""v0.10: carousels. Stage scenes round one spine driven by one Open control,
stage count changes, openings (through to the frames behind and to the next
stage), sketched and painted holes, and carousel export with glued or shared
pages."""
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
import popup_pro as addon  # noqa: E402
from mathutils import Vector  # noqa: E402
from popup_pro import art, build, carousel, export_svg, holes, live  # noqa: E402
from popup_pro.core.layout import build_layout  # noqa: E402
from popup_pro.naming import N  # noqa: E402
from popup_pro.ops import _add  # noqa: E402

addon.register()
sc = bpy.context.scene
sc.name = "Carousel"
sc.popup.size = "A5"
assert bpy.ops.popup.make_carousel(count=5) == {"FINISHED"}
S = carousel.stages(sc)
assert len(S) == 5 and len({s.popup.suffix for s in S}) == 5
for s in S:
    st = s.popup
    assert st.card_dict()["tmax"] == 72.0 and st.card_dict()["hold"] == "SYM"
    assert [m.kind for m in st.mechs] == ["FRAME", "FRAME"], [m.kind for m in st.mechs]
    assert not st.warnings, st.warnings
# every stage has its own data
assert len({s.popup.rig.name for s in S}) == 5
assert len({build.folded_collection(s).name for s in S}) == 5
print("5 stages, each its own card opening to 72 degrees")

# one Open drives all: stage open = T / n, stage i turned i * T / n
c = carousel.ctrl(sc)
for T in (0.0, 180.0, 360.0):
    c[carousel.OPEN] = T
    c.update_tag()
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    for i, s in enumerate(S):
        assert abs(s.popup.rig["pop_open"] - T / 5) < 1e-4, (T, s.popup.rig["pop_open"])
        inst = bpy.data.objects[f"Stage {i + 1} · Carousel"].evaluated_get(dg)
        assert abs(inst.rotation_euler[1] - math.radians(T) * i / 5) < 1e-5
print("one Open control drives every stage and turns them round the spine")

# pages meet: stage i's right page lies on stage i+1's left page at any opening
c[carousel.OPEN] = 250.0
c.update_tag()
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
worst = 0.0
for i in range(4):
    a, b = S[i], S[i + 1]
    ma, mb = build.make_model(a)[0], build.make_model(b)[0]
    t = 250.0 / 5
    ia = bpy.data.objects[f"Stage {i + 1} · Carousel"].evaluated_get(dg).matrix_world
    ib = bpy.data.objects[f"Stage {i + 2} · Carousel"].evaluated_get(dg).matrix_world
    s_ = 1 / a.popup.mm_per_unit
    for q in ((60.0, 30.0), (140.0, 200.0)):
        pa = ia @ ((ma.panels["Page.R"].asm(t) @ Vector((q[0], q[1], 0))) * s_)
        pb = ib @ ((mb.panels["Page.L"].asm(t) @ Vector((-q[0], q[1], 0))) * s_)
        worst = max(worst, (pa - pb).length / s_)
assert worst < 0.01, worst
print(f"neighbouring pages lie back to back ({worst:.4f} mm)")

# stage count: 6 stages of 60 degrees, frames re-sized
sc.popup.stage_count = 6
carousel.make(sc)
S = carousel.stages(sc)
assert len(S) == 6 and S[5].popup.card_dict()["tmax"] == 60.0
m6 = build.make_model(S[0])[0]
assert abs(m6.frames[S[0].popup.mechs[0].uid]["width"] -
           2 * S[0].popup.mechs[0].x * math.sin(math.radians(30))) < 1e-6
assert sum(1 for o in bpy.data.objects if o.name.startswith("Stage ")) == 6
sc.popup.stage_count = 5
carousel.make(sc)
S = carousel.stages(sc)
assert sum(1 for o in bpy.data.objects if o.name.startswith("Stage ")) == 5
print("stage count 6 then back to 5: frames follow, spare stage kept")

# floors, ceilings, openings
s1, s2 = S[0], S[1]
st = s1.popup
st["live"] = False
_add(st, "FLOOR")
stage_frame, frame1 = st.mechs[0], st.mechs[1]
o = st.openings.add()
o.on_uid, o.shape, o.x, o.y, o.width, o.height = stage_frame.uid, "ARCH", 0.0, 30.0, 90.0, 140.0
o = st.openings.add()
o.on_uid, o.shape, o.x, o.y, o.width, o.height, o.through = frame1.uid, "OVAL", 0.0, 100.0, 30.0, 30.0, "BEHIND"
o = st.openings.add()
o.on_uid, o.shape, o.x, o.y, o.width, o.height, o.through = 0, "ARCH", 60.0, 0.0, 30.0, 60.0, "NEXT"
carousel.rebuild_stage(s1)
carousel.rebuild_stage(s2)
assert not st.warnings, st.warnings
m1 = build.make_model(s1)[0]
h1 = holes.collect(s1, m1)
assert len(h1[f"Frame{stage_frame.uid}"]) == 1 and len(h1[f"Frame{frame1.uid}"]) == 1
assert len(h1["Card"]) == 3  # window carried back (both pages) + the doorway
h2 = holes.collect(s2, build.make_model(s2)[0])
door = h2["Card"][0]
assert max(x for x, y in door) < -44.9 and min(x for x, y in door) > -75.1
print("openings: through the frames behind, and through to the next stage")

# sketched hole: a closed stroke on the staging frame's cut layer
with carousel.in_scene(s1):
    obj, layer = art.sketch_layer(s1, f"Frame{stage_frame.uid}.L", cut=True)
    dr = layer.current_frame().drawing
    dr.add_strokes([12])
    stroke = dr.strokes[0]
    bone = st.rig.data.bones[f"Frame{stage_frame.uid}.L"]
    M = bone.matrix_local @ layer.matrix_parent_inverse @ layer.matrix_local
    P = build.make_model(s1)[1]["prints"][f"Frame{stage_frame.uid}"]
    for i, pt in enumerate(stroke.points):
        a = 2 * math.pi * i / 12
        q = Vector((-60 + 8 * math.cos(a), 60 + 12 * math.sin(a), 0))
        pt.position = M.inverted() @ ((P @ q) / st.mm_per_unit)
    stroke.cyclic = True
carousel.rebuild_stage(s1)
m1, lay1 = build.make_model(s1)
assert len(holes.collect(s1, m1, lay1)[f"Frame{stage_frame.uid}"]) == 2
print("sketched hole cut")

# painted hole: a see-through blob in Frame 1's art tile
with carousel.in_scene(s1):
    img = art.add_art_texture(s1, dpi=60)
meta = live.meta(st.rig)
slot = meta["pieces"][f"Frame{frame1.uid}"]["slot"]
tmp = tempfile.mkdtemp()
tiles = export_svg._tile_pngs(img, tmp)
t = bpy.data.images.load(tiles[1001 + slot])
w, h = t.size
px = list(t.pixels)
for r in range(h):
    for cc in range(w):
        if (cc - w / 2) ** 2 + (r - 0.62 * h) ** 2 < (0.06 * w) ** 2:
            px[4 * (r * w + cc) + 3] = 0.0
t.pixels[:] = px
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
n = holes.trace_painted(s1)
assert n == 1, n
carousel.rebuild_stage(s1)
assert not st.warnings, st.warnings
m1, lay1 = build.make_model(s1)
assert len(holes.collect(s1, m1, lay1)[f"Frame{frame1.uid}"]) == 2
print("painted hole traced and cut")

# the rig still follows the geometry, holes and all
rig, card = st.rig, st.card
s_ = 1 / st.mm_per_unit
me = card.data
worst = 0.0
for T in (20.0, 180.0, 355.0):
    c[carousel.OPEN] = T
    c.update_tag()
    rig.update_tag()
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    ev = card.evaluated_get(dg).data
    attr = me.attributes["pop_panel"]
    for poly in me.polygons:
        p = m1.panels[m1.order[attr.data[poly.index].value]]
        D = p.asm(T / 5) @ lay1["prints"][p.piece].inverted()
        for vi in poly.vertices:
            worst = max(worst, (ev.vertices[vi].co - (D @ (me.vertices[vi].co / s_)) * s_).length / s_)
assert worst < 0.1, worst
print(f"stage rig matches geometry within {worst:.4f} mm")

# export: glued (stages + carousel page), then shared pages (leaves)
fs = carousel.export(sc, os.path.join(OUT, "carousel.svg"), **export_svg.settings_from(sc.popup))
names = [os.path.basename(f) for f in fs]
assert "carousel_stage1_sheet1.svg" in names and "carousel_carousel.svg" in names, names
sheet = open(os.path.join(OUT, "carousel_stage1_sheet2.svg")).read()
assert sheet.count('id="cut"') == 1
sc.popup["join"] = 1  # SHARED (no resync needed for export)
fs = carousel.export(sc, os.path.join(OUT, "carousel_shared.svg"), **export_svg.settings_from(sc.popup))
names = [os.path.basename(f) for f in fs]
assert "carousel_shared_leaf1_front.svg" in names and "carousel_shared_leaf5_back.svg" in names
assert not any(n.endswith("_sheet1.svg") for n in names), names
print("exported", len(fs), "files for shared pages")


# every panel draws in a card, a carousel and a stage scene (a stand-in layout
# records the properties each one shows)
class Lay:
    def __init__(self, seen):
        self.seen = seen
        self.use_property_split = self.use_property_decorate = False
        self.scale_y = 1.0
        self.active = True

    def prop(self, data, name, **kw):
        if not name.startswith('["'):
            assert hasattr(data, name), (type(data).__name__, name)
        self.seen.append(name)

    def operator(self, idname, **kw):
        mod, op = idname.split(".")
        assert hasattr(getattr(bpy.ops, mod), op), idname

        class Op:
            pass
        return Op()

    def __getattr__(self, k):  # row, column, box, label, separator, menu, ...
        def f(*a, **kw):
            return Lay(self.seen)
        return f


class Ctx:
    def __init__(self, scene):
        self.scene = scene
        self.window = None


from popup_pro import ui  # noqa: E402
import types  # noqa: E402
plain = bpy.data.scenes.new("Plain card")
for scene in (sc, S[0], plain):
    seen = []
    drawn = 0
    for cls in ui.classes:
        if not issubclass(cls, bpy.types.Panel):
            continue
        if "poll" in cls.__dict__ and not cls.poll(Ctx(scene)):
            continue
        stub = types.SimpleNamespace(layout=Lay(seen))
        for k, fn in cls.__dict__.items():
            if callable(fn) and not k.startswith("__"):
                setattr(stub, k, types.MethodType(fn, stub))
        stub.draw(Ctx(scene))
        drawn += 1
    print(f"{scene.name}: {drawn} panels draw")
    if scene == sc:
        assert "stage_count" in seen and "join" in seen
    if scene == S[0]:
        assert "x" in seen or "on" in seen or "paper_thickness" in seen
addon.unregister()
print("V10 OK")
