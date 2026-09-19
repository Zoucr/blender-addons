# Playblaster 1.0.0 import

Source: user-supplied `playblaster.zip`.
SHA-256: `bb6e91eb36ccc662c367620d4bb467c550060b2ef5dfb7b7b103711cf8b41a6e`.

All 13 non-cache files, including the manifest, font and dependency wheel, are
preserved byte-for-byte under `addons/playblaster/`. Nine compiled Python cache
files were omitted. The original upload is retained outside this repository.
Added README, GPL-3 license text and the bundled Inter font's OFL license text.
The font license was obtained from rsms/inter LICENSE.txt (blob
9b2ca37b3ffc77391d8b2ebef4a974ef32bf46ea), matching the font's embedded notices.
The fontTools wheel retains its embedded license files.

ID playblaster, version 1.0.0, maintainer and Blender 4.2 minimum are unchanged.
No code changes or preference/property migration are part of this import.
FFmpeg is an external runtime requirement; see the add-on README.

Validation: safe archive paths, Python syntax, manifest/folder identity and
byte-for-byte import verification passed. Repository infrastructure tests pass
with the optional local Blender CLI integration test skipped. The PR workflow
performs official Blender 4.5.3 package validation. Interactive viewport capture,
FFmpeg export, audio and GPU overlays have not been tested in this environment.
