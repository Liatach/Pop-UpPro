"""v0.77: where mechanisms stand. Stands On offers only hosts a kind can
stand on, and picking one starts on a fold that works; the Add menu offers
nothing the model then skips; Fold and On the Crease can't disagree; V-folds,
cubes and double 45s stand on a stand-up's folds; towers only in the corners
a tube has; things fit on a platform and a mouth on quadrilaterals; and the
warnings name the fold that isn't there."""
# families: hosts, ui, standups, boxfolds, vfolds, tubes, folds45, zigzags
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
import popup_pro as addon  # noqa: E402
from popup_pro import build, ops, props, ui  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ui_stub import adds_offered, draw  # noqa: E402

addon.register()
sc = bpy.context.scene
st = sc.popup
st.live = False


def add(kind, **kw):
    assert bpy.ops.popup.add(kind=kind, **kw) == {"FINISHED"}, (kind, kw)
    return st.mechs[-1]


def mech(uid):
    return next(x for x in st.mechs if x.uid == uid)


def clear():
    st.mechs.clear()
    st["pop_next_uid"] = 1


def host(name):
    """A card with one host on it."""
    clear()
    if name == "strap with peaks":
        m = add("BOX")
        m.peaks = 3
    elif name == "angled box":
        m = add("BOX", variant="ANGLED")
    elif name.startswith("VFOLD:"):
        m = add("VFOLD")
        m.shape = name.split(":")[1]
    elif name == "asymmetric":
        m = add("VFOLD", variant="ASYM")
    elif name == "dipped tube":
        m = add("TUBE")
        m.roof, m.roof_fold = "FLAT", "DIP"
    elif name == "loop":
        m = add("TUBE", variant="LOOP")
    elif name == "cylinder":
        m = add("TUBE")
        m.front_style = "ROUND"
    elif name == "ceiling":
        add("STAGE")
        m = add("CEILING")
    elif name == "tower":
        t = add("TUBE")
        t.y, t.x, t.depth, t.height = 60.0, 30.0, 40.0, 25.0
        t.front = t.back = 30.0
        m = add("BOX", host=t.uid, fold="KFL")
        m.height = m.depth = 18.0
        m.width = 60.0
    else:
        m = add(name)
    return m.uid


def offered(child, huid):
    return str(huid) in [i[0] for i in props.host_items(child, bpy.context)]


def built(uid):
    """(placed and not skipped, its warnings)"""
    model = build.make_model(sc)[0]
    w = [x for x in model.warnings if x.startswith(mech(uid).label + ":")]
    return uid in model.placed and not any("skipped" in x for x in w), w, model


HOSTS = ["BOX", "BOXCUT", "strap with peaks", "angled box", "tower", "STANDUP", "VFOLD",
         "asymmetric", "VFOLD:TRI", "VFOLD:FAN", "VFOLD:ZIGZAG", "VFOLD:M", "ZIGZAG", "QUADS",
         "CUBE", "TUBE", "dipped tube", "loop", "PLATFORM", "ceiling"]
CHILDREN = ["VFOLD", "BOX", "BOXCUT", "MOUTH", "CUBE", "TUBE", "PYRAMID", "STANDUP",
            "PLATFORM", "RISER", "DOUBLE45", "JACK", "ZIGZAG", "QUADS"]

# ---- Stands On: every host it offers builds, on the fold picking it starts on
# (bar the few that only need resizing by hand, which say so)
NEEDS_RESIZING = {("VFOLD:TRI", "JACK"), ("VFOLD:M", "JACK")}  # "its chest's folds run off"
picked = 0
for hname in HOSTS:
    for c in CHILDREN:
        huid = host(hname)
        if c == "JACK":  # (Add puts a jack on a V-fold of its own)
            m = st.mechs.add()
            m.kind, m.uid, m.label = "JACK", 90, "Jack"
        else:
            m = add(c)
        uid = m.uid
        if not offered(mech(uid), huid):
            continue
        mech(uid).host = str(huid)
        ok, w, _ = built(uid)
        assert ok or (hname, c) in NEEDS_RESIZING, (hname, c, w)
        picked += 1
print(f"Stands On: {picked} picks of a host all build")

# what isn't offered because it could never stand there
uid = host("VFOLD:FAN")
assert not offered(add("BOX"), uid) and not offered(add("VFOLD"), uid)
uid = host("angled box")
assert not offered(add("BOX"), uid) and not offered(add("CUBE"), uid)
uid = host("tower")  # (a tower's Glue Angle is ignored: things do stand on a tower)
mech(uid).fan_angle = 20.0
assert offered(add("BOX"), uid)
uid = host("STANDUP")
assert not offered(add("BOXCUT"), uid) and not offered(add("MOUTH"), uid)
assert offered(add("BOX"), uid)
for hname in ("BOX", "STANDUP", "PLATFORM", "CUBE", "dipped tube", "ceiling", "ZIGZAG"):
    uid = host(hname)
    j = st.mechs.add()
    j.kind, j.uid = "JACK", 90
    assert not offered(j, uid), hname
uid = host("VFOLD")
j = st.mechs.add()
j.kind, j.uid = "JACK", 90
assert offered(j, uid)
for hname in ("ZIGZAG", "QUADS"):  # (the Add menu put things here; Stands On couldn't show it)
    uid = host(hname)
    for c in ("BOX", "BOXCUT", "VFOLD", "CUBE", "TUBE", "STANDUP"):
        assert offered(add(c), uid), (hname, c)
print("Stands On leaves out fans, angled box folds, and what a kind can't stand on")

# picking a host starts on a fold that can work
uid = host("BOX")
b = add("BOXCUT")
b.host = str(uid)
assert b.fold == "C", b.fold  # a glued box: only its inset fold is one piece of paper
uid = host("strap with peaks")
b = add("MOUTH")
b.host = str(uid)
assert b.fold == "V", b.fold  # several peaks: no inset fold, a valley
uid = host("VFOLD")
b = add("BOXCUT")
b.host = str(uid)
assert b.vside == "V" and b.on_crease
uid = host("QUADS")
b = add("BOX")
b.host = str(uid)
assert b.vside == "V"
uid = host("TUBE")
b = add("VFOLD")
b.wall = "NONE"
b.host = str(uid)
assert b.wall == "L", b.wall  # no dipped roof: a wall, not the roof crease
print("picking a host starts on a fold that works")

# ---- Fold and On the Crease say the same thing
uid = host("VFOLD")
b = add("BOX", host=uid, fold="V")
assert (b.vside, b.on_crease, b.to_dict()["vside"]) == ("V", True, "V")
b.vside = "FL"  # (v0.76: On the Crease stayed on, unseen, and so did the box)
assert (b.on_crease, b.to_dict()["vside"]) == (False, "FL")
b.vside = "V"
assert b.on_crease and b.to_dict()["vside"] == "V"
uid = host("ceiling")
v = add("VFOLD", host=uid)
v.on_crease = True
assert v.vside == "V" and v.to_dict()["vside"] == "V"
v.on_crease = False
assert v.vside != "V" and v.to_dict()["vside"] != "V"
# an older file left that way opens showing what is built
uid = host("VFOLD")
b = add("BOX", host=uid, fold="V")
b["vside"] = 0
assert b.on_crease and b.vside == "FL" and b.to_dict()["vside"] == "V"
props.sync_folds(sc)
assert b.vside == "V" and b.to_dict()["vside"] == "V"
print("Fold and On the Crease keep in step")

# ---- the Add menu offers nothing the model skips
clear()
basics = adds_offered(draw(ui.POPUP_MT_add))
checked = 0
for hname in HOSTS + ["cylinder"]:
    huid = host(hname)
    st.active = next(i for i, x in enumerate(st.mechs) if x.uid == huid)
    extra = adds_offered(draw(ui.POPUP_MT_add))[len(basics):]
    for kw in extra:
        huid = host(hname)  # (the same ids again: the counter starts over)
        assert kw.get("host") == huid, (hname, kw)
        n = len(st.mechs)
        assert bpy.ops.popup.add(**kw) == {"FINISHED"}, (hname, kw)
        new = list(st.mechs)[n:]
        assert new and any(x.host_uid == huid for x in new), (hname, kw)
        model = build.make_model(sc)[0]
        skipped = [w for w in model.warnings if "skipped" in w
                   and any(w.startswith(x.label) or x.label + ":" in w for x in new)]
        assert not skipped, (hname, kw, skipped)
        checked += 1
print(f"Add menu: {checked} offers on a selected host all build")


def menu_on(hname):
    huid = host(hname)
    st.active = next(i for i, x in enumerate(st.mechs) if x.uid == huid)
    return adds_offered(draw(ui.POPUP_MT_add))[len(basics):]


assert not menu_on("angled box") and not menu_on("VFOLD:FAN")
assert not any(a.get("fold", "").startswith("K") or a.get("variant") == "TOWERS"
               for a in menu_on("loop"))  # round both ends: no corners
cyl = [a.get("fold") for a in menu_on("cylinder") if a.get("fold", "").startswith("K")]
assert set(cyl) == {"KBL", "KBR", "KB"}, cyl  # round in front: only the back's
assert not any(a.get("fold") == "C" for a in menu_on("strap with peaks"))
assert {a["kind"] for a in menu_on("PLATFORM")} >= {"BOX", "VFOLD", "CUBE", "TUBE", "STANDUP"}

# towers only in the corners a tube has
uid = host("cylinder")
assert ops.tube_corners(st, uid) == ["KBR", "KBL", "KB"]
assert bpy.ops.popup.add(kind="BOX", host=uid, variant="TOWERS") == {"FINISHED"}
assert sorted(x.wall for x in st.mechs if x.host_uid == uid) == ["KB", "KBL", "KBR"]
assert not [w for w in build.make_model(sc)[0].warnings if "skipped" in w]
uid = host("loop")
assert ops.tube_corners(st, uid) == []
n = len(st.mechs)
try:
    r = bpy.ops.popup.add(kind="BOX", host=uid, variant="TOWERS")
except RuntimeError as e:  # (an operator's error report, outside a window)
    r = str(e)
assert "no inside corners" in str(r) and len(st.mechs) == n, r
print("towers go only in the corners a tube has")

# ---- V-folds, cubes and double 45s on a stand-up's folds (v0.76: "Rebuild failed")
stood = 0
for stand in ("UPRIGHT", "TAIL", "FLAT"):
    for c in ("VFOLD", "CUBE", "DOUBLE45"):
        for fold in "ABC":
            clear()
            h = add("STANDUP")
            h.stand = stand
            m = add(c)
            ops._put_on(st, m.uid, h.uid, fold)
            ok, w, model = built(m.uid)
            assert ok, (stand, c, fold, w)
            stood += 1
# those folds have no short formula, so the solved fold is sampled instead...
assert model.__dict__.get("refit"), "expected sampled hinges on a flat stand-up's inset fold"
# ...which the ordinary mechanisms never need (their formulas are exact)
clear()
for kind in ("VFOLD", "BOX", "BOXCUT", "MOUTH", "CUBE", "TUBE", "STANDUP", "PLATFORM",
             "RISER", "DOUBLE45", "PYRAMID"):
    add(kind).y = 20.0 + 14.0 * len(st.mechs)
model = build.make_model(sc)[0]
assert not model.__dict__.get("refit"), model.__dict__.get("refit")
uid = host("BOX")
for c, fold in (("VFOLD", "A"), ("CUBE", "B"), ("BOXCUT", "C"), ("VFOLD", "B")):
    add(c, host=uid, fold=fold)
model = build.make_model(sc)[0]
assert not model.__dict__.get("refit"), model.__dict__.get("refit")
print(f"{stood} V-folds, cubes and double 45s stand on stand-ups' folds")

# ---- things fit where they are put
uid = host("PLATFORM")
for c in ("BOX", "VFOLD", "CUBE", "TUBE", "STANDUP"):
    m = add(c, host=uid, fold="A")
    ok, w, _ = built(m.uid)
    assert ok and not [x for x in w if "hangs off" in x], (c, w)
    st.mechs.remove(len(st.mechs) - 1)
for hname in ("QUADS", "ZIGZAG", "VFOLD:ZIGZAG", "VFOLD:M"):
    uid = host(hname)
    m = add("MOUTH", host=uid, fold="V")
    ok, w, _ = built(m.uid)
    assert ok and not w, (hname, w)  # (v0.76: sized as a V-fold, it overlapped and was skipped)
print("things fit on a platform, and a mouth on a zig-zag's or quadrilaterals' crease")

# ---- the warnings name the fold that isn't there
uid = host("BOX")
m = add("VFOLD", host=uid, fold="VAL")
ok, w, _ = built(m.uid)
assert not ok and "has no valley to stand in" in w[0], w
uid = host("strap with peaks")
m = add("BOX", host=uid, fold="C")
ok, w, _ = built(m.uid)
assert not ok and "has no inset fold" in w[0], w
uid = host("angled box")
m = add("CUBE")
ops._put_on(st, m.uid, uid, "A")
ok, w, _ = built(m.uid)
assert not ok and "angled box fold, which nothing stands on" in w[0], w
uid = host("TUBE")
m = add("VFOLD")
ops._put_on(st, m.uid, uid, "A")
mech(m.uid)["wall"] = 0
ok, w, _ = built(m.uid)
assert not ok and "has no roof crease to stand on" in w[0], w
print("warnings say which fold is missing")

addon.unregister()
print("V77 OK")
