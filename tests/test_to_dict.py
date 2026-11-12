"""Guard: every mechanism setting reaches the model. The model only sees what
`PopupMech.to_dict` (props.py) sends for a mechanism's kind, and reads most
settings with a default (`m.get("x", ...)`), so a setting left out of
to_dict for its kind is quietly ignored. Two checks:

1. every property on PopupMech is read somewhere in to_dict, or is listed in
   NOT_SENT below with the reason it needn't be;
2. building each kind of mechanism, with each of its on/off and list
   settings (those to_dict reads for its kind) tried in turn, the model
   never asks a mechanism for a setting that to_dict didn't send for that
   kind (bar INTERNAL below)."""
# families: core
import ast
import collections
import importlib
import os
import pkgutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
import popup_pro as addon  # noqa: E402
from popup_pro import build, props  # noqa: E402
from popup_pro import core  # noqa: E402

# Properties the model doesn't need, and why. A new property goes in to_dict
# (for every kind it applies to), not here, unless it truly never shapes paper.
NOT_SENT = {
    "visibility": "viewport only",
    "selected": "Align's selection",
    "active_line": "which line the panel shows",
    "host": "list for the panel; sets host_uid, fold and side, which are sent",
    "from_tube": "list for the panel; sets from_uid, which is sent",
    "to_tube": "list for the panel; sets to_uid, which is sent",
    "pic_on": "list for the panel; sets host_uid, which is sent",
    "pic_face": "list for the panel; sets face, which is sent",
    "tri_pic_layout": "read when pictures are added to 45 degree triangles (ops)",
    "m_inner": "only read by fit_to_host (props)",
    "cone_lean": "Top Radius as an angle: sets cone_top, which is sent",
    # left from the M-fold before v0.70; nothing reads them
    "m_hinge": "unused", "m_outer": "unused", "m_lean": "unused",
}

# Keys the model looks for that are never settings: only the model's own
# V-folds (roofs, collars, floors) pass them, or they are fixed sizes.
INTERNAL = {
    "VFOLD": {"slot", "flip", "pref"},
    "TETHER": {"foot"},
}

# ---- 1. every property is read in to_dict
src = open(os.path.join(ROOT, "popup_pro", "props.py"), encoding="utf-8").read()
cls = next(n for n in ast.parse(src).body
           if isinstance(n, ast.ClassDef) and n.name == "PopupMech")
declared = [n.target.id for n in cls.body if isinstance(n, ast.AnnAssign)]
to_dict = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "to_dict")
sent = {n.attr for n in ast.walk(to_dict) if isinstance(n, ast.Attribute)
        and isinstance(n.value, ast.Name) and n.value.id == "self"}
assert len(declared) > 100, len(declared)
forgotten = [p for p in declared if p not in sent and p not in NOT_SENT]
assert not forgotten, (
    f"PopupMech.{', PopupMech.'.join(forgotten)}: not read in PopupMech.to_dict, so the "
    "model never sees it. Add it there for each kind it applies to (or, if it never "
    "shapes the paper, to NOT_SENT in this test with the reason).")
stale = [p for p in NOT_SENT if p not in declared or p in sent]
assert not stale, f"NOT_SENT lists {stale}: gone from PopupMech, or sent by to_dict now"
print(f"{len(declared)} properties: {len(declared) - len(NOT_SENT)} read in to_dict, "
      f"{len(NOT_SENT)} listed as not needed")


def self_attrs(nodes):
    return {n.attr for b in nodes for n in ast.walk(b) if isinstance(n, ast.Attribute)
            and isinstance(n.value, ast.Name) and n.value.id == "self"}


# which settings to_dict reads for each kind: its branch of the if/elif on
# self.kind, plus what is read outside it (for every kind)
chain = next(n for n in to_dict.body if isinstance(n, ast.If))
sent_for, node = {}, chain
while True:
    ks = [c.value for c in ast.walk(node.test) if isinstance(c, ast.Constant)]
    for k in ks:
        sent_for[k] = self_attrs(node.body)
    if len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If):
        node = node.orelse[0]
    else:
        for k in ("BOX", "BOXCUT"):  # the final else
            sent_for[k] = self_attrs(node.orelse)
        break
common = self_attrs([n for n in to_dict.body if n is not chain])
assert set(sent_for) == {k[0] for k in props.KINDS}, sorted(sent_for)

# ---- 2. the model asks for nothing to_dict didn't send
asked = collections.defaultdict(set)  # type -> keys looked for and not there


class Watched(dict):
    """A mechanism's dict that notes the keys it is asked for and hasn't got."""
    watch = False

    def _note(self, k):
        if self.watch and not dict.__contains__(self, k):
            asked[dict.get(self, "type")].add(k)

    def get(self, k, default=None):
        self._note(k)
        return dict.get(self, k, default)

    def __contains__(self, k):
        self._note(k)
        return dict.__contains__(self, k)


def watched_dict(*a, **kw):
    # the model copies each mechanism with dict(m): watch those copies, and
    # copies of them with a setting changed, but not the V-folds it makes up
    # itself from a mechanism (dict(m, type="VFOLD", ...))
    d = Watched(*a, **kw)
    if a and "type" not in kw:
        src_ = a[0]
        d.watch = src_.watch if isinstance(src_, Watched) else (
            not kw and type(src_) is dict and "uid" in src_ and "type" in src_)
    return d


# (each model module's own name for dict, for this test only)
for _, name, _ in pkgutil.iter_modules(core.__path__):
    importlib.import_module(f"popup_pro.core.{name}").dict = watched_dict

addon.register()
sc = bpy.context.scene
st = sc.popup
st.live = False


def add(kind, **kw):
    assert bpy.ops.popup.add(kind=kind, **kw) == {"FINISHED"}, kind
    return st.mechs[-1]


def tower(fold):
    t = add("TUBE")
    t.y, t.x, t.depth, t.height = 60.0, 30.0, 40.0, 25.0
    t.front = t.back = 30.0
    m = add("BOX", host=t.uid, fold=fold)
    m.height = m.depth = 18.0
    m.width = 60.0
    return m


def setup(name):
    st.mechs.clear()
    if name in ("FLOOR", "CEILING", "FRAME"):
        add("STAGE")
        return add(name)
    if name == "JACK":
        return add("JACK", host=add("VFOLD").uid)
    if name == "TETHER":
        add("TUBE")
        return add("TETHER")
    if name == "corner tower":
        return tower("KFL")
    if name == "crease tower":
        return tower("KF")
    return add(name)


kinds = [k[0] for k in props.KINDS]
rna = props.PopupMech.bl_rna.properties
built = 0
for name in kinds + ["corner tower", "crease tower"]:
    m = setup(name)
    mine = sent_for[m.kind] | common
    trials = [None]
    for p in rna:
        if p.identifier not in mine or p.identifier == "kind" or p.is_readonly:
            continue
        if p.type == "BOOLEAN":
            trials.append((p.identifier, not getattr(m, p.identifier)))
        elif p.type == "ENUM" and not p.is_enum_flag:
            trials += [(p.identifier, i.identifier) for i in p.enum_items]
    n = 0
    for tr in trials:
        old = getattr(m, tr[0]) if tr else None
        try:
            if tr:
                setattr(m, *tr)
            build.make_model(sc)
            n += 1
        except Exception:  # a combination that can't be built: nothing to learn
            pass
        if tr:
            try:
                setattr(m, tr[0], old)
            except Exception:
                pass
    assert n > len(trials) // 2, (name, n, len(trials))
    built += n

missing = {t: sorted(ks - INTERNAL.get(t, set())) for t, ks in asked.items()
           if ks - INTERNAL.get(t, set())}
assert not missing, (
    f"The model looks for settings to_dict doesn't send: {missing} (model type: keys). "
    "Add each to PopupMech.to_dict for that kind; BOX and BOXCUT share the BOX branch, "
    "and a tower's or collar's settings go in both BOX and CUBE.")
stale = {t: sorted(ks - asked.get(t, set())) for t, ks in INTERNAL.items()
         if ks - asked.get(t, set())}
assert not stale, f"INTERNAL lists keys the model no longer looks for: {stale}"
print(f"{built} models built over {len(kinds) + 2} set-ups: nothing asked for that "
      "to_dict didn't send")

addon.unregister()
print("TO_DICT OK")
