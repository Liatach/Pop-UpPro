"""v0.42: painting carries on across the folded card and its flat layout
(the same paper) without stopping; brush, colour and layers in our panel;
box folds and straps are one mechanism (Strap: lies flat)."""
# families: paint, straps
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
import popup_pro as addon  # noqa: E402
from popup_pro import build, holes, ops  # noqa: E402

addon.register()
sc = bpy.context.scene
st = sc.popup
assert bpy.ops.popup.build() == {"FINISHED"}

# ---- painting: the card shows its flat layout too, as the same paper
n_card = len(st.card.data.polygons)
assert bpy.ops.popup.paint() == {"FINISHED"}
mod = st.card.modifiers[ops.PAINT_BOTH]
assert mod.show_viewport and not mod.show_render and st.layout.hide_get()
dg = bpy.context.evaluated_depsgraph_get()
dg.update()
ev = st.card.evaluated_get(dg).data
assert len(ev.polygons) > n_card * 2 and ev.uv_layers.active.name == "PopupArt"
bpy.ops.popup.paint()
assert not mod.show_viewport and not st.layout.hide_get()
print("painting shows the flat layout on the card too: one object, both shapes")

# ---- (switching objects, kept for the record) paint on the card, the layout and back
assert bpy.ops.popup.paint() == {"FINISHED"}
art = ops.paint_images(sc)[0]
assert ops.painting(bpy.context) and ops.painting_into(sc) == art
assert ops.paint_switch(bpy.context, st.layout)
assert bpy.context.view_layer.objects.active == st.layout
assert ops.painting(bpy.context) and ops.painting_into(sc) == art
assert ops.switching(sc)
holes._last_mode["mode"] = "PAINT_TEXTURE"
holes._mode_changed()  # Blender's mode notification while switching: nothing cut, nothing reset
assert "pop_true_colours" in sc or not st.true_colours
assert not ops.paint_switch(bpy.context, st.layout), "already there"
assert ops.paint_switch(bpy.context, st.card)
assert ops.painting(bpy.context)
assert bpy.ops.popup.paint() == {"FINISHED"}  # off, from either
assert bpy.context.mode == "OBJECT"
print("one painting session across the folded card and the flat layout")

# ---- the paint panel draws its brush sections (stub layout)
from popup_pro import ui  # noqa: E402


class Lay:
    def __init__(self):
        self.calls = []

    def __getattr__(self, k):
        def f(*a, **kw):
            self.calls.append(k)
            if k == "panel":
                return Lay(), Lay()
            return Lay() if k in ("row", "column", "box", "split") else None
        return f


bpy.ops.popup.paint()
lay = Lay()
ui._brush_sections(lay, bpy.context)
assert lay.calls.count("panel") >= 2
bpy.ops.popup.paint()
print("colour and brush sections draw")

# ---- box fold and strap: one mechanism
st.mechs.clear()
assert bpy.ops.popup.add(kind="BOX") == {"FINISHED"}
b = st.mechs[-1]
assert b.label == "Box fold 1" and not b.strap
b.height, b.depth = 40.0, 25.0
b.strap = True
assert b.label == "Strap 1" and b.depth == b.height
assert b.to_dict()["depth"] == b.to_dict()["height"] == 40.0
b.height = 30.0
assert b.to_dict()["depth"] == 30.0, "a strap's sides stay equal"
b.strap = False
assert b.label == "Box fold 1"
assert bpy.ops.popup.add(kind="BOX", variant="STRAP") == {"FINISHED"}
s2 = st.mechs[-1]
assert s2.strap and s2.label.startswith("Strap")
build.rebuild(sc, force=True)
print("box folds and straps are one: Strap makes it lie flat")
print("all v42 checks pass")
