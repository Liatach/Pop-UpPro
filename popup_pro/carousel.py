"""Carousel books: several stages round one spine, opened right round.

A carousel scene holds no paper of its own. Each stage is a scene of its own,
a normal Pop-Up Pro card (same tools, art, sketches and export) whose pages
open to 360 / Stages degrees and whose names carry a suffix so stages never
share data. The carousel scene shows every stage's folded card as a
collection instance turned round the spine, and one Open control (0-360
degrees) drives them all:

* each stage's rig gets Open = carousel Open / Stages, and
* stage i is turned i x that angle about the spine, so its left page lies
  on the previous stage's right page.
"""

import contextlib
import math

import bpy

from . import live
from .naming import N

OPEN = "carousel_open"


def stages(master):
    return [r.scene for r in master.popup.stages if r.scene is not None]


def ctrl(master):
    return master.popup.carousel_ctrl


def open_value(scene):
    """The carousel's Open (degrees) for a carousel or one of its stages."""
    st = scene.popup
    master = st.stage_master or scene
    c = ctrl(master)
    return None if c is None else c.get(OPEN)


def _coll(master):
    name = f"Carousel · {master.name}"
    coll = bpy.data.collections.get(name)
    if coll is None:
        coll = bpy.data.collections.new(name)
    if coll.name not in master.collection.children:
        master.collection.children.link(coll)
    return coll


def _empty(name, coll):
    obj = bpy.data.objects.get(name)
    if obj is None or obj.type != "EMPTY":
        obj = bpy.data.objects.new(name, None)
    if obj.name not in coll.objects:
        coll.objects.link(obj)
    return obj


@contextlib.contextmanager
def in_scene(scene):
    """Run with scene as the active scene (rebuilding a rig needs Edit Mode in
    its own view layer)."""
    win = bpy.context.window
    if win is not None:
        prev = win.scene
        if prev != scene:
            win.scene = scene
        try:
            with bpy.context.temp_override(window=win, scene=scene,
                                           view_layer=scene.view_layers[0]):
                yield
        finally:
            if prev != scene:
                win.scene = prev
    else:
        with bpy.context.temp_override(scene=scene, view_layer=scene.view_layers[0]):
            yield


def rebuild_stage(scene):
    from . import build
    with in_scene(scene):
        build.rebuild(scene, force=True)


def new_stage(master, index):
    """A stage scene for the carousel, with a staging frame and one frame."""
    from . import build
    from .ops import _add
    sc = bpy.data.scenes.new(f"{master.name} · Stage {index}")
    st = sc.popup
    st.suffix = f" · {sc.name}"
    st.stage_master = master
    st.stage_index = index
    st["live"] = False
    st.keep_open = False
    st.hold = "SYM"
    st.mm_per_unit = master.popup.mm_per_unit
    sc.unit_settings.system = master.unit_settings.system
    sc.unit_settings.scale_length = master.unit_settings.scale_length
    _add(st, "FRAME")  # staging frame at the front
    _add(st, "FRAME")  # one floating frame behind it
    rebuild_stage(sc)
    st["live"] = True
    return sc


def make(master, count=None):
    """Turn a scene into a carousel (or update one): stage scenes, instances
    round the spine, and the Open control."""
    st = master.popup
    st.is_carousel = True
    if count is not None:
        st["stage_count"] = int(count)
    n = st.stage_count
    have = stages(master)
    # spare stages (from a larger count earlier) are kept, not deleted
    spares = sorted((s for s in bpy.data.scenes
                     if s.popup.stage_master == master and s not in have),
                    key=lambda s: s.popup.stage_index)
    while len(have) < n:
        sc = spares.pop(0) if spares else new_stage(master, len(have) + 1)
        have.append(sc)
    st.stages.clear()
    for i, sc in enumerate(have[:n]):
        r = st.stages.add()
        r.scene = sc
        sc.popup.stage_index = i + 1
    assemble(master)
    return have[:n]


def assemble(master):
    from . import build
    st = master.popup
    coll = _coll(master)
    c = _empty(f"Carousel Open · {master.name}", coll)
    c.empty_display_type = "SPHERE"
    c.empty_display_size = 0.5
    if OPEN not in c:
        c[OPEN] = 360.0
    c.id_properties_ui(OPEN).update(min=0.0, max=360.0, soft_min=0.0, soft_max=360.0,
                                    description="How far the carousel is open (degrees)")
    st.carousel_ctrl = c
    # the stages' cards have the spine along Y: stand it up
    base = _empty(f"Carousel Spine · {master.name}", coll)
    base.empty_display_type = "SINGLE_ARROW"
    base.rotation_euler = (math.pi / 2, 0.0, 0.0)
    n = st.stage_count
    keep = set()
    for i, sc in enumerate(stages(master)):
        rebuild_stage(sc)
        inst = _empty(f"Stage {i + 1} · {master.name}", coll)
        inst.instance_type = "COLLECTION"
        inst.instance_collection = build.folded_collection(sc)
        inst.parent = base
        inst.empty_display_size = 0.2
        keep.add(inst.name)
        if inst.animation_data:
            for fc in list(inst.animation_data.drivers):
                inst.animation_data.drivers.remove(fc)
        fc = inst.driver_add("rotation_euler", 1)
        d = fc.driver
        d.type = "SCRIPTED"
        v = d.variables.new()
        v.name = "T"
        v.targets[0].id = c
        v.targets[0].data_path = f'["{OPEN}"]'
        d.expression = f"radians(T)*{i}/{n}"
    for o in list(coll.objects):  # stages dropped by a smaller count
        if o.name.startswith("Stage ") and o.name not in keep:
            bpy.data.objects.remove(o, do_unlink=True)


def link_stage(scene):
    """Drive a stage's Open from its carousel (after every rebuild)."""
    st = scene.popup
    master = st.stage_master
    rig = st.rig
    if master is None or rig is None:
        return
    c = ctrl(master)
    if c is None:
        return
    try:
        rig.driver_remove('["pop_open"]')
    except TypeError:
        pass
    fc = rig.driver_add('["pop_open"]')
    d = fc.driver
    d.type = "SCRIPTED"
    v = d.variables.new()
    v.name = "T"
    v.targets[0].id = c
    v.targets[0].data_path = f'["{OPEN}"]'
    d.expression = f"T/{master.popup.stage_count}"


def set_open(scene, degrees):
    master = scene.popup.stage_master or scene
    c = ctrl(master)
    if c is not None:
        c[OPEN] = max(0.0, min(360.0, float(degrees)))
        c.update_tag()


_pending = set()


def schedule_sync(master):
    """Stage count or joins changed: rebuild the stages and the carousel."""
    if not master.popup.is_carousel:
        return
    _pending.add(master.name)
    if not bpy.app.timers.is_registered(_sync):
        bpy.app.timers.register(_sync, first_interval=0.2)


def _sync():
    for name in list(_pending):
        _pending.discard(name)
        sc = bpy.data.scenes.get(name)
        if sc is not None:
            make(sc)
    return None


def goto(context, scene):
    if context.window is not None:
        context.window.scene = scene
    live.schedule(scene)


# ------------------------------------------------------------------ export
def _crop(svg_text, x0, w, h):
    """Inner markup of an exported sheet, as a nested svg showing x0..x0+w."""
    head_end = svg_text.index(">", svg_text.index("<svg")) + 1
    body = svg_text[head_end:svg_text.rindex("</svg>")]
    return (f'<svg x="0" y="0" width="{w:.3f}" height="{h:.3f}" '
            f'viewBox="{x0:.3f} 0 {w:.3f} {h:.3f}" overflow="hidden">{body}</svg>')


def _page(w, h, body):
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" '
            f'width="{w:.2f}mm" height="{h:.2f}mm" viewBox="0 0 {w:.3f} {h:.3f}">\n'
            + body + "\n</svg>\n")


def export(master, filepath, **settings):
    """Every stage's sheets, named by stage. Shared Page joins replace each
    stage's card sheet with the leaves: one sheet per pair of neighbouring
    pages, printed double-sided. Adds a carousel assembly page."""
    import os
    from xml.sax.saxutils import escape
    from . import export_svg
    st = master.popup
    root, ext = os.path.splitext(filepath)
    ext = ext or ".svg"
    sts = stages(master)
    n = len(sts)
    written, cards = [], {}
    for i, sc in enumerate(sts):
        with in_scene(sc):
            fs = export_svg.export(sc, f"{root}_stage{i + 1}{ext}", **settings)
        card = next((f for f in fs if f.endswith("_sheet1" + ext)), None)
        cards[i] = card
        written += fs
    W, H = st.card_dict()["W"], st.card_dict()["H"]
    shared = st.join == "SHARED" and settings.get("content", "PRINT") in ("PRINT", "ART_CUT")
    if shared and all(cards.values()):
        texts = {i: open(f, encoding="utf-8").read() for i, f in cards.items()}
        for k in range(n):
            nxt = (k + 1) % n
            front = _page(W, H, _crop(texts[k], W, W, H))
            back = _page(W, H, _crop(texts[nxt], 0.0, W, H))
            for side, svg in (("front", front), ("back", back)):
                path = f"{root}_leaf{k + 1}_{side}{ext}"
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(svg)
                written.append(path)
        for f in cards.values():  # the spreads are replaced by the leaves
            if f in written:
                written.remove(f)
                os.remove(f)
    if settings.get("content", "PRINT") == "PRINT":
        lines = [f"Carousel: {n} stages, each opening to {360.0 / n:.1f} degrees",
                 f"Stage size: {W:.1f} mm deep x {H:.1f} mm tall"]
        if shared:
            lines += ["Joins: shared pages. Print each leaf double-sided (front, then back",
                      "flipped on the long edge). Leaf k is stage k's right page on the front",
                      "and stage k+1's left page on the back. Hinge the leaves together",
                      "along their spine edges with a strip of tape or paper."]
        else:
            lines += ["Joins: glued. Make each stage as its own folded card, then glue the",
                      "back of each stage's right page to the back of the next stage's left",
                      f"page, in order 1 to {n}. Tie or clip stage {n}'s right page to stage",
                      "1's left page to stand it up (or glue them for a fixed carousel)."]
        lines += ["", "Build each stage: pages first, then floors and ceilings, then frames",
                  "from the back to the front; the staging frame goes on last."]
        for i, sc in enumerate(sts):
            mech = ", ".join(m.label for m in sc.popup.mechs) or "background only"
            lines.append(f"Stage {i + 1} ({sc.name}): {mech}")
        body = "".join(f'<text x="10" y="{14 + 6 * j:.1f}" font-size="{4.5 if j == 0 else 3.4}" '
                       f'font-family="sans-serif" fill="#333333">{escape(t)}</text>'
                       for j, t in enumerate(lines))
        path = f"{root}_carousel{ext}"
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(_page(2 * W, max(H, 20 + 6 * len(lines)), body))
        written.append(path)
    return written
