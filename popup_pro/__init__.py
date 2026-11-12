"""Pop-Up Pro: design pop-up cards and books in Blender with movement tests.
V-folds, box folds and cut-in box layers on a folded card, a driver rig
that animates the open angle, art that stays on the paper, and print SVGs."""

import bpy

from . import arrange, debug, highlight, history, holes, images, materials, ops, props, scene_setup, ui


def register():
    props.register()
    ops.register()
    arrange.register()
    materials.register()
    scene_setup.register()
    images.register()
    ui.register()
    highlight.register()
    debug.register()
    history.register()
    holes.subscribe()
    if holes.subscribe not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(holes.subscribe)
    if props.on_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(props.on_load)


def unregister():
    debug.unregister()
    highlight.unregister()
    history.unregister()
    holes.unsubscribe()
    if holes.subscribe in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(holes.subscribe)
    if props.on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(props.on_load)
    ui.unregister()
    images.unregister()
    scene_setup.unregister()
    materials.unregister()
    arrange.unregister()
    ops.unregister()
    props.unregister()
