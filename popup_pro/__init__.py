"""Pop-Up Pro: design pop-up cards and books in Blender with movement tests.
V-folds, box folds and cut-in box layers on a folded card, a driver rig
that animates the open angle, art that stays on the paper, and print SVGs."""

from . import ops, props, ui


def register():
    props.register()
    ops.register()
    ui.register()


def unregister():
    ui.unregister()
    ops.unregister()
    props.unregister()
