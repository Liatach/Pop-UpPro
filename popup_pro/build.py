"""Turn the mechanism settings into Blender data.

* "Pop-up Card"   one mesh holding every panel, deformed by the rig
* "Pop-up Layout" the same mesh with no modifiers: the flat print sheets
* "Pop-up Rig"    one bone per panel. Hinged bones turn about their local Y
                  axis with a driver on rotation_euler[1] (simple expressions
                  only, no Python auto-run needed). Glued tabs are fixed.

The mesh rest shape *is* the print layout, so editing or painting the Layout
object edits the flat paper, and the folded card follows.
"""

import json
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from .naming import N

from .core.geom import frame, scaled, v3
from .core.layout import build_layout
from .core.model import Model

COLL = "Pop-up Card"
ART_UV = "PopupArt"
TILE_MM = 297.0
BONE_MM = 12.0


# ------------------------------------------------------------------ model
def make_model(scene):
    st = scene.popup
    mechs = [m.to_dict() for m in st.mechs]
    model = Model(st.card_dict(), mechs)
    model.check_fit()
    layout = build_layout(model)
    return model, layout


def art_uv(model, piece, q):
    """UDIM tile per piece (slot): stable when other pieces move around."""
    pc = model.pieces[piece]
    k = pc.slot
    tu, tv = k % 10, k // 10
    if pc.is_card:
        W, H = model.W, model.H
        return (tu + (q[0] + W) / (2 * W), tv + q[1] / H)
    ax, ay = pc.anchor
    u = 0.5 + (q[0] - ax) / TILE_MM
    v = 0.5 + (q[1] - ay) / TILE_MM
    return (tu + min(max(u, 0.0), 0.999), tv + min(max(v, 0.0), 0.999))


TILE_UV = "PopupTile"
T_SHARE = 5.0  # degrees: folds checked closed from here up to full open  # each piece's own place in the art (bake target, export)


def tab_art(model):
    """Outside tabs: glue tabs whose printed side faces out, on the front
    of the part they glue to, so it shows. They carry that part's art where
    they land (as Papercraft Pro's outside tabs do) and blend into it.
    {tab: (host piece, tab pattern -> host pattern)}"""
    out = {}
    t = model.t_ref
    z = Vector((0.0, 0.0, 1.0))
    for name in model.order:
        p = model.panels[name]
        if p.kind != "tab" or not p.parent:
            continue
        host = model.panels[p.parent]
        R = host.asm(t).inverted() @ p.asm(t)
        if (R.to_3x3() @ z).z > 0.9 and R.to_translation().z > -1e-6:
            out[name] = (host.piece, R)
    return out


def panel_frame(panel):
    """Bone frame in the panel's own pattern: the hinge, or (for glued tabs)
    an axis-aligned frame at the first corner."""
    if panel.hinge is not None:
        return panel.hinge.Fc
    q = panel.polys[0][0]
    return frame(v3(q), (1, 0, 0), (0, 1, 0))


# ------------------------------------------------------------- objects
def _collection(scene):
    name = N(scene, COLL)
    coll = bpy.data.collections.get(name)
    if coll is None:
        coll = bpy.data.collections.new(name)
    if coll.name not in scene.collection.children:
        try:
            scene.collection.children.link(coll)
        except RuntimeError:
            pass
    return coll


def folded_collection(scene):
    """Where the folded card, its rig and sketches live. A carousel stage keeps
    them in a child collection of their own, which the carousel instances
    round its spine (the flat layout stays out of it)."""
    coll = _collection(scene)
    if scene.popup.stage_master is None:
        return coll
    name = N(scene, "Pop-up Folded")
    sub = bpy.data.collections.get(name)
    if sub is None:
        sub = bpy.data.collections.new(name)
    if sub.name not in coll.children:
        coll.children.link(sub)
    return sub


def _place(obj, coll, scene):
    """Link obj to coll only (out of the scene's other Pop-up collections)."""
    for c in (_collection(scene), folded_collection(scene)):
        if c != coll and obj.name in c.objects:
            c.objects.unlink(obj)
    _link(obj, coll)


def _link(obj, coll):
    if obj.name not in coll.objects:
        coll.objects.link(obj)


def ensure_objects(scene):
    st = scene.popup
    coll = _collection(scene)
    if st.rig is None or st.rig.name not in bpy.data.objects:
        arm = bpy.data.armatures.new(N(scene, "Pop-up Rig"))
        st.rig = bpy.data.objects.new(N(scene, "Pop-up Rig"), arm)
        arm.display_type = "STICK"
    fold = folded_collection(scene)
    _place(st.rig, fold, scene)
    rig = st.rig
    if "pop_open" not in rig:
        rig["pop_open"] = 90.0
    ui = rig.id_properties_ui("pop_open")
    ui.update(min=0.0, max=180.0, soft_min=0.0, soft_max=180.0, subtype="NONE",
              description="How far the card is open, in degrees (0 closed, 180 flat)")
    if st.card is None or st.card.name not in bpy.data.objects:
        me = st.layout.data if st.layout else bpy.data.meshes.new(N(scene, "Pop-up Paper"))
        st.card = bpy.data.objects.new(N(scene, "Pop-up Card"), me)
    _place(st.card, fold, scene)
    if st.layout is None or st.layout.name not in bpy.data.objects:
        st.layout = bpy.data.objects.new(N(scene, "Pop-up Layout"), st.card.data)
    _place(st.layout, coll, scene)
    if st.layout.data != st.card.data:
        st.layout.data = st.card.data
    mod = st.card.modifiers.get("Pop-up Rig")
    if mod is None:
        mod = st.card.modifiers.new("Pop-up Rig", "ARMATURE")
    mod.object = rig
    mod.use_vertex_groups = True
    mod.show_in_editmode = True
    mod.show_on_cage = True
    for m in list(st.layout.modifiers):
        if m.type == "ARMATURE":
            st.layout.modifiers.remove(m)
    return rig, st.card, st.layout


def ensure_solid(card, st):
    """Solid Paper: thickness behind the printed side (after the rig)."""
    mod = card.modifiers.get("Pop-up Paper")
    if not st.solid_paper:
        if mod is not None:
            card.modifiers.remove(mod)
        return
    if mod is None:
        mod = card.modifiers.new("Pop-up Paper", "SOLIDIFY")
    mod.thickness = st.paper_thickness / st.mm_per_unit
    mod.offset = -1.0
    # folds are shared edges now: plain offsets meet at each fold without
    # Even Thickness's long spikes where the card shuts a fold flat
    mod.use_even_offset = False
    mod.use_rim = True


def ensure_material(mesh, scene=None):
    name = N(scene, "Pop-up Paper")
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        nt = mat.node_tree
        bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
        bsdf.inputs["Base Color"].default_value = (0.95, 0.93, 0.88, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.9
        mat.diffuse_color = (0.95, 0.93, 0.88, 1.0)
    if not mesh.materials:
        mesh.materials.append(mat)
    return mat


# ----------------------------------------------------------------- mesh
def mesh_hash(mesh):
    n = len(mesh.vertices)
    s = 0.0
    for v in mesh.vertices:
        s += v.co.x * 1.3 + v.co.y * 1.7 + v.co.z * 2.9
    return f"{n}:{len(mesh.polygons)}:{s:.4f}"


def build_mesh(mesh, model, layout, s, holes=None):
    from .holes import cut
    holes = holes or {}
    bm = bmesh.new()
    lay = bm.faces.layers.int.new("pop_panel")
    uvl = bm.loops.layers.uv.new(ART_UV)
    tile = bm.loops.layers.uv.new(TILE_UV)
    carry = tab_art(model)
    groups = {}
    # Panels of one piece meeting along a fold share the fold's vertices, so
    # the paper is one surface there: Solid Paper then mitres each fold (no
    # slab poking through the panel next to it, no slit along a crease).
    # Each shared vertex is in both panels' groups; the two bones agree on
    # the fold line, so the rig keeps it exact. Glue tabs stay apart (they
    # fold right back on themselves), and so does anything that doesn't
    # keep its fold closed all the way (a sliding bend, a lifted strip).
    shared = {}  # piece -> pattern point -> [(vertex, {panels})]
    ok_pair = {}
    ts = sorted({max(T_SHARE, 0.25 * model.tmax), model.t_ref, 0.75 * model.tmax,
                 model.tmax})

    def joins(a, b, q):
        k = (a, b) if a < b else (b, a)
        got = ok_pair.get(k)
        if got is None:
            pa, pb = model.panels[a], model.panels[b]
            got = (pa.kind != "tab" and pb.kind != "tab" and abs(pa.zoff - pb.zoff) < 1e-9
                   and frozenset(k) not in model.soft)
            ok_pair[k] = got
        if not got:
            return False
        v = Vector((q[0], q[1], 0.0))
        return all((model.shown(a, t) @ v - model.shown(b, t) @ v).length < 2e-4 for t in ts)

    for pi, name in enumerate(model.order):
        p = model.panels[name]
        P = layout["prints"][p.piece]
        cache = {}
        pool = shared.setdefault(p.piece, {})
        idx = []
        polys = []
        for poly in p.polys:
            tris = cut(poly, holes[p.piece]) if holes.get(p.piece) else None
            polys += [poly] if tris is None else tris
        for poly in polys:
            vs = []
            for q in poly:
                key = (round(q[0], 5), round(q[1], 5))
                bv = cache.get(key)
                if bv is None:
                    for cand, users in pool.get(key, ()):
                        if all(joins(u, name, q) for u in users):
                            bv = cand
                            users.add(name)
                            break
                    if bv is None:
                        bv = bm.verts.new((P @ Vector((q[0], q[1], p.zoff))) * s)
                        pool.setdefault(key, []).append((bv, {name}))
                    cache[key] = bv
                    idx.append(bv)
                vs.append(bv)
            if len(set(vs)) < 3:
                continue
            try:
                f = bm.faces.new(vs)
            except ValueError:
                continue
            f[lay] = pi
            to_host = carry.get(name)
            for loop, q in zip(f.loops, poly):
                own = art_uv(model, p.piece, q)
                loop[tile].uv = own
                if to_host is not None:
                    h = to_host[1] @ Vector((q[0], q[1], 0.0))
                    loop[uvl].uv = art_uv(model, to_host[0], (h.x, h.y))
                else:
                    loop[uvl].uv = own
        groups[name] = idx
    bm.verts.index_update()
    order = {name: [v.index for v in vs] for name, vs in groups.items()}
    bm.to_mesh(mesh)
    bm.free()
    mesh.uv_layers.active = mesh.uv_layers[ART_UV]
    mesh.uv_layers[ART_UV].active_render = True
    mesh.update()
    return order


# ------------------------------------------------------------------ rig
TERM = "{0:.9g}{1:+.9g}*cos(radians(max(T,0.05))){2:+.9g}*sin(radians(max(T,0.05)))"


def open_expr(t0):
    """The real open angle as an expression in the Open slider t: with a
    closing stop t0, Open 0..180 maps onto t0..180 degrees."""
    if t0 <= 1e-6:
        return "t"
    return f"({t0:.6g}{(180.0 - t0) / 180.0:+.9g}*t)"


def _var(d, name, id_type, idb, path):
    v = d.variables.new()
    v.name = name
    v.type = "SINGLE_PROP"
    v.targets[0].id_type = id_type
    v.targets[0].id = idb
    v.targets[0].data_path = path
    return v


def _fresh(fc):
    d = fc.driver
    d.type = "SCRIPTED"
    while d.variables:
        d.variables.remove(d.variables[0])
    for m in list(fc.modifiers):
        fc.modifiers.remove(m)
    return d


def _driver(rig, pb, hinge, const, t0=0.0):
    """Bone driver. Spherical (V-fold) hinges read three helper properties on
    the armature data, each driven by the open angle, to stay within
    Blender's 256-character expression limit."""
    d = _fresh(pb.driver_add("rotation_euler", 1))
    if hinge.kind == "SPHERICAL":
        arm = rig.data
        for key in "ABD":
            prop = f"pop_{pb.name}_{key}"
            arm[prop] = 0.0
            hd = _fresh(arm.driver_add(f'["{prop}"]'))
            _var(hd, "t", "OBJECT", rig, '["pop_open"]')
            full = TERM.format(*hinge.parts[key]).replace("T", open_expr(t0))
            if len(full) > 255:
                raise RuntimeError(f"driver for {pb.name} is too long")
            hd.expression = full
            _var(d, key.lower(), "ARMATURE", arm, f'["{prop}"]')
    elif hinge.kind == "PULL":
        _var(d, "p", "OBJECT", rig, f'["{pull_prop(hinge.sph["uid"])}"]')
    else:
        _var(d, "t", "OBJECT", rig, '["pop_open"]')
    if hinge.kind == "TABLE":
        # The driver gives the real open angle; its curve maps that to the
        # hinge angle solved when the card was built.
        d.expression = open_expr(t0)
        fc = pb.id_data.animation_data.drivers.find(f'pose.bones["{pb.name}"].rotation_euler', index=1)
        kps = fc.keyframe_points
        # New drivers come with placeholder keys (0,0) and (1,1): reuse them
        # (clearing and refilling a driver curve can crash Blender).
        n = len(hinge.table)
        if len(kps) < n:
            kps.add(n - len(kps))
        while len(kps) > n:
            kps.remove(kps[len(kps) - 1], fast=True)
        for kp, (tt, vv) in zip(kps, hinge.table):
            kp.co = (tt, const + vv)
            kp.interpolation = "LINEAR"
        fc.extrapolation = "CONSTANT"
        fc.update()
        return d
    expr = hinge.expr
    if hinge.kind == "LINEAR":
        expr = expr.replace("radians(t)", f"radians({open_expr(t0)})")
    elif hinge.kind == "EXPR":
        expr = expr.replace("radians(T)", f"radians({open_expr(t0)})")
    full = f"{const:.9g}+({expr})"
    if len(full) > 255:  # Blender truncates silently
        raise RuntimeError(f"driver for {pb.name} is too long ({len(full)} characters)")
    d.expression = full
    return d


def pull_prop(uid):
    return f"pop_pull_{uid}"


def _slide_drivers(rig, pb, hinge, K, s):
    """A part that slides along its bone's Y (the pull strip): the pose is
    K @ Translate(0, d, 0), so each location channel is K.t + K.R[:,1] * d."""
    Kt, Kr = K.to_translation(), K.to_3x3()
    for i in range(3):
        d = _fresh(pb.driver_add("location", i))
        _var(d, "p", "OBJECT", rig, f'["{pull_prop(hinge.sph["uid"])}"]')
        full = f"{Kt[i]:.9g}{Kr[i][1] * s:+.9g}*({hinge.expr})"
        if len(full) > 255:
            raise RuntimeError(f"driver for {pb.name} is too long ({len(full)} characters)")
        d.expression = full


from .core.model import Model as _M  # noqa: E402
LIFT_FROM, LIFT_SPAN = _M.LIFT_FROM, _M.LIFT_SPAN  # degrees before full open


def _lift_drivers(rig, pb, K, lift, tmax, t0, d=None):
    """Raise a part off the panel it hangs from (along that panel's normal)
    as the card nears fully open: a glued strip shown resting on its tabs,
    folded down level with its hinge while the card closes."""
    v = K.to_3x3() @ (Vector((0.0, 0.0, 1.0)) if d is None else d)
    base = K.to_translation()
    T = open_expr(t0)
    for i in range(3):
        if abs(v[i] * lift) < 1e-9:
            continue
        d = _fresh(pb.driver_add("location", i))
        _var(d, "t", "OBJECT", rig, '["pop_open"]')
        d.expression = (f"{base[i]:.9g}{v[i] * lift:+.9g}*max(0,min(1,({T}-"
                        f"{tmax - LIFT_FROM:.6g})/{LIFT_SPAN:.6g}))")


def build_rig(scene, rig, model, layout, s, t0=0.0):
    view_layer = bpy.context.view_layer
    prev_active = view_layer.objects.active
    prev_mode = bpy.context.mode
    if prev_mode != "OBJECT":
        try:
            bpy.ops.object.mode_set(mode="OBJECT")
        except RuntimeError:
            pass
    if rig.name not in view_layer.objects:
        raise RuntimeError("the rig is hidden from the view layer")
    hidden = rig.hide_get()
    rig.hide_set(False)
    view_layer.objects.active = rig
    # drop old drivers on bones
    if rig.animation_data:
        for fc in list(rig.animation_data.drivers):
            if fc.data_path.startswith("pose.bones"):
                rig.animation_data.drivers.remove(fc)
    if rig.data.animation_data:
        for fc in list(rig.data.animation_data.drivers):
            rig.data.animation_data.drivers.remove(fc)
    for k in [k for k in rig.data.keys() if k.startswith("pop_")]:
        del rig.data[k]
    bpy.ops.object.mode_set(mode="EDIT")
    eb = rig.data.edit_bones
    for b in list(eb):
        eb.remove(b)
    rests = {}
    for name in model.order:
        p = model.panels[name]
        rest = layout["prints"][p.piece] @ panel_frame(p)
        rests[name] = rest
        b = eb.new(name)
        b.head = (0, 0, 0)
        b.tail = (0, BONE_MM * s, 0)
        b.matrix = scaled(rest, s)
        b.use_deform = True
        if p.parent:
            b.parent = eb[p.parent]
    bpy.ops.object.mode_set(mode="OBJECT")
    coll = rig.data.collections.get("Panels") or rig.data.collections.new("Panels")
    for b in rig.data.bones:
        coll.assign(b)

    for name in model.order:
        p = model.panels[name]
        pb = rig.pose.bones[name]
        pb.rotation_mode = "YZX"
        pb.scale = (1, 1, 1)
        rest = rests[name]
        pp = layout["prints"][model.panels[p.parent].piece] if p.parent else Matrix.Identity(4)
        if p.hinge is not None:
            K = rest.inverted() @ pp @ p.hinge.Hp
        else:
            rel = model.rel(name, model.t_ref)
            K = rest.inverted() @ pp @ rel @ panel_frame(p)
        K = scaled(K, s)
        e = K.to_euler("YZX")
        pb.location = K.to_translation()
        pb.rotation_euler = e
        if p.hinge is not None and p.hinge.kind == "SLIDE":
            _slide_drivers(rig, pb, p.hinge, K, s)
        elif p.hinge is not None:
            _driver(rig, pb, p.hinge, e.y, t0)
        if getattr(p, "lift", 0.0) and p.hinge is not None:
            _lift_drivers(rig, pb, K, p.lift * s, model.tmax, t0,
                          None if p.lift_dir is None else
                          p.hinge.Hp.to_3x3().inverted() @ p.lift_dir)
    rig.hide_set(hidden)
    if prev_active is not None and prev_active.name in view_layer.objects:
        view_layer.objects.active = prev_active
    if prev_mode not in ("OBJECT", "EDIT_ARMATURE"):
        mode = {"POSE": "POSE", "PAINT_TEXTURE": "TEXTURE_PAINT",
                "PAINT_GREASE_PENCIL": "PAINT_GREASE_PENCIL",
                "EDIT_MESH": "EDIT"}.get(prev_mode)
        if mode:
            try:
                bpy.ops.object.mode_set(mode=mode)
            except (RuntimeError, TypeError):
                pass


def _piece_bounds(model, piece):
    """The piece's face (tabs left out) in its own pattern: x0, y0, x1, y1."""
    pts = [q for n in model.pieces[piece].panels if model.panels[n].kind != "tab"
           for poly in model.panels[n].polys for q in poly]
    if not pts:
        pts = [q for n in model.pieces[piece].panels for poly in model.panels[n].polys
               for q in poly]
    if not pts:
        return [0.0, 0.0, 1.0, 1.0]
    return [round(min(q[0] for q in pts), 3), round(min(q[1] for q in pts), 3),
            round(max(q[0] for q in pts), 3), round(max(q[1] for q in pts), 3)]


def write_meta(rig, model, layout, s):
    meta = dict(
        version=1,
        mm_per_unit=1.0 / s,
        W=model.W, H=model.H,
        panels=[dict(name=n, piece=model.panels[n].piece, kind=model.panels[n].kind,
                     label=model.panels[n].label, parent=model.panels[n].parent)
                for n in model.order],
        pieces={k: dict(label=p.label, slot=p.slot, sheet=layout["on_sheet"].get(k, 0),
                        anchor=list(p.anchor), is_card=p.is_card,
                        bounds=_piece_bounds(model, k), wrap=p.wrap)
                for k, p in model.pieces.items() if p.panels},
        sheets=[dict(size=list(sh.size), origin=list(sh.origin)) for sh in layout["sheets"]],
        flaps={str(k): v for k, v in model.flaps.items()},
        roofs={str(k): v for k, v in getattr(model, "roofs", {}).items()},
        prints={k: [v for row in layout["prints"][k] for v in row]
                for k, p in model.pieces.items() if p.panels},
    )
    rig["pop_meta"] = json.dumps(meta)


# ---------------------------------------------------------------- rebuild
def rebuild(scene, force=False):
    st = scene.popup
    s = 1.0 / st.mm_per_unit
    model, layout = make_model(scene)
    rig, card, lay = ensure_objects(scene)
    mesh = card.data
    if bpy.context.mode == "EDIT_MESH" and bpy.context.edit_object in (card, lay):
        st.status = "Leave Edit Mode to rebuild"
        return model
    if not force and mesh.get("pop_hash") and mesh.get("pop_hash") != mesh_hash(mesh):
        st.edited = True
        st.status = "Panels edited by hand: Rebuild resets their shapes"
        st.warnings = "\n".join(model.warnings)
        return model
    from . import holes as _holes
    _holes.follow_layout(scene, model, layout)  # strokes stay on their pieces
    cuts = _holes.collect(scene, model, layout)
    _holes.check_joins(model, cuts)
    groups = build_mesh(mesh, model, layout, s, cuts)
    ensure_material(mesh, scene)
    for obj in (card,):
        obj.vertex_groups.clear()
        for name in model.order:
            vg = obj.vertex_groups.new(name=name)
            if groups.get(name):
                vg.add(groups[name], 1.0, "REPLACE")
    from . import art
    art.release_orphans(scene, set(model.order))
    stage = st.stage_master is not None
    # a stage opens and shuts with the carousel, which never squashes it shut
    t0 = model.close_angle(st.paper_thickness) if st.keep_open and not stage else 0.0
    rig["pop_close"] = t0
    for uid in model.flaps:
        name = pull_prop(uid)
        try:
            rig[name] = min(1.0, max(0.0, float(rig.get(name, 0.0))))  # keep it a float
        except (TypeError, ValueError):
            rig[name] = 0.0
        rig.id_properties_ui(name).update(min=0.0, max=1.0, soft_min=0.0, soft_max=1.0,
                                          description="Pull the flap's tab (0 = flat, 1 = "
                                          "fully lifted)")
    build_rig(scene, rig, model, layout, s, t0)
    ensure_solid(card, st)
    write_meta(rig, model, layout, s)
    from . import materials
    materials.apply(scene)
    from . import art as _art, colours as _colours
    _colours.heal(scene)  # flat painting colours never outlast painting
    try:
        _art.extend_tiles(scene)  # new mechanisms get their own place to paint
    except Exception as ex:  # never stop a rebuild over the paint texture
        print(f"Pop-Up Pro: art tiles not extended: {ex}")
    mesh["pop_hash"] = mesh_hash(mesh)
    st.edited = False
    st.warnings = "\n".join(model.warnings)
    st.status = f"{len(model.panels)} panels on {len(layout['sheets'])} sheet(s)"
    for o in (card, lay, rig):
        o.update_tag()
    from . import art
    art.refresh_material(scene)
    from . import images
    images.sync(scene)
    if stage:
        from . import carousel
        carousel.link_stage(scene)
    return model
