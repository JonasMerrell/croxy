# CroXY

An enclosed cross-XY 3D printer with a 150 °C heated chamber, a 180 × 180 × 180 mm build volume, and
everything that moves in XY mounted on top of one machined steel top plate, out of the chamber. The
toolhead reaches down into the chamber through a cutout in the plate. It is designed in
[rCAD](https://github.com/JonasMerrell/cad-rust-app).

<img alt="CroXY gantry on the top plate" src="out/render-gantry.png" width="100%">

## Status

| Area | State |
|---|---|
| Layout sketches (rev B) | approved, [docs/layout-sketches.html](docs/layout-sketches.html) |
| Top plate, corner pulley blocks, motor towers, XY drive, gantry, toolhead yoke | modelled on top of the plate, clearance-checked over full travel |
| Sliding shutter over the plate cutout | space reserved (15 mm), not modelled |
| Frame posts | placed (3030 × 290); floor plate, back shear plate, panels not yet |
| Z system and bed | not started |
| Enclosure, insulation, door, back module (filter + electronics) | not started |
| Toolhead | envelope stand-in only (Chube Conduction + Sherpa Heavy) |

## Build the model

    pip install pyyaml
    python3 cad/build.py path/to/rcad out

This writes:

- `out/CroXY.json`: the rCAD document (one Part Studio per part, plus the `CroXY` assembly). Open it with `rcad out/CroXY.json`.
- `out/CroXY-xy.step`: the assembly as STEP.
- `out/render-*.png`: renders.
- `out/clearance-sweep.json`: interference check with the toolhead at the centre, all four corners and the four edge midpoints of travel.

All key sizes are in [`cad/params.yaml`](cad/params.yaml). Change a number and rebuild.

## How the XY works

- **Above the plate.** The MGN12 rails, belts, pulleys and beams all sit on top of the plate, outside the heated chamber. The plate has a 246 mm square cutout, and the toolhead hangs from the beams down through it. A sliding insulated shutter over the cutout (15 mm of height kept clear for it) keeps chamber air out of the gantry bay.
- **Cross gantry.** The Y beam spans side to side on the Y-end towers and moves in Y. The X beam spans front to back on the taller X-end towers, above the Y beam, and moves in X. The toolhead yoke rides an MGN9H on the bottom of each beam and wraps around the Y beam. The toolhead hangs below the yoke.
- **Beams.** Bent U-channel backers (mild steel or 4130, Send Cut Send) carry the MGN9 rails. Their size will be set by the dynamic simulation. The rail face is left for finish machining.
- **Perimeter rails and towers.** Four MGN12 rails are screwed to the top of the plate. Each belt runs directly above its rail, and each tower stands on its MGN12H and clamps the inner strand of its belt.
- **Drive.** There are four NEMA23s, one per belt, pinwheeled around the corners on steel motor towers above the X beam. Each motor turns an 8 mm shaft through a coupling. The shaft runs in two 608 bearings in the corner block, so the pulley is in double shear and the motor only sees torque.
- **Corner blocks.** One design is used four times. Each block stands on the plate and holds its corner's drive pulley and the idler for the neighbouring belt.
- **Tensioning.** Each idler sits in a 6 mm slot and is adjusted from above.
- **Thermal matching.** The top plate, floor plate, corner blocks, towers and beam backers are all steel, so the steel rails don't bow as things heat up.

## Decisions made so far

See [docs/spec.yaml](docs/spec.yaml) for the full spec. Changes from the approved sketches:

- The frame is 380 mm (was 340) so each corner block fits its drive pulley, the other belt's idler, and 6 mm of tension travel.
- The back centre post is replaced by a steel back shear plate carrying the Z3 rail. The post would have cut through the X-back belt.
- The XY system moved from under the plate to on top of it (belts and rails out of the chamber), with a cutout for the toolhead. That lets the chamber shrink to 290 mm tall, because the beams no longer take up chamber height.
