# Pop-Up Pro: version history

Newest first. `python scripts/since_upload.py` shows what has changed since the
last upload to GitHub.

* **0.94.0**: the **Animal Face**'s mouth corner can be placed: **Mouth
  Out** (how far out from the nose crease) and **Mouth Down** (how far
  below the nose's tip; minus is above it, beside the nose), on either
  pattern, so with Mouth Angle (the lip and jaw turned about the corner)
  and Muzzle either can take the other's mouth: a koala with a goblin's
  frown, a goblin with a muzzle and a smile. Choosing a Pattern sets the
  corner where that face has it; a face saved before 0.94 (Mouth Out 0)
  keeps its pattern's corner.
* **0.93.1**: the **Animal Face**'s creases sit the way card's do. Each
  crease now has a light spring: open flat, any shape the facets leave
  free goes the way creased card springs back (each crease a little
  mountain, 10°); on the way shut each crease is held lightly to its fold
  open flat, let go over the last 45° as the pages press it flat (this
  replaces 0.93's springs on the jaw alone). No more pronounced valley at
  the bottom corner of the mouth on either pattern: through the whole fold
  no crease goes more than a few degrees valley (a test checks it).
* **0.93.0**: the **Animal Face** gets a second hand-made pattern, the
  **Goblin** (Pattern: Koala or Goblin; choosing one sets the landmarks as
  that face was made): no muzzle, a big frown turned down past the nose's
  tip with the jaw tucking up under it, an extra row of quads along C and
  an extra column by the mouth, a pointed ear. **Muzzle** can now be 0 on
  either (none: the upper lip runs straight off the nose's tip), and a
  muzzle can be added to the goblin (carried on down C's line, leant 20°
  to its side). The koala's jaw no longer folds deep partway shut: the
  jaw, free to swing below the mouth, is held lightly to its open shape
  until the last 45°. The fold-over check lets a facet tuck under a
  little (the goblin's jaw does).
* **0.92.1**: the **Animal Face** no longer caves in as the card closes:
  the nose's tip and the chin were turning valley part way shut. The
  muzzle's quads were bending too freely across their diagonals (the spring
  keeping each flat is now as stiff as a crease, and they still meet within
  a twentieth of a millimetre), and the seams down the middle (forehead,
  muzzle, chin) are now kept ridges all the way shut, each facet off them
  falling away towards the card. The guide gains a view part way shut.
* **0.92.0**: the **Animal Face** rebuilt on a hand-made koala's pattern,
  facet for facet as its creases were drawn on the flattened card: C up
  the middle, a band of quads (two rows of three) out to the ear's hinge,
  three forehead triangles, two over the muzzle, the mouth a slot cut in
  from the side with the jaw's three facets below, and the koala's ear.
  The pattern comes first now (so it always lays out without cuts) and the
  face is stood up from it open flat, then crushed step by step down to
  shut with each facet a rigid piece; nothing pokes through a page or the
  other half on the way. Each quad is two triangles across its shorter
  diagonal (no crease printed) so it can bend a hair where the card would
  give. Landmarks stretch their own part of the pattern: Forehead, Nose,
  Muzzle and Chin (the seams and C), Mouth Width, Lower Lip (was Mouth
  Depth), Mouth Angle (turns the lip, chin and jaw about the mouth's
  corner), Jaw, Cheek (was Ear Hinge: how far out the ears' hinges are)
  and Ear Size; the defaults are the koala's. Ears At, Face Width and
  Snout Height are gone from the face's panel. Tabs on the face's seams
  now fold along the whole seam (their fold was printed as a cut).
* **0.91.0**: the **Animal Face** rebuilt as a quad grid after hand-drawn
  topology: spokes from the middle (with corners along C itself, the card
  round each lying flat on C's line) out to the outline, crossed by two
  rings, the ring corners placed where the card round each lies flat; quads
  split on their shorter diagonal, left uncreased where near flat. The mouth
  is a hole between the rings with the **Jaw** below (new), placed so the
  hole lays out as a closed shape and the ring of card round it unfolds.
  Every facet is now posed as a rigid piece (a best fit of its corners):
  0.90's stretched and mirrored poses scrambled the Blender rig, which
  turns each pose into a position and a rotation. The crush solver works in
  arrays (about a second for the whole opening table), eased flat onto the
  middle over the last few degrees. Mouth defaults: Width 14, Depth 6,
  Angle 0.
* **0.90.1**: the **Animal Face** in three rings: the middle (with a
  corner part way down the forehead's seam), an inner ring of temple, eye
  and cheekbone, and an elliptical outline, triangulated as strips between
  them, about twenty facets a half. The inner corners are moved as little as
  they need to lie flat, so it still unfolds without cuts. The ears' hinges
  lie along the outline at their clock, so they turn round the head. The
  mouth is a slot cut up from the bottom edge beside a tongue of chin, its
  tip the mouth's corner, leant out (a smile) or in by Mouth Angle (now
  -15 by default). The crush is solved step by step down from full open,
  each opening from the last, the ears riding their pages and C free on
  the middle: the facets keep within about 2% of their size all the way
  shut. Checks says if the mesh would fold over itself.
* **0.90.0**: **Animal Face** (+ menu) is a new mechanism: a mirrored
  low-poly mesh on the fold, nine triangles a side all cornered on the
  half's edge so it unfolds flat, one piece joined along the nose crease C,
  tabbed down the middle along the forehead, muzzle and chin, glued down by
  its ears. C and the ear hinges meet at one point up the fold, so it opens
  as a V-fold of two meshes; between full open and shut each half's free
  corners are solved to keep the triangles' edges their length (within a
  few percent), the seams on the middle and clear of the pages, until it
  lies pressed flat. Landmarks: Nose At, Face Width, Snout Height;
  Forehead, Nose, Muzzle and Chin lengths; Mouth Width, Depth and Angle
  (smile to frown); Ears At (o'clock), Ear Hinge, Ear Size. The loop face
  stays as **Loop with a Muzzle**.
* **0.89.1**: the animal face's round ends are a few regular facets, the
  one each side of C as wide at the top as Muzzle Width: the muzzle creases
  off that facet's top edge and the forehead across the facet, so neither
  leaves a gap against the loop. The muzzle's dart, like the forehead's,
  narrows to what lets it close at every opening (Nose Dart at most) rather
  than warning. Pictures on a back-to-back pair go on its top, not the
  first facet of its bend.
* **0.89.0**: the **Animal Face** on a round loop is cut as Birmingham's
  pattern: one band symmetric about the centre crease C, joined at the back
  of the loop (K under L); a **Forehead Join** up the foot of C, a bite stuck
  closed by a tab (M under N; 0 leaves an open arch), its dart as wide as
  lets it open flat; **Nose Crease** (C between the eyes; the loop's height
  is the two together); the muzzle's seam held by a tab (**Muzzle Join**, H
  under J); **Loop Diameter**; **Ears At** 10 and 2, 9 and 3 or 8 and 4
  o'clock. A straight loop with a face leans in 3° so it's cut the same way.
  **Back-to-Back Pair** (Birmingham 53): two pieces glued back to back on
  parallel strips, each leg a low-poly bend round an arc from its tab up
  into the joined top.
* **0.88.3**: a cube's dipped lid (on a strut or not) is a host: **Fold:
  Roof Crease** stands a mechanism along its crease from the front corner,
  and is where a mechanism picked onto such a cube starts. The turning
  disc's L piece is one piece again, laid out as an L: leg F glued on the
  triangle up the centre crease, leg G straight out across it under the
  disc, a short band between bending round the corner from one to the
  other.
* **0.88.2**: **Lid: Dipped, on a Strut** replaces 0.88.0's flat lid on a
  strut, which was the wrong mechanism: the dipped lid creased at 45° from
  the front corner, held by a V-fold strut (two panels across a crease, a
  tab at its foot on the short wall's page, a tab at its top on the other
  panel under the lid's larger side) that pulls the lid in as the card
  closes, so a cube can stretch into a rectangle either way. It fits
  exactly at every opening. **Strut In (F)** places it. **Show the Disc**
  for turning discs: off, only the L piece's turning arm shows (the L
  piece now drawn as two arms you can see and paste on).
* **0.88.1**: rectangular cubes take peaked and dipped lids, creased at 45
  degrees from the front corner: a right-angled triangle on the shorter
  wall, a trapezoid on the longer. Turning discs take paste-ons.
* **0.88.0**: **Lid: On a Strut** for cubes: a flat lid hinged on a front
  wall, held parallel to that wall's page by a strut inside the box, so it
  lifts as the card closes (on whichever wall, any box size, wherever a cube
  stands). **Triangle Angle** for a box's 45° triangles, and a **Turning
  Disc** on them, flat on the box's front or top, turning through twice
  that angle; **Turning Disc** and **Turning Wheels** in the + menu.
* **0.87.0**: **Jack in the Box (flat body)**, Birmingham 78: the jack's
  figure on a body of its own lying on the pages across the fold, glued by
  strips folded under at its sides; its arms rise from the chest's folds at
  45 degrees (straight out, as the book draws them, they'd turn down
  through the page as the chest lifts).
* **0.86.3**: the Bite settings show on beaks (0.86.2 built them there,
  but the panel only offered them on plain V-folds).
* **0.86.2**: **Add a Bite Step** gives each step of a
  V-fold's bite its own **Length** (from the step before's crease) and
  **Turn**, for a hooked beak; 0.86.0's even steps move over to them.
  Checks says when a step's too short for its turn. Bites work on beaks
  (triangle halves) too. **Hinge Lies Flat:
  Shut**, the book's other hinge for the arm behind a mask: back to front,
  flat with the card shut, folded up open flat.
* **0.86.1**: the arm behind a mask, reworked. The arm no longer
  cuts through its hinge: it's glued on C and creased across where it
  leaves it, its outer part bending there to slope down onto the page
  under the mask. **Arm Points** 0 now runs straight out of C's edge beside
  the pivot. Checks warns when the arm would run into the hinge or reach
  back over the fold. The mask's fold is a host (box folds, V-folds,
  stand-ups, cubes and more in front of the mask).
* **0.86**: rising sheets and their cross pieces are laid out standing up
  (their height up the paper), and a rising sheet's corners and 45° folds
  carry box folds, V-folds, cubes, tubes, stand-ups and more (**Sheet's
  Side**, **On Its 45° Fold**). Pictures glued on a face are **Paste-ons**
  now, apart from the art on the paper. **Bite Steps** and **Each Step
  Turns** take a V-fold's bite in up to six steps for a rounder beak. **Arm
  Behind a Mask** (Birmingham 75): an arm glued on a creased hinge behind a
  mask layer turns a right angle in its own plane as the card opens,
  clockwise or anticlockwise, on either page.
* **0.85**: door flaps on cubes, tubes and stand-ups (every piece now);
  a V-fold's **Bite** (Birmingham 13-14) bends its end into a beak;
  **Flapping Arms** (65-66) swing out through slots in a V-fold or a box
  fold. The roadmap tidied.
* **0.84**: **Slotted Cross Pieces** are mechanisms of their own on a
  rising sheet, each sized and placed on its own, with feet that grow with
  its width and can go on one page only. Older files' cross pieces are
  made separate when opened.
* **0.83**: fixes and additions to 0.82. The house's roof is pushed open by its
  walls, never through them. Slotted cross pieces: millimetres, **Slots
  Meet At**, a position along the sheet and up to four. **Cut Across
  Folds** for an opening on a face (a gate through a tower's corner).
  Castle towers are laid out standing up, their faces' Y runs up them and
  a box fold added on a corner is named as a tower. **Box with Ends** gets
  the book's tuck flaps and an inside **Far Tab**.
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
