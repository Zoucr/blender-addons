# Strand Flow 5.1.0

Adds optional guide-following point lights to illuminate nearby objects in Eevee. The rig uses eight persistent point light datablocks at most, with constraint positions and energy drivers for reliable final render animation. Existing systems remain unlit until the toggle is enabled. The shader, geometry generation, alpha, particle trails and V5 settings remain compatible.

Blender 5.2.0 integration test checks light creation, energy distribution, guide movement and toggling. The build workflow now packages and validates against Blender 5.2.0, the extension's declared minimum version.
