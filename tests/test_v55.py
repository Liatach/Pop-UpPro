"""v0.55: painting's flat layout never outlasts painting (it showed round a
carousel when stages were left painting), and Print Layout in Renders."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
import popup_pro as addon  # noqa: E402
from popup_pro import build, carousel, ops  # noqa: E402
from popup_pro.carousel import in_scene  # noqa: E402

addon.register()
sc = bpy.context.scene
assert bpy.ops.popup.make_carousel(count=3) == {"FINISHED"}
S = carousel.stages(sc)
for s in S:
    with in_scene(s):
        ops._paint_both(s, True)  # as painting leaves it
    assert s.popup.card.modifiers[ops.PAINT_BOTH].show_viewport
# the master is on screen: the stages aren't being painted
for s in S:
    assert ops.stale_paint_view(s)
    assert not s.popup.card.modifiers[ops.PAINT_BOTH].show_viewport
    assert "pop_paint_flat" not in s
    assert not s.popup.layout.hide_get(view_layer=s.view_layers[0])
print("a stage's leftover painting view is put back")
# and a rebuild does it too
with in_scene(S[0]):
    ops._paint_both(S[0], True)
    build.rebuild(S[0], force=True)
assert not S[0].popup.card.modifiers[ops.PAINT_BOTH].show_viewport

# Print Layout in Renders: off by default; the carousel's switch sets every stage
assert all(s.popup.layout.hide_render for s in S)
sc.popup.layout_in_render = True
assert not any(s.popup.layout.hide_render for s in S)
with in_scene(S[1]):
    build.rebuild(S[1], force=True)
assert not S[1].popup.layout.hide_render, "stages follow the carousel"
sc.popup.layout_in_render = False
assert all(s.popup.layout.hide_render for s in S)
print("v55 ok")
