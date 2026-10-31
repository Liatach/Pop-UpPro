"""v0.14: extra creases and cuts on V-fold pieces (Birmingham 5, 6, 9, 10).
Regions split off by the lines turn so their share of the centre fold still
meets (reverse points, steps, jaws) or jut out flat (projections); the rig
follows, and the print shows the new creases and cuts."""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "tests", "out")
os.makedirs(OUT, exist_ok=True)

import bpy  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
from mathutils import Vector  # noqa: E402

import popup_pro as addon  # noqa: E402
from popup_pro import build  # noqa: E402
from popup_pro.core.folds import _inside  # noqa: E402
from popup_pro.core.model import Model  # noqa: E402

V = dict(type="VFOLD", uid=1, label="V", y=70, phi_l=60, phi_r=60, alpha_l=80,
         alpha_r=80, glue=40, height=50, tab=12, tab_side="IN")
CARD = dict(W=148.5, H=210, hold="RIGHT")
CASES = {
    "reverse": ([dict(kind="CREASE", pts=[(0, 40), (-12, 25)]),
                 dict(kind="CUT", pts=[(0, 25), (-12, 25)])], (0, 32)),
    "step": ([dict(kind="CREASE", pts=[(-8, 60), (-8, 30)]),
              dict(kind="CUT", pts=[(0, 30), (-8, 30)])], (0, 40)),
    "top": ([dict(kind="CREASE", pts=[(0, 30), (-15, 60)])], (0, 45)),
    "jaw": ([dict(kind="CREASE", pts=[(0, 30), (-50, 50)])], (0, 40)),
}


def at(model, pt):
    return [n for n in model.order if n.startswith("VFold1") and
            any(_inside(pt, poly) for poly in model.panels[n].polys)]


# ---- core: the folded regions keep the centre fold together, and fold
for name, (lines, probe) in CASES.items():
    m = Model(CARD, [dict(V, lines=lines)])
    assert not m.warnings, (name, m.warnings)
    folds = [n for n in m.order if ".Fold" in n]
    assert len(folds) == 2, (name, folds)
    a, = at(m, (probe[0] - 0.01, probe[1]))
    b, = at(m, (probe[0] + 0.01, probe[1]))
    assert ".Fold" in a and ".Fold" in b
    for t in (0.5, 10, 45, 90, 135, 180):
        q = Vector((probe[0], probe[1], 0))
        gap = (m.panels[a].asm(t) @ q - m.panels[b].asm(t) @ q).length
        assert gap < 1e-3, (name, t, gap)
        psi = abs(m.panels[folds[0]].hinge.fn(t))
        assert psi > math.radians(30), (name, t, math.degrees(psi))  # it really folds
    print(f"{name}: two regions fold, centre fold stays together")

# a projection: a cut from the centre fold back to it, one half only
m = Model(CARD, [dict(V, lines=[dict(kind="CUT", mirror=False,
                                     pts=[(0, 20), (-15, 22), (-18, 35), (0, 40)])])])
assert not [n for n in m.order if ".Fold" in n]
assert at(m, (-10, 30)) == ["VFold1.HalfR"]  # juts out with the right half
assert at(m, (-10, 15)) == ["VFold1.HalfL"]
print("projection rides flat on the other half")

# one-sided creases have nothing to fold against: flat, with a hint
m = Model(CARD, [dict(V, lines=[dict(kind="CREASE", mirror=False, pts=[(0, 30), (-50, 50)])])])
assert any("Mirror" in w for w in m.warnings), m.warnings
m = Model(CARD, [dict(V, lines=[dict(kind="CUT", pts=[(-5, 30), (-10, 30)])])])
assert any("do nothing" in w for w in m.warnings), m.warnings
print("lone crease and stray cut flagged")

# ---- in Blender: presets, rig, print
addon.register()
sc = bpy.context.scene
st = sc.popup
st.live = False
for k, preset in enumerate(("REVERSE", "STEP", "JAW", "PROJECTION")):
    assert bpy.ops.popup.add(kind="VFOLD") == {"FINISHED"}
    st.active = len(st.mechs) - 1
    st.mechs[-1].y = 40 + 40 * k
    st.mechs[-1].height = 30
    st.mechs[-1].glue = 25
    assert bpy.ops.popup.add_line(preset=preset) == {"FINISHED"}
assert bpy.ops.popup.build() == {"FINISHED"}
assert not st.warnings, st.warnings
model, layout = build.make_model(sc)
folds = [n for n in model.order if ".Fold" in n]
assert len(folds) == 6, folds
st.keep_open = False
model = build.rebuild(sc, force=True)
rig, card = st.rig, st.card
sc_ = 1 / st.mm_per_unit
me = card.data
attr = me.attributes["pop_panel"]
lay = build.make_model(sc)[1]
worst = 0.0
n_chk = 0
for t in (5, 45, 90, 150, 180):
    rig["pop_open"] = float(t)
    rig.update_tag()
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    ev = card.evaluated_get(dg).data
    for poly in me.polygons:
        p = model.panels[model.order[attr.data[poly.index].value]]
        if ".Fold" not in p.name:
            continue
        D = p.asm(t) @ lay["prints"][p.piece].inverted()
        for vi in poly.vertices:
            want = (D @ (me.vertices[vi].co / sc_)) * sc_
            worst = max(worst, (ev.vertices[vi].co - want).length / sc_)
            n_chk += 1
assert worst < 0.5 and n_chk > 50, (worst, n_chk)
print(f"rig follows the extra folds to {worst:.3f} mm ({n_chk} points)")
path = os.path.join(OUT, "v14.svg")
assert bpy.ops.popup.export_svg(filepath=path) == {"FINISHED"}
svg = "".join(open(os.path.join(OUT, f)).read() for f in os.listdir(OUT)
              if f.startswith("v14_sheet"))
assert svg.count("<line") + svg.count("<path") > 0
print("printed")
# remove a line
st.active = 0
st.mechs[0].lines[0].expanded = True  # one line of the shape (v0.35: shapes group)
assert bpy.ops.popup.remove_line() == {"FINISHED"}
assert len(st.mechs[0].lines) == 1

# the V-fold panel shows its lines
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

    def panel(self, idname, **kw):  # a collapsible sub-panel: (header, body)
        return Lay(self.seen), Lay(self.seen)

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
seen = []
stub = types.SimpleNamespace(layout=Lay(seen))
for k, fn in ui.POPUP_PT_mechs.__dict__.items():
    if callable(fn) and not k.startswith("__"):
        setattr(stub, k, types.MethodType(fn, stub))
stub.draw_warnings = types.MethodType(ui._draw_warnings, stub)
stub.draw_flap = types.MethodType(ui._draw_flap, stub)
st.active = 1
st.mechs[1].active_line = 0
st.mechs[1].lines[0].expanded = True  # a shape shows its lines once opened
stub.draw(Ctx(sc))
ui._mech_lines(Lay(seen), Ctx(sc), st.mechs[1])  # (v0.43: in Creases, Cuts and Holes)
assert "x0" in seen and "mirror" in seen and "pleat" in seen, seen
print("lines panel draws")
addon.unregister()
print("V14 OK")
