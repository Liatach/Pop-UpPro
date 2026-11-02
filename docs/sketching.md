# Sketching on the pieces with Grease Pencil

Grease Pencil strokes drawn on the card ride on their panels as the card
opens and closes, survive rebuilds, and print as vector lines on the pieces
they belong to. Each panel gets its own layer on one object, **Pop-up
Sketch**.

## Draw Anywhere

1. **Build the card** and open it as far as you like.
2. In the **Artwork** panel, under **Sketch (Grease Pencil)**, press **Draw
   Anywhere**. Blender switches to Grease Pencil **Draw** mode, with strokes
   set to land on the paper's surface. Nothing turns: draw from wherever
   you're looking.
3. **Draw** with any Grease Pencil brush, colour or material, on the folded
   card or on the flat layout (they're the same paper), across folds, from
   page to page. You can change the opening between strokes.
4. **Done Drawing** puts every stroke on the panel(s) it was drawn on. Each
   point goes onto the paper under it, and a stroke that crosses a fold is
   cut exactly on the fold, each part on its own panel's layer, so it bends
   with the card. Points off the paper are left out (the report says how
   many).

A stroke that runs from one piece of paper onto another (from a page onto a
V-fold standing on it, say) becomes two strokes, which part as the card
moves: they're on different paper. A filled shape drawn across a fold
becomes one fill on each side.

## Sketch on one panel

1. **Build the card** and open it part way, so the panel you want to draw
   on faces you (the **Open** slider, or the 0–180° buttons).
2. In the **Artwork** panel, under **Sketch (Grease Pencil)**, pick the
   panel from the list. Panels are named after their mechanism and side,
   such as *V-fold 1: left half*, *Box fold 1: front* or *Cube 1: front
   left*. The card's own pages are *Left page* and *Right page*.
3. Press **On a Panel** (Sketch on Panel). The view turns to face the panel, Blender
   switches to Grease Pencil **Draw** mode, and strokes are set to land on
   the paper's surface. A layer named after the panel is made and selected
   (or picked up again if it already exists).
4. **Draw.** Use the Draw tool; the toolbar's Erase tool removes strokes.
   Strokes are dark ink (the *Pop-up Ink* material) to start with: change
   the colour in the tool settings, or add materials to Pop-up Sketch.
5. **Another panel?** Pick it in the list and press **Sketch on This Panel
   Instead**. You stay in Draw mode.
6. **Done Drawing** (in the Artwork panel, or the red button in the 3D
   view's header) goes back to Object Mode and the view you had.
7. Drag **Open** to watch the sketches move with their panels.

## Good to know

* **One panel per stroke.** With Sketch on Panel a stroke belongs to the
  panel its layer is on, so a line drawn across a fold won't bend with it.
  Use **Draw Anywhere** for that: it cuts strokes on the folds for you.
* **Layers.** The layers are listed in Pop-up Sketch's Object Data
  properties. You can hide, lock, reorder or change their opacity there.
  Keep their names and parents as they are: that is what keeps each layer
  on its panel.
* **Changing the card.** Resizing a mechanism or adding others keeps every
  sketch on its panel. If you delete a mechanism, its sketches are kept,
  hidden and renamed *… (removed)*, rather than lost.
* **Printing.** **Export SVG Sheets** prints the sketches as vector paths
  on their pieces (the *sketch* layer in each SVG), in their stroke colour,
  with fills where the material has one. *Sketches* in the export options
  turns them off. Cut- and crease-only files leave them out.
* **Holes** drawn by hand use **Draw Holes** in Creases, Cuts and Holes, not a
  sketch layer.
* **Carousels.** Sketches show in each stage's own scene, not in the
  carousel view (a collection instance can't carry bone-parented Grease
  Pencil layers). Painted art shows in both.
