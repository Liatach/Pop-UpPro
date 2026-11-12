import json
import math

import bpy
from bpy.props import EnumProperty, FloatProperty, IntProperty, StringProperty, BoolProperty
from bpy_extras.io_utils import ExportHelper
from mathutils import Quaternion, Vector

from .naming import N
from . import art, build, live


def _scene_ok(context):
    return context.scene is not None


def _rebuild(op, context, force=True):
    try:
        build.rebuild(context.scene, force=force)
    except Exception as ex:
        op.report({"ERROR"}, f"Rebuild failed: {ex}")
        return False
    for w in context.scene.popup.warnings.splitlines():
        op.report({"WARNING"}, w)
    return True


class POPUP_OT_build(bpy.types.Operator):
    """Build (or rebuild) the card, rig and print layout from the settings.
    Resets hand-edited panel shapes"""
    bl_idname = "popup.build"
    bl_label = "Build Card"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        st = context.scene.popup
        first = st.rig is None
        if first and not st.mechs:
            _add(st, "CUBE")  # something to play with: it's Blender after all
        if not _rebuild(self, context):
            return {"CANCELLED"}
        if first:
            st.card.select_set(True)
            context.view_layer.objects.active = st.rig
            _first_setup(context)
        return {"FINISHED"}


def _first_setup(context):
    """The first card (or carousel) in a file sets the scene up for pop-up
    work once; Set Up Scene does it again on demand."""
    from . import scene_setup
    sc = context.scene
    master = sc.popup.stage_master or sc
    if not master.get("pop_setup_done"):
        try:
            scene_setup.setup(context, view_camera=True)
        except (RuntimeError, TypeError, AttributeError, KeyError):
            pass
        # a movement test ready to play: press Play or scrub the timeline
        try:
            bpy.ops.popup.animate(mode="CYCLE")
        except RuntimeError:
            pass


DEFAULTS = {
    "VFOLD": dict(y=70.0, height=50.0, glue=40.0, phi_l=60.0, alpha_l=80.0, tab=12.0),
    "BOX": dict(y=130.0, width=50.0, height=40.0, depth=30.0, tab=12.0),
    "BOXCUT": dict(y=20.0, width=40.0, height=30.0, depth=30.0),
    "MOUTH": dict(y=150.0, jaw=30.0, upper=20.0, lower=15.0),
    "CUBE": dict(y=60.0, size=40.0, height=40.0, tab=10.0),
    "FLAP": dict(y=170.0, x=50.0, width=40.0, length=35.0, tab=8.0),
    "TUBE": dict(y=80.0, x=25.0, depth=40.0, height=50.0, front=30.0, back=30.0, tab=10.0),
    "TETHER": dict(height=30.0, tab=8.0, to_y=40.0),
    "PYRAMID": dict(y=80.0, x=25.0, depth=50.0, height=40.0, ridge=0.0, front=25.0,
                    back=25.0, tab=10.0),
    "FRAME": dict(y=0.0, tab=8.0),
    "STAGE": dict(y=80.0, phi_l=60.0, glue=60.0, height=80.0, tab=10.0, tab_side="OUT"),
    "FLOOR": dict(tab=8.0),
    "CEILING": dict(tab=8.0),
    "STANDUP": dict(y=60.0, width=30.0, height=45.0, depth=30.0, img_w=80.0, img_h=90.0,
                    tab=10.0),
    "PLATFORM": dict(y=70.0, width=60.0, height=35.0, depth=30.0, tab=10.0,
                     brace_size=15.0),
    "RISER": dict(y=60.0, width=70.0, height=80.0, tab=12.0, brace_size=20.0),
    "DOUBLE45": dict(y=105.0, width=30.0, height=45.0, depth=104.0, tab=10.0),
    "JACK": dict(y=30.0, width=60.0, height=25.0, depth=25.0, tab=10.0),
    "ZIGZAG": dict(y=80.0, phi_l=120.0, x=20.0, width=25.0, height=50.0, faces="30", tab=10.0),
    "QUADS": dict(y=70.0, phi_l=120.0, x=20.0, width=25.0, height=50.0, faces="16, 16",
                  q_side=25.0, q_front=40.0, tab=8.0),
    "PICTURE": dict(img_w=30.0, img_h=40.0),
    "ROOF": dict(phi_l=100.0, alpha_l=70.0, glue=150.0, height=60.0, tab=8.0,
                 tab_side="IN"),
}
NAMES = {"VFOLD": "V-fold", "BOX": "Box fold", "BOXCUT": "Box layer", "MOUTH": "Mouth",
         "CUBE": "Cube", "FLAP": "Flap", "TUBE": "Tube", "TETHER": "Tether",
         "PYRAMID": "Pyramid", "FRAME": "Frame", "FLOOR": "Floor", "CEILING": "Ceiling",
         "STAGE": "Stage set", "STANDUP": "Stand-up", "ROOF": "Roof",
         "PLATFORM": "Platform", "RISER": "Rising sheet", "DOUBLE45": "Double 45",
         "JACK": "Jack in the box", "PICTURE": "Picture", "ZIGZAG": "Zig-zag",
         "QUADS": "Quadrilaterals"}


def unique_label(items, base, skip=None):
    """The next free "<base> N": numbers are never reused while any name in
    use carries them, and keep counting up past the highest."""
    import re
    pat = re.compile(re.escape(base) + r" (\d+)")
    nums = [int(mt.group(1)) for x in items if x != skip
            for mt in [pat.fullmatch(x.label)] if mt]
    return f"{base} {max(nums, default=0) + 1}"


def _add(st, kind):
    # never reuse an id: sketch layers and art tiles are keyed by it
    uid = max([m.uid + 1 for m in st.mechs] + [st.get("pop_next_uid", 1)])
    st["pop_next_uid"] = uid + 1
    was_live = st.live
    st["live"] = False  # no rebuild per property
    m = st.mechs.add()
    m.uid = uid
    m.kind = kind
    n = sum(1 for x in st.mechs if x.kind == kind)
    m.label = unique_label(st.mechs, NAMES[kind], m)
    H = st.card_dict()["H"]
    for k, v in DEFAULTS[kind].items():
        setattr(m, k, v)
    m.y = min(m.y, max(0.0, H - (m.width if kind in ("BOX", "BOXCUT", "STANDUP") else 0.0) - 10))
    W = st.card_dict()["W"]
    if kind == "FRAME":  # first frame stands at the front of the stage, the rest behind
        n = sum(1 for x in st.mechs if x.kind == "FRAME")
        m.label = "Staging frame" if n == 1 else f"Frame {n - 1}"
        m.x = W - 1.0 if n == 1 else max(10.0, W * (1.0 - 0.25 * (n - 1)))
        m.y, m.height = 0.0, H
    if kind in ("FLOOR", "CEILING"):
        m.depth = W
    if kind == "CUBE":
        m.y = min(m.y, max(0.0, H - m.size * 1.42 - 5))
    if kind == "ROOF":
        m.y = round(0.7 * H, 1)
        # the eaves to the card's side edge
        m.glue = round(W / math.sin(math.radians(m.phi_l)) - 0.5, 1)
    if kind == "FLAP":
        m.y = min(m.y, max(m.tab + m.length, H - 15))
    if kind == "TETHER":
        tubes = [x for x in st.mechs if x.kind == "TUBE"]
        if tubes:  # join the selected (or last) tube's front left corner to a foot
            t = tubes[-1]
            m.from_uid = t.uid
            m.from_pt = "FL"
            m.to = "LEFT"
            m.to_y = max(5.0, t.y - 30.0)
            m.height = 0.6 * t.height
    st["live"] = was_live
    st.active = len(st.mechs) - 1
    return m


class POPUP_OT_add(bpy.types.Operator):
    """Add a pop-up mechanism"""
    bl_idname = "popup.add"
    bl_label = "Add Mechanism"
    bl_options = {"REGISTER", "UNDO"}
    kind: EnumProperty(items=[(k, NAMES[k], "") for k in NAMES])
    # (never remembered between uses: a plain Add after Add Castle, or after
    # adding onto a host, must not come out a castle or on that host)
    host: IntProperty(default=0, description="Mechanism id of the host box (0 = spine)",
                      options={"SKIP_SAVE"})
    fold: StringProperty(default="A", options={"SKIP_SAVE"})
    side: StringProperty(default="", description="Wall, for a corner of a floor or ceiling",
                         options={"SKIP_SAVE"})
    variant: StringProperty(default="", description="ASYM: an asymmetric V-fold; "
                           "VALLEY: a roof upside down; STRAP: a box fold with equal sides "
                           "(gullies off the centre); ANGLED: a box fold with angled glue "
                           "lines; CASTLE: a tube with towers; LOOP: a ring on two tabs; TOWERS: "
                           "a tower in every inside corner of a tube; TOP: a V-fold at the top of a "
                           "V-fold's crease",
                           options={"SKIP_SAVE"})

    def execute(self, context):
        st = context.scene.popup
        if self.host and not any(x.uid == self.host for x in st.mechs):
            self.host = 0  # (a host that's gone: on the card, not skipped)
        if self.kind in ("FRAME", "FLOOR", "CEILING") and not self.pick_stage(st):
            return {"CANCELLED"}
        # (by uid: adding to the list can move its items in memory)
        was_active = st.mechs[st.active].uid if 0 <= st.active < len(st.mechs) else None
        m = _add(st, self.kind)
        uid = m.uid
        if self.kind == "FRAME" and not self.host and st.stage_master is None:
            _as_card_frame(st, m)
        if self.kind == "VFOLD" and self.variant == "ASYM":
            _as_asymmetric(st, m)
        if self.kind == "BOX" and self.variant == "STRAP":
            _as_strap(st, m)
        if self.kind == "ROOF" and self.variant == "VALLEY":
            _as_valley(st, m)
        if self.kind == "BOX" and self.variant == "TOWERS" and self.host:
            # a tower up every inside corner of the tube (the castle's corners)
            _remove_new(st, uid)
            corners = tube_corners(st, self.host)
            if not corners:
                self.report({"ERROR"}, "This tube has no inside corners (its ends are round)")
                return {"CANCELLED"}
            for fold in corners:
                _tower(st, self.host, fold)
            return self.done(context, st)
        if self.kind == "PICTURE":
            _place_picture(st, m, self.host, self.side, was_active)
            return self.done(context, st, uid)
        if self.kind == "JACK" and not self.host:
            _place_jack(st, uid, was_active)
            return self.done(context, st, uid)
        if self.kind == "BOX" and self.variant == "ANGLED" and not self.host:
            _as_angled(st, m)
        if self.kind == "TUBE" and self.variant == "LOOP":
            _as_loop(st, m)
        if self.kind == "TUBE" and self.variant == "CASTLE":
            _as_castle(st, m)
            for fold in ("KFL", "KFR", "KBR", "KBL"):
                _tower(st, uid, fold)
            return self.done(context, st, uid)
        if self.host and self.kind != "PICTURE":
            if self.side:
                next(x for x in st.mechs if x.uid == uid)["side"] = 1 if self.side == "L" else 0
            _put_on(st, uid, self.host, self.fold)
        if self.kind == "BOX" and self.variant == "BALCONIES" and self.host:
            _remove_new(st, uid)
            new = _side_balconies(st, self.host)
            return self.done(context, st, new[0])
        if self.kind == "BOX" and self.variant == "TOWER_BALCONIES" and self.host:
            _remove_new(st, uid)
            new = _tower_balconies(st, self.host)
            if not new:
                self.report({"ERROR"}, "No towers in this tube's corners")
                return {"CANCELLED"}
            return self.done(context, st, new[0])
        if self.kind == "BOX" and self.variant == "BALCONY" and self.host:
            _balcony(st, uid, self.host)
        if self.kind == "VFOLD" and self.variant == "TOP" and self.host:
            _as_top(st, uid, self.host)
        if self.kind == "STAGE":  # a staging frame at the front, one frame behind
            for _ in range(2):
                _put_on(st, _add(st, "FRAME").uid, uid, "A")
            st.active = next(i for i, x in enumerate(st.mechs) if x.uid == uid)
        return self.done(context, st)

    def pick_stage(self, st):
        """A frame, floor or ceiling goes in a stage: the selected one, or the
        last made (a frame with no stage about goes across the card's own
        fold). False, with the reason reported, if it can't be added."""
        if st.stage_master is None and not self.host:
            stages = [x for x in st.mechs if x.kind == "STAGE"]
            act = st.mechs[st.active] if st.active < len(st.mechs) else None
            in_stage = act is not None and (act.kind == "STAGE" or any(
                x.uid == act.host_uid for x in stages))
            if self.kind == "FRAME" and not in_stage:
                stages = []  # a frame across the card's own fold
            elif not stages:
                self.report({"ERROR"}, "Add a Stage Set first (or make a carousel)")
                return False
        if st.stage_master is None and not self.host and stages:
            act = st.mechs[st.active] if st.active < len(st.mechs) else None
            if act is not None and act.kind == "STAGE":
                self.host = act.uid
            elif act is not None and act.host_uid and any(x.uid == act.host_uid
                                                           for x in stages):
                self.host = act.host_uid
            else:
                self.host = stages[-1].uid
        same = [x for x in st.mechs if x.kind == self.kind and x.host_uid == self.host]
        if self.kind == "FRAME" and len(same) >= 4:
            self.report({"ERROR"}, "A stage has a staging frame and up to three frames")
            return False
        if self.kind in ("FLOOR", "CEILING") and same:
            self.report({"ERROR"}, f"This stage already has a {self.kind.lower()}")
            return False
        return True

    def done(self, context, st, active=None):
        """Select the mechanism with this id (if one is given), rebuild, finish."""
        if active is not None:
            st.active = next(i for i, x in enumerate(st.mechs) if x.uid == active)
        _rebuild(self, context, force=st.rig is not None and not st.edited)
        return {"FINISHED"}


def _as_card_frame(st, m):
    """A frame across the card's own fold: a layer that pulls flat as it opens."""
    was = st.live
    st["live"] = False
    W_, H_ = st.card_dict()["W"], st.card_dict()["H"]
    m.label = unique_label(st.mechs, "Frame", m)
    n_ = sum(1 for x in st.mechs if x.kind == "FRAME" and not x.host_uid)
    m.x = round(0.7 * W_ * (1.0 - 0.25 * (n_ - 1)), 1)  # (each one further in)
    m.y, m.height = round(0.1 * H_, 1), round(0.75 * H_, 1)
    st["live"] = was


def _as_asymmetric(st, m):
    """An asymmetric V-fold that folds flat."""
    was = st.live
    st["live"] = False
    m.symmetric = False
    m.phi_l, m.phi_r, m.lean, m.fold_flat = 40.0, 75.0, 20.0, True
    m.glue_r = m.glue
    m.label = unique_label(st.mechs, "Asymmetric V-fold", m)
    st["live"] = was


def _as_strap(st, m):
    """A strap: a box fold with equal sides, its glue folds gullies off the centre."""
    # Pop-Up Tutorial 9: a glued box fold with equal sides lies flat
    # when the card is open; its two glue folds are gullies away from
    # the spine that open just like it, for pop-ups off the centre
    was = st.live
    st["live"] = False
    H = st.card_dict()["H"]
    m.height = m.depth = 35.0
    m.width = 70.0
    m.y = round(0.5 * H - 35.0, 1)
    m["strap"] = True
    m.label = unique_label(st.mechs, "Strap", m)
    st["live"] = was


def _as_valley(st, m):
    """A roof upside down: a valley floor."""
    was = st.live
    st["live"] = False
    m.valley = True
    m.y = round(0.3 * st.card_dict()["H"], 1)
    m.label = unique_label(st.mechs, "Valley floor", m)
    st["live"] = was


def _as_angled(st, m):
    """A box fold with angled glue lines."""
    was = st.live
    st["live"] = False
    m.fan_angle = 20.0
    m.label = unique_label(st.mechs, "Angled box fold", m)
    st["live"] = was


def _as_loop(st, m):
    """A loop: a ring on two tabs."""
    # Birmingham 16: a band curving round both ways from two short flat
    # sides glued down on tabs, the tabs' distance out setting its size
    was = st.live
    st["live"] = False
    m.x, m.depth, m.height, m.tab = 25.0, 14.0, 20.0, 8.0
    m.front_style = m.back_style = "ROUND"
    m.label = unique_label(st.mechs, "Loop", m)
    st["live"] = was


def _as_castle(st, m):
    """A castle's walls (its towers are added after)."""
    # Birmingham's parallel castle: a box-shaped tube (front and back as
    # wide as the strips are apart) with a roofed tower in each corner
    was = st.live
    st["live"] = False
    H = st.card_dict()["H"]
    # (one strip round all six walls: kept within an A4 sheet)
    m.x = m.front = m.back = 34.0
    m.depth, m.height, m.roof = 64.0, 40.0, "NONE"
    m.y = round(0.5 * H - 32.0, 1)
    m.label = unique_label(st.mechs, "Castle", m)
    st["live"] = was


def _as_top(st, uid, host):
    """A V-fold on top of the V-fold it stands on."""
    # Birmingham 21-22: stuck on top of the V-fold it stands on, whose
    # top is cut to a point and whose own tabs (A) stick under it
    h = next(x for x in st.mechs if x.uid == host)
    was = st.live
    st["live"] = False
    m = next(x for x in st.mechs if x.uid == uid)
    m.on_top = True
    m.y = round(h.height, 1)
    m.top_angle = m.top_angle_r = 50.0
    m.top_piece = m.top_piece_r = 70.0
    # small enough to fold away inside the lifting piece's height
    m.glue = m.height = round(max(10.0, 0.4 * h.height), 1)
    m.tab = min(h.tab, round(0.3 * m.glue, 1))
    st["live"] = was


def _place_picture(st, m, host, side, was_active):
    """Glue a new picture on a face: the one asked for, or the first face of
    the mechanism that was selected, or the right page."""
    from .props import pic_faces
    act = next((x for x in st.mechs if x.uid == was_active and x.uid != m.uid
                and x.kind != "PICTURE"), None)
    on = host or (act.uid if act is not None else 0)
    was = st.live
    st["live"] = False
    m.host_uid = on
    faces = pic_faces(st, on)
    if side:
        m.face = side
    elif faces:
        m.face = faces[0][0] if on else "Page.R"
    else:
        m.face = "Page.R"
    if not on:
        m.pic_x, m.pic_y = 0.0, 20.0
    st["live"] = was


def _place_jack(st, uid, was_active):
    """Stand a new jack in the box on the selected V-fold's crease, or
    (Birmingham 79) on a new V-fold made for its body."""
    act = next((x for x in st.mechs if x.uid == was_active), None)
    if act is not None and act.kind == "VFOLD" and not any(
            x.kind == "JACK" and x.host_uid == act.uid for x in st.mechs):
        _put_on(st, uid, act.uid, "V")
        return
    was = st.live
    st["live"] = False
    vf = _add(st, "VFOLD")
    vf.phi_l, vf.alpha_l, vf.glue, vf.height = 60.0, 90.0, 40.0, 60.0
    vf.y = round(0.4 * st.card_dict()["H"], 1)
    vf.label = unique_label(st.mechs, "Jack's body", vf)
    st["live"] = was
    _put_on(st, uid, vf.uid, "V")


def _side_balconies(st, host):
    """A balcony on each side wall of a tube or cube; their ids."""
    new = []
    for fold in ("WL", "WR"):
        m = _add(st, "BOX")
        _put_on(st, m.uid, host, fold)
        _balcony(st, m.uid, host)
        new.append(m.uid)
    return new


def _tower_balconies(st, host):
    """A balcony on the side wall outside each corner tower; their ids."""
    # (by value: adding to the list moves its items in memory)
    h = next(x for x in st.mechs if x.uid == host)
    hd, hh = h.depth, h.height
    towers = [(max(x.height, x.depth), x.wall, x.label) for x in st.mechs
              if x.kind == "BOX" and x.host_uid == host and
              x.wall in ("KFL", "KFR", "KBR", "KBL")]  # (by a side wall)
    new = []
    for size, wall, tlab in towers:
        span = min(size, hd)
        side = "WL" if wall in ("KFL", "KBL") else "WR"
        # (the left wall's foot runs back to front, the right's front to back)
        at_start = wall in ("KBL", "KFR")
        nu = _add(st, "BOX").uid
        _put_on(st, nu, host, side)
        _balcony(st, nu, host)
        m = next(x for x in st.mechs if x.uid == nu)
        was = st.live
        st["live"] = False
        m.width = round(span, 1)
        m.y = 0.0 if at_start else round(hd - span, 1)
        m.height = round(hh, 1)
        m.rail = round(min(12.0, 0.3 * hh), 1)
        m.bays = max(1, min(6, int(span // 12)))
        m.label = f"{tlab} balcony"
        st["live"] = was
        new.append(nu)
    return new


def _remove_new(st, uid):
    i = next(i for i, x in enumerate(st.mechs) if x.uid == uid)
    st.mechs.remove(i)


def tube_corners(st, host):
    """A tube's inside corners a tower can stand in: where the sides meet the
    front and the back (unless that end is round), and its front and back
    creases when they point out."""
    h = next(x for x in st.mechs if x.uid == host)
    out = []
    if h.front_style != "ROUND":  # (a round end has no corners)
        out += ["KFL", "KFR"]
    if h.back_style != "ROUND":
        out += ["KBR", "KBL"]
    if h.front_style == "OUT" and h.front > h.x + 0.5:
        out.append("KF")
    if h.back_style == "OUT" and h.back > h.x + 0.5:
        out.append("KB")
    return out


def _tower(st, host, fold):
    """A roofed tower (a glued box fold) up one inside corner of a tube."""
    t = _add(st, "BOX")
    uid = t.uid
    _put_on(st, uid, host, fold)
    was = st.live
    st["live"] = False
    t = next(x for x in st.mechs if x.uid == uid)
    where = {"KFL": "front left", "KFR": "front right", "KBR": "back right",
             "KBL": "back left", "KF": "front", "KB": "back"}[fold]
    h = next(x for x in st.mechs if x.uid == host)
    t.label = f"{h.label}: {where} tower"
    t.roof = "POINTED"
    t.roof_height = round(0.9 * t.height, 1)
    st["live"] = was
    return uid


def _balcony(st, uid, host):
    """A box fold made a balcony: its top the floor, part way up the wall
    (or box front) it stands against, a railing round its front."""
    was = st.live
    st["live"] = False
    try:
        m = next(x for x in st.mechs if x.uid == uid)
        h = next((x for x in st.mechs if x.uid == host), None)
        tall = h.height if h is not None else 2.0 * m.height
        if h is not None and h.kind in ("BOX", "BOXCUT", "STANDUP") and m.fold == "B":
            tall = h.height  # (up the box's front)
        m.height = round(max(8.0, 0.55 * tall), 1)
        m.depth = round(max(8.0, min(0.35 * tall, 20.0)), 1)
        if h is not None and h.kind == "TUBE":
            m.width = round(0.8 * h.depth, 1)
            m.y = round(0.1 * h.depth, 1)
        m.rail = round(min(12.0, 0.4 * m.height), 1)
        m.support = "ARCHES"
        m.bays = max(1, min(6, int(m.width // 12)))
        m.rail_open = m.rail >= 8.0
        m.tab = min(m.tab, round(0.8 * min(m.height, m.depth), 1))
        m.label = unique_label(st.mechs, "Balcony", m)
    finally:
        st["live"] = was


def _put_on(st, uid, host, fold="A"):
    """Stand a new mechanism on a host and size it to fit."""
    from .props import fit_to_host
    was = st.live
    st["live"] = False
    m = next(x for x in st.mechs if x.uid == uid)
    m.host_uid = host
    if fold in ("FL", "BL", "FR", "BR", "V"):  # on a V-fold: a half, or its crease
        m["vside"] = ("FL", "BL", "FR", "BR", "V").index(fold)
        m["on_crease"] = fold == "V"  # (a floor's or ceiling's crease)
    elif fold in ("WL", "WR"):  # outside a cube's or tube's wall
        m["wall"] = 1 if fold == "WL" else 2
    elif fold in ("KFL", "KFR", "KBR", "KBL", "KF", "KB"):  # up a tube's inside corner
        m["wall"] = 3 + ("KFL", "KFR", "KBR", "KBL", "KF", "KB").index(fold)
    elif fold == "VAL":  # a strap's valley between two peaks
        m["fold"] = 3
    else:
        m["fold"] = {"A": 0, "B": 1, "C": 2}.get(fold, 0)
    fit_to_host(m, st)
    h = next((x for x in st.mechs if x.uid == host), None)
    if m.kind == "FRAME" and h is not None and h.kind == "STAGE":
        n = sum(1 for x in st.mechs if x.kind == "FRAME" and x.host_uid == host)
        m.label = f"{h.label}: staging frame" if n == 1 else f"{h.label}: frame {n - 1}"
    st["live"] = was


class POPUP_OT_remove(bpy.types.Operator):
    """Remove the selected mechanism"""
    bl_idname = "popup.remove"
    bl_label = "Remove Mechanism"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return len(context.scene.popup.mechs) > 0

    def execute(self, context):
        st = context.scene.popup
        st.mechs.remove(st.active)
        st.active = max(0, min(st.active, len(st.mechs) - 1))
        if st.rig is not None:
            _rebuild(self, context)
        return {"FINISHED"}


def _copy_props(src, dst, skip=()):
    """Copy a property group's stored values."""
    for k in src.keys():
        if k in skip:
            continue
        v = src[k]
        if hasattr(v, "to_dict"):
            v = v.to_dict()
        elif hasattr(v, "to_list"):
            v = v.to_list()
        elif isinstance(v, list):
            v = [x.to_dict() if hasattr(x, "to_dict") else x for x in v]
        try:
            dst[k] = v
        except (TypeError, ValueError, KeyError):
            pass


class POPUP_OT_duplicate(bpy.types.Operator):
    """Duplicate the selected mechanism, with its settings, creases, cuts and
    openings, a little further along"""
    bl_idname = "popup.duplicate"
    bl_label = "Duplicate Mechanism"
    bl_options = {"REGISTER", "UNDO"}
    offset: FloatProperty(name="Move Along", default=15.0, soft_min=-200.0, soft_max=200.0,
                          description="How far along its fold the copy goes (mm)")

    @classmethod
    def poll(cls, context):
        st = context.scene.popup
        return 0 <= st.active < len(st.mechs)

    def execute(self, context):
        import re
        st = context.scene.popup
        i_src = st.active
        src = st.mechs[i_src]
        was = st.live
        st["live"] = False
        try:
            m = _add(st, src.kind)
            uid = m.uid
            src = st.mechs[i_src]  # the collection may have moved in memory
            _copy_props(src, m, skip=("uid", "label", "lines", "selected"))
            m.uid = uid
            for ln in src.lines:
                n = m.lines.add()
                _copy_props(ln, n)
            base = re.sub(r" \d+$", "", src.label) or NAMES.get(src.kind, "Mechanism")
            m.label = unique_label(st.mechs, base, m)
            m.y = max(0.0, src.y + self.offset)
            # openings cut in it come along, on the copy's own piece and faces
            pat = re.compile(rf"^([A-Za-z]+){src.uid}(?=$|\.)")
            for o in list(st.openings):
                if not (pat.match(o.on_piece or "") or pat.match(o.face or "")):
                    continue
                n = st.openings.add()
                _copy_props(o, n)
                n.label = unique_label([x for x in st.openings if x != n], "Opening")
                n.on_piece = pat.sub(rf"\g<1>{uid}", o.on_piece)
                n.face = pat.sub(rf"\g<1>{uid}", o.face)
            st.active = len(st.mechs) - 1
        finally:
            st["live"] = was
        if st.rig is not None:
            _rebuild(self, context)
        return {"FINISHED"}


class POPUP_OT_set_open(bpy.types.Operator):
    """Set how far the card is open"""
    bl_idname = "popup.set_open"
    bl_label = "Set Open Angle"
    bl_options = {"REGISTER", "UNDO"}
    angle: FloatProperty(min=0.0, max=360.0)

    @classmethod
    def poll(cls, context):
        st = context.scene.popup
        return st.rig is not None or st.is_carousel

    def execute(self, context):
        st = context.scene.popup
        if st.is_carousel or st.stage_master is not None:
            from . import carousel
            carousel.set_open(context.scene, self.angle)
            context.view_layer.update()
            return {"FINISHED"}
        rig = st.rig
        rig["pop_open"] = self.angle
        rig.update_tag()
        context.view_layer.update()
        return {"FINISHED"}


def _clear_keys(idb, data_path):
    """Remove an animated property's keys (layered actions in Blender 4.4+,
    plain fcurves before)."""
    ad = idb.animation_data
    if ad is None or ad.action is None:
        return
    fcs = getattr(ad.action, "fcurves", None)
    if fcs is None:
        try:
            from bpy_extras import anim_utils
            cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
        except (ImportError, AttributeError):
            cb = None
        fcs = cb.fcurves if cb is not None else None
    if fcs is None:
        return
    for fc in [f for f in fcs if f.data_path == data_path]:
        fcs.remove(fc)


def _frames(sc, seconds):
    fps = sc.render.fps / (sc.render.fps_base or 1.0)
    return max(1, int(round(seconds * fps)))


def anim_timing(sc, cycle=True):
    """Frames to open, hold and close, from the movement test settings."""
    st = sc.popup
    return (_frames(sc, st.anim_open), _frames(sc, st.anim_hold) if st.anim_hold > 0 else 0,
            _frames(sc, st.anim_close))


class POPUP_OT_animate(bpy.types.Operator):
    """Keyframe a movement test from the start frame: open to the Open To
    angle, hold, and close, taking the times set below (replaces the last test)"""
    bl_idname = "popup.animate"
    bl_label = "Keyframe Movement Test"
    bl_options = {"REGISTER", "UNDO"}
    mode: EnumProperty(items=[("OPEN", "Open", "Closed to open"),
                              ("CYCLE", "Open and Close", "Closed, open, closed")],
                       default="CYCLE")

    @classmethod
    def poll(cls, context):
        st = context.scene.popup
        return st.rig is not None or st.is_carousel

    def execute(self, context):
        sc = context.scene
        st = sc.popup
        rig, prop, top = st.rig, '["pop_open"]', min(st.anim_to, 180.0)
        if st.is_carousel or st.stage_master is not None:
            from . import carousel  # the carousel's Open drives every stage
            master = st.stage_master or sc
            rig, prop = carousel.ctrl(master), f'["{carousel.OPEN}"]'
            sc = master
            top = sc.popup.anim_to_carousel
        n_open, n_hold, n_close = anim_timing(sc)
        f0 = sc.frame_start
        _clear_keys(rig, prop)
        keys = [(f0, 0.0), (f0 + n_open, top)]
        if self.mode == "CYCLE":
            f = f0 + n_open
            if n_hold:
                f += n_hold
                keys.append((f, top))
            keys.append((f + n_close, 0.0))
        for f, v in keys:
            rig[prop[2:-2]] = v
            rig.keyframe_insert(prop, frame=f)
        sc.frame_end = keys[-1][0]
        sc.frame_set(f0)
        self.report({"INFO"}, f"Movement test: frames {f0} to {keys[-1][0]}, open to {top:g}°")
        return {"FINISHED"}


class POPUP_OT_animate_pull(bpy.types.Operator):
    """Keyframe a pull test for this flap: pull fully out and back in, from the
    current frame"""
    bl_idname = "popup.animate_pull"
    bl_label = "Keyframe Pull Test"
    bl_options = {"REGISTER", "UNDO"}
    uid: IntProperty()

    @classmethod
    def poll(cls, context):
        return context.scene.popup.rig is not None

    def execute(self, context):
        from .build import pull_prop
        sc = context.scene
        rig = sc.popup.rig
        name = pull_prop(self.uid)
        if name not in rig:
            self.report({"ERROR"}, "Rebuild the card first")
            return {"CANCELLED"}
        n_open, n_hold, n_close = anim_timing(sc)
        f0 = sc.frame_current
        _clear_keys(rig, f'["{name}"]')
        keys = [(f0, 0.0), (f0 + n_open, 1.0)]
        if n_hold:
            keys.append((f0 + n_open + n_hold, 1.0))
        keys.append((keys[-1][0] + n_close, 0.0))
        for f, v in keys:
            rig[name] = v
            rig.keyframe_insert(f'["{name}"]', frame=f)
        sc.frame_end = max(sc.frame_end, keys[-1][0])
        sc.frame_set(f0)
        return {"FINISHED"}


class POPUP_OT_add_art(bpy.types.Operator):
    """Add a paint texture (one UDIM tile per piece on the PopupArt UV map)
    to the paper material, ready for Texture Paint"""
    bl_idname = "popup.add_art"
    bl_label = "Add Paint Texture"
    bl_options = {"REGISTER", "UNDO"}
    dpi: IntProperty(name="DPI", default=150, min=30, max=600)

    @classmethod
    def poll(cls, context):
        return context.scene.popup.rig is not None

    def execute(self, context):
        try:
            img = art.add_art_texture(context.scene, self.dpi)
        except Exception as ex:
            self.report({"ERROR"}, str(ex))
            return {"CANCELLED"}
        self.report({"INFO"}, f"{img.name}: {len(img.tiles)} tile(s)")
        return {"FINISHED"}


def _remember_view(context, painting_card=False):
    """Before drawing on the layout: the view and active object to go back to."""
    sc = context.scene
    _area, rv3d = _view3d(context)
    if rv3d is not None and "pop_view_before" not in sc:
        sc["pop_view_before"] = dict(rot=list(rv3d.view_rotation), loc=list(rv3d.view_location),
                                     dist=rv3d.view_distance, persp=rv3d.view_perspective)
    act = context.view_layer.objects.active
    if act is not None and "pop_active_before" not in sc and not act.name.startswith(
            "Pop-up Holes") and not (painting_card and act == sc.popup.card):
        sc["pop_active_before"] = act.name


def _restore_view(context, keep=False, active_only=False):
    """Back to the view (and, unless keep, the active object) from before."""
    from mathutils import Quaternion as Q
    sc = context.scene
    v = sc.get("pop_view_before")
    _area, rv3d = _view3d(context)
    if v is not None and rv3d is not None and not active_only:
        rv3d.view_rotation = Q(v["rot"])
        rv3d.view_location = Vector(v["loc"])
        rv3d.view_distance = v["dist"]
        rv3d.view_perspective = v["persp"]
    if keep:
        return
    name = sc.get("pop_active_before")
    ob = bpy.data.objects.get(name) if name else None
    if ob is not None and ob.name in context.view_layer.objects:
        for o in context.selected_objects:
            o.select_set(False)
        ob.select_set(True)
        context.view_layer.objects.active = ob
    for k in ("pop_view_before", "pop_active_before"):
        if k in sc:
            del sc[k]


def drawing(context):
    """Drawing holes, creases or cuts on the layout right now?"""
    from . import holes
    obj = context.view_layer.objects.active if context.view_layer else None
    return (context.mode == "PAINT_GREASE_PENCIL" and obj is not None and
            (obj == holes.hole_sketch(context.scene, create=False)[0] or sketching(context)
             or drawing_anywhere(context)))


def drawing_anywhere(context):
    """Drawing on the Draw Anywhere layer right now?"""
    vl = getattr(context, "view_layer", None)
    obj = vl.objects.active if vl else None
    if getattr(context, "mode", "") != "PAINT_GREASE_PENCIL" or obj is None or \
            obj.name != N(context.scene, art.SKETCH):
        return False
    layer = obj.data.layers.active
    return layer is not None and layer.name == art.FREE


def sketching(context):
    """Sketching on a panel (Grease Pencil) right now? The panel's name, or ''."""
    vl = getattr(context, "view_layer", None)
    obj = vl.objects.active if vl else None
    if getattr(context, "mode", "") != "PAINT_GREASE_PENCIL" or obj is None or \
            obj.name != N(context.scene, art.SKETCH):
        return ""
    layer = obj.data.layers.active
    return layer.parent_bone if layer is not None and layer.parent is not None else ""


class POPUP_OT_done_drawing(bpy.types.Operator):
    """Stop drawing on the layout: back to Object Mode and the view you had.
    The strokes stay, to be cut (holes) or added (creases and cuts) when you
    choose"""
    bl_idname = "popup.done_drawing"
    bl_label = "Done Drawing"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        if context.mode != "OBJECT":
            try:
                bpy.ops.object.mode_set(mode="OBJECT")
            except RuntimeError:
                pass
        _restore_view(context)
        _place_drawn(self, context.scene)
        return {"FINISHED"}


def _place_drawn(op, scene):
    """Strokes drawn anywhere: painted onto the paper."""
    if scene.popup.rig is None:
        return
    try:
        made, dropped = art.paint_free(scene)
    except Exception as ex:  # keep the strokes where they are; say so
        op.report({"WARNING"}, f"Couldn't put the strokes on the paper: {ex}")
        return
    if made:
        op.report({"INFO"}, f"{made} stroke{'s' if made != 1 else ''} on the paper" +
                  (f"; {dropped} point(s) off the paper left out" if dropped else ""))
    elif dropped:
        op.report({"WARNING"}, f"{dropped} point(s) drawn off the paper left out")


class POPUP_OT_ink_paper(bpy.types.Operator):
    """Put what you've drawn on the paper now (painted into the card's art,
    flat on each piece, folded and flat alike) and carry on drawing"""
    bl_idname = "popup.ink_paper"
    bl_label = "Put on the Paper"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.scene.popup.rig is not None

    def execute(self, context):
        _place_drawn(self, context.scene)
        return {"FINISHED"}


class POPUP_OT_ink_new(bpy.types.Operator):
    """A new ink (Grease Pencil material) to draw with"""
    bl_idname = "popup.ink_new"
    bl_label = "New Ink"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = art.ensure_sketch(context.scene)
        n = sum(1 for m in obj.data.materials if m and m.name.startswith(art.INK))
        mat = bpy.data.materials.new(f"{art.INK} {n + 1}")
        bpy.data.materials.create_gpencil_data(mat)
        mat.grease_pencil.color = (0.8, 0.15, 0.1, 1.0)
        mat.grease_pencil.show_stroke = True
        mat.grease_pencil.show_fill = False
        obj.data.materials.append(mat)
        obj.active_material_index = len(obj.data.materials) - 1
        return {"FINISHED"}


class POPUP_OT_draw_anywhere(bpy.types.Operator):
    """Draw with Grease Pencil anywhere on the card, folded or flat, across
    folds, with any brush. When you're done (or press Put on the Paper) the
    strokes are painted into the paper itself, flat on each piece: they show
    on the folded card and the flat layout alike and print with the art"""
    bl_idname = "popup.draw_anywhere"
    bl_label = "Draw Anywhere"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.scene.popup.rig is not None

    def execute(self, context):
        sc = context.scene
        st = sc.popup
        if st.plan_view:
            st.plan_view = False  # it squashes the card: draw on the real one
        _remember_view(context)
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        _place_drawn(self, sc)  # anything left from last time
        obj, layer = art.free_layer(sc)
        obj.data.layers.active = layer
        if obj.data.materials:
            obj.active_material_index = 0
        for o in context.selected_objects:
            o.select_set(False)
        obj.hide_set(False)
        obj.select_set(True)
        context.view_layer.objects.active = obj
        ts = sc.tool_settings
        ts.gpencil_stroke_placement_view3d = "SURFACE"
        ts.gpencil_surface_offset = art.OFFSET_MM / st.mm_per_unit
        try:
            bpy.ops.object.mode_set(mode="PAINT_GREASE_PENCIL")
        except (RuntimeError, TypeError):
            pass
        return {"FINISHED"}


def _view3d(context):
    if context.area and context.area.type == "VIEW_3D":
        return context.area, context.space_data.region_3d
    for area in context.window.screen.areas if context.window else []:
        if area.type == "VIEW_3D":
            return area, area.spaces.active.region_3d
    return None, None


def painting(context):
    """In Texture Paint on this card (folded, or its flat layout) right now?"""
    st = context.scene.popup
    obj = context.view_layer.objects.active if context.view_layer else None
    return context.mode == "PAINT_TEXTURE" and obj is not None and obj in (st.card, st.layout)


def paint_switch(context, obj):
    """Carry on painting on the other of the card and its flat layout (they
    are the same paper): same image, same brush, same layer."""
    import time
    sc = context.scene
    st = sc.popup
    if obj not in (st.card, st.layout) or context.view_layer.objects.active == obj:
        return False
    sc["pop_paint_switching"] = time.time() + 1.0  # not leaving: no cut, no colours
    ip = sc.tool_settings.image_paint
    keep = (ip.mode, ip.canvas)
    bpy.ops.object.mode_set(mode="OBJECT")
    for o in context.selected_objects:
        o.select_set(False)
    obj.hide_set(False)
    obj.select_set(True)
    context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="TEXTURE_PAINT")
    ip.mode = keep[0]
    if keep[0] == "IMAGE" and keep[1] is not None:
        ip.canvas = keep[1]
    return True


def switching(scene):
    import time
    return float(scene.get("pop_paint_switching", 0.0)) > time.time()


PAINT_BOTH = "Pop-up Paint Both"


def _paint_both(scene, on):
    """While painting, the card also shows its flat layout, as part of the
    same object (a Geometry Nodes join of the Layout's paper): the brush
    paints either shape, folded or flat, with no switching. The Layout
    object itself steps aside meanwhile, as it would sit in the same place."""
    st = scene.popup
    card, layout = st.card, st.layout
    if card is None or layout is None:
        return
    mod = card.modifiers.get(PAINT_BOTH)
    if not on:
        if mod is not None:
            mod.show_viewport = False
        return
    name = N(scene, PAINT_BOTH)
    ng = bpy.data.node_groups.get(name)
    if ng is None or ng.bl_idname != "GeometryNodeTree":
        ng = bpy.data.node_groups.new(name, "GeometryNodeTree")
        ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
        ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
        gi = ng.nodes.new("NodeGroupInput")
        go = ng.nodes.new("NodeGroupOutput")
        oi = ng.nodes.new("GeometryNodeObjectInfo")
        oi.name = "Layout"
        oi.transform_space = "ORIGINAL"
        j = ng.nodes.new("GeometryNodeJoinGeometry")
        gi.location, oi.location, j.location, go.location = (-400, 0), (-400, -200), (-150, 0), (
            50, 0)
        ng.links.new(gi.outputs[0], j.inputs[0])
        ng.links.new(oi.outputs["Geometry"], j.inputs[0])
        ng.links.new(j.outputs[0], go.inputs[0])
    oi = ng.nodes.get("Layout")
    if oi is not None:
        oi.inputs[0].default_value = layout
    if mod is None:
        mod = card.modifiers.new(PAINT_BOTH, "NODES")
    mod.node_group = ng
    mod.show_render = False
    mod.show_viewport = True
    mod.show_in_editmode = False
    layout.hide_set(True)
    scene["pop_paint_flat"] = True  # the Layout comes back when painting stops


def paint_images(scene):
    """(the paper's art image, other images the card's material paints with,
    e.g. paint layers of your own)"""
    st = scene.popup
    art_img = bpy.data.images.get(N(scene, art.ART_IMAGE))
    others, seen = [], set()

    def walk(tree):
        for n in tree.nodes:
            if n.type == "GROUP" and n.node_tree is not None and n.node_tree.name not in seen:
                seen.add(n.node_tree.name)
                walk(n.node_tree)
            elif n.type == "TEX_IMAGE" and n.image is not None and n.image != art_img \
                    and n.image not in others:
                others.append(n.image)
    mat = st.card.data.materials[0] if st.card is not None and st.card.data.materials else None
    if mat is not None and mat.use_nodes:
        walk(mat.node_tree)
    return art_img, others


def painting_into(scene):
    """The image the brush paints into now."""
    ip = scene.tool_settings.image_paint
    if ip.mode == "IMAGE":
        return ip.canvas
    st = scene.popup
    mat = st.card.data.materials[0] if st.card is not None and st.card.data.materials else None
    if mat is not None and mat.use_nodes:
        n = mat.node_tree.nodes.active
        if n is not None and n.type == "TEX_IMAGE":
            return n.image
    return None


def _paint_into_art(scene):
    """Brush into the paper itself (Pop-up Art): colour, and erased alpha
    for holes and trims. What else was being painted is remembered."""
    st = scene.popup
    ip = scene.tool_settings.image_paint
    now = painting_into(scene)
    art_img = bpy.data.images.get(N(scene, art.ART_IMAGE))
    if now is not None and now != art_img:
        scene["pop_paint_other"] = now.name
    mat = st.card.data.materials[0] if st.card.data.materials else None
    if mat is not None and mat.use_nodes:
        node = next((n for n in mat.node_tree.nodes if n.type == "TEX_IMAGE" and
                     n.image == art_img), None)
        if node is not None:
            mat.node_tree.nodes.active = node
    ip.mode = "MATERIAL"


def _paint_into_other(scene, name=None):
    ip = scene.tool_settings.image_paint
    img = bpy.data.images.get(name or scene.get("pop_paint_other", ""))
    if img is None:
        _a, others = paint_images(scene)
        img = others[0] if others else None
    if img is not None:
        ip.mode = "IMAGE"
        ip.canvas = img


class POPUP_OT_paint(bpy.types.Operator):
    """Paint on or off: Texture Paint on the card just as it stands, and back.
    Turning it off cuts any see-through areas painted on the paper"""
    bl_idname = "popup.paint"
    bl_label = "Paint"
    bl_options = {"REGISTER", "UNDO"}
    target: EnumProperty(items=[("TOGGLE", "Toggle", ""), ("CARD", "On", ""),
                                ("LAYOUT", "On", "(older: the same as On)"),
                                ("OFF", "Off", "")], default="TOGGLE")

    @classmethod
    def poll(cls, context):
        return context.scene.popup.card is not None

    def execute(self, context):
        sc = context.scene
        st = sc.popup
        on = painting(context)
        if self.target == "OFF" or (self.target == "TOGGLE" and on):
            return bpy.ops.popup.done_painting()
        if on:
            return {"FINISHED"}
        if bpy.data.images.get(N(sc, art.ART_IMAGE)) is None:
            art.add_art_texture(sc)
        _remember_view(context, painting_card=True)
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        _end_paint_view(sc)  # (a card left flat by an older version folds again)
        obj = st.card
        for o in context.selected_objects:
            o.select_set(False)
        obj.hide_set(False)
        obj.select_set(True)
        context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode="TEXTURE_PAINT")
        from . import colours
        colours.enter(sc)  # (also done on any switch into Texture Paint)
        ip = sc.tool_settings.image_paint
        _a, others = paint_images(sc)
        if not (others and ip.mode == "IMAGE" and ip.canvas in others):
            _paint_into_art(sc)  # unless a paint layer was already in use
        _paint_both(sc, True)
        return {"FINISHED"}


def _brush(scene):
    ip = scene.tool_settings.image_paint
    return getattr(ip, "brush", None)


def erasing(scene):
    b = _brush(scene)
    return b is not None and b.blend == "ERASE_ALPHA"


def _stop_erasing(scene):
    b = _brush(scene)
    was = scene.get("pop_brush_blend")
    if b is not None and was and b.blend == "ERASE_ALPHA":
        try:
            b.blend = was
        except TypeError:
            pass
    if "pop_brush_blend" in scene:
        del scene["pop_brush_blend"]


class POPUP_OT_paint_erase(bpy.types.Operator):
    """Erase: the brush rubs the paper see-through instead of painting
    colour. Cut Painted Holes then cuts what you erased out of the paper
    (holes inside a piece, a new edge where you erase up to its outline)"""
    bl_idname = "popup.paint_erase"
    bl_label = "Erase"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        sc = context.scene
        b = _brush(sc)
        if b is None:
            self.report({"WARNING"}, "No brush to switch")
            return {"CANCELLED"}
        if b.blend == "ERASE_ALPHA":
            b.blend = sc.get("pop_brush_blend") or "MIX"
            if "pop_brush_blend" in sc:
                del sc["pop_brush_blend"]
        else:
            _paint_into_art(sc)  # holes are in the paper
            sc["pop_brush_blend"] = b.blend
            b.blend = "ERASE_ALPHA"
        return {"FINISHED"}


class POPUP_OT_erase_paper(bpy.types.Operator):
    """Erase the paper: Texture Paint on the card with a brush that rubs it
    see-through (the background round a drawing, say). Cut Painted Holes
    then cuts what's erased out of the paper"""
    bl_idname = "popup.erase_paper"
    bl_label = "Erase Paper"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.scene.popup.card is not None

    def execute(self, context):
        sc = context.scene
        if not painting(context):
            r = bpy.ops.popup.paint(target="CARD")
            if "FINISHED" not in r:
                return {"CANCELLED"}
        if not erasing(sc):
            return bpy.ops.popup.paint_erase()
        return {"FINISHED"}


def flat_layers(mat):
    """A layer stack set up as "paint over" on the paper: a node group fed by
    the shaded paper (Shader to RGB) and mixed over it as flat colour. Returns (group
    node, shader to RGB, mix shader, output) or None."""
    if mat is None or not mat.use_nodes:
        return None
    nt = mat.node_tree
    out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL" and n.is_active_output),
               None)
    if out is None or not out.inputs["Surface"].links:
        return None
    mix = out.inputs["Surface"].links[0].from_node
    if mix.type != "MIX_SHADER":
        return None
    for g in nt.nodes:
        if g.type != "GROUP" or "Color" not in g.inputs or not g.inputs["Color"].links:
            continue
        s2r = g.inputs["Color"].links[0].from_node
        if s2r.bl_idname == "ShaderNodeShaderToRGB" and any(l.to_node == mix for o in g.outputs
                                                for l in o.links):
            return g, s2r, mix, out
    return None


def light_layers(mat):
    """Turn a Paint Over layer stack into one in the paper's Base Color: the
    layers go over the art and are lit like the paper (and render in Cycles
    too). The layers and their images are untouched."""
    got = flat_layers(mat)
    if got is None:
        return False
    g, s2r, mix, out = got
    nt = mat.node_tree
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is None:
        return False
    base = bsdf.inputs["Base Color"]
    src = base.links[0].from_socket if base.links else None
    if src is not None:
        nt.links.new(src, g.inputs["Color"])
    else:
        for ln in list(g.inputs["Color"].links):
            nt.links.remove(ln)
        g.inputs["Color"].default_value = base.default_value
    nt.links.new(g.outputs["Color"], base)
    if "Color Alpha" in g.outputs and bsdf.inputs.get("Alpha") is not None:
        a = bsdf.inputs["Alpha"]
        if a.links and "Color Alpha" in g.inputs:
            nt.links.new(a.links[0].from_socket, g.inputs["Color Alpha"])
        nt.links.new(g.outputs["Color Alpha"], a)
    nt.links.new(bsdf.outputs[0], out.inputs["Surface"])
    gone = [s2r, mix] + [ln.from_node for i in mix.inputs for ln in i.links
                         if ln.from_node.bl_idname == "ShaderNodeBsdfTransparent"]
    for n in gone:
        if n.name in nt.nodes:
            nt.nodes.remove(n)
    return True


class POPUP_OT_light_layers(bpy.types.Operator):
    """Paint layers on the paper are set up as paint over: they show as flat,
    unlit colour on top of the shaded paper (and only in EEVEE). Put them into
    the paper's colour instead, so they're lit like the paper. Layers and
    images stay as they are"""
    bl_idname = "popup.light_layers"
    bl_label = "Light the Paint Layers"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        st = context.scene.popup
        mat = st.card.data.materials[0] if st.card and st.card.data.materials else None
        if not light_layers(mat):
            self.report({"INFO"}, "The paint layers are already lit like the paper")
            return {"CANCELLED"}
        return {"FINISHED"}


class POPUP_OT_paint_into(bpy.types.Operator):
    """Choose what the brush paints into: the paper itself (its colour, and
    erase alpha to cut holes and trims) or a paint layer on top of it (Paint
    System's, colour only)"""
    bl_idname = "popup.paint_into"
    bl_label = "Paint Into"
    bl_options = {"REGISTER", "UNDO"}
    into: StringProperty(default="ART")

    def execute(self, context):
        if self.into == "ART":
            _paint_into_art(context.scene)
        else:
            _paint_into_other(context.scene, None if self.into == "OTHER" else self.into)
        return {"FINISHED"}


class POPUP_OT_done_painting(bpy.types.Operator):
    """Stop painting: back to Object Mode and the object you had selected.
    See-through areas painted on the paper are cut now (Cut Painted Areas)"""
    bl_idname = "popup.done_painting"
    bl_label = "Done Painting"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        sc = context.scene
        if context.mode != "OBJECT":
            try:
                bpy.ops.object.mode_set(mode="OBJECT")
            except RuntimeError:
                pass
        from . import colours
        colours.leave(sc)  # (also done on any switch out of Texture Paint)
        _stop_erasing(sc)  # the brush paints again next time
        _end_paint_view(sc)
        _restore_view(context, active_only=True)
        return {"FINISHED"}


def stale_paint_view(sc):
    """Painting's view (the flat layout joined onto the card, the Layout
    object hidden) left on with the card no longer painted: a session that
    ended by switching scenes, say. Put it back; True if it was."""
    st = sc.popup
    card = st.card
    if card is None:
        return False
    mod = card.modifiers.get(PAINT_BOTH)
    left = (mod is not None and mod.show_viewport) or sc.get("pop_paint_flat") is not None
    try:
        here = bpy.context.scene == sc
    except AttributeError:
        here = False
    # a card only paints in the scene on screen (a stage left in Texture
    # Paint keeps that mode on its object, but isn't being painted)
    if not left or (card.mode == "TEXTURE_PAINT" and here):
        return False
    _end_paint_view(sc)
    return True


def _end_paint_view(sc):
    st = sc.popup
    _paint_both(sc, False)
    mod = st.card.modifiers.get("Pop-up Rig") if st.card is not None else None
    if mod is not None:
        mod.show_viewport = True
    if st.layout is not None and sc.get("pop_paint_flat") is not None:
        try:
            for vl in sc.view_layers:  # this scene's own, wherever we are
                st.layout.hide_set(False, view_layer=vl)
        except (RuntimeError, TypeError):
            try:
                st.layout.hide_set(False)
            except RuntimeError:
                pass
    if "pop_paint_flat" in sc:
        del sc["pop_paint_flat"]


class POPUP_OT_sketch(bpy.types.Operator):
    """Draw with Grease Pencil on a panel. Strokes go on a layer parented to
    the panel, so they move with it"""
    bl_idname = "popup.sketch"
    bl_label = "Sketch on Panel"
    bl_options = {"REGISTER", "UNDO"}
    panel: StringProperty()
    align: BoolProperty(name="Align View", default=True)
    cut: BoolProperty(name="Holes", default=False,
                      description="Draw closed outlines that are cut out of the panel")

    @classmethod
    def poll(cls, context):
        return context.scene.popup.rig is not None

    def execute(self, context):
        sc = context.scene
        st = sc.popup
        panel = self.panel or st.sketch_panel
        if panel not in st.rig.pose.bones:
            self.report({"ERROR"}, "Pick a panel (build the card first)")
            return {"CANCELLED"}
        _remember_view(context)
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        obj, layer = art.sketch_layer(sc, panel, cut=self.cut)
        for o in context.selected_objects:
            o.select_set(False)
        obj.hide_set(False)
        obj.select_set(True)
        context.view_layer.objects.active = obj
        ts = sc.tool_settings
        ts.gpencil_stroke_placement_view3d = "SURFACE"
        ts.gpencil_surface_offset = 0.25 / st.mm_per_unit
        try:
            bpy.ops.object.mode_set(mode="PAINT_GREASE_PENCIL")
        except (RuntimeError, TypeError):
            pass
        if self.align:
            area, rv3d = _view3d(context)
            if rv3d is not None:
                M, centre, normal = art.panel_view(sc, panel)
                q = normal.to_track_quat("Z", "Y")
                rv3d.view_rotation = q
                rv3d.view_location = centre
                rv3d.view_distance = 120.0 / st.mm_per_unit
        return {"FINISHED"}


class POPUP_OT_bake(bpy.types.Operator):
    """Bake the card's material colour (Texture Paint, layers or any
    shader) into the Pop-up Print image used by the SVG export. Uses Cycles"""
    bl_idname = "popup.bake"
    bl_label = "Bake Art for Print"
    bl_options = {"REGISTER", "UNDO"}
    dpi: IntProperty(name="DPI", default=150, min=30, max=600)

    @classmethod
    def poll(cls, context):
        return context.scene.popup.rig is not None

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        try:
            art.bake_art(context.scene, self.dpi)
        except Exception as ex:
            self.report({"ERROR"}, f"Bake failed: {ex}")
            return {"CANCELLED"}
        notes = []
        if getattr(art.bake_art, "last_pass", "BASE") == "EMIT":
            notes.append("baked the emission colour (the material colours through emission)")
        if getattr(art.bake_art, "textures_fixed", False):
            notes.append("decoded sRGB paint textures for Cycles (this Blender skips it)")
        self.report({"INFO"}, "Baked" + (": " + "; ".join(notes) if notes else ""))
        return {"FINISHED"}


class POPUP_OT_export_svg(bpy.types.Operator, ExportHelper):
    """Export one SVG per sheet using the Export settings: print sheets with
    art, or cut / crease lines only for a cutting machine"""
    bl_idname = "popup.export_svg"
    bl_label = "Export SVG Sheets"
    filename_ext = ".svg"
    filter_glob: StringProperty(default="*.svg", options={"HIDDEN"})

    @classmethod
    def poll(cls, context):
        return context.scene.popup.rig is not None

    def draw(self, context):
        from .ui import draw_export
        draw_export(self.layout, context.scene.popup)

    def execute(self, context):
        from . import export_svg, holes
        st = context.scene.popup
        try:
            if st.auto_holes and not st.edited:
                holes.cut_painted(context.scene)  # print the shape the paint shows
            files = export_svg.export(context.scene, self.filepath,
                                      **export_svg.settings_from(st))
        except Exception as ex:
            self.report({"ERROR"}, f"Export failed: {ex}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"Wrote {len(files)} sheet(s)")
        return {"FINISHED"}


class POPUP_OT_view_layout(bpy.types.Operator):
    """Look straight down on the print sheets"""
    bl_idname = "popup.view_layout"
    bl_label = "View Layout"

    @classmethod
    def poll(cls, context):
        return context.scene.popup.rig is not None

    def execute(self, context):
        st = context.scene.popup
        meta = live.meta(st.rig)
        area, rv3d = _view3d(context)
        if meta is None or rv3d is None:
            return {"CANCELLED"}
        mmu = meta["mm_per_unit"]
        sh = meta["sheets"]
        x0 = sh[0]["origin"][0]
        x1 = sh[-1]["origin"][0] + sh[-1]["size"][0]
        y0 = min(s["origin"][1] for s in sh)
        y1 = max(s["origin"][1] + s["size"][1] for s in sh)
        rv3d.view_rotation = Quaternion((1, 0, 0, 0))
        rv3d.view_location = Vector(((x0 + x1) / 2 / mmu, (y0 + y1) / 2 / mmu, 0))
        rv3d.view_distance = max(x1 - x0, y1 - y0) / mmu * 1.05
        rv3d.view_perspective = "ORTHO"
        return {"FINISHED"}


class POPUP_OT_make_carousel(bpy.types.Operator):
    """Make this scene a carousel: a stage scene for each stage (each a Pop-Up
    card of its own, opening to 360 / Stages degrees), shown together round
    one spine"""
    bl_idname = "popup.make_carousel"
    bl_label = "Make Carousel"
    bl_options = {"REGISTER", "UNDO"}
    count: IntProperty(name="Stages", default=5, min=2, max=9)

    @classmethod
    def poll(cls, context):
        st = context.scene.popup
        return st.stage_master is None and st.rig is None

    def execute(self, context):
        from . import carousel
        carousel.make(context.scene, self.count)
        context.scene.frame_set(context.scene.frame_current)
        _first_setup(context)
        return {"FINISHED"}


class POPUP_OT_goto_stage(bpy.types.Operator):
    """Edit one stage on its own (0: back to the whole carousel)"""
    bl_idname = "popup.goto_stage"
    bl_label = "Go to Stage"
    index: IntProperty(default=0)

    def execute(self, context):
        from . import carousel
        st = context.scene.popup
        master = st.stage_master or context.scene
        if self.index == 0:
            carousel.goto(context, master)
            return {"FINISHED"}
        sts = carousel.stages(master)
        if not 1 <= self.index <= len(sts):
            return {"CANCELLED"}
        carousel.goto(context, sts[self.index - 1])
        return {"FINISHED"}


class POPUP_OT_carousel_sync(bpy.types.Operator):
    """Rebuild every stage and the carousel"""
    bl_idname = "popup.carousel_sync"
    bl_label = "Rebuild Carousel"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        from . import carousel
        carousel.make(context.scene.popup.stage_master or context.scene)
        return {"FINISHED"}


class POPUP_OT_export_carousel(bpy.types.Operator, ExportHelper):
    """Export every stage of the carousel (and its leaves, for shared pages)"""
    bl_idname = "popup.export_carousel"
    bl_label = "Export Carousel SVG"
    filename_ext = ".svg"

    def invoke(self, context, event):
        if not self.filepath:
            self.filepath = bpy.path.ensure_ext(
                bpy.path.abspath("//") + context.scene.name, ".svg")
        return ExportHelper.invoke(self, context, event)

    def draw(self, context):
        from .ui import draw_export
        draw_export(self.layout, context.scene.popup)

    def execute(self, context):
        from . import carousel, export_svg
        sc = context.scene
        master = sc.popup.stage_master or sc
        try:
            from . import holes
            for stage in carousel.stages(master):
                if stage.popup.auto_holes and not stage.popup.edited:
                    with carousel.in_scene(stage):
                        holes.cut_painted(stage)
            files = carousel.export(master, self.filepath,
                                    **export_svg.settings_from(master.popup))
        except RuntimeError as ex:
            self.report({"ERROR"}, str(ex))
            return {"CANCELLED"}
        self.report({"INFO"}, f"Wrote {len(files)} file(s)")
        return {"FINISHED"}


class POPUP_OT_add_opening(bpy.types.Operator):
    """Add a window, doorway or arch cut through the paper"""
    bl_idname = "popup.add_opening"
    bl_label = "Add Opening"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        st = context.scene.popup
        o = st.openings.add()
        o.label = unique_label([x for x in st.openings if x != o], "Opening")
        # on the selected mechanism if it can take one, else the card
        o.on_piece = "Card"
        meta = live.meta(st.rig)
        if st.mechs and st.active < len(st.mechs) and meta:
            m = st.mechs[st.active]
            # the selected mechanism's own piece, if it has one
            for name, info in meta["pieces"].items():
                if not info["is_card"] and int(info["slot"]) == 1 + m.uid:
                    o.on_piece = name
            if m.kind in ("BOX", "BOXCUT"):
                # a doorway in the box's front, standing on the floor
                front = f"Box{m.uid}.CB"
                p = next((p for p in meta["panels"] if p["name"] == front), None)
                if p is not None:
                    o.on_piece = p["piece"]
                    o.face = front
                    o.shape = "ARCH"
                    o.x, o.y = 0.0, 0.0
                    o.width = min(20.0, 0.4 * m.width)
                    o.height = 0.6 * m.height  # the front stands the box's height
        if o.on_piece == "Card" and not o.face:
            o.x = 0.5 * st.card_dict()["W"]
        st.active_opening = len(st.openings) - 1
        live.schedule(context.scene)
        return {"FINISHED"}


class POPUP_OT_remove_opening(bpy.types.Operator):
    """Remove the selected opening"""
    bl_idname = "popup.remove_opening"
    bl_label = "Remove Opening"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        st = context.scene.popup
        if 0 <= st.active_opening < len(st.openings):
            o = st.openings[st.active_opening]
            o.through = "NONE"  # neighbours lose it too
            st.openings.remove(st.active_opening)
            st.active_opening = max(0, st.active_opening - 1)
        live.schedule(context.scene)
        return {"FINISHED"}


class POPUP_OT_draw_holes(bpy.types.Operator):
    """Draw hole outlines with Grease Pencil straight onto the flat layout (any
    piece, either half of a fold). Closed strokes are cut at the next rebuild"""
    bl_idname = "popup.draw_holes"
    bl_label = "Draw Holes"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.scene.popup.layout is not None

    def execute(self, context):
        from . import holes
        sc = context.scene
        st = sc.popup
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        _remember_view(context)
        obj, layer = holes.hole_sketch(sc)
        obj.data.layers.active = layer
        obj.active_material_index = len(obj.data.materials) - 1
        st.layout.hide_set(False)
        for o in context.selected_objects:
            o.select_set(False)
        obj.hide_set(False)
        obj.select_set(True)
        context.view_layer.objects.active = obj
        ts = sc.tool_settings
        ts.gpencil_stroke_placement_view3d = "SURFACE"
        ts.gpencil_surface_offset = 0.2 / st.mm_per_unit
        try:
            bpy.ops.object.mode_set(mode="PAINT_GREASE_PENCIL")
        except (RuntimeError, TypeError):
            pass
        area, rv3d = _view3d(context)
        if rv3d is not None:  # look straight down on the layout
            bb = [st.layout.matrix_world @ Vector(c) for c in st.layout.bound_box]
            mid = sum(bb, Vector()) / 8.0
            rv3d.view_rotation = Quaternion((1, 0, 0, 0))
            rv3d.view_location = mid
            rv3d.view_perspective = "ORTHO"
        return {"FINISHED"}


class POPUP_OT_keep_holes(bpy.types.Operator):
    """Fix the drawn hole outlines onto their pieces (they then stay with them
    when the layout is rearranged) and clear the strokes. Edit brings them
    back as strokes"""
    bl_idname = "popup.keep_holes"
    bl_label = "Keep Drawn Holes"
    bl_options = {"REGISTER", "UNDO"}
    edit: BoolProperty(default=False)

    @classmethod
    def poll(cls, context):
        return context.scene.popup.rig is not None

    def execute(self, context):
        from . import holes
        sc = context.scene
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        model, layout = build.make_model(sc)
        if self.edit:
            n = holes.edit_kept(sc, model, layout)
            build.rebuild(sc, force=True)
            self.report({"INFO"}, f"{n} hole outline(s) back as strokes")
            return {"FINISHED"}
        n = holes.keep_drawn(sc, model, layout)
        build.rebuild(sc, force=True)
        self.report({"INFO"}, f"{n} hole(s) kept")
        return {"FINISHED"}


LINE_PRESETS = [
    ("NONE", "Line", "A plain line to set by numbers"),
    ("REVERSE", "Reverse Point", "Two creases and a cut: a point folding forward out of "
     "the V (Birmingham 5, angles A)"),
    ("STEP", "Step", "Creases parallel to the centre fold and a cut: a stepped top "
     "(Birmingham 5, lengths B)"),
    ("TOP", "Folded Top", "Two creases from the centre fold to the top edge: the top "
     "folds back (Birmingham 5, angles C)"),
    ("JAW", "Jaw", "Creases from the centre fold out to the sides, the centre fold "
     "turning from mountain to valley: a chomping jaw (Birmingham 9 and 10)"),
    ("PROJECTION", "Projection", "A cut starting and ending on the centre fold, on one "
     "half only: the shape juts out flat past the fold (Birmingham 6)"),
    ("FAN", "Fan Pleats", "Three creases fanning out from the V point each side: with "
     "Concertina they pleat like a folding fan"),
    ("PLEATS", "Concertina Pleats", "Three creases beside the centre fold each side, "
     "parallel to it: with Concertina they pleat like a concertina"),
]
BOX_PRESETS = [
    ("NONE", "Line", "A plain line to set by numbers"),
    ("BATTLEMENTS", "Battlements", "Notches cut along the front's top fold: the "
     "merlons stand up above the top (Birmingham 37, the castle)"),
    ("TOWER", "Pointed Tower", "A pointed shape cut into the top from the front's top "
     "fold: it stands up above the box like a spire"),
    ("INSET", "Inset Step", "Two creases and two cuts across the front-top fold: that "
     "part folds in (a step back)"),
]


def _lined_active(context):
    st = context.scene.popup
    if 0 <= st.active < len(st.mechs) and st.mechs[st.active].kind in ("VFOLD", "BOX",
                                                                         "BOXCUT", "ROOF"):
        return st.mechs[st.active]
    return None


_vfold_active = _lined_active


def _preset_items(self, context):
    m = _lined_active(context) if context else None
    return BOX_PRESETS if m is not None and m.kind in ("BOX", "BOXCUT") else LINE_PRESETS


def _arch(x0, yc, r, hgt, seg=8):
    """Arch outline from the fold at x0, rising toward -x (box front)."""
    top = x0 - max(hgt - r, 0.0)
    pts = [(x0, yc - r), (top, yc - r)]
    pts += [(top - r * math.sin(math.pi * i / seg), yc - r * math.cos(math.pi * i / seg))
            for i in range(1, seg)]
    return pts + [(top, yc + r), (x0, yc + r)]


class POPUP_OT_add_line(bpy.types.Operator):
    """Add an extra crease or cut (a V-fold: on its left half; a box: measured
    from its front-top fold). Mirror copies it onto the other side"""
    bl_idname = "popup.add_line"
    bl_label = "Add Crease or Cut"
    bl_options = {"REGISTER", "UNDO"}
    preset: EnumProperty(name="Shape", items=_preset_items)

    @classmethod
    def poll(cls, context):
        return _lined_active(context) is not None

    def execute(self, context):
        m = _lined_active(context)
        if m.kind in ("VFOLD", "ROOF"):
            w = m.glue * math.sin(math.radians(m.alpha_l))
            h = m.height
            t15 = math.tan(math.radians(15))
            P = {
                "NONE": [("CREASE", True, [(0.0, 0.6 * h), (-0.5 * w, 0.4 * h)])],
                "REVERSE": [("CREASE", True, [(0.0, 0.8 * h), (-0.35 * w, 0.45 * h)]),
                            ("CUT", True, [(0.0, 0.45 * h), (-0.35 * w, 0.45 * h)])],
                "STEP": [("CREASE", True, [(-0.3 * w, 1.5 * h), (-0.3 * w, 0.55 * h)]),
                         ("CUT", True, [(0.0, 0.55 * h), (-0.3 * w, 0.55 * h)])],
                "TOP": [("CREASE", True, [(0.0, 0.5 * h), (-0.45 * w, 1.5 * h)])],
                "JAW": [("CREASE", True, [(0.0, 0.5 * h),
                                          (-1.3 * w, 0.5 * h + 1.3 * w * t15)])],
                "PROJECTION": [("CUT", False, [(0.0, 0.55 * h), (-0.25 * w, 0.6 * h),
                                               (-0.25 * w, 0.85 * h), (0.0, 0.9 * h)])],
                "FAN": [("CREASE", True, [(0.0, 0.0), (-3 * h * math.sin(a), 3 * h * math.cos(a))])
                        for a in (math.radians(m.alpha_l) * k / 4 for k in (1, 2, 3))],
                "PLEATS": [("CREASE", True, [(-w * k / 4, -0.5 * h), (-w * k / 4, 3 * h)])
                           for k in (1, 2, 3)],
            }.get(self.preset)
            if self.preset in ("FAN", "PLEATS") and m.pleat <= 0:
                m.pleat = 45.0
        else:
            a, b, w = m.height, m.depth, m.width  # front, top, along
            P = None
            if self.preset == "NONE":
                P = [("CUT", True, [(0.0, 0.3 * w), (-0.3 * b, 0.3 * w)])]
            elif self.preset == "BATTLEMENTS":
                n = max(2, int(round(w / 14.0)))
                gap = w / (2 * n + 1)
                hh = min(0.3 * b, 8.0)
                P = [("CUT", False, [(0.0, gap * (2 * i + 1)), (-hh, gap * (2 * i + 1)),
                                     (-hh, gap * (2 * i + 2)), (0.0, gap * (2 * i + 2))])
                     for i in range(n)]
            elif self.preset == "TOWER":
                r, hh = 0.15 * w, 0.8 * b
                P = [("CUT", False, [(0.0, 0.5 * w - r), (-0.6 * hh, 0.5 * w - r),
                                     (-hh, 0.5 * w), (-0.6 * hh, 0.5 * w + r),
                                     (0.0, 0.5 * w + r)])]
            elif self.preset == "DOORWAY":
                P = [("CUT", False, _arch(a, 0.5 * w, min(0.15 * w, 0.3 * a), 0.6 * a))]
            elif self.preset == "INSET":
                e = 0.3 * min(a, b)
                P = [("CREASE", False, [(-e, 0.3 * w), (-e, 0.7 * w)]),
                     ("CREASE", False, [(e, 0.3 * w), (e, 0.7 * w)]),
                     ("CUT", True, [(-e, 0.3 * w), (e, 0.3 * w)])]
            if P is None:
                return {"CANCELLED"}
        group = 1 + max([ln.group for ln in m.lines] + [0])
        allp = [q for _k, _m, pts in P for q in pts]
        px = 0.5 * (min(q[0] for q in allp) + max(q[0] for q in allp))
        py = 0.5 * (min(q[1] for q in allp) + max(q[1] for q in allp))
        for kind, mirror, pts in P:
            ln = m.lines.add()
            ln.kind, ln.mirror = kind, mirror
            ln.group, ln.pivot_x, ln.pivot_y = group, px, py
            names = {k: n for k, n, _ in BOX_PRESETS + LINE_PRESETS}
            ln.shape_name = names.get(self.preset, "Line") if len(P) > 1 else ""
            (ln.x0, ln.y0), (ln.x1, ln.y1) = pts[0], pts[-1]
            if len(pts) > 2:
                ln.path = json.dumps([(round(x, 3), round(y, 3)) for x, y in pts])
        m.active_line = len(m.lines) - 1
        live.schedule(context.scene)
        return {"FINISHED"}


class POPUP_OT_remove_line(bpy.types.Operator):
    """Remove the selected extra crease or cut"""
    bl_idname = "popup.remove_line"
    bl_label = "Remove Line"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        m = _vfold_active(context)
        return m is not None and 0 <= m.active_line < len(m.lines)

    def execute(self, context):
        m = _vfold_active(context)
        ln = m.lines[m.active_line]
        if ln.group and not ln.expanded:
            # a collapsed shape goes as a whole
            g = ln.group
            for i in reversed(range(len(m.lines))):
                if m.lines[i].group == g:
                    m.lines.remove(i)
                    m.active_line = min(m.active_line, i)
        else:
            m.lines.remove(m.active_line)
        m.active_line = max(0, min(m.active_line, len(m.lines) - 1))
        live.schedule(context.scene)
        return {"FINISHED"}


CARD_PRESETS_LINES = [
    ("PEAKED", "Peaked Roof", "The background's top, cut apart at the spine and joined "
     "again by a glue tab: it folds in over the stage as a peaked roof, its ridge level "
     "when the stage is fully open (change the Join Tab's angle to tilt the ridge, the "
     "creases' to change the pitch)"),
    ("CEILING", "Hanging Ceiling", "Two creases rising from the spine to the top edge: the "
     "top of the background folds in over the stage and hangs down at the centre"),
    ("FLOOR", "Floor", "Two creases falling from the spine to the bottom edge: the bottom "
     "of the background folds in as a floor"),
    ("NONE", "Line", "A plain crease to set by numbers"),
]


class POPUP_OT_add_card_line(bpy.types.Operator):
    """Add an extra crease or cut to the card itself (the background): x across
    the card from the spine (left page negative), y up from the bottom edge"""
    bl_idname = "popup.add_card_line"
    bl_label = "Add Crease or Cut to the Card"
    bl_options = {"REGISTER", "UNDO"}
    preset: EnumProperty(name="Shape", items=CARD_PRESETS_LINES)

    def execute(self, context):
        st = context.scene.popup
        card = st.card_dict()
        W, H = card["W"], card["H"]
        tmax = float(card.get("tmax", 180.0))
        # folded in from the spine, it lies closest to level at the stage's
        # full opening with these angles
        phi = math.radians(60.0 if tmax >= 100.0 else 50.0)
        sx, cy = math.sin(phi), math.cos(phi)
        L = 2.0 * max(W, H)
        if self.preset == "CEILING":
            y0 = 0.75 * H
            pts = [(0.0, y0), (-L * sx, y0 + L * cy)]
        elif self.preset == "FLOOR":
            y0 = 0.25 * H
            pts = [(0.0, y0), (-L * sx, y0 - L * cy)]
        else:
            pts = [(0.0, 0.5 * H), (-0.5 * W, 0.5 * H)]
        if self.preset == "PEAKED":
            y0 = 0.8 * H
            # with the eaves 10 degrees below level, this join angle keeps the
            # ridge level at the stage's full opening
            psi = max(5.0, min(80.0, 99.0 - 0.5 * tmax))
            for kind, mirror, ang, x0 in (("CREASE", True, 100.0, 0.0),
                                          ("JOIN", True, psi, 0.0)):
                ln = st.card_lines.add()
                ln.kind, ln.mirror, ln.by_angle = kind, mirror, True
                ln.x0, ln.y0, ln.angle, ln.length = x0, y0, ang, L
            ln = st.card_lines.add()
            ln.kind, ln.mirror = "CUT", False
            (ln.x0, ln.y0), (ln.x1, ln.y1) = (0.0, y0), (0.0, H + 5.0)
            st.active_card_line = len(st.card_lines) - 3
            live.schedule(context.scene)
            return {"FINISHED"}
        ln = st.card_lines.add()
        ln.kind, ln.mirror, ln.by_angle = "CREASE", True, True
        (ln.x0, ln.y0) = pts[0]
        ln.length = L
        dx, dy = pts[1][0] - pts[0][0], pts[1][1] - pts[0][1]
        ln.angle = math.degrees(math.atan2(-dx, dy))
        st.active_card_line = len(st.card_lines) - 1
        live.schedule(context.scene)
        return {"FINISHED"}


class POPUP_OT_remove_card_line(bpy.types.Operator):
    """Remove the selected crease or cut from the card"""
    bl_idname = "popup.remove_card_line"
    bl_label = "Remove Card Line"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        st = context.scene.popup
        return 0 <= st.active_card_line < len(st.card_lines)

    def execute(self, context):
        st = context.scene.popup
        st.card_lines.remove(st.active_card_line)
        st.active_card_line = max(0, min(st.active_card_line, len(st.card_lines) - 1))
        live.schedule(context.scene)
        return {"FINISHED"}


class POPUP_OT_draw_lines(bpy.types.Operator):
    """Draw extra creases (straightened end to end) or cuts with Grease Pencil
    on the V-fold pieces in the flat layout, then press Add Drawn Lines"""
    bl_idname = "popup.draw_lines"
    bl_label = "Draw Lines"
    bl_options = {"REGISTER", "UNDO"}
    kind: EnumProperty(items=[("CREASE", "Creases", ""), ("CUT", "Cuts", "")])

    @classmethod
    def poll(cls, context):
        return context.scene.popup.layout is not None

    def execute(self, context):
        from . import holes
        sc = context.scene
        st = sc.popup
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        _remember_view(context)
        obj, layer = holes.line_layer(sc, self.kind)
        st.layout.hide_set(False)
        for o in context.selected_objects:
            o.select_set(False)
        obj.hide_set(False)
        obj.select_set(True)
        context.view_layer.objects.active = obj
        ts = sc.tool_settings
        ts.gpencil_stroke_placement_view3d = "SURFACE"
        ts.gpencil_surface_offset = 0.2 / st.mm_per_unit
        try:
            bpy.ops.object.mode_set(mode="PAINT_GREASE_PENCIL")
        except (RuntimeError, TypeError):
            pass
        area, rv3d = _view3d(context)
        if rv3d is not None:
            bb = [st.layout.matrix_world @ Vector(c) for c in st.layout.bound_box]
            rv3d.view_rotation = Quaternion((1, 0, 0, 0))
            rv3d.view_location = sum(bb, Vector()) / 8.0
            rv3d.view_perspective = "ORTHO"
        return {"FINISHED"}


class POPUP_OT_take_lines(bpy.types.Operator):
    """Turn the drawn creases and cuts into extra lines on the V-folds they were
    drawn on (Mirror as set below) and clear the strokes"""
    bl_idname = "popup.take_lines"
    bl_label = "Add Drawn Lines"
    bl_options = {"REGISTER", "UNDO"}
    mirror: BoolProperty(name="Mirror", default=True)

    @classmethod
    def poll(cls, context):
        return context.scene.popup.rig is not None

    def execute(self, context):
        from . import holes
        sc = context.scene
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        model, layout = build.make_model(sc)
        got, miss = holes.take_lines(sc, model, layout, self.mirror)
        build.rebuild(sc, force=True)
        msg = f"{got} line(s) added"
        if miss:
            msg += f"; {miss} not on a V-fold piece, dropped"
        self.report({"INFO"} if not miss else {"WARNING"}, msg)
        return {"FINISHED"}


class POPUP_OT_trace_holes(bpy.types.Operator):
    """Cut out everything painted see-through in the art (paint with Erase
    Alpha in Texture Paint). Run again after repainting"""
    bl_idname = "popup.trace_holes"
    bl_label = "Cut Painted Holes"
    bl_options = {"REGISTER", "UNDO"}
    clear: BoolProperty(default=False)

    @classmethod
    def poll(cls, context):
        return context.scene.popup.rig is not None

    def execute(self, context):
        from . import holes
        sc = context.scene
        if self.clear:
            sc.popup["pop_painted"] = "{}"
            n = 0
        else:
            try:
                n = holes.trace_painted(sc)
            except RuntimeError as ex:
                self.report({"ERROR"}, str(ex))
                return {"CANCELLED"}
        build.rebuild(sc, force=True)
        self.report({"INFO"}, f"{n} painted hole(s)")
        return {"FINISHED"}


class POPUP_OT_tri_pictures(bpy.types.Operator):
    """Glue a picture on the box's 45° triangles: the left, the right or both
    of each pair, pointing out of the box (turn and size them after)"""
    bl_idname = "popup.tri_pictures"
    bl_label = "Pictures on Triangles"
    bl_options = {"REGISTER", "UNDO"}
    uid: IntProperty(options={"SKIP_SAVE"})
    which: EnumProperty(items=[("LEFT", "Left", ""), ("RIGHT", "Right", ""),
                               ("BOTH", "Both", "")], default="BOTH", options={"SKIP_SAVE"})

    def execute(self, context):
        st = context.scene.popup
        bx = next((x for x in st.mechs if x.uid == self.uid), None)
        if bx is None or bx.tri45 == "NONE":
            self.report({"ERROR"}, "Turn on the box's 45° triangles first")
            return {"CANCELLED"}
        ends = {"TOP": "T", "BOTTOM": "B", "BOTH": "TB"}[bx.tri45]
        sides = {"LEFT": "L", "RIGHT": "R", "BOTH": "LR"}[self.which]
        done = {x.face for x in st.mechs if x.kind == "PICTURE" and x.host_uid == bx.uid}
        from . import arrange
        from .core.openings import face_frame
        from mathutils import Vector
        model = arrange._model(st)
        hc = model.hosts.get((bx.uid, "C"))
        if hc is None:
            self.report({"ERROR"}, "Build the card first")
            return {"CANCELLED"}
        Ti = hc.T1.inverted()  # piece pattern -> the crease's own frame (x across, y up it)
        was = st.live
        st["live"] = False
        made = 0
        for e in ends:
            for sd in sides:
                face = f"Box{bx.uid}.Tri{e}{sd}"
                tri = model.panels.get(face)
                if face in done or tri is None:
                    continue
                pts = [Ti @ Vector((q[0], q[1], 0.0)) for q in tri.polys[0]]
                on = [p for p in pts if abs(p.x) < 1e-4]  # the two on the crease
                if len(on) != 2:
                    continue
                edge = max(on, key=lambda p: p.y) if e == "T" else min(on, key=lambda p: p.y)
                apex = on[0] if on[1] is edge else on[1]
                k = (edge - apex).length  # the triangle's size
                out = Vector((-1.0 if sd == "L" else 1.0, 0.0, 0.0))
                inward = (apex - edge).normalized()
                if bx.tri_pic_layout == "ALONG":
                    # bottom edge along the crease from the box's edge in,
                    # reaching out across the face (as Box 1 in Kim's file)
                    ay, w_, h_ = out, round(0.6 * k, 1), round(k, 1)
                    ax = inward if inward.cross(ay).z > 0 else -inward
                    corner = edge if ax.dot(inward) > 0 else edge + inward * w_
                else:
                    # standing on the triangle, out past the box's edge
                    ay, w_, h_ = -inward, round(0.6 * k, 1), round(1.6 * k, 1)
                    ax = Vector((ay.y, -ay.x, 0.0))
                    mid = apex + out * (0.5 * k)
                    corner = mid - ax * (0.5 * w_)
                # into the face's own frame (what X, Y and Turn are measured in)
                T1 = hc.T1
                cp = T1 @ corner
                axp = T1.to_3x3() @ ax
                origin, across, upv, _ = face_frame(model, face)
                rel = (cp.x - origin[0], cp.y - origin[1])
                m = _add(st, "PICTURE")
                m.host_uid, m.face = bx.uid, face
                m.img_w, m.img_h = w_, h_
                m.pic_x = round(rel[0] * across[0] + rel[1] * across[1], 2)
                m.pic_y = round(rel[0] * upv[0] + rel[1] * upv[1], 2)
                ca = axp.x * across[0] + axp.y * across[1]
                sa = axp.x * upv[0] + axp.y * upv[1]
                m.pic_turn = round(math.degrees(math.atan2(sa, ca)), 3)
                m.label = unique_label(st.mechs, f"{bx.label} picture", m)
                made += 1
        st["live"] = was
        if not made:
            self.report({"INFO"}, "Those triangles have pictures already")
            return {"CANCELLED"}
        _rebuild(self, context, force=st.rig is not None and not st.edited)
        return {"FINISHED"}


class POPUP_OT_visibility(bpy.types.Operator):
    """How mechanisms show in the viewport: Normal, Wire (outline only) or
    Hidden. Draw Anywhere paints through wire and hidden ones onto the paper
    behind. Renders, prints and exports always show everything"""
    bl_idname = "popup.visibility"
    bl_label = "Mechanism Visibility"
    bl_options = {"REGISTER", "UNDO"}
    action: EnumProperty(items=[
        ("CYCLE", "Cycle", "Normal, then Wire, then Hidden"),
        ("ALL", "Show All", "Every mechanism shown as usual"),
        ("ISOLATE", "Isolate", "Only the selected (and active) mechanisms shown"),
        ("WIRE_OTHERS", "Others as Wire", "The rest drawn as outlines")],
        default="CYCLE", options={"SKIP_SAVE"})
    uid: IntProperty(default=0, options={"SKIP_SAVE"})

    def execute(self, context):
        st = context.scene.popup
        if not st.mechs:
            return {"CANCELLED"}
        if self.action == "CYCLE":
            m = next((x for x in st.mechs if x.uid == self.uid), None)
            if m is None:
                return {"CANCELLED"}
            nxt = {"NORMAL": "WIRE", "WIRE": "HIDDEN", "HIDDEN": "NORMAL"}
            m["visibility"] = ("NORMAL", "WIRE", "HIDDEN").index(nxt[m.visibility])
        else:
            act = st.mechs[st.active].uid if 0 <= st.active < len(st.mechs) else None
            keep = {x.uid for x in st.mechs if x.selected} | {act}
            for m in st.mechs:
                if self.action == "ALL" or m.uid in keep:
                    m["visibility"] = 0
                else:
                    m["visibility"] = 2 if self.action == "ISOLATE" else 1
        from . import visibility
        visibility.refresh(context.scene)
        for area in context.screen.areas if context.screen else ():
            area.tag_redraw()
        return {"FINISHED"}


classes = (POPUP_OT_visibility, POPUP_OT_tri_pictures, POPUP_OT_add_card_line, POPUP_OT_remove_card_line, POPUP_OT_add_line,
           POPUP_OT_remove_line, POPUP_OT_draw_lines,
           POPUP_OT_take_lines, POPUP_OT_draw_holes, POPUP_OT_keep_holes, POPUP_OT_export_carousel,
           POPUP_OT_add_opening, POPUP_OT_remove_opening, POPUP_OT_trace_holes,
           POPUP_OT_make_carousel, POPUP_OT_goto_stage, POPUP_OT_carousel_sync,
           POPUP_OT_build, POPUP_OT_draw_anywhere, POPUP_OT_ink_paper, POPUP_OT_ink_new, POPUP_OT_add, POPUP_OT_remove, POPUP_OT_duplicate, POPUP_OT_done_drawing, POPUP_OT_done_painting, POPUP_OT_paint_into, POPUP_OT_paint_erase, POPUP_OT_erase_paper, POPUP_OT_light_layers, POPUP_OT_set_open,
           POPUP_OT_animate, POPUP_OT_animate_pull, POPUP_OT_add_art, POPUP_OT_paint, POPUP_OT_sketch,
           POPUP_OT_bake, POPUP_OT_export_svg, POPUP_OT_view_layout)


def register():
    for c in classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
