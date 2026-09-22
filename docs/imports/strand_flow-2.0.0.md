# Strand Flow 2.0.0 import

Source: user-requested, ChatGPT-generated Strand_Flow_V2.zip.
Archive SHA-256: `51aada28d5cb6834144bf85d4803cfce7d6924706bbc9d36d104ac1aab839bed`.

All supplied Python source and the bundled smoke test are unchanged. Added extension manifest and GPL-3.0-or-later license for this user-owned generated add-on; appended repository installation guidance. No external dependencies, network access, file writes, or additional permissions are required. Relative module imports support the extension namespace; registration removes its handlers, timers and properties on disable. Existing sf scene properties and shader attributes are preserved.

The extension targets Blender 5.2.0+, more conservatively than the legacy bl_info 5.0 declaration. V1 was confirmed working by the user; V2 native rendering is unverified. Repository tests and CI package validation do not establish Blender 5.2 runtime correctness. The supplied smoke script is preserved as a development tool, excluded from release ZIPs.

Disable the old disk installation before enabling this extension. The original ZIP is retained in the user's workspace; generated archives are not committed.
