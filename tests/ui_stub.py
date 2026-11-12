"""Stand-ins for a UILayout and a panel, so tests can run a panel's or menu's
draw without a window and see what it showed (test_ui_draw, test_placement)."""
import inspect
import types

import bpy


class Layout:
    """Stands in for a UILayout: any call is noted and gives another one
    (lay.panel gives a header and a body), any attribute can be set."""

    def __init__(self, log, path="layout"):
        object.__setattr__(self, "log", log)
        object.__setattr__(self, "path", path)

    def __getattr__(self, name):
        def call(*args, **kw):
            child = f"{self.path}.{name}{len(self.log)}"
            self.log.append((self.path, name, args, kw))
            if name in ("panel", "panel_prop"):
                return Layout(self.log, child), Layout(self.log, child)
            return Layout(self.log, child)
        return call

    def __setattr__(self, name, value):
        self.log.append((self.path, "set", (name, value), {}))


class Drawn:
    """Stands in for a panel or menu: its class's own methods, on our layout."""

    def __init__(self, cls, layout):
        self._cls, self.layout = cls, layout

    def __getattr__(self, name):
        a = inspect.getattr_static(self._cls, name)
        return types.MethodType(a, self) if isinstance(a, types.FunctionType) else \
            getattr(self._cls, name)


def draw(cls):
    log = []
    cls.draw(Drawn(cls, Layout(log)), bpy.context)
    return log


def props_shown(log):
    return [e[2][1] for e in log if e[1] == "prop" and len(e[2]) > 1]


def adds_offered(log):
    """The settings of each popup.add the menu offers."""
    out = []
    for i, e in enumerate(log):
        if e[1] == "operator" and e[2][0] == "popup.add":
            op = f"{e[0]}.operator{i}"
            out.append({s[2][0]: s[2][1] for s in log if s[0] == op and s[1] == "set"})
    return out
