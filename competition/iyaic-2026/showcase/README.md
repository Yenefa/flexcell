# Competition showcase (IYAIC 2026)

Purpose: present the workcell to judges. This folder holds the **narrative and captured assets**,
never runtime logic.

## Core demo (honest scope)
**Visual pick + Observe localization + existing verified skills.**
- Agent looks at the current camera frame, chooses the GREEN box among three distinctly coloured
  boxes (colour assignment randomised per run so selection follows the image, not a hard-coded
  colour->id table).
- The chosen 3-D object id comes from a fresh Observe (simulation ground truth); vision selects,
  it does not perform pure-visual 3-D localization.
- One bounded `RunPickPlace` moves it to zone_1; independent Verify checks all boxes.

Reference results (single window, n=1 unless stated):
- #114 (2026-11-04): green A -> zone_1, placement error **2.536 mm**, other boxes <=2.5e-9 m,
  health 19/19. Before/after frames on branch `evidence/camera-select-114`.
- #119: region clear + restore, two layouts, 8 RunPickPlace, restore error <=5.3 mm.

## Shot list to capture (to be filled with real captures)
1. Three-box camera scene (distinct colours), with zone markers visible.
2. Selected frame + annotated green-box projection (show colour share / unique match).
3. One successful pick-place with end-state verification table.
4. A negative: gate refusal / occupied zone -> stops without motion.

> Wording required in any talk track: "visual selection + Observe localization + existing skill
> transport", n=1 unless a larger window is explicitly claimed; not pure visual grasping.
