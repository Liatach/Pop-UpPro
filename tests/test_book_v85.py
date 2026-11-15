"""v0.85: door flaps on cubes, tubes and stand-ups; a V-fold's bite
(Birmingham 13-14); flapping arms through slots in a V-fold or a box fold
(Birmingham 65-66)."""
# families: vfolds, boxes, openings, cubes, tubes
import math
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
import popup_pro as addon  # noqa: E402
from popup_pro import build, export_svg, holes, ui  # noqa: E402
from popup_pro.core.geom import v3  # noqa: E402
from popup_pro.core.model import Model  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ui_stub import adds_offered, draw, props_shown  # noqa: E402

addon.register()
sc = bpy.context.scene
st = sc.popup
st.live = False
svg = os.path.join(tempfile.mkdtemp(), "t.svg")


def add(kind, **kw):
    assert bpy.ops.popup.add(kind=kind, **kw) == {"FINISHED"}, (kind, kw)
    return st.mechs[-1]


def model():
    return Model(st.card_dict(), [m.to_dict() for m in st.mechs])


def warns():
    return [w for w in st.warnings.split("\n") if w]


def reset():
    st.mechs.clear()
    st.openings.clear()
    st["pop_next_uid"] = 1


def world(M, name, t):
    p = M.panels[name]
    A = p.asm(t)
    return [A @ v3(q) for poly in p.polys for q in poly]


def clean(M, prefix):
    for n in M.order:
        p = M.panels[n]
        if not n.startswith(prefix) or p.kind != "panel":
            continue
        for t in M.samples:
            l, r, nl, nr = M.dirs(t)
            d = min(min(w.dot(nl), w.dot(nr)) for w in world(M, n, t))
            assert d > -0.3, (n, t, d)


# ---- door flaps on cubes, tubes and stand-ups
for kind in ("CUBE", "TUBE", "STANDUP"):
    reset()
    add(kind)
    bpy.ops.popup.build()
    M = model()
    pc = next(p for p in M.pieces if p != "Card")
    faces = [n for n in M.pieces[pc].panels if M.panels[n].kind == "panel"]
    face = faces[1 if len(faces) > 1 else 0]
    bpy.ops.popup.add_opening()
    o = st.openings[-1]
    o.on_piece, o.face, o.shape, o.cut = pc, face, "RECT", "DOOR"
    o.width, o.height, o.y = 8.0, 12.0, 6.0
    bpy.ops.popup.build()
    assert not warns(), (kind, warns())
    M = build.make_model(sc)[0]
    doors = [n for n in M.order if ".Door" in n]
    assert len(doors) == 1, (kind, doors)
    d = M.panels[doors[0]]
    assert d.parent == face or M.panels[d.parent].piece == pc
    # it swings open off its face, as the card opens
    t = M.tmax
    F = M.panels[d.parent].asm(t)
    nf = F.to_3x3() @ v3((0.0, 0.0, 1.0))
    off = max(abs(nf.dot(w - F @ v3((0.0, 0.0)))) for w in world(M, doors[0], t))
    assert off > 3.0, (kind, off)
    export_svg.export(sc, svg)
print("door flaps on cubes, tubes and stand-ups")

# ---- a V-fold's bite
reset()
v = add("VFOLD")
v.bite = True
assert {"bite", "bite_len", "bite_angle"} <= set(props_shown(draw(ui.POPUP_PT_mechs)))
bpy.ops.popup.build()
assert not warns(), warns()
M = model()
for n in ("VFold1.BiteL", "VFold1.BiteR", "VFold1.BiteRTab"):
    assert n in M.panels, n
Lc = v.height
for t in M.samples:
    L, R = world(M, "VFold1.BiteL", t), world(M, "VFold1.BiteR", t)
    # the two facets meet along the bite's seam, from its point on the crease
    seam = [w for w in L if min((w - q).length for q in R) < 0.02]
    assert len(seam) >= 2, (t, len(seam))
    pt = M.panels["VFold1.HalfL"].asm(t) @ v3((0.0, Lc - v.bite_len))
    assert min((w - pt).length for w in seam) < 0.02
clean(M, "VFold1")
# the halves are cut back to the bite's creases: their far ends are the facets
hy = max(q[1] for q in M.panels["VFold1.HalfL"].polys[0])
assert hy < Lc - 1.0
v.bite_angle = 40.0
v.phi_l, v.alpha_l = 75.0, 85.0
assert any("dart is too wide" in w for w in model().warnings), model().warnings
v.shape = "TRI"
assert not props_shown(draw(ui.POPUP_PT_mechs)).count("bite")
print("a V-fold's bite")

# ---- flapping arms
for host in ("VFOLD", "BOX"):
    reset()
    h = add(host)
    hu = h.uid
    st.active = 0
    offered = adds_offered(draw(ui.POPUP_MT_add))
    assert {"kind": "ARMS", "host": hu, "fold": "A"} in offered
    a = add("ARMS", host=hu, fold="A")
    assert a.label.endswith(": arms 1") or a.label.endswith(": arms"), a.label
    st.active = len(st.mechs) - 1
    assert {"host", "arm_slot", "arm_back", "arm_width", "arm_len", "arm_y"} <= \
        set(props_shown(draw(ui.POPUP_PT_mechs)))
    bpy.ops.popup.build()
    assert not warns(), (host, warns())
    export_svg.export(sc, svg)
    M = model()
    au = st.mechs[-1].uid
    hpiece = "VFold1" if host == "VFOLD" else "Box1"
    assert len(M.slots.get(hpiece, [])) == 2
    hs = holes.collect(sc, M)
    assert len(hs.get(hpiece, [])) == 2  # (the slots are cut)
    E, G = a.arm_slot, a.arm_back
    for t in M.samples + [M.tmax]:
        bl, br = M.panels[f"Arms{au}.BackL"], M.panels[f"Arms{au}.BackR"]
        # the back piece's halves meet at its crease, and each reaches its slot
        K1 = bl.asm(t) @ v3((0.0, 0.0))
        K2 = br.asm(t) @ v3((0.0, 0.0))
        assert (K1 - K2).length < 0.02
        for side, back, sx in (("L", bl, -1.0), ("R", br, 1.0)):
            end = back.asm(t) @ v3((sx * G, 0.0))
            sl = M.slots[hpiece][0 if side == "L" else 1]
            hp = M.panels[f"{hpiece}.HalfL" if host == "VFOLD" and side == "L" else
                          f"{hpiece}.HalfR" if host == "VFOLD" else
                          f"{hpiece}.AC" if side == "L" else f"{hpiece}.CB"]
            mid = (v3(sl[0]) + v3(sl[1])) * 0.5
            assert (end - hp.asm(t) @ mid).length < 0.05, (host, side, t)
            # the arm goes on out through the slot, in line with its back half
            arm = M.panels[f"Arm{side}{au}.Arm"]
            a0, a1 = arm.asm(t) @ v3((0.0, 0.0)), arm.asm(t) @ v3((10.0, 0.0))
            dk = (a0 - K1).normalized()
            assert (a0 - end).length < 0.05 and ((a1 - a0).normalized() - dk).length < 1e-3
    clean(M, f"Arms{au}")
    clean(M, f"ArmL{au}")
    clean(M, f"ArmR{au}")
    a = st.mechs[-1]
    a.arm_back = 0.3 * a.arm_slot  # too short to reach across
    assert any("can't reach across" in w for w in model().warnings)
    if host == "BOX":
        a.arm_back = a.arm_slot * 1.6
        assert any("fold flat with them" in w for w in model().warnings)
reset()
a = add("ARMS")
assert any("V-fold or a box fold" in w for w in model().warnings)
print("flapping arms through a V-fold and a box fold")

addon.unregister()
print("V85 OK")
_ = math
