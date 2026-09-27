# Strand Flow 4.0.0 import

Imported the user's Strand Flow extension as `addons/strand_flow/`. Its stable ID, GPL-3.0-or-later license, author and settings are retained. This is the first Strand Flow release in this repository.

V4 introduces live Geometry Nodes generation with one guide set, localized wake deformation and direct frame rendering. New systems use V4. Existing V3 systems remain legacy objects; **Create V4 Live Copy** creates a separate procedural system, retains its guide A settings, clears B on the copy and hides the source. Existing V3 blend animation does not control V4; keyframe Wake Amount and Noise Travel instead. Back up a blend before switching installations, disable the old extension to avoid duplicate registration, and keep this extension enabled for live property drivers.

Validated with Blender 5.2.0: native live graph generation, 60 viewport strands out of 240 at 25% preview density, mesh attributes, guide transform and wake keyframe changes, V3 copy operation, file save/reopen and still renders at frames 1 and 10. The two renders differ in 21,108 pixels at 260 x 180 resolution. Official extension build and validation passed. Infrastructure tests and repository build should also run on this branch. GPU rendering and high strand counts were not profiled.
