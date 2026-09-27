# Strand Flow 4.0

Live guide-driven strand bundles for Blender 5.2+. Geometry Nodes generates the strands and evaluates their deformation on each frame, including final renders. There is one guide set. No A/B guide pairing, per-frame mesh bake or Python frame handler is needed for a V4 system.

## Install and migrate

Install the ZIP from **Preferences > Extensions > Install from Disk**, then enable Strand Flow. Disable any other installation of the same add-on first. Save a copy of your `.blend` before changing an existing project.

New systems use V4 automatically. For a V3 system, select it and click **Create V4 Live Copy** in the 3D View sidebar > Strand Flow. This makes a separate system with the V3 settings and its guide A references, clears guide B assignments on the copy, sets single-set wake mode, and hides the original in the Outliner. The original V3 system and its animation data stay in the file. V3 blend keyframes have no equivalent effect on the live copy. Keyframes on wake amount, spread and other retained controls continue to drive V4. Clear any V3 bake before making a copy. Keep this extension enabled when rendering a file with live systems because the custom settings supply the node graph's drivers.

## Create an airflow layout

1. Draw open Bezier or Poly guide curves for the tight inlet, the path around your object and the reconverging outlet. Select them and choose **Create from Selected Guides**. **Create Reference Demo** provides a starter layout.
2. Choose **Around Guides** for one guide or a bundle around each guide. **Between Guides** and **Hybrid** connect adjacent curves within each Group. Use the guide order in the list to define the neighbours.
3. Under **Guide Animation**, set Start and End (normalized distance from 0 to 1 along each guide). Set Outward Spread and Wake Waviness. Keyframe Wake Amount from 0 to 1 to open the flow, and Noise Travel to move the waviness.
4. Set Preview % for interactive density. The final render uses Strands (total) automatically. Render the frame range directly; there is no Build Full or Bake step for V4.

Wake directions are measured from the centre of each guide Group. The guides determine the flow around your object; this is art-directed geometry, not a physical fluid simulation. Fade In and Fade Out soften the affected section. A zero Fade Out holds the spread through End. Global Waviness affects the entire strand, independent of the localized wake.

Guide object transforms and editable curve points feed the live graph. Guide input should have no bevel/extrusion. Keep the output object at identity scale for predictable widths and distances. Structural edits such as adding guide rows, changing distribution or shape, changing the material or exclusion collection require **Refresh Guide Links** if they do not refresh automatically. Moving guide points, animating guide transforms and keyframing numeric controls do not require a refresh.

## Appearance and obstacles

Choose Tube or Ribbon. **Airflow Ribbon Preset** switches to a pale, simple, transparent ribbon shader with soft width edges. Gradient Material remains available for the stylized palette. Trail Particles animate transparent segments along the curves in the material; Continuous shows full strands. Ribbon twist and Orientation Axis affect which side faces the camera.

Assign a collection of closed mesh objects for exclusions. Remove Strand, Cut Inside and Soft Fade use sampled surface proximity in the live graph; increase Points / Strand for narrow obstacles. The live proximity approximation near overlapping or nonmanifold objects can differ from V3's ray-parity mesh bake. Strands do not automatically bend around an exclusion mesh.

## Performance and limits

Each V4 system has one procedural modifier and one output mesh evaluated for the current frame. The `.blend` does not store one mesh per animation frame. Lower Preview % while editing, then adjust the total count, Points / Strand and Tube Sides for render cost. Very high counts still create real geometry and can consume substantial render memory. Guide intervals each add a node section, so many guide splines also raise graph evaluation cost.

The live graph samples open Bezier and Poly splines with at least two points. Stray single-point splines are skipped when building intervals. Cyclic and NURBS splines, beveled source curves and automatically following topology-changing modifiers are outside the supported guide input. V3 systems continue to use the old mesh and bake controls until converted to a live copy.

## Validation

Blender 5.2.0 native checks cover live mesh generation, per-strand named shader attributes, keyframed wake and phase, viewport density, saving/reopening the file, and two final frame renders with visibly different geometry. The source repository includes `tests/strand_flow_live_blender.py` for reproducible checks. GPU rendering and very large scenes have not been profiled.

License: GPL-3.0-or-later. Author: Lucca / OpenAI. See LICENSE.txt.
