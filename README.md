# Pop-Up Pro

**Design pop-up cards and books in Blender, test the movement, and print
them.**

![Pop-Up Pro](docs/images/hero.png)

## Features

* **Preset mechanisms** you tune with sliders: V-folds (panels or beaks),
  cut-in mouths, glued box folds and cut-in box layers.
* **Stack them**: boxes on boxes, steps up and forward, and inset (valley)
  boxes; V-folds and mouths sit on any box fold too.
* **Movement test**: one Open slider (0–180°) drives a driver-only rig, with
  no Python auto-run needed. One click keyframes open-and-close.
* **Art stays on the paper**: paint flat or folded (Texture Paint or Paint
  System), or sketch with Grease Pencil on any panel, and it rides along.
* **Checks** as you design: tearing V-folds, panels poking through the card,
  pieces sticking out when closed, overlapping glue and cuts.
* **Print sheets** as layered SVG, plus cut-only and crease-only files for
  Cricut and other cutting machines.
* **Card sizes**: folded A6–A3, US Letter sizes, 5×7 in, and common
  picture-book trims.

![Movement test](docs/images/movement.gif)

## Install

1. Download `popup_pro-x.y.z.zip` from
   [Releases](https://github.com/Liatach/Pop-UpPro/releases), or build it
   with `scripts/build.sh`.
2. In Blender 4.3 or later: **Edit → Preferences → Get Extensions → ⌄ →
   Install from Disk**.
3. Open the sidebar (**N**) in the 3D view and pick the **Pop-Up** tab.

Upgrading from *Pop-up Mechanics* 0.1–0.2: uninstall it first, since Blender
treats the renamed add-on as a separate extension. Your cards keep their
mechanisms, art and sketches.

## Use

1. **Card**: A5 (A4 folded, the default), A6, 150 mm square or custom.
   **Hold** picks which page stays still (right page flat is the usual 90°
   view; *Both Pages Move* keeps the spine upright).
2. **Build Card**. The first build adds a V-fold and a box fold to play with.
3. **Mechanisms**: add, remove and tune them. With **Live Rebuild** on (the
   clock icon) the card updates as you drag values.
4. **Open**: slider and 0/45/90/135/180° buttons; **Keyframe Movement Test**
   animates closed → flat → closed.
5. **Checks** lists problems found by sweeping the open angle: paper that
   would tear, panels poking through a page, pieces sticking out of the
   closed card, pieces too big for the sheet.
6. **Export SVG Sheets** writes one SVG per sheet.

### Closing and paper thickness

* **Paper Thickness** (default 0.3 mm, typical card stock).
* **Stop at Paper Thickness** (on by default): Open 0 is where the pages meet
  the folded mechanisms, not 0°, so a closed card doesn't squash everything
  through itself. The sidebar shows the angle it stops at. Turn it off for a
  card that closes to exactly 0°.
* **Solid Paper**: gives the card real thickness (behind the printed side)
  for renders. Modifiers you add to the card after it are kept on rebuild.

### Card sizes

A6, A5, A4 and A3 (from a folded A5, A4, A3 and A2), Half Letter and Letter
(folded US Letter and Tabloid), a 5 x 7 in greeting card, 150 mm square, the
common picture-book trims (8.5 x 8.5, 8 x 10, 10 x 8, 7.5 x 7.5 and
8.5 x 11 in), or Custom. Loose pieces go on the **Piece Paper** sheet, which
includes 12 x 12 and 12 x 24 in cutting mats.

### Mechanisms (all lengths in mm)

| | What it is | Settings |
|---|---|---|
| **V-fold** | A folded piece glued along two lines that meet on a fold | Position, Fold Length, Glue Length, Glue Angle (fold to glue line), Piece Angle (centre fold to glue edge), tab size and side, symmetric or separate left/right. **Shape: Panels or Beak** (two triangles meeting at a point) |
| **Mouth** | A slit across a fold with two pairs of triangles cut into the paper; the jaws open as the card opens | Slit Position, Jaw Length (slit each side of the fold), Upper Jaw, Lower Jaw |
| **Box fold** | A separate strip glued across a fold (parallel fold) | Position, Width, Height (up the left panel), Depth (across the right panel), tab size |
| **Box layer** | The same parallel fold cut into the paper itself | Position, Width, Height, Depth |

### Stacking: Host and Where

Every mechanism sits on a **Host**: the card spine, or any box. On a box,
**Where** picks which of its three folds:

* **On Top**: on the box's top, against the back panel (a step up).
* **In Front**: on the floor, against the box's front (a step forward).
* **Inset**: pushed into the box's outer corner. Its folds reverse (valley
  in the middle, mountains at the sides) and it opens inside the box, which
  makes doorways, windows and recesses.

Boxes stack as deep as you like, and V-folds and mouths can sit on a box
fold too. Cut-in mechanisms (box layers, mouths) need both sides of the fold
to be one piece of paper: any fold of a box layer, or the inset fold of a
glued box. Glued mechanisms can go anywhere.

![Stacked boxes, inset, beak and mouth](docs/images/stacked.png)

Rules of thumb the checks enforce: a V-fold's piece angle must be at least
its glue angle, or it tears before the card is flat; a box on the spine must
have height + depth within the page width; nothing may stick out of the
closed card or poke through a page; glue tabs and cut-outs on the same paper
must not overlap; and a tab must not land on a hole.

## Artwork that stays on the paper

Everything is one mesh, **Pop-up Card**, deformed by **Pop-up Rig**. Its rest
shape is the print layout, which you also see as **Pop-up Layout** (same
mesh, no rig). So:

* **Paint Flat / Paint Folded** opens Texture Paint on the layout or on the
  folded card. The paint goes into **Pop-up Art**, a UDIM image with one
  tile per piece (tile 1001 is the card), and shows on both.
* **Paint System**: paint the Layout or Card object and choose the
  **PopupArt** UV map for its layers. Then **Bake Art for Print** flattens
  whatever the material shows into **Pop-up Print** for the export. The bake
  works on temporary copies of the layout and its materials, so your
  materials and render settings are never changed.
* **Sketch on Panel** (Grease Pencil): pick a panel and press the button.
  It makes a layer on **Pop-up Sketch** parented to that panel's bone, sets
  the stroke placement to *Surface* and turns the view to face the panel.
  Strokes ride along as the card moves and survive rebuilds, and export as
  vector paths.
* **Editing shapes**: edit the Layout object in Edit Mode (cut an arch into
  a box front, round the top of a V-fold) and the folded card follows. A
  hand-edited card stops live rebuilding; **Rebuild** resets the shapes.

## Export

The **Export** panel (also shown in the file dialog) sets:

* **Content**:
  * *Print*: art, glue guides, labels and every line.
  * *Art + Cut Lines* (`_art`): art outlined by cut lines only, with no fold
    lines, guides or labels over the art.
  * *Cut Lines Only* (`_cut`), *Crease Lines Only* (`_crease`), *Cut +
    Crease* (`_lines`, creases red so they import as their own colour layer):
    plain solid strokes for cutting machines, with no art or text. For a
    Cricut, export Cut and Crease separately, upload both, set the crease
    file to *Score*, and attach them.
* **Colour Tabs**: glue tabs are paper white unless you tick this and pick a
  colour.
* **Bleed** (mm, off by default): the art runs that far past each piece's
  outline so a slightly-off cut doesn't show white.
* **Lines**: *Default* (black cuts, red mountain dash-dot, blue valley
  dashed), *Custom Colour* (one colour at your opacity, e.g. white at 40%
  over dark art), or *No Lines* (kept as hidden layers).
* **Line Width** in mm, and **Dashed Folds** (turn off for cutting machines,
  which treat each dash as a separate cut).

Sheet 1 is the card; loose pieces are packed onto further sheets. Each SVG
has Inkscape layers for art, sketch, glue, guides, valley, mountain, cut and
labels. Folds and slits are read from the actual mesh, so hand-edited
outlines print as edited. Glue guides (dotted) are drawn on whichever piece
each tab glues to.

| Card sheet | Stacked layers sheet |
|---|---|
| ![](docs/images/sheet1.png) | ![](docs/images/stacked_sheet.png) |

## How it works

* `core/model.py` solves each mechanism as rigid panels on a *host*: a fold
  between two panels whose opening always equals the card's. Every box
  fold makes three new hosts. A box is a parallelogram (each panel stays
  parallel to one side of its host). V-folds, beaks and both jaws of a
  mouth are V joints: the crease is the unit vector making the piece's
  fixed angles with both glue lines, on the branch that reaches into the
  host's gap.
* Cut-in mechanisms carve their outline out of the host paper (convex
  pieces), so you can stack them.
* Each hinge's angle is written as a Blender driver on the bone's
  `rotation_euler[1]` (YZX order, so a constant offset can sit in X and Z).
  Box folds are linear in the open angle; V-folds use
  `atan2(b,a) ± acos(d/√(a²+b²))`, where a, b and d are helper properties
  driven by the open angle (Blender caps expressions at 256 characters).
  All are simple expressions, so the rig works without enabling Python
  auto-run. The formulas are checked against the solved geometry at every
  build.
* The open angle is the `pop_open` property on the rig (degrees).

## Development

```bash
python tests/test_core.py      # kinematics, stacking, overlap checks (needs: pip install bpy)
python tests/test_blender.py   # end to end in Blender
python tests/test_v04.py       # closing stop, solid paper, exports, safe bakes
```

## Limits and roadmap

* One card per scene. Mechanisms sit on the spine or on box folds, not yet on
  V-folds.
* The checks look at paper footprints, but not at 3D collisions between
  separate mechanisms.
* Next mechanisms: floating layers and pedestals, V-folds on V-folds, arch
  V-folds, moving arms, pull tabs.
* Paint System with UDIM tiles is untested; Bake Art for Print is the safe
  route for printing.


## Licence

GPL-3.0-or-later. By Kim Lang / [Liatach Makes](https://shop.kim-lang.com).
A companion to [Papercraft Pro](https://github.com/Liatach/papercraft-pro).
Pop-Up Pro is not affiliated with or endorsed by the Blender Foundation.
