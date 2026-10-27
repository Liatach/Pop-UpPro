"""Pop-Up Pro: design pop-up cards and books in Blender with movement tests.
V-folds, box folds and cut-in box layers on a folded card, a driver rig
that animates the open angle, art that stays on the paper, and print SVGs."""

import bpy

from . import highlight, holes, images, ops, props, scene_setup, ui


def register():
    props.register()
    ops.register()
    scene_setup.register()
    images.register()
    ui.register()
    highlight.register()
    holes.subscribe()
    if holes.subscribe not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(holes.subscribe)


def unregister():
    highlight.unregister()
    holes.unsubscribe()
    if holes.subscribe in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(holes.subscribe)
    ui.unregister()
    images.unregister()
    scene_setup.unregister()
    ops.unregister()
    props.unregister()
