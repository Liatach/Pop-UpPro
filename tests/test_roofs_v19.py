"""v0.19/0.20: a peaked roof for a stage or card. The background is cut to a
gable along the eaves and a V-fold glued along them rises to a ridge, level
at full opening, folding flat inside the card when shut."""
# families: roofs, stage
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
from mathutils import Vector  # noqa: E402

import popup_pro as addon  # noqa: E402
from popup_pro import build  # noqa: E402
from popup_pro.core.folds import _inside  # noqa: E402
from popup_pro.core.model import Model  # noqa: E402

W, H = 148.5, 210.0
for tm in (120.0, 90.0, 72.0):
    card = dict(W=W, H=H, hold="SYM", tmax=tm)
    for slope in (110.0, 135.0):
        R = dict(type="ROOF", uid=1, label="Roof", y=0.85 * H, phi_l=slope, glue=100.0,
                 height=400.0, tab=10, tab_side="IN", level=True)
        R["height"] = Model(card, [R]).roofs[1]["fit"]  # as long as fits shut
        m = Model(card, [R])
        m.check_fit()
        assert not m.warnings, (tm, slope, m.warnings)
        c = m.crease("VFold1", tm)[0]
        Y = m.hosts[(0, "S")].L(tm).to_3x3() @ Vector((0, 1, 0))
        assert abs(c.dot(Y)) < 1e-3 and c.z > 0.9, (tm, slope, c)  # level, into the stage
        for t in (0.3 * tm, 0.6 * tm):  # part open the ridge climbs: peaked all the way
            assert m.crease("VFold1", t)[0].dot(Y) > 0.05, (tm, slope, t)
        # the gable: no paper left above the eaves
        pages = [poly for n in ("Page.L", "Page.R") for poly in m.panels[n].polys]
        assert not any(_inside((-60.0, H - 3.0), poly) for poly in pages)
        assert any(_inside((-60.0, 0.5 * H), poly) for poly in pages)
print("roof: gable cut, ridge level at full opening, peaked as it opens, fits shut")

addon.register()
sc = bpy.context.scene
st = sc.popup
st.live = False
assert bpy.ops.popup.add(kind="ROOF") == {"FINISHED"}
r = st.mechs[-1]
assert abs(r.y - 0.7 * st.card_dict()["H"]) < 0.2
r.glue = 100.0
assert bpy.ops.popup.build() == {"FINISHED"}
model = build.make_model(sc)[0]
assert "VFold%d.HalfL" % r.uid in model.panels, model.warnings
addon.unregister()
print("V19 OK")
