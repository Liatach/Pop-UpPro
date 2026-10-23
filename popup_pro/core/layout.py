"""Print layout: the card fills sheet 1, loose pieces are shelf-packed onto
further sheets. Each piece gets a rigid 2D placement (a 4x4 matrix that maps
its pattern space onto the layout plane, in millimetres).

Sheets sit in a row in front of the assembled card (towards -Y), so the
layout and the folded card can be seen side by side."""

import math

from mathutils import Matrix

from .geom import bbox2, rot2

SHEET_GAP = 20.0
LAYOUT_DROP = 40.0


class Sheet:
    def __init__(self, index, size, origin):
        self.index = index
        self.size = size
        self.origin = origin  # lower-left corner in layout mm


def place(rot, dx, dy):
    m = Matrix.Rotation(rot, 4, "Z")
    m[0][3], m[1][3] = dx, dy
    return m


def build_layout(model, margin=8.0, gap=6.0):
    card_sheet = tuple(model.card.get("sheet", (2 * model.W, model.H)))
    piece_sheet = tuple(model.card.get("piece_sheet", card_sheet))
    sheets = []
    prints = {}
    on_sheet = {}

    def new_sheet(size):
        if sheets:
            last = sheets[-1]
            x = last.origin[0] + last.size[0] + SHEET_GAP
        else:
            x = -size[0] / 2.0
        s = Sheet(len(sheets), size, (x, -size[1] - LAYOUT_DROP))
        sheets.append(s)
        return s

    # sheet 1: the card, centred
    s0 = new_sheet(card_sheet)
    W, H = model.W, model.H
    prints["Card"] = place(0.0, s0.origin[0] + card_sheet[0] / 2.0,
                           s0.origin[1] + (card_sheet[1] - H) / 2.0)
    on_sheet["Card"] = 0

    loose = [p for p in model.pieces.values() if not p.is_card and p.panels]
    loose.sort(key=lambda p: p.slot)
    sheet = None
    cx = cy = row = 0.0
    for piece in loose:
        pts = [q for n in piece.panels for poly in model.panels[n].polys for q in poly]
        best = None
        for k in (0, 1):
            rp = [rot2(q, k * math.pi / 2) for q in pts]
            x0, y0, x1, y1 = bbox2(rp)
            w, h = x1 - x0, y1 - y0
            if best is None or (w >= h and best[3] < best[4]):
                best = (k, x0, y0, w, h)
        k, x0, y0, w, h = best
        SW, SH = piece_sheet
        if sheet is None:
            sheet = new_sheet(piece_sheet)
            cx, cy, row = margin, margin, 0.0
        if cx + w > SW - margin and cx > margin:
            cx, cy, row = margin, cy + row + gap, 0.0
        if cy + h > SH - margin and cy > margin:
            sheet = new_sheet(piece_sheet)
            cx, cy, row = margin, margin, 0.0
        if w > SW - 2 * margin or h > SH - 2 * margin:
            model.warn(f"{piece.label}: bigger than the print sheet")
        ox = sheet.origin[0] + cx - x0
        oy = sheet.origin[1] + cy - y0
        prints[piece.name] = place(k * math.pi / 2, ox, oy)
        on_sheet[piece.name] = sheet.index
        cx += w + gap
        row = max(row, h)
    return dict(sheets=sheets, prints=prints, on_sheet=on_sheet)
