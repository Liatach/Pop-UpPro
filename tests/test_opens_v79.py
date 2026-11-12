"""v0.79: Opens To. A card that stands part open (90 or 120 degrees, say) is
worked out to be fully open at that angle: the Open slider stops there, and
frames, floors and ceilings go straight in the card, pulling flat as it gets
there, as in a carousel's stage."""
# families: stage, scene, ui, hosts
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
from popup_pro import build, export_svg, props, ui  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ui_stub import adds_offered, draw  # noqa: E402

addon.register()
sc = bpy.context.scene
st = sc.popup
st.live = False


def add(kind, **kw):
    assert bpy.ops.popup.add(kind=kind, **kw) == {"FINISHED"}, (kind, kw)
    return st.mechs[-1]


def normal(model, name, t):
    return (model.panels[name].asm(t).to_3x3() @ Vector((0, 0, 1))).normalized()


def offered():
    return [a["kind"] for a in adds_offered(draw(ui.POPUP_MT_add))]


# ---- an ordinary card: flat at 180, as ever
assert st.opens_to == 180.0 and st.open_max == 180.0 and not st.part_open
assert st.card_dict()["tmax"] == 180.0
assert "FLOOR" not in offered() and "CEILING" not in offered()
try:
    r = bpy.ops.popup.add(kind="FLOOR")
except RuntimeError as e:
    r = str(e)
assert "Add a Stage Set first" in str(r), r
f = add("FRAME")  # (across the fold, flat at 180)
model = build.make_model(sc)[0]
assert model.tmax == 180.0 and not model.warnings, model.warnings
assert abs(normal(model, f"Frame{f.uid}.L", 180.0).dot(normal(model, f"Frame{f.uid}.R", 180.0))) > 0.9999
print("180: an ordinary card, no floors offered")

# ---- Opens To 120: the card is the stage
st.mechs.clear()
st.opens_to = 120.0
assert st.part_open and st.open_max == 120.0 and st.card_dict()["tmax"] == 120.0
menu = offered()
assert {"FRAME", "FLOOR", "CEILING"} <= set(menu), menu
assert menu.count("FRAME") == 1, menu  # (not also "across the fold")
fr, fl, ce = add("FRAME"), add("FLOOR"), add("CEILING")
assert (fr.host_uid, fl.host_uid, ce.host_uid) == (0, 0, 0)  # straight in the card
v = add("VFOLD")
b = add("BOX")
b.y = 150.0
model = build.make_model(sc)[0]
assert model.tmax == 120.0 and not model.warnings, model.warnings
# the frame is Depth x sin(60) each side, and pulls flat exactly at 120
L, R = f"Frame{fr.uid}.L", f"Frame{fr.uid}.R"
assert abs(normal(model, L, 120.0).dot(normal(model, R, 120.0))) > 0.9999
assert abs(normal(model, L, 60.0).dot(normal(model, R, 60.0))) < 0.99
xs = [p[0] for p in model.panels[L].polys[0]]
assert abs((max(xs) - min(xs)) - fr.x * math.sin(math.radians(60.0))) < 0.05, xs
# floor and ceiling lie flat (their halves in one plane, square to the fold) at 120
for m in (fl, ce):
    HL, HR = f"VFold{m.uid}.HalfL", f"VFold{m.uid}.HalfR"
    nl, nr = normal(model, HL, 120.0), normal(model, HR, 120.0)
    assert abs(nl.dot(nr)) > 0.9999 and abs(abs(nl.y) - 1.0) < 1e-4, (m.label, nl, nr)
    assert abs(normal(model, HL, 60.0).dot(normal(model, HR, 60.0))) < 0.99
print("120: frame, floor and ceiling in the card, flat when it is fully open")

# the built card: Open stops at 120, and the rig follows the geometry
st.keep_open = True
bpy.ops.popup.build()
assert not st.warnings, st.warnings
rig, card = st.rig, st.card
assert rig.id_properties_ui("pop_open").as_dict()["max"] == 120.0
bpy.ops.popup.set_open(angle=180.0)
assert rig["pop_open"] == 120.0
buttons = [e[3]["text"] for e in draw(ui.POPUP_PT_card) if e[1] == "operator"
           and e[2][0] == "popup.set_open"]
assert buttons == ["0°", "30°", "60°", "90°", "120°"], buttons
model, layout = build.make_model(sc)
s_ = 1 / st.mm_per_unit
me = card.data
t0 = rig["pop_close"]
assert 0.0 < t0 < 30.0, t0
worst = 0.0
for ov in (0.0, 40.0, 80.0, 120.0):
    real = t0 + ov * (120.0 - t0) / 120.0  # Open 0..120 runs from the closing stop to 120
    rig["pop_open"] = ov
    rig.update_tag()
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    ev = card.evaluated_get(dg).data
    attr = me.attributes["pop_panel"]
    for poly in me.polygons:
        p = model.panels[model.order[attr.data[poly.index].value]]
        # (shown: with the lift onto its tabs the rig gives a box near full open)
        D = model.shown(p.name, real) @ layout["prints"][p.piece].inverted()
        for vi in poly.vertices:
            worst = max(worst, (ev.vertices[vi].co - (D @ (me.vertices[vi].co / s_)) * s_).length
                        / s_)
assert worst < 0.1, worst
svg = os.path.join(tempfile.mkdtemp(), "opens.svg")
assert export_svg.export(sc, svg, **export_svg.settings_from(st))
print(f"built: Open stops at 120, the rig within {worst:.4f} mm, sheets export")

# back to 180: floors can't lie flat there, and say what to do
st.opens_to = 180.0
assert rig.id_properties_ui("pop_open").as_dict()["max"] == 180.0
model = build.make_model(sc)[0]
w = [x for x in model.warnings if "Floor" in x or "Ceiling" in x]
assert len(w) == 2 and all("Opens To" in x for x in w), model.warnings
st.opens_to = 160.0
w = [x for x in build.make_model(sc)[0].warnings if "Floor" in x]
assert w and "under 150" in w[0], w

# ---- Opens To 90: every kind builds
st.opens_to = 90.0
st.keep_open = False
kinds = [k[0] for k in props.KINDS]
for name in kinds:
    st.mechs.clear()
    if name == "JACK":
        add("JACK", host=add("VFOLD").uid)
    elif name == "TETHER":
        add("TUBE")
        add("TETHER")
    else:
        add(name)
    model = build.make_model(sc)[0]
    assert model.tmax == 90.0 and not model.warnings, (name, model.warnings)
# a box fold on the fold is square when the card is: its top level, its front upright
st.mechs.clear()
b = add("BOX")
model = build.make_model(sc)[0]
top, front = normal(model, f"Box{b.uid}.AC", 90.0), normal(model, f"Box{b.uid}.CB", 90.0)
assert abs(top.dot(front)) < 1e-4, (top, front)
print(f"90: all {len(kinds)} kinds build")

# a carousel's stages still open to 360 / n, whatever Opens To says
st.mechs.clear()
sc2 = bpy.data.scenes.new("Carousel")
sc2.popup.opens_to = 120.0
with bpy.context.temp_override(scene=sc2):
    assert bpy.ops.popup.make_carousel(count=4) == {"FINISHED"}
from popup_pro import carousel  # noqa: E402
stage = carousel.stages(sc2)[0].popup
assert stage.open_max == 90.0 and stage.card_dict()["tmax"] == 90.0 and stage.part_open
print("a carousel's stages keep their own angle")

addon.unregister()
print("V79 OK")
