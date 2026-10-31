# Sketching on the pieces with Grease Pencil

Grease Pencil strokes drawn on a panel ride on that panel as the card opens
and closes, survive rebuilds, and print as vector lines on the piece they
belong to. Each panel gets its own layer on one object, **Pop-up Sketch**.

## Get started

1. **Build the card** and open it part way, so the panel you want to draw
   on faces you (the **Open** slider, or the 0–180° buttons).
2. In the **Artwork** panel, under **Sketch (Grease Pencil)**, pick the
   panel from the list. Panels are named after their mechanism and side,
   such as *V-fold 1: left half*, *Box fold 1: front* or *Cube 1: front
   left*. The card's own pages are *Left page* and *Right page*.
3. Press **Sketch on Panel**. The view turns to face the panel, Blender
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

* **One panel per stroke.** A stroke belongs to the panel its layer is on,
  so a line drawn across a fold won't bend with it. Draw each side on its
  own panel; the ends meet again as the card opens.
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
