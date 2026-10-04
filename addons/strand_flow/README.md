# Strand Flow 5.0

Live guide-driven strands for Blender 5.2+. One guide set feeds a Geometry Nodes system, with keyframeable wake deformation, ribbons or tubes, exclusion zones and shader trails. Render the animated range directly. No per-frame geometry bake is required for V5 systems.

## Install cleanly

This is a Blender **extension**, with `blender_manifest.toml` at the ZIP root. In **Edit > Preferences > Get Extensions**, use the top-right menu > **Install from Disk**, select this ZIP and enable Strand Flow. Do not extract the ZIP into Blender's scripts folder. If another Strand Flow installation is enabled, disable/remove it first and restart Blender before enabling V5. A legacy Add-ons installation and an extension installation can coexist on disk and conflict at registration. V5 reports that conflict explicitly and rolls back any partial class registration.

A disk-installed extension lives in a local repository and does not receive automatic updates from the public remote feed. Disable/remove a disk-installed copy before installing this extension from the remote repository, then restart Blender. Save a copy of your `.blend` before replacing an older installation.

Existing V4 live systems retain their settings and generated node graph; V5 adds the material controls when opened. An existing V3 mesh system remains V3 until **Create V5 Live Copy** is used. The source V3 object is preserved and hidden. V3 A/B blend animation has no V5 equivalent. Keep the extension enabled while rendering because live node controls use drivers on the object's custom settings.

## Alpha and color controls

In the **Material** panel:

- **Output Opacity** applies after Gradient/Airflow and optional Trail Particles. At 1 the final surface keeps the style's own alpha, at 0 it becomes invisible.
- **Alpha from Brightness** at 0 keeps alpha independent of the strand brightness. At 1 dimmer strands receive less alpha. **Minimum Alpha** sets a floor for that variation. These controls are keyframeable.
- In **Gradient** style, **Color Boost** and **Brightness Floor** increase color visibility independently of alpha. The Color Ramp and Emission Strength remain editable.
- In **Airflow** style, **Opacity** and **Edge Softness** still shape that style's transparency. Output Opacity is applied afterwards.
- **Strong RGBA Preset** makes final alpha solid. For Airflow it sets style opacity to 1. For Gradient it also raises Color Boost and Brightness Floor. This intentionally changes the appearance; adjust the sliders after applying it.

Use **Render Properties > Film > Transparent** and **Output Properties > Color > RGBA** for a transparent PNG sequence. Alpha is composited over the eventual background. If you want a faint, translucent strand, its visible brightness will depend on that background. For editing in Blender's compositor, keep the render's premultiplied alpha convention; convert only at the boundary of an application that requires straight alpha.

Shader trails have transparent gaps, so Output Opacity cannot turn those gaps into continuous strands. Choose **Continuous** under Trail Particles if you want solid strands.

## Shape and animation

Draw open Bezier or Poly guides with no bevel/extrusion. Select them and use **Create from Selected Guides**. Around Guides supports a single guide; Between Guides and Hybrid use neighbouring guides in each Group. Start/End and Fade In/Out limit the wake along the curves. Keyframe Wake Amount and Noise Travel. Use Preview % for viewport density; final renders use Strands (total).

The geometry is art-directed, not a physical fluid simulation. The guides determine the shape around a product. Keep the output transform at identity scale for predictable thickness. Very high strand counts, points per strand and tube sides can still create substantial render geometry. The live graph shares its strand construction across guide intervals, so creating many guides is much faster than V4.0.

## Validation

Blender 5.2.0 native checks cover V5 registration, existing system evaluation, tube and ribbon width, guide animation, gradient/Airflow styles, material alpha in saved RGBA renders, and the extension build/validation. GPU/Eevee rendering and every external compositor have not been comprehensively tested.

License: GPL-3.0-or-later. Author: Lucca / OpenAI. See LICENSE.txt.
