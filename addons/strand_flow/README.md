# Strand Flow 2.0

Guide-driven 3D strands for Blender 5.2. No dependencies.


## New in V2: Trail Particles

Install V2 over V1 using the same addon name. If Blender still shows the old panel, restart Blender after installing. Existing systems and palettes remain intact. In **Trail Particles**, choose **Trail Particles** once to upgrade an existing V1 system; this rebuilds full geometry once to add distance attributes. Save your .blend normally afterwards.

For one guide carrying multiple moving trails:
1. Select one open guide and Create from Selected Guides, or select an existing system.
2. Open Trail Particles and choose that mode.
3. Click **Single Strand Preset**. This uses the first enabled guide of the first group, with one strand, no spread, no waviness, and no random end trim. With multiple splines, the first one is used.
4. Press Play in Material Preview or Rendered view.

Trail controls update instantly without a mesh rebuild. The existing Colour Ramp still colours the strands along their length; the trail mask animates their visibility. The particles are visible sections of a continuous mesh, not individual objects, simulations, or geometric tail tapers.

| Control | Behaviour |
| --- | --- |
| Continuous / Trail Particles | Restores the original full shader or shows only moving streaks |
| World Units | Length, spacing and speed measured in Blender units; consistent speed across unequal curve lengths |
| Per Curve | Amount is the number of evenly spaced particle slots per curve; length is a curve fraction and speed is curve lengths per second |
| Length / Relative Length | Maximum streak length before random variation |
| Spacing / Amount | Distance between heads, or slots per curve; fractional Amount values round to an integer |
| Speed / Relative Speed | Maximum travel speed |
| Length Variation | Random reduction from maximum length, separately for each travelling particle |
| Speed Variation | Random reduction from maximum speed, per strand |
| Forward / Reverse | Travel toward the guide end or toward its start |
| Head Fade | Soft leading edge as a fraction of the trail length |
| Tail Falloff | Higher values give a tighter bright head and a dimmer tail |
| Seed | Changes independent per-strand offsets and variations |

Length is capped at 95% of spacing to preserve gaps. For longer streaks, also increase Spacing or decrease Amount. Particle heads are spaced regularly within each strand, with independent strand offsets. Different particle lengths produce varied gaps. The tail points opposite the travel direction.

Time is driven by `(frame - 1) * fps_base / fps`, so playback and rendered animation use seconds at the scene frame rate. The driver references the scene in which the material was created/upgraded. Using that material in a different scene keeps the original scene's FPS reference. Ordinary render frame changes animate the shader without requiring live geometry updates. No Python frame handler is needed for the animation.

Use **Build Full** before final rendering. Rebuild after scaling the output object or changing guide geometry so the stored world-distance attributes stay accurate. The generated mesh remains static until rebuilt; moving guides are not automatically baked for final animation.

The gaps use a Transparent BSDF mixed with the original surface, not black emission. Eevee uses Dithered surface rendering. Dense overlapping tubes may require higher samples in Eevee or more Transparent bounces in Cycles. Solid viewport mode does not display this effect.

## Install and start
1. Blender Preferences > Add-ons > menu > Install from Disk. Select Strand_Flow_V2.zip and enable Strand Flow.
2. Open the 3D View sidebar with N, then the Strand Flow tab.
3. Click **Create Reference Demo**, or select your own open Bezier/Poly curve objects and click **Create from Selected Guides**.
4. Switch to Material Preview or Rendered view to see the gradient material.
5. Adjust settings and click **Update Preview**. Click **Build Full** before rendering.

The demo creates only guide curves and the strand output. It does not change your camera, world, lighting or compositor. For the reference look, use a dark world and restrained compositor glare. Start with 400-1000 strands, a small radius, modest depth, and a camera looking along the Y axis toward the demo. Adjust radius to your scene scale and render resolution. Emission alone is not glow.

## Editing guides
The newly created system is automatically pinned in the panel. You can select and edit its guides while still accessing the system controls. Select another system to work on that system, or change Pinned System.

The guide list initially sorts objects by name. Use the arrow buttons to reorder, the direction toggle to reverse, and Group to separate independent bundles. Each spline within an object participates in its data order. Group, enable and reverse apply to all splines in that object; separate splines into objects for independent control.

Guides must be open Bezier or Poly splines. Different point counts are fine. Sampling uses normalized arc length. NURBS, cyclic guides, curve modifiers and shape-key deformation are not evaluated in this version. For those, use a converted, editable copy as a guide. Object transforms are supported. Keep the generated object's transform at identity for predictable world-space widths and clearance.

## Generation
- **Between Guides:** blends corresponding positions between adjacent guides within each group.
- **Around Guides:** creates bundles around each guide. Spread controls radius; Concentration attracts strands toward the centre.
- **Hybrid:** fills adjacent guide gaps, with Concentration biasing strands toward the guides.
- **Strands:** total candidate count, shared evenly across guides or guide pairs. Exclusions may reduce the visible total.
- **Preview %:** generates a subset using the same IDs as full output.
- **Points / Strand:** curve sampling and cut accuracy, independent of strand count.
- **Depth Spread:** thickens fill along the transported orientation normal. Choose an Orientation Axis approximately perpendicular to your intended sheet. For the demo, this is Y.

Random distribution is used in V2. Count changes preserve the earlier strands if guide order, groups and other settings stay unchanged. Changing guide membership/order can redistribute strands. Exact spatial spacing, density painting and uniform volume filling are not included.

## Tube and ribbon output
Tube produces round mesh strips with configurable sides. Ribbon produces two-sided flat strips. Radius / Half Width controls either cross section. Ribbons can disappear edge-on; change the Orientation Axis and Ribbon Twist to control them. Orientation is transported along each curve to reduce sudden flips, although cusps and reversing tangents can still produce artifacts.

Width Variation, Waviness, Wave Frequency, End Taper and Random End Trim control the overall texture. Taper affects both width and brightness. Output is an ordinary generated mesh with shader attributes, not editable filler splines or a Geometry Nodes network. The source guides remain editable. To keep a fixed output copy, duplicate it, make its mesh single-user and do not rebuild the copy.

## Exclusion zones
Choose a collection containing closed, manifold mesh objects. Modifier-evaluated geometry and object transforms are supported. The addon does not hide these objects; control their render visibility yourself.

- **Remove Strand:** discards a candidate strand if sampled points enter the zone/clearance or a centreline segment crosses its surface.
- **Cut Inside:** omits affected segments, leaving visible gaps.
- **Soft Fade:** also reduces width and brightness near the boundary.

Clearance adds a buffer. Cuts are sampled, not exact Boolean intersections; increase Points / Strand for small obstacles and cleaner boundaries. Very thin obstacles, near-tangent paths and narrow clearances may need higher sampling. The surface-crossing test helps catch obstacles between samples, but clearance is sampled at points. Soft-fade tube ends are open. Obstacles do not steer paths around themselves.

## Material
The material is created once per system and preserved across rebuilds. Edit the actual Color Ramp directly in the panel or Shader Editor.

- **Gradient Scale:** gradient variation along each strand.
- **Random Scale / Random Offset:** independent per-strand gradient variation.
- **Travel:** shifts the gradient; right-click its value to insert keyframes.
- **Emission Strength:** overall brightness.
- **Patch Scale:** size/frequency of smooth brightness patches.

The material reads mesh attributes sf_u, sf_random and sf_brightness; sf_id is also available. These follow the generated geometry rather than world-space texture positions. The default palette is mainly purple with green and pale-blue accents. Colour and brightness are separate. Full custom node editing is supported; keep the named nodes if you want their controls to remain visible in the panel.

## Updating and animation
Manual update is the default. Live Update debounces guide/exclusion changes and rebuilds preview geometry; it can still pause the UI with large systems. There is a 2.2 million vertex safety limit. Preview and Full are explicit build states, not automatic per-render switches.

**Build Full disables Live Update** to keep full output in place. Re-enable Live when editing again. Material controls update instantly and shader Travel can animate without rebuilding. V2 does not bake or automatically evaluate animated guide geometry for final frame rendering. Treat geometry output as a snapshot, and use shader animation for this version.

## Validation and limitations
Target: Blender 5.2, using standard Python APIs available in Blender 5.x. The package was syntax-checked and the generator's mathematical and topology logic was tested with a lightweight test harness: arc-length sampling, zero-length rejection, frame orthogonality, axis singularities, all three distribution modes, tube/ribbon topology, shader-coordinate arrays and stable density growth.

A native Blender runtime was not available during development. Installation, the UI, shader compilation, Blender BVH exclusions and rendering have **not been run in Blender 5.2**. A native smoke-test script is included at tests/smoke_blender.py for further validation.

No automatic obstacle avoidance, exact cut surfaces, GPU generation, automatic render-density switching, or external dependencies.

### V2 validation
The generated shader math graph was evaluated with a CPU test harness: visible trails and zero-valued gaps, forward/reverse translation, stable random lengths as particles move, world-space speed independent of curve length, relative scaling, and exact Continuous bypass all passed. The V1 generator checks also passed with the new arc-length attributes. The native smoke script now includes V1 material migration and timeline driver checks, but has not been executed here because a Blender runtime is unavailable. Native shader rendering and transparency still require testing in Blender 5.2.

## Repository installation
Refresh the remote repository in Get Extensions and install Strand Flow. Requires Blender 5.2 or newer. Save your work and disable the legacy disk-installed Strand Flow before enabling the extension to avoid duplicate operators and properties. Scene property names and material attributes are unchanged. No preferences migration is promised.

This user-owned, ChatGPT-generated add-on is distributed under GPL-3.0-or-later; see LICENSE.txt. The repository import preserves all supplied Python files byte-for-byte. The original legacy bl_info advertises 5.0; the extension manifest conservatively requires the intended 5.2 target. V1 was user-tested; V2 native rendering remains unverified.
