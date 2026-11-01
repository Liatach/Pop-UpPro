"""Align: line selected mechanisms up and space them evenly, along the fold
they share or across the whole card. One undo step, one rebuild."""

import bpy
from bpy.props import EnumProperty

from .core import align as A
from .core.model import Model

PASSES = 4  # measure, move, rebuild the model, measure again
TOL = 0.05  # mm


def chosen(st):
    """Selected mechanisms (and the active one), in list order."""
    act = st.mechs[st.active].uid if 0 <= st.active < len(st.mechs) else None
    return [m for m in st.mechs if m.selected or m.uid == act], act


def _model(st):
    return Model(st.card_dict(), [m.to_dict() for m in st.mechs])


def _host_name(model, host):
    return host.label if host is not None else "its fold"


def plan(st, scope, how, relative):
    """Move the chosen mechanisms. Returns (moved uids, notes). Changes the
    property values only (the caller rebuilds)."""
    mechs, act = chosen(st)
    notes = []
    by_uid = {m.uid: m for m in st.mechs}
    keep = [m for m in mechs if m.kind not in A.FIXED]
    for m in mechs:
        if m.kind in A.FIXED:
            notes.append(f"{m.label}: placed by what it stands in; left where it is")
    model = _model(st)
    dicts = {m.uid: m.to_dict() for m in keep}
    moved = set()

    # ---- what each one is measured on, and where it should go
    if scope == "FOLD":
        groups = {}
        for m in keep:
            if m.kind == "FLAP":
                notes.append(f"{m.label}: a flap isn't on a fold; use Whole Card")
                continue
            h = model.placed.get(m.uid)
            if h is None:
                notes.append(f"{m.label}: not built (see Checks); left where it is")
                continue
            groups.setdefault(id(h), (h, []))[1].append(m.uid)
        jobs = []  # (targets, measure(model, uid) -> (lo, hi), axis: None along the fold)
        for h, uids in groups.values():
            ext = {u: A.fold_extent(model, u) for u in uids}
            ext = {u: e for u, e in ext.items() if e is not None}
            if how != "DISTRIBUTE" and len(ext) < 2 and relative != "HOST":
                continue
            span = A.fold_span(model, h)
            rel = relative
            if rel == "ACTIVE" and act not in ext:
                rel = "SELECTION"  # another fold's: line up among themselves
            if rel == "HOST" and span is None:
                rel = "SELECTION"
            if how == "DISTRIBUTE" and rel != "HOST" and len(ext) < 3:
                notes.append(f"Distribute needs three or more on {_host_name(model, h)} "
                             f"(or Relative To: Fold)")
                continue
            tg = A.targets(ext, how, rel, act, span)
            jobs.append((tg, A.fold_extent, None))
    else:
        axis = "X" if how in ("INNER", "HCENTRE", "OUTER", "DIST_H") else "Y"
        ext, bounds = {}, {}
        for m in keep:
            d = dicts[m.uid]
            if axis == "X" and m.kind != "FLAP":
                if m.uid != act or relative != "ACTIVE":
                    notes.append(f"{m.label}: only flaps move across a page")
                continue
            if axis == "Y" and A.y_sense(model, d) == 0.0:
                notes.append(f"{m.label}: its fold doesn't run up the card; use Along Fold")
                continue
            e = A.card_extent(model, d, axis)
            if e is None:
                notes.append(f"{m.label}: not built (see Checks); left where it is")
                continue
            ext[m.uid] = e
            if axis == "Y":
                bounds[m.uid] = (0.0, model.H)
            else:  # its page, out from the spine
                bounds[m.uid] = (0.0, model.W)
        rel = relative
        if rel == "ACTIVE" and act not in ext:
            rel = "SELECTION"
        if how in ("DIST_H", "DIST_V") and rel != "HOST" and len(ext) < 3:
            notes.append("Distribute needs three or more (or Relative To: Fold / Card)")
            return moved, notes
        if how == "DIST_H" and len({by_uid[u].side for u in ext}) > 1:
            notes.append("Flaps on both pages: each page's are spaced on their own")
            jobs = []
            for side in ("L", "R"):
                e2 = {u: e for u, e in ext.items() if by_uid[u].side == side}
                if e2:
                    jobs.append((A.targets(e2, how, rel, act, bounds),
                                 lambda mdl, u, ax=axis: A.card_extent(
                                     mdl, _dict(st, u), ax), None))
        else:
            jobs = [(A.targets(ext, how, rel, act, bounds),
                     lambda mdl, u, ax=axis: A.card_extent(mdl, _dict(st, u), ax), None)]
        for j, (tg, meas, _) in enumerate(jobs):
            jobs[j] = (tg, meas, axis)

    # ---- move, rebuild the model, measure again (things riding on things
    # that moved, folds that don't move one-for-one)
    for _ in range(PASSES):
        worst = 0.0
        for tg, meas, axis in jobs:
            for u, want in tg.items():
                if u == act and relative == "ACTIVE" and how not in (
                        "DISTRIBUTE", "DIST_H", "DIST_V"):
                    continue
                e = meas(model, u)
                if e is None:
                    continue
                d = want - A.feature(e[0], e[1], how)
                if abs(d) <= TOL:
                    continue
                worst = max(worst, abs(d))
                m = by_uid[u]
                if axis == "X":  # a flap: x is from the spine, out across its page
                    m.x = max(0.0, m.x + d)
                elif axis == "Y":
                    m.y = max(0.0, m.y + d * A.y_sense(model, _dict(st, u)))
                else:
                    m.y = max(0.0, m.y + d)
                moved.add(u)
        if worst <= TOL:
            break
        model = _model(st)

    # ---- tell them what doesn't fit
    for tg, meas, axis in jobs:
        for u in tg:
            m = by_uid[u]
            e = meas(model, u)
            if e is None:
                continue
            if abs(A.feature(e[0], e[1], how) - tg[u]) > 0.5:
                notes.append(f"{m.label}: couldn't go all the way (it can't go below 0)")
            if axis is None:
                h = model.placed.get(u)
                span = A.fold_span(model, h) if h is not None else None
                if span and (e[0] < span[0] - 0.5 or e[1] > span[1] + 0.5):
                    notes.append(f"{m.label}: runs off {_host_name(model, h)}")
            elif axis == "Y" and (e[0] < -0.5 or e[1] > model.H + 0.5):
                notes.append(f"{m.label}: runs off the card")
            elif axis == "X":
                if e[0] < -0.5 or e[1] > model.W + 0.5:
                    notes.append(f"{m.label}: runs off its page")
    return moved, notes


def _dict(st, uid):
    return next(m for m in st.mechs if m.uid == uid).to_dict()


HOW = [
    ("START", "Start", "Line up their starts (the end of the fold they're measured from)",
     "ALIGN_LEFT", 0),
    ("CENTRE", "Centre", "Line up their middles along the fold", "ALIGN_CENTER", 1),
    ("END", "End", "Line up their ends", "ALIGN_RIGHT", 2),
    ("DISTRIBUTE", "Distribute", "Space them evenly along the fold: equal gaps between "
     "the outermost two, or along the whole fold (Relative To: Fold)", "ALIGN_JUSTIFY", 3),
    ("INNER", "Spine Side", "Line up flaps' edges nearest the spine (measured out from "
     "the spine, so flaps on opposite pages mirror each other)", "ANCHOR_LEFT", 4),
    ("HCENTRE", "Centre Across", "Line up flaps' middles, out from the spine",
     "ANCHOR_CENTER", 5),
    ("OUTER", "Edge Side", "Line up flaps' edges nearest the card's side edge",
     "ANCHOR_RIGHT", 6),
    ("BOTTOM", "Bottom", "Line up their bottoms (towards the card's bottom edge)",
     "ANCHOR_BOTTOM", 7),
    ("VCENTRE", "Middle", "Line up their middles up the card", "ALIGN_MIDDLE", 8),
    ("TOP", "Top", "Line up their tops", "ANCHOR_TOP", 9),
    ("DIST_H", "Distribute Across", "Space flaps evenly across their page (each page's "
     "on their own)", "ALIGN_JUSTIFY", 10),
    ("DIST_V", "Distribute Up", "Space them evenly up the card", "ALIGN_JUSTIFY", 11),
]


class POPUP_OT_align(bpy.types.Operator):
    """Line the selected mechanisms up with the active one, or space them
    evenly, along their fold or across the card"""
    bl_idname = "popup.align"
    bl_label = "Align Mechanisms"
    bl_options = {"REGISTER", "UNDO"}
    how: EnumProperty(name="How", items=HOW)
    scope: EnumProperty(name="Along", items=[
        ("FOLD", "Along Fold", ""), ("CARD", "Whole Card", "")])
    relative: EnumProperty(name="Relative To", items=[
        ("ACTIVE", "Active", ""), ("SELECTION", "Selection", ""),
        ("HOST", "Fold / Card", "")])

    @classmethod
    def poll(cls, context):
        st = context.scene.popup
        return 0 <= st.active < len(st.mechs)

    def invoke(self, context, event):
        st = context.scene.popup
        self.scope, self.relative = st.align_scope, st.align_to
        return self.execute(context)

    def execute(self, context):
        sc = context.scene
        st = sc.popup
        fold_how = self.how in A.FOLD_HOW
        if fold_how != (self.scope == "FOLD"):
            self.scope = "FOLD" if fold_how else "CARD"
        was = st.live
        st["live"] = False  # one rebuild, at the end
        try:
            moved, notes = plan(st, self.scope, self.how, self.relative)
        finally:
            st["live"] = was
        for n in notes:
            self.report({"WARNING"}, n)
        if moved and st.rig is not None:
            from .ops import _rebuild
            _rebuild(self, context, force=not st.edited)
        if not moved and not notes:
            self.report({"INFO"}, "Already lined up")
        return {"FINISHED"}


class POPUP_OT_select_mechs(bpy.types.Operator):
    """Pick mechanisms to align"""
    bl_idname = "popup.select_mechs"
    bl_label = "Select Mechanisms"
    bl_options = {"REGISTER", "UNDO"}
    action: EnumProperty(items=[
        ("FOLD", "Same Fold", "Everything on the active mechanism's fold"),
        ("ALL", "All", "Every mechanism"),
        ("NONE", "None", "Clear the selection (the active one stays the reference)"),
        ("INVERT", "Invert", "")])

    def execute(self, context):
        st = context.scene.popup
        if self.action == "FOLD":
            if not 0 <= st.active < len(st.mechs):
                return {"CANCELLED"}
            model = _model(st)
            h = model.placed.get(st.mechs[st.active].uid)
            for m in st.mechs:
                m.selected = h is not None and model.placed.get(m.uid) is h and \
                    m.kind not in A.FIXED and m.kind != "FLAP"
        else:
            for m in st.mechs:
                m.selected = {"ALL": True, "NONE": False}.get(self.action, not m.selected)
        return {"FINISHED"}


classes = (POPUP_OT_align, POPUP_OT_select_mechs)


def register():
    for c in classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
