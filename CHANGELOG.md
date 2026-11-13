# Pop-Up Pro: version history

Newest first. `python scripts/since_upload.py` shows what has changed since the
last upload to GitHub.

* **0.82.1**: the animal face comes a little conical, a muzzle goes on
  cones too, and its base tabs are ears (**Ear Size**), out from the loop.
* **0.82**: more of Birmingham's mechanisms. **Pop-up House** (49): a cube
  takes a gabled roof, with the book's sizes in the **+** menu. **Slotted
  Cross Piece** on a rising sheet (81): the two 45° folds as one piece
  slotted across the sheet, free to rise past it. **Box with Ends** (82): a
  box on one page pulled up by a 45° fold from the other, its ends filled
  in by pairs of 45° folds. **Animal Face** (17): a loop whose top carries
  on as a muzzle, folded back into a nose by a dart.
* **0.81.3**: **Used lately** and **Palette** now show while drawing (and
  Colour History while painting): an error in how the swatches were drawn
  cut the panel short, hiding them and the brush size, strength and ink
  layers below.
* **0.81.2**: while drawing, **Used lately** fills in as you draw (each
  stroke's colour, at once), and it and **Palette** are always shown, with a
  line saying what goes there while they're empty. **Done Drawing** is at
  the top of Artwork while you draw on the card, and no longer in Creases,
  Cuts and Holes (where it stays for drawn creases, cuts and holes).
* **0.81.1**: while drawing, the colour wheel in Artwork now sets the colour
  you draw with (it showed a colour Draw mode doesn't use). With it: a second
  colour and swap, Mix Factor, **Used lately** (colours you've drawn with,
  the latest first: click one to draw with it again) and a palette of your
  own.
* **0.81**: **Ink Layers**. What you draw with Draw Anywhere is kept as
  Grease Pencil strokes on layers you can hide, fade, reorder and remove,
  and **Edit Ink** lays them out on the flat layout to change; the paper
  is redrawn from them, so nothing is baked in. **Whole Strokes While
  Drawing** shows strokes in front of the card as you draw, not cut by
  the paper.
* **0.80**: the **+** menu in columns, one for each place things go: on the
  card's fold (V-folds, box folds, 45° folds, cubes and tubes, roofs), in a
  stage, and on what's selected.
* **0.79**: **Opens To**, for a card that stands part open (90° or 120°,
  say): the Open slider and movement test stop there, and frames, floors
  and ceilings go straight in the card, flat when it is fully open, as in
  a carousel's stage.
* **0.78**: a cone's **Lean** as an angle (it and Top Radius set each
  other) and a lid on a cone (a Flat roof, peaked or dipped); a collar's
  railing runs into the curled corner as one strip, bending where the curl
  starts instead of splitting there; clicking a warning in Checks selects
  the mechanism it's about.
* **0.77.1**: needs Blender 5.0 or later (the manifest said 4.3, but on
  Blender 4.x Draw Anywhere, the sketch layers, Set Up Scene and the rig's
  folding don't work: tested on 4.3, 4.5, 5.0 and 5.2). No change to how
  it works on 5.x; unused code cleared out with a linter.
* **0.77**: where mechanisms stand, tidied. Stands On lists only what a kind
  can stand on (zig-zags and quadrilaterals now, not fans or angled box
  folds) and picking from it starts on a fold that works; the + menu no
  longer offers what would be skipped (towers in a round tube end, an inset
  on a strap with several peaks, anything on an angled box fold) and offers
  a platform's top. Fixed: Fold did nothing after adding onto a V-fold's
  crease from the menu; V-folds, cubes and double 45s on a stand-up's folds
  ("Rebuild failed"); a mouth on a zig-zag's or quadrilaterals' crease
  (skipped as overlapping); things on a platform now fit it. Warnings name
  the fold that isn't there.
* **0.76**: collars' sliding corners curl as far as they must right down to
  shut (they gave up part-way and cut through); a 0.75 mm corner gap; tiers
  alternating out and in; the loop with wider tabs, and as a slice of a cone
  (Top Radius); tower roofs and collars on cubes.
* **0.75**: Angled box folds, under Box Fold settings: the glue
  lines turned, with one crease or three; the loop (Birmingham 16), a ring
  on two tabs; collars stacked in tiers, out or tapering in, their railings
  running right round the curled corners.
* **0.74**: the collar's free corners slide one inside the other, the end
  curling (no slits); railings and battlements on collars; the collar upside
  down as a tapered top; Erase the Paper back in the Artwork panel.
* **0.72–0.73**: Tower collars, a sloping balcony floor all the way
  round a tower that folds flat; towers up a tube's front and back creases,
  so castles can be pentagonal or hexagonal; flat tower roofs, sunk behind
  battlements or at the top with a ledge round the tower.
* **0.71**: gabled tower roofs that overhang the walls (Birmingham 49: a rib
  between the gable tips, the roof stuck only to the rib); tubes and castles
  in two strips; balconies on arches with open railings, and balconies
  outside a castle's towers.
* **0.70**: cylinders (Birmingham 68: a tube's front or back curves round,
  creased above the fold); balconies with railings on tube and cube walls
  and in front of box folds; the M-fold reworked with the book's crease D and
  panel E, so its outer panels actuate; the multiple quadrilaterals' back
  faces set one by one and the front piece no longer cut needlessly.
* **0.69**: V-fold on Top as Birmingham 21-22 (the top piece runs on below
  the join, a V-shaped top, a third piece on the second; a lifting piece that
  vanished from the mesh fixed); Zig-zag is now a V-fold shape (faces each
  side and a face width); fans and M-folds take Glued From; shapes name
  themselves; M-folds stand up by default and move without lag; lighter
  bottom cuts (Bottoms: light, clear or square); zig-zag and quadrilateral
  centre creases take other mechanisms.
* **0.68**: zig-zag folds (Birmingham 45-48) and multiple quadrilaterals (57)
  on angled sticking strips, their bottoms cut away where they'd dip into a
  page; the M-fold (28-29); V-fold on Top reworked as the book has it (the
  lifting piece cut to a point, its tabs A under the top piece); glued-away
  arches with Round, Square or Pointed cuts and uneven sides.
* **0.67**: V-folds glued away from the spine (Glued From, the piece arched
  away between the tabs, each side its own distance); a V-fold on top of a
  V-fold, the lower one's halves growing points to carry its tabs.
* **0.61–0.66**: the double 45° fold, its top piece twisting without passing
  through itself; the jack in the box on any V-fold; 45° triangles in a box
  fold's corners; pictures glued on any face; the stand-up's rolled tail;
  visibility per mechanism; frames across an ordinary card's fold; widths
  that grow one way; pyramids on other folds.
* **0.56–0.60**: Align (along a fold or across the card) and a see-through
  Plan View; castle towers in a tube's corners with pyramid roofs that fold
  flat; self-contained for Blender Extensions; Draw Anywhere with Grease
  Pencil, across folds, painted into the paper.
* **0.46–0.55**: 45° folds (Platform, Rising Sheet); part materials (metallic,
  glossy, glow) and metallic images; outside tabs that carry the art; folds
  that share vertices; the Studio look; colour history; painting tidied up.
* **0.40–0.45**: Grease Pencil sketching end to end; concertinas and fans;
  painting the card flat or folded without stopping.
* **0.32–0.39**: render looks; openings on any face, turned; crease and cut
  shapes you can flip, turn and move; door flaps; Duplicate; sheets sized to
  fit; painting sessions with Erase and painted holes.
* **0.24–0.31**: Set Up Scene; bake guards; images on pieces; picture-book
  sizes; off-centre pop-ups (straps, V-fold glue folds), slanted straps and
  peaks; images that wrap round cubes; the card camera.
* **0.17–0.23**: asymmetric V-folds and mechanisms on a V-fold's crease;
  floors and ceilings from card creases; peaked roofs; Solid Paper.
* **0.10–0.16**: carousels and stage sets; openings and holes; extra creases
  and cuts on V-folds and boxes; parallelogram stand-ups; True Colours.
* **0.3–0.9**: Pop-up Mechanics becomes Pop-Up Pro; the closing stop and export
  options; the 180° cube and pull-tab flaps; tubes and tethers; pyramids,
  tents and roofs; reverse sides and the assembly page; the basic box.
