import os
import tempfile
from pathlib import Path

# Since Blender's built-in font cannot be directly used in ffmpeg,
# I extracted the bfont from the source code to a separate TTF file.
# For consistency, this plugin uses this font as the default.
BFONT_PATH = Path(__file__).parent / "font" / "bfont.ttf"

# Path to the ASS template file that is used to build subtitles
TEMPLATE_ASS_PATH = Path(__file__).parent / "template" / "template.ass"

# If the output directory cannot be resolved at all, fall back to a temporary directory.
TEMPORARY_OUTPUT_DIR = Path(tempfile.gettempdir(), "blender_playblaster")


def _get_desktop_dir() -> Path:
    """Get the user's Desktop folder.

    On Windows the Desktop may be redirected (e.g. by OneDrive), so query the
    shell for the real location and fall back to ~/Desktop.
    """
    desktop = Path.home() / "Desktop"

    if os.name == "nt":
        try:
            import ctypes
            import ctypes.wintypes

            CSIDL_DESKTOPDIRECTORY = 0x10
            buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
            ctypes.windll.shell32.SHGetFolderPathW(
                None, CSIDL_DESKTOPDIRECTORY, None, 0, buf
            )
            if buf.value:
                desktop = Path(buf.value)
        except Exception:
            pass

    return desktop


# Default output location for playblast videos
DESKTOP_DIR = _get_desktop_dir()
