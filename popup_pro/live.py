"""Debounced rebuilds and small shared helpers."""

import json

import bpy

_pending = set()
_items_cache = []


def schedule(scene, delay=0.15):
    if scene is None or not scene.popup.live or scene.popup.rig is None:
        return
    name = scene.name
    if name in _pending:
        return
    _pending.add(name)

    def run():
        _pending.discard(name)
        sc = bpy.data.scenes.get(name)
        if sc is None:
            return None
        from . import build
        try:
            build.rebuild(sc)
        except Exception as ex:  # keep the UI alive; report in the panel
            sc.popup.status = f"Rebuild failed: {ex}"
        return None

    bpy.app.timers.register(run, first_interval=delay)


def meta(rig):
    if rig is None or "pop_meta" not in rig:
        return None
    try:
        return json.loads(rig["pop_meta"])
    except ValueError:
        return None


def panel_items(scene):
    """Enum items for panels of the current card (cached: Blender needs the
    strings to stay alive)."""
    global _items_cache
    m = meta(scene.popup.rig) if scene else None
    items = []
    if m:
        for i, p in enumerate(m["panels"]):
            if p["kind"] != "tab":
                items.append((p["name"], p["label"], "", i))
    if not items:
        items = [("NONE", "Build the card first", "", 0)]
    _items_cache = items
    return _items_cache
