"""Plan view, continued: where two pieces of paper actually pass through each
other at the plan view's opening, drawn as bright lines on top (squashed
flat with the rest), and listed in the panel. Viewport only."""

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import intersect_ray_tri

from .naming import N

OBJ = "Pop-up Clashes"
MAT = "Pop-up Clash"
EDGE_MM = 0.05  # a meeting along an edge (a hinge, a fold resting on a page) isn't a clash
WIDTH_MM = 0.9
TAB_THROUGH_MM = 1.0  # how far right through a glue tab something must go to count


def _seg_tri(a, b, tri):
    """Where segment a-b passes through triangle tri, or None."""
    d = b - a
    L = d.length
    if L < 1e-12:
        return None
    p = intersect_ray_tri(tri[0], tri[1], tri[2], d / L, a, True)
    if p is None:
        p = intersect_ray_tri(tri[0], tri[2], tri[1], d / L, a, True)
    if p is None:
        return None
    s = (p - a).dot(d) / (L * L)
    return p if -1e-9 <= s <= 1.0 + 1e-9 else None


def _dist_to_edges(p, tri):
    best = 1e30
    for i in range(3):
        a, b = tri[i], tri[(i + 1) % 3]
        d = b - a
        L2 = d.length_squared
        s = 0.0 if L2 < 1e-18 else max(0.0, min(1.0, (p - a).dot(d) / L2))
        best = min(best, (a + d * s - p).length)
    return best


def tri_tri(A, B, eps):
    """The segment two triangles cross along, or None (touching along an
    edge or lying flat on each other doesn't count)."""
    na = (A[1] - A[0]).cross(A[2] - A[0])
    nb = (B[1] - B[0]).cross(B[2] - B[0])
    if na.length < 1e-12 or nb.length < 1e-12:
        return None
    if abs(na.normalized().dot(nb.normalized())) > 0.9995:
        return None  # parallel: resting on each other, not through
    pts = []
    for T, U in ((A, B), (B, A)):
        for i in range(3):
            p = _seg_tri(T[i], T[(i + 1) % 3], U)
            if p is not None and all((p - q).length > 1e-7 for q in pts):
                pts.append(p)
    if len(pts) < 2:
        return None
    # the two farthest apart
    best = max(((pts[i], pts[j]) for i in range(len(pts)) for j in range(i + 1, len(pts))),
               key=lambda pq: (pq[0] - pq[1]).length)
    p, q = best
    if (p - q).length < eps:
        return None
    mid = 0.5 * (p + q)
    if _dist_to_edges(mid, A) < eps or _dist_to_edges(mid, B) < eps:
        return None  # along an edge: a hinge, or a fold lying on a page
    return p, q


def _shown_mesh(scene):
    """The card as it stands (card-local coordinates), without the plan
    view's squash or the visibility settings: (verts, tris, tri panel)."""
    st = scene.popup
    card = st.card
    from . import debug, visibility
    off = []
    for name in (debug.MOD, visibility.MOD):
        mod = card.modifiers.get(name)
        if mod is not None and mod.show_viewport:
            mod.show_viewport = False
            off.append(mod)
    try:
        dg = bpy.context.evaluated_depsgraph_get()
        dg.update()
        ev = card.evaluated_get(dg)
        me = ev.to_mesh()
        n0 = len(card.data.polygons)  # (Solid Paper's back shell comes after)
        vals = [0] * len(me.polygons)
        at = me.attributes.get("pop_panel")
        if at is not None and at.domain == "FACE":
            at.data.foreach_get("value", vals)
        V = [v.co.copy() for v in me.vertices]
        tris, tp = [], []
        for i, poly in enumerate(me.polygons[:n0]):
            vs = list(poly.vertices)
            for k in range(1, len(vs) - 1):
                tris.append((vs[0], vs[k], vs[k + 1]))
                tp.append(vals[i])
        ev.to_mesh_clear()
    finally:
        for mod in off:
            mod.show_viewport = True
    return V, tris, tp


def find(scene, limit=4000):
    """[(point, point, panel a, panel b)] in card-local coordinates."""
    st = scene.popup
    if st.card is None or st.rig is None:
        return []
    from . import live
    meta = live.meta(st.rig)
    if meta is None:
        return []
    from .core.align import uid_of
    kinds = [p["kind"] for p in meta["panels"]]
    mech = [uid_of(p["name"]) or 0 for p in meta["panels"]]
    s = 1.0 / st.mm_per_unit
    V, tris, tp = _shown_mesh(scene)
    if not tris:
        return []
    bvh = BVHTree.FromPolygons(V, tris)
    out = []
    eps = EDGE_MM * s
    for i, j in bvh.overlap(bvh):
        if i >= j or tp[i] == tp[j]:
            continue
        if set(tris[i]) & set(tris[j]):
            continue  # neighbours meeting at a fold
        a_, b_ = tp[i], tp[j]
        if a_ < len(kinds) and b_ < len(kinds) and "tab" in (kinds[a_], kinds[b_]) and \
                mech[a_] == mech[b_]:
            continue  # a glue tab against its own mechanism's paper
        A = [V[k] for k in tris[i]]
        B = [V[k] for k in tris[j]]
        graze = False
        for T, U, kk in ((A, B, a_), (B, A, b_)):
            if kk < len(kinds) and kinds[kk] == "tab":
                # a tab is glued flat on something: a panel hinged where it
                # lies cuts it by a hair; only going right through counts
                n = (T[1] - T[0]).cross(T[2] - T[0]).normalized()
                d = [(q - T[0]).dot(n) for q in U]
                if min(d) > -TAB_THROUGH_MM * s or max(d) < TAB_THROUGH_MM * s:
                    graze = True
        if graze:
            continue
        seg = tri_tri(A, B, eps)
        if seg is None:
            continue
        out.append((seg[0], seg[1], tp[i], tp[j]))
        if len(out) >= limit:
            break
    return out


def _material():
    mat = bpy.data.materials.get(MAT) or bpy.data.materials.new(MAT)
    mat.diffuse_color = (1.0, 0.0, 0.85, 1.0)  # (not one of the plan view's colours)
    return mat


def show(scene, axis, keep):
    """Draw the clashes as thin ribbons, squashed with the plan view; returns
    the pairs of mechanism labels that clash."""
    st = scene.popup
    card = st.card
    name = N(scene, OBJ)
    obj = bpy.data.objects.get(name)
    segs = find(scene) if (st.plan_view and st.plan_clashes) else []
    if not segs:
        if obj is not None:
            me = obj.data
            bpy.data.objects.remove(obj)
            if me.users == 0:
                bpy.data.meshes.remove(me)
        scene["pop_clashes"] = []
        return []
    s = 1.0 / st.mm_per_unit
    ax = Vector(axis).normalized()

    def squash(p):
        return p - ax * (p.dot(ax) * (1.0 - keep))

    verts, faces = [], []
    w = 0.5 * WIDTH_MM * s
    for p, q, _, _ in segs:
        p, q = squash(p), squash(q)
        d = q - p
        side = ax.cross(d)
        if side.length < 1e-12:
            continue
        side = side.normalized() * w
        k = len(verts)
        verts += [p - side, q - side, q + side, p + side]
        faces.append((k, k + 1, k + 2, k + 3))
    if obj is None:
        me = bpy.data.meshes.new(name)
        obj = bpy.data.objects.new(name, me)
        for c in card.users_collection:
            c.objects.link(obj)
            break
    me = obj.data
    me.clear_geometry()
    me.from_pydata(verts, [], faces)
    me.update()
    if not me.materials:
        me.materials.append(_material())
    obj.matrix_world = card.matrix_world.copy()
    obj.show_in_front = True
    obj.hide_render = True
    obj.hide_select = True
    obj.color = (1.0, 0.0, 0.85, 1.0)
    from .core.align import uid_of
    from . import live
    names = [p["name"] for p in live.meta(st.rig)["panels"]]
    labels = {m.uid: m.label for m in st.mechs}
    pairs = set()
    for _, _, a_, b_ in segs:
        la = labels.get(uid_of(names[a_]) or 0, "Card") if a_ < len(names) else "?"
        lb = labels.get(uid_of(names[b_]) or 0, "Card") if b_ < len(names) else "?"
        pairs.add(tuple(sorted((la, lb))))
    pairs = sorted(pairs)
    scene["pop_clashes"] = [f"{a} ↔ {b}" if a != b else f"{a} (through itself)"
                            for a, b in pairs]
    return pairs


def clear(scene):
    obj = bpy.data.objects.get(N(scene, OBJ))
    if obj is not None:
        me = obj.data
        bpy.data.objects.remove(obj)
        if me.users == 0:
            bpy.data.meshes.remove(me)
    if "pop_clashes" in scene:
        del scene["pop_clashes"]
