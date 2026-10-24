# Pop-Up Pro

**Design pop-up cards and books in Blender, test the movement, and print
them.**

![Pop-Up Pro](docs/images/hero.png)

## Features

* **Preset mechanisms** you tune with sliders: V-folds (panels or beaks),
  cut-in mouths, glued box folds, cut-in box layers, 180° cubes with lids,
  pull-tab flaps, tubes (hexagons, boxes) tethered together on parallel
  strips, and pyramids, tents and roofs.
* **Stack them**: boxes on boxes, steps up and forward, and inset (valley)
  boxes; V-folds and mouths sit on any box fold too.
* **Movement test**: one Open slider (0–180°) drives a driver-only rig, with
  no Python auto-run needed, and each flap has its own Pull slider. One click
  keyframes open-and-close, or a pull.
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
| **Box fold** | A separate strip glued across a fold (parallel fold) | Position, Height (along the fold), Width Left, Width Right, tab size |
| **Box layer** | The same parallel fold cut into the paper itself | Position, Height, Width Left, Width Right |
| **Cube (180°)** | A box standing on one corner edge on the fold; it rises as the card opens flat | Position, Size, Height, Lid (Peaked, Dipped or None), base tab size and side |
| **Tube** | Hexagon, box or recessed tube on two parallel sticking strips (Birmingham 51, 67, 68) | Position, Strip Distance, Side Length, Height, Front and Back Width, each Pointed Out or In, base tabs, Roof (None, Pointed, or Flat with Peak/Dip and Overhang) |
| **Tether** | Wall from a tube's corner or crease to another tube or to a foot on a strip | From (tube and point), To (another tube's point, or a foot on the left or right strip), Height, Bend, Slack |
| **Pyramid** | Pyramid, hexagonal pyramid or tent on two parallel sticking strips (Birmingham 52) | Position, Strip Distance, Base Length, Height, Ridge, Front and Back Width, each Pointed Out or In, base tabs |
| **Flap** | A lift-the-flap worked by a pull tab, with its own **Pull** slider | Page, From Spine, Up the Page, Hinge edge, Width, Length, Hinge Tab, Lift angle, Glue Point (5 mm from the hinge by default), Strip Width, Slit Gap, Pull Tab |

### Cube (180°)

Four walls in one strip with a closing tab. The two front walls are a V-fold
on the fold (45° glue lines, square corners), glued down by the base tabs;
the back walls follow as a parallelogram. The lid is two right triangles on
the front walls, creased along the diagonal and joined by a glue tab: it
rises to a ridge (Peaked) or sinks into the box (Dipped) as the card closes.
A flat one-piece lid can't fold, so the lid is always two triangles.

### Tubes and tethers (parallel sticking strips)

A tube's side walls are glued to two strips parallel to the fold, the same
distance either side of it. Its front and back are pairs of walls whose
creases stay vertical above the fold, so the tube stays upright and folds
flat. A pair as wide as the strip distance gives a flat face when the card is
open flat (a box); wider pairs point out (a hexagon) or in (a recess).

Every wall in this family leans together, halfway between the pages, and
every crease stays parallel, so one tube can pull others into shape:

* **Tethers** join a tube's corner or crease to another tube's, or to a small
  foot glued on a strip. A tether stays flat (no crease) when its ends keep
  the same distance apart, such as two corners on the same strip. Otherwise
  it gets a crease, sized so it still folds flat when the card shuts, for
  example a tether crossing the centre. **Bend** picks the side the crease
  goes (Auto keeps it between the strips).
* All tubes joined by tethers must share the same **Strip Distance**: a strip
  further out sits lower, so the walls would have to slide.
* Anything standing at strip level must stay between the two strips, or it
  would pass under the pages as the card closes. The checks warn if a tether
  swings outside.
* Tethers whose ends would collide, or meet head-on along the fold as the
  card shuts, can't fold flat and are refused.

Their fold angles are solved when the card is built and stored in the rig as
driver curves (sampled every degree, more finely where needed), so the rig
still needs no scripts.

### Pyramids, tents and roofs (Birmingham 52)

![A hexagonal tower with a pyramid cap, a house with a ridge roof and a
pyramid, opening](docs/images/roofs.jpg)

A pyramid's two sloping sides are glued to the same pair of strips as a
tube, and meet above the fold at an apex. Give it a **Ridge** and it becomes
a tent: a ridge as long as the base gives upright gable ends, a shorter one a
hipped roof. Each end is a pair of triangles creased down the middle above
the fold. Its bottom edge floats free, as in the book, and the ends fold flat
as the card shuts. **Front** and **Back Width** shape the ends just as on a
tube: as wide as the strip distance gives a flat end, wider points it out
(a hexagonal pyramid) or, Pointed In, tucks it in. A flat end can crease
either way as the card starts to close; Pointed Out sends the crease
outwards, Pointed In tucks it under.

A tube can wear the same roof: set its **Roof** to *Pointed* and choose
**Roof Height** and **Ridge**. The roof is a separate piece whose tabs glue
inside the top of the side walls. Lying flat, a roof adds its slope length to
the tube's height, and the checks warn if that runs past the page edge.

**Flat** roofs are two halves creased straight down the middle above the
fold. Tabs folded in off the tops of the side walls are glued underneath, so
the roof can **Overhang** the walls all round, like eaves.

![Flat roof with an overhang: Peak (top) and Dip (bottom) at 180, 130 and
80 degrees](docs/images/flat_roof.jpg)

* **Peak**: the centre crease rises as the card closes and the halves stand
  up when shut. This adds the strip distance to how far the tube reaches
  out.
* **Dip**: the centre crease sinks into the tube and the halves tuck down
  inside the walls, so nothing extra sticks out. This needs walls at least
  as tall as the strip distance, and ends that don't point in.

### Flap and the Pull control

The flap is glued down by a tab along its hinge. A strip is glued under the
flap at the **Glue Point**. It runs back through a slit in the page, behind
the page, and out past the card edge as a pull tab. Pulling it lifts the
flap, which swings over towards the side you pull. Gluing the strip close to
the hinge lifts the flap furthest for the least pull.

Each flap has a **Pull** slider (0–1) and **Keyframe Pull Test**, separate
from the card's Open slider, so you can animate both. The checks warn when the
strip would run across the spine, or the pull tab is too short for the travel.
The strip runs behind the page, so glue a backing card behind it, leaving the
edge open where the tab comes out.

### Stacking: Host and Where

Every mechanism sits on a **Host**: the card spine, or any box. On a box,
**Where** picks which of its three folds:

* **On Top**: on the box's top, against the back panel (a step up).
* **In Front**: on the floor, against the box's front (a step forward).
* **Inset**: pushed into the box's outer corner. Its folds reverse (valley
  in the middle, mountains at the sides) and it opens inside the box, which
  makes doorways, windows and recesses.

Boxes stack as deep as you like, and V-folds and mouths can sit on a box
fold too. With a box selected, the **+** menu has *Inset Box Layer*, *Box
Layer on Top*, *Box Layer in Front* and the glued equivalents, which add
straight onto it. Whenever you pick a host and fold, the mechanism is
resized to half the host's panels and centred on it, so there's paper left
round it to read as a step or a recess. Each mechanism's warnings show under
its settings. Cut-in mechanisms (box layers, mouths) need both sides of the fold
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

Some tabs glue to the back of a piece, for example a roof's tabs inside a
tube's walls or a flat roof's tabs under the roof. Their guides are kept off
the art, and with **Reverse Sides** on, those sheets get a mirrored
`_sheetN_reverse.svg`. It shows faint outlines of every piece, the glue
markers, and labels reading *BACK of ...*. Print it on the other side of the
sheet (double-sided: flip on the long edge for portrait sheets, the short
edge for landscape), or hold the sheets up to the light and trace the
markers. Pieces that have markers on the back say so in their label.

![A sheet of roof pieces and its reverse](docs/images/reverse.png)

**Assembly Page** (`_layout.svg`) shows the open card with each part's glue
footprint shaded and numbered, plus a parts list: which sheet each part is
on, and what its tabs glue to.

![Assembly page](docs/images/assembly.png)

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
python tests/test_v05.py       # 180° cube, pull-tab flaps, stacking
python tests/test_v06.py       # tubes and tethers on parallel strips
python tests/test_roofs.py     # pyramid, tent, hip, tube-cap and flat-roof kinematics
python tests/test_v07.py       # roofs end to end, reverse sheets, assembly page
```

## Limits and roadmap

* One card per scene. Mechanisms sit on the spine or on box folds, not yet on
  V-folds.
* The checks look at paper footprints, but not at 3D collisions between
  separate mechanisms.
* Next mechanisms: the 90° box with lid, floating layers on pedestals,
  V-folds on V-folds, arch V-folds, moving arms.
* Paint System with UDIM tiles is untested; Bake Art for Print is the safe
  route for printing.


## Licence

GPL-3.0-or-later. By Kim Lang / [Liatach Makes](https://shop.kim-lang.com).
A companion to [Papercraft Pro](https://github.com/Liatach/papercraft-pro).
Pop-Up Pro is not affiliated with or endorsed by the Blender Foundation.
