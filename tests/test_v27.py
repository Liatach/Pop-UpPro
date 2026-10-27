"""v0.27: picture-book defaults (both pages open, one cube, a camera past
the spine's bottom end, a movement test ready to play), cubes and tubes on
other creases (a V-fold's, a box fold's)."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
import popup_pro as addon  # noqa: E402
from popup_pro import scene_setup  # noqa: E402
from popup_pro.core.model import Model  # noqa: E402

CARD = dict(W=148.5, H=210.0, hold="SYM")

# ---- cubes and tubes on other creases
V = dict(type="VFOLD", uid=1, label="V", y=40, phi_l=45, phi_r=45, alpha_l=80, alpha_r=80,
         glue=60, height=70, tab=10, tab_side="IN")
k = 0.35 * 60
for kid in (dict(type="CUBE", uid=2, label="cube", y=28.0, size=0.7 * k, height=0.7 * k,
                 tab=8, host=1, vside="V", lid="PEAK", tab_side="IN"),
            dict(type="TUBE", uid=2, label="tube", y=17.5, x=0.35 * k, depth=31.5,
                 height=0.8 * k, front=0.45 * k, back=0.45 * k, tab=8, host=1, vside="V",
                 front_style="OUT", back_style="OUT", tab_side="IN", roof="NONE")):
    m = Model(CARD, [V, kid])
    m.check_fit()
    assert not m.warnings, (kid["type"], m.warnings)
    assert any(n.startswith(("Cube2", "Tube2")) for n in m.order)
B = dict(type="BOX", style="GLUED", uid=1, label="B", y=50, width=80, height=60, depth=60, tab=10)
T = dict(type="TUBE", uid=2, label="tube", y=60, x=10, depth=40, height=25, front=15, back=15,
         tab=8, host=1, fold="A", front_style="OUT", back_style="OUT", tab_side="IN",
         roof="NONE")
m = Model(CARD, [B, T])
m.check_fit()
assert not m.warnings, m.warnings
# the tube's frame stays steady through the V-fold's right angle (no flip)
m = Model(CARD, [V, dict(T, host=1, vside="V", y=17.5, x=7.35, depth=31.5, height=16.8,
                         front=9.45, back=9.45)])
host = m.tubes[2]["host"]
xs = [m.strip_frame(host, t)[4] for t in range(5, 181, 5)]
assert all(x > 0 for x in xs), xs
print("cubes and tubes stand on V-fold and box-fold creases")

# ---- picture-book defaults: build once and press play
addon.register()
sc = bpy.context.scene
st = sc.popup
assert st.hold == "SYM"
assert bpy.ops.popup.build() == {"FINISHED"}
assert [x.kind for x in st.mechs] == ["CUBE"]
cam = bpy.data.objects.get(scene_setup.CAMERA)
assert cam is not None and sc.camera == cam
# past the bottom end of the spine, above the card, looking at it
assert cam.location.y < 0 and cam.location.z > 0 and abs(cam.location.x) < 1e-6
fc = st.rig.animation_data.action.layers[0].strips[0].channelbags[0].fcurves[0]
keys = [(round(kp.co[0]), round(kp.co[1])) for kp in fc.keyframe_points]
assert keys[0][1] == 0 and max(v for _, v in keys) == 180 and keys[-1][1] == 0, keys
assert sc.frame_end == keys[-1][0]
sc.frame_set(keys[1][0])
assert abs(st.rig["pop_open"] - 180.0) < 1e-3
# one-sided still there, either way round
for hold in ("RIGHT", "LEFT"):
    st.hold = hold
    assert bpy.ops.popup.build() == {"FINISHED"}
# the clean render world: white light, grey to the camera
w = bpy.data.worlds.get(scene_setup.WHITE)
assert w is not None and any(n.type == "LIGHT_PATH" for n in w.node_tree.nodes)
addon.unregister()
print("V27 OK")
