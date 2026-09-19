# Playblaster 1.0.0

Create viewport playblast videos with configurable metadata burn-in, audio,
background color, render overrides and automatically incremented output versions.

## Requirements and use

- Manifest declares Blender 4.2 or newer; interactive compatibility has not been verified during this import.
- Install FFmpeg separately and make `ffmpeg` available on the system PATH. Burn-in needs the subtitles filter (libass); the selected video encoder must also be available.
- Set an active scene camera and keep a 3D View open.
- Open **3D View > N sidebar > Tool > Playblaster**, set output and video options, then run **Playblast**.
- Outputs default to the Desktop; choose another folder in the panel as needed.
- fontTools 4.60.1 is bundled as a wheel; no separate Python installation is needed.

## Existing installations

Disable any older Playblaster installation before enabling this repository copy.
Back up settings using the settings export. Scene property and operator names are
unchanged; add-on preferences may need re-entering when changing repositories.

## Attribution and licenses

Maintainer: Lucca Kreuzer. Based on [Anim Reviewer by FhyTan](https://github.com/FhyTan/blender-anim-reviewer).
Add-on code: GPL-3.0-or-later, see LICENSE.txt and the original source notices.
The bundled `font/bfont.ttf` identifies itself as Inter Variable, copyright 2016
The Inter Project Authors, SIL Open Font License 1.1; see font/OFL.txt.
The unchanged fontTools wheel includes its own license notices under its dist-info directory.

Source and manifest are imported unchanged from the supplied playblaster.zip.
Only documentation and license texts were added; Python caches were omitted.
