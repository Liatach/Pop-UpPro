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
    # sheets a piece may go on, smallest first: the piece paper either way
    # round, then the card's sheet either way round
    sizes = []
    for sz in (piece_sheet, piece_sheet[::-1], card_sheet, card_sheet[::-1]):
        if tuple(sz) not in sizes:
            sizes.append(tuple(sz))

    def fits(o, sz):
        return o[3] <= sz[0] - 2 * margin + 1e-6 and o[4] <= sz[1] - 2 * margin + 1e-6

    sheet = None
    cx = cy = row = 0.0
    for piece in loose:
        pts = [q for n in piece.panels for poly in model.panels[n].polys for q in poly]
        opts = []
        for k in (0, 1):
            rp = [rot2(q, k * math.pi / 2) for q in pts]
            x0, y0, x1, y1 = bbox2(rp)
            opts.append((k, x0, y0, x1 - x0, y1 - y0))
        best, size = None, None
        # the current sheet first, if it's one the piece fits
        order = ([tuple(sheet.size)] if sheet is not None else []) + sizes
        for sz in order:
            ok = [o for o in opts if fits(o, sz)]
            if not ok:
                continue
            if getattr(piece, "upright", False) and ok[0][0] == 0:
                best = ok[0]  # the way up it stands (frames, stage sets)
            else:
                best = max(ok, key=lambda o: (o[3] >= o[4], -o[0]))
            size = sz
            break
        if best is None:
            size = max(sizes, key=lambda z: z[0] * z[1])
            best = min(opts, key=lambda o: max(o[3] - size[0], o[4] - size[1]))
            hint = ""
            if piece.name.startswith("Tube") and not piece.name.endswith("b"):
                hint = " (Strips: 2 cuts its walls in two)"
            model.warn(f"{piece.label}: bigger than the print sheet{hint}")
        elif size != tuple(piece_sheet):
            model.warn(f"{piece.label}: too big for the piece paper, so it has a "
                       f"{size[0]:.0f} x {size[1]:.0f} mm sheet of its own")
        k, x0, y0, w, h = best
        if sheet is None or tuple(sheet.size) != size:
            sheet = new_sheet(size)
            cx, cy, row = margin, margin, 0.0
        SW, SH = size
        if cx + w > SW - margin and cx > margin:
            cx, cy, row = margin, cy + row + gap, 0.0
        if cy + h > SH - margin and cy > margin:
            sheet = new_sheet(size)
            cx, cy, row = margin, margin, 0.0
        ox = sheet.origin[0] + cx - x0
        oy = sheet.origin[1] + cy - y0
        prints[piece.name] = place(k * math.pi / 2, ox, oy)
        on_sheet[piece.name] = sheet.index
        cx += w + gap
        row = max(row, h)
    return dict(sheets=sheets, prints=prints, on_sheet=on_sheet)
