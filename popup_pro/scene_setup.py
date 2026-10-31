"""Set Up Scene: viewport and EEVEE settings that suit pop-up work.

Light, sharp and easy to read: Material Preview lit by Blender's dawn HDRI
(sunrise.exr), a sun lamp for crisp shadows inside the stage, faint fold
lines where panels meet at an angle, and EEVEE's cheap screen-space
ambient occlusion in the creases (no full ray tracing, no blur filters).
Shadows and creases are what tell a valley from a mountain fold at a
glance, which wards off the inside-out (Necker cube) illusion."""
import math

import bpy

HDRI = "sunrise.exr"
SUN = "Pop-up Sun"
GRAIN = "Pop-up Paper Texture"


def popup_scenes(scene):
    """The scene, and with a carousel all its stages (or a stage's carousel)."""
    from . import carousel
    st = scene.popup
    master = st.stage_master or scene
    out = [master]
    if master.popup.is_carousel:
        out += carousel.stages(master)
    if scene not in out:
        out.append(scene)
    return out


def eevee(scene):
    scene.render.engine = "BLENDER_EEVEE"
    e = scene.eevee
    e.taa_samples = 16  # converges to a sharp image when the view stops
    e.use_taa_reprojection = True
    # screen-space AO in the creases; nothing traced (paper is matt, so every
    # surface takes the fast path) and no bilateral blur
    e.use_raytracing = True
    e.ray_tracing_method = "PROBE"
    r = e.ray_tracing_options
    r.trace_max_roughness = 0.0
    r.resolution_scale = "2"
    r.use_denoise = True
    r.denoise_spatial = True
    r.denoise_temporal = True
    r.denoise_bilateral = False
    e.use_fast_gi = True
    e.fast_gi_method = "AMBIENT_OCCLUSION_ONLY"
    e.fast_gi_resolution = "2"  # 1/2 resolution: crisp (1/8 looks smeared)
    e.fast_gi_step_count = 4
    e.fast_gi_ray_count = 2
    e.fast_gi_quality = 0.25
    mm = 1.0 / _mm_per_unit(scene)
    e.fast_gi_distance = 25.0 * mm  # creases and corners, not the whole stage
    e.fast_gi_thickness_near = 2.0 * mm
    e.fast_gi_bias = 0.05
    # shadows: one sun, modest maps
    e.use_shadows = True
    e.shadow_ray_count = 1
    e.shadow_step_count = 4
    e.shadow_pool_size = "256"
    e.use_shadow_jitter_viewport = False
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"


def _mm_per_unit(scene):
    from . import live
    meta = live.meta(scene.popup.rig) if scene.popup.rig is not None else None
    if meta and meta.get("mm_per_unit"):
        return float(meta["mm_per_unit"])
    return 10.0  # the add-on builds in centimetres


def sun(scenes, strength=0.6):
    ob = bpy.data.objects.get(SUN)
    if ob is None or ob.type != "LIGHT":
        light = bpy.data.lights.new(SUN, "SUN")
        ob = bpy.data.objects.new(SUN, light)
    L = ob.data
    L.energy = strength
    L.angle = math.radians(3.0)  # a little softness, still crisp
    L.use_shadow = True
    # from above, in front and to the left of the card, as from a window
    ob.rotation_euler = (math.radians(50.0), math.radians(-20.0), math.radians(-35.0))
    for sc in scenes:
        if sc.collection.objects.get(ob.name) is None:
            sc.collection.objects.link(ob)
    return ob


WHITE = "Pop-up White"
CAMERA = "Pop-up Camera"


def camera(scene, make_active=True):
    """A camera past the bottom end of the spine, looking down along it from
    above, framed so the whole card shows from shut (standing on its spine)
    to fully open (flat, both pages out)."""
    from mathutils import Vector
    st = scene.popup
    master = st.stage_master or scene
    card = master.popup.card_dict()
    mu = _mm_per_unit(scene)
    W, H = card["W"] / mu, card["H"] / mu
    ob = bpy.data.objects.get(CAMERA)
    if ob is None or ob.type != "CAMERA":
        cam = bpy.data.cameras.new(CAMERA)
        ob = bpy.data.objects.new(CAMERA, cam)
    cam = ob.data
    cam.lens = 35.0
    cam.sensor_fit = "AUTO"
    if master.popup.is_carousel:
        # round the spine: the whole ring from above, a little in front
        target = Vector((0.0, 0.5 * H, 0.0))
        span = 2.4 * W
        aim = Vector((0.0, -0.62, 1.0)).normalized()  # from past the bottom end, above
        fov = 2.0 * math.atan(18.0 / cam.lens)  # 36 mm sensor across
        r = scene.render
        aspect = max(r.resolution_x * r.pixel_aspect_x, 1) / \
            max(r.resolution_y * r.pixel_aspect_y, 1)
        vfov = 2.0 * math.atan(math.tan(0.5 * fov) / max(aspect, 1.0))
        tall = 1.15 * (H * 0.85 + 0.6 * W)
        dist = max(0.5 * span / math.tan(0.5 * fov),
                   0.5 * tall / math.tan(0.5 * vfov)) + 0.3 * H
        ob.location = target + aim * dist
        ob.rotation_euler = (target - ob.location).to_track_quat("-Z", "Y").to_euler()
    else:
        # Kim's framing for an A5 card (297 x 210 mm open): 310 mm back from
        # the spine's bottom end, 303 mm up, tipped 58.8 degrees from looking
        # straight down; scaled with the card
        f = max(2.0 * W / 29.7, H / 21.0)
        ob.location = (0.0, -30.981 * f, 30.296 * f)
        ob.rotation_euler = (math.radians(58.82), 0.0, 0.0)
        dist = 43.3 * f
    cam.clip_start = 0.01 * dist
    cam.clip_end = 20.0 * dist
    for sc in popup_scenes(scene):
        if sc.collection.objects.get(ob.name) is None:
            sc.collection.objects.link(ob)
        if make_active:  # (a new file's own Camera would otherwise win)
            sc.camera = ob
    return ob


def look_through(context):
    """Point this window's 3D views through the card camera (orbit to leave)."""
    win = context.window
    if win is None:
        return 0
    n = 0
    for area in win.screen.areas:
        if area.type == "VIEW_3D":
            r3 = area.spaces.active.region_3d
            if r3 is not None:
                r3.view_perspective = "CAMERA"
                n += 1
    return n


def clean_render(scenes, on=True):
    """Renders lit evenly in white: the sun stays in the viewport (shadows
    while you work) but is left out of renders, and the scene's world is a
    plain white light. Painting and printing never use the lighting."""
    ob = bpy.data.objects.get(SUN)
    if ob is not None:
        ob.hide_render = on
    w = bpy.data.worlds.get(WHITE)
    if on and w is None:
        w = bpy.data.worlds.new(WHITE)
        w.use_nodes = True
        nt = w.node_tree
        bg = next((n for n in nt.nodes if n.type == "BACKGROUND"), None)
        out = next((n for n in nt.nodes if n.type == "OUTPUT_WORLD"), None)
        if bg is not None:
            bg.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
            bg.inputs["Strength"].default_value = 1.0
        if bg is not None and out is not None:
            # lit in white, but seen against a soft grey (white paper on a
            # white background would vanish)
            seen = nt.nodes.new("ShaderNodeBackground")
            seen.inputs["Color"].default_value = (0.32, 0.33, 0.35, 1.0)
            lp = nt.nodes.new("ShaderNodeLightPath")
            mix = nt.nodes.new("ShaderNodeMixShader")
            nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs[0])
            nt.links.new(bg.outputs[0], mix.inputs[1])
            nt.links.new(seen.outputs[0], mix.inputs[2])
            nt.links.new(mix.outputs[0], out.inputs["Surface"])
            lp.location = bg.location.x - 220, bg.location.y + 220
            seen.location = bg.location.x, bg.location.y - 160
            mix.location = bg.location.x + 200, bg.location.y
        w.color = (1.0, 1.0, 1.0)
    for sc in scenes:
        if on:
            old = sc.world
            if old is not None and old.name not in OURS:
                sc["pop_world_before"] = old.name
            sc.world = w
        elif sc.world is not None and sc.world.name in OURS:
            before = sc.get("pop_world_before")
            sc.world = bpy.data.worlds.get(before) if before else None


DAWN = "Pop-up Dawn"
SHOW = "Pop-up Showcase"
OURS = ("Pop-up White", DAWN, SHOW, "Pop-up Studio")
LOOKS = [
    ("CLEAN", "Clean", "Even white light, no sun: plain, flat images of the design"),
    ("SHOWCASE", "Showcase", "White light and the sun's shadows, at 64 render samples: "
     "every fold reads at a glance"),
    ("DAWN", "Dawn", "Blender's sunrise light, as in Material Preview (warm where the low "
     "sun strikes, blue where the sky does) with the sun's shadows, at 64 samples"),
    ("OWN", "Your Own", "Renders use your own world and lights; the card's sun stays in the "
     "viewport only"),
    ("STUDIO", "Studio", "A photo studio's light (Blender's studio HDRI) with the sun's "
     "shadows, at 64 samples: soft, even light with real reflections, so metallic and "
     "glossy parts shine")]
STUDIO = "Pop-up Studio"


def _sunrise_path(name="sunrise.exr"):
    import os
    p = bpy.utils.system_resource("DATAFILES", path=f"studiolights/world/{name}")
    if not p:
        p = os.path.join(bpy.utils.resource_path("LOCAL"), "datafiles", "studiolights",
                         "world", name)
    return p if p and os.path.exists(p) else None


def _seen_grey(w, light_socket):
    """Light with one thing, show the camera a soft grey (white paper on a
    bright background would vanish)."""
    nt = w.node_tree
    out = next((n for n in nt.nodes if n.type == "OUTPUT_WORLD"), None)
    if out is None:
        return
    seen = nt.nodes.new("ShaderNodeBackground")
    seen.inputs["Color"].default_value = (0.32, 0.33, 0.35, 1.0)
    lp = nt.nodes.new("ShaderNodeLightPath")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs[0])
    nt.links.new(light_socket, mix.inputs[1])
    nt.links.new(seen.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    lp.location, seen.location, mix.location = (-500, 300), (-300, -200), (100, 0)


def _show_world():
    """A softer, faintly cool sky so the sun's light and shadows read."""
    w = bpy.data.worlds.get(SHOW)
    if w is not None:
        return w
    w = bpy.data.worlds.new(SHOW)
    w.use_nodes = True
    bg = next((n for n in w.node_tree.nodes if n.type == "BACKGROUND"), None)
    if bg is not None:
        bg.inputs["Color"].default_value = (0.85, 0.9, 1.0, 1.0)
        bg.inputs["Strength"].default_value = 0.5
        _seen_grey(w, bg.outputs[0])
    return w


def _dawn_world(name=DAWN, hdri="sunrise.exr", strength=1.0):
    w = bpy.data.worlds.get(name)
    if w is not None:
        return w
    path = _sunrise_path(hdri)
    w = bpy.data.worlds.new(name)
    w.use_nodes = True
    nt = w.node_tree
    bg = next((n for n in nt.nodes if n.type == "BACKGROUND"), None)
    if bg is None:
        return w
    bg.inputs["Strength"].default_value = strength
    if path:
        env = nt.nodes.new("ShaderNodeTexEnvironment")
        env.image = bpy.data.images.load(path, check_existing=True)
        env.location = (-500, 0)
        nt.links.new(env.outputs["Color"], bg.inputs["Color"])
    _seen_grey(w, bg.outputs[0])
    w.color = (0.8, 0.75, 0.7)
    return w


KEY = "Pop-up Key Light"


def _key(scenes, sun_ob, on):
    """Showcase's own sun: renders only, stronger than the viewport's sun
    (which is balanced for Material Preview), from the same direction."""
    ob = bpy.data.objects.get(KEY)
    if not on:
        if ob is not None:
            ob.hide_render = True
        return
    if ob is None or ob.type != "LIGHT":
        light = bpy.data.lights.new(KEY, "SUN")
        ob = bpy.data.objects.new(KEY, light)
    ob.data.energy = 3.0
    ob.data.angle = math.radians(3.0)
    ob.data.use_shadow = True
    ob.rotation_euler = (sun_ob.rotation_euler.copy() if sun_ob is not None else
                         (math.radians(50.0), math.radians(-20.0), math.radians(-35.0)))
    ob.hide_viewport = True
    ob.hide_render = False
    for sc in scenes:
        if sc.collection.objects.get(ob.name) is None:
            sc.collection.objects.link(ob)


def render_look(scenes, look="CLEAN"):
    """How finished renders are lit. Painting, baking and printing never use
    the lighting; the viewport keeps its own (Material Preview, dawn)."""
    if look == "OWN":
        _key(scenes, None, False)
        clean_render(scenes, False)
        ob = bpy.data.objects.get(SUN)
        if ob is not None:
            ob.hide_render = True
        return
    clean_render(scenes, True)  # the white world, the scenes' own worlds remembered
    ob = bpy.data.objects.get(SUN)
    if ob is not None:
        ob.hide_render = look != "DAWN"
    _key(scenes, ob, look in ("SHOWCASE", "STUDIO"))
    if look in ("DAWN", "SHOWCASE", "STUDIO"):
        w = (_dawn_world() if look == "DAWN" else
             _dawn_world(STUDIO, "studio.exr", 1.2) if look == "STUDIO" else _show_world())
        for sc in scenes:
            sc.world = w
    if look in ("SHOWCASE", "DAWN", "STUDIO"):
        for sc in scenes:
            sc.eevee.taa_render_samples = max(64, sc.eevee.taa_render_samples)


def paper_texture(scenes, on=True, strength=0.12):
    """A fine procedural grain on the paper (a bump only, so the colours you
    paint and print are untouched). It lives in one node group: edit the
    group to use your own paper texture in every card."""
    grp = bpy.data.node_groups.get(GRAIN)
    if grp is None:
        grp = _grain_group()
    from .naming import N
    for sc in scenes:
        mat = bpy.data.materials.get(N(sc, "Pop-up Paper"))
        if mat is None or not mat.use_nodes:
            continue
        nt = mat.node_tree
        bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if bsdf is None:
            continue
        node = nt.nodes.get(GRAIN)
        if node is None:
            node = nt.nodes.new("ShaderNodeGroup")
            node.name = node.label = GRAIN
            node.node_tree = grp
            node.location = bsdf.location + type(bsdf.location)((-250.0, -420.0))
        node.inputs["Strength"].default_value = strength
        normal = bsdf.inputs["Normal"]
        for ln in list(normal.links):
            nt.links.remove(ln)
        if on:
            nt.links.new(node.outputs["Normal"], normal)


def _grain_group():
    grp = bpy.data.node_groups.new(GRAIN, "ShaderNodeTree")
    grp.interface.new_socket("Strength", in_out="INPUT", socket_type="NodeSocketFloat")
    grp.interface.new_socket("Normal", in_out="OUTPUT", socket_type="NodeSocketVector")
    n = grp.nodes
    gi, go = n.new("NodeGroupInput"), n.new("NodeGroupOutput")
    tc = n.new("ShaderNodeTexCoord")
    noise = n.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 40.0  # fibres about a quarter mm
    noise.inputs["Detail"].default_value = 6.0
    noise.inputs["Roughness"].default_value = 0.6
    bump = n.new("ShaderNodeBump")
    bump.inputs["Distance"].default_value = 0.002
    for i, node in enumerate((gi, tc, noise, bump, go)):
        node.location = (i * 220.0 - 440.0, 0.0)
    grp.links.new(tc.outputs["Object"], noise.inputs["Vector"])
    grp.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    grp.links.new(gi.outputs["Strength"], bump.inputs["Strength"])
    grp.links.new(bump.outputs["Normal"], go.inputs["Normal"])
    return grp


def viewports(context, all_workspaces=False, fold_lines=True):
    """Material Preview with the dawn HDRI and the sun; fold lines overlay."""
    screens = []
    win = context.window
    if all_workspaces:
        screens = [ws.screens[0] for ws in bpy.data.workspaces if ws.screens]
    elif win is not None:
        screens = [win.screen]
    n = 0
    for scr in screens:
        for area in scr.areas:
            if area.type != "VIEW_3D":
                continue
            sp = area.spaces.active
            sh = sp.shading
            sh.type = "MATERIAL"
            try:
                sh.studio_light = HDRI
            except TypeError:
                pass
            sh.use_scene_lights = True
            sh.use_scene_world = False
            sh.studiolight_intensity = 1.0
            sh.studiolight_rotate_z = 0.0
            ov = sp.overlay
            ov.show_wireframes = fold_lines
            ov.wireframe_threshold = 0.05  # only edges where panels meet at an angle
            ov.wireframe_opacity = 0.35
            n += 1
    return n


def setup(context, sun_on=True, grain=False, fold_lines=True, all_workspaces=False,
          sun_strength=0.6, clean=True, cam=True, view_camera=False, active_camera=True,
          look=None):
    scenes = popup_scenes(context.scene)
    for sc in scenes:
        eevee(sc)
    if sun_on:
        sun(scenes, sun_strength)
    else:
        ob = bpy.data.objects.get(SUN)
        if ob is not None:
            for sc in scenes:
                if sc.collection.objects.get(ob.name) is not None:
                    sc.collection.objects.unlink(ob)
    paper_texture(scenes, on=grain)
    look = look or ("CLEAN" if clean else "OWN")
    render_look(scenes, look)
    master = scenes[0]
    master.popup["clean_render"] = look != "OWN"
    master.popup["render_look"] = [k for k, *_ in LOOKS].index(look)
    views = viewports(context, all_workspaces, fold_lines)
    if cam:
        camera(context.scene, make_active=active_camera)
        if view_camera:
            look_through(context)
    for sc in scenes:
        sc["pop_setup_done"] = True
    return scenes, views


class POPUP_OT_setup_scene(bpy.types.Operator):
    """Viewport and EEVEE settings that suit pop-up work: Material Preview lit
    by the dawn HDRI, a sun for crisp shadows, fold lines, and light ambient
    occlusion in the creases. Light enough for modest graphics cards"""
    bl_idname = "popup.setup_scene"
    bl_label = "Set Up Scene"
    bl_options = {"REGISTER", "UNDO"}

    sun: bpy.props.BoolProperty(name="Sun (shadows)", default=True,
                                description="A sun lamp from above left: shadows inside the "
                                "stage show at once which way each fold goes")
    sun_strength: bpy.props.FloatProperty(name="Sun Strength", default=0.6, min=0.0,
                                          soft_max=3.0,
                                          description="Gentle: enough for shadows and a "
                                          "different shade on each panel, without burning "
                                          "the lit side to white")
    fold_lines: bpy.props.BoolProperty(name="Fold Lines", default=True,
                                       description="Faint lines where panels meet at an angle "
                                       "(the Wireframe overlay, folds only)")
    grain: bpy.props.BoolProperty(name="Paper Texture", default=False,
                                  description="A fine paper grain (a bump only; colours and "
                                  "prints untouched). Edit the 'Pop-up Paper Texture' node "
                                  "group to use your own")
    look: bpy.props.EnumProperty(name="Render Look", items=LOOKS, default="CLEAN",
                                 description="How finished renders are lit")
    cam: bpy.props.BoolProperty(name="Camera", default=True,
                                description="A camera past the bottom end of the spine, "
                                "above it, framing the whole card as it opens")
    active_camera: bpy.props.BoolProperty(name="Make It the Scene Camera", default=True,
                                          description="Render through the card camera. Off: "
                                          "keep the scene's own camera for renders (the card "
                                          "camera is still placed)")
    view_camera: bpy.props.BoolProperty(name="Look Through Camera", default=False,
                                        description="Point the 3D view through the camera "
                                        "(orbit to leave it)")
    all_workspaces: bpy.props.BoolProperty(name="All Workspaces", default=False,
                                           description="Set every workspace's 3D views, not "
                                           "just this one")

    def execute(self, context):
        scenes, views = setup(context, self.sun, self.grain, self.fold_lines,
                              self.all_workspaces, self.sun_strength, self.look != "OWN",
                              self.cam, self.view_camera, self.active_camera, self.look)
        self.report({"INFO"}, f"Set up {len(scenes)} scene(s), {views} view(s)")
        return {"FINISHED"}


classes = (POPUP_OT_setup_scene,)


def register():
    for c in classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
