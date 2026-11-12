"""The panels and the Add menu draw without error for every kind of
mechanism, with each on/off and list setting tried in turn. They are drawn
onto a stand-in layout that notes every call, so this runs without a window
and can check what was offered: every kind's panel shows its settings, the
Add menu offers every kind, and every Add it offers works."""
# families: ui
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
import popup_pro as addon  # noqa: E402
from popup_pro import build, props, ui  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ui_stub import adds_offered, draw, props_shown  # noqa: E402

addon.register()
sc = bpy.context.scene
st = sc.popup
st.live = False


def add(kind, **kw):
    assert bpy.ops.popup.add(kind=kind, **kw) == {"FINISHED"}, (kind, kw)
    return st.mechs[-1]


def select(m):
    st.active = next(i for i, x in enumerate(st.mechs) if x.uid == m.uid)


def tower(fold):
    t = add("TUBE")
    t.y, t.x, t.depth, t.height = 60.0, 30.0, 40.0, 25.0
    t.front = t.back = 30.0
    m = add("BOX", host=t.uid, fold=fold)
    m.height = m.depth = 18.0
    m.width = 60.0
    return m


def setup(name):
    """A card with this on it, selected (the same ids every time)."""
    st.mechs.clear()
    st["pop_next_uid"] = 1
    if name in ("FLOOR", "CEILING", "FRAME"):
        add("STAGE")
        m = add(name)
    elif name == "STAGE":
        add("STAGE")
        m = st.mechs[0]
    elif name == "JACK":
        m = add("JACK", host=add("VFOLD").uid)
    elif name == "TETHER":
        add("TUBE")
        m = add("TETHER")
    elif name == "tower":
        m = tower("KFL")
    elif name == "castle":
        add("TUBE", variant="CASTLE")
        m = st.mechs[st.active]
    elif name == "strap with peaks":
        m = add("BOX")
        m.peaks = 3
    elif name == "box on a floor":
        add("STAGE")
        m = add("BOX", host=add("FLOOR").uid, side="L")
    else:
        m = add(name)
    select(m)
    return m


kinds = [k[0] for k in props.KINDS]
others = [c for c in ui.classes if hasattr(c, "draw") and "_UL_" not in c.__name__
          and c not in (ui.POPUP_PT_mechs, ui.POPUP_MT_add)]
rna = props.PopupMech.bl_rna.properties

# ---- nothing on the card
st.mechs.clear()
basics = adds_offered(draw(ui.POPUP_MT_add))
offered = {a["kind"] for a in basics}
# (floors and ceilings are offered with a stage to put them in; zig-zags are a V-fold shape)
assert offered == set(kinds) - {"FLOOR", "CEILING", "ZIGZAG"}, sorted(set(kinds) - offered)
assert "kind" not in props_shown(draw(ui.POPUP_PT_mechs))
for c in others:
    draw(c)
print(f"empty card: the Add menu offers {len(offered)} kinds")

# ---- every kind selected: its panel, with each setting tried, and the menu
draws = 0
for name in kinds + ["tower", "castle", "strap with peaks", "box on a floor"]:
    m = setup(name)
    shown = props_shown(draw(ui.POPUP_PT_mechs))
    assert shown[0] == "highlight" and "kind" in shown and len(shown) >= 5, (name, shown)
    trials = []
    for p in rna:
        if p.is_readonly or p.identifier in ("kind", "rna_type", "name"):
            continue
        if p.type == "BOOLEAN":
            trials.append((p.identifier, not getattr(m, p.identifier)))
        elif p.type == "ENUM" and not p.is_enum_flag:
            trials += [(p.identifier, i.identifier) for i in p.enum_items]
    for ident, value in trials:
        old = getattr(m, ident)
        try:
            setattr(m, ident, value)
        except (TypeError, ValueError):  # (a list that has no such choice just now)
            continue
        draw(ui.POPUP_PT_mechs)
        draws += 1
        setattr(m, ident, old)
    menu = adds_offered(draw(ui.POPUP_MT_add))
    assert menu[:len(basics)] == basics, name  # (the basics first, always)
    for c in others:
        draw(c)
print(f"{draws} panels drawn over {len(kinds) + 4} set-ups")

# ---- every Add the menu offers, with each kind selected, works
made = 0
# (a ceiling, not a floor: in a card the stage stands on the card, which is its floor)
for name in ["VFOLD", "BOX", "BOXCUT", "CUBE", "TUBE", "STANDUP", "STAGE", "CEILING", "QUADS",
             "castle", "strap with peaks"]:
    setup(name)
    extra = adds_offered(draw(ui.POPUP_MT_add))[len(basics):]
    assert extra, name  # (something goes on each of these)
    for kw in extra:
        h = setup(name)
        n = len(st.mechs)
        assert kw["host"] == h.uid, (name, kw)
        assert bpy.ops.popup.add(**kw) == {"FINISHED"}, (name, kw)
        new = list(st.mechs)[n:]
        # it stands on what was selected, and the model doesn't skip it
        assert new and any(x.host_uid == kw["host"] for x in new), (name, kw)
        skipped = [w for w in build.make_model(sc)[0].warnings if "skipped" in w
                   and any(w.startswith(x.label) or x.label + ":" in w for x in new)]
        assert not skipped, (name, kw, skipped)
        draw(ui.POPUP_PT_mechs)
        made += 1
st.mechs.clear()
for kw in basics:
    st.mechs.clear()
    assert bpy.ops.popup.add(**kw) == {"FINISHED"}, kw
    draw(ui.POPUP_PT_mechs)
    made += 1
print(f"{made} Adds from the menu made and drawn")

addon.unregister()
print("UI DRAW OK")
