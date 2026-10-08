import getpass
import os
from collections import defaultdict
from datetime import datetime
from typing import TypedDict

import bpy


class MetaData(TypedDict):
    """The metadata used to replace the placeholders for burn-in text."""

    datetime: str
    date: str
    time: str
    width: int
    height: int
    file_name: str
    file_version: str
    file_ext: str
    file_full_name: str
    blend_file: str
    scene_name: str
    view_layer: str
    frame_current: int
    frame_start: int
    frame_end: int
    frame_total: int
    frame_rate: int
    timecode: str
    marker: str
    camera_name: str
    camera_focal: str
    camera_lens_unit: str
    user: str
    blender_version: str


META_DATA_DESCRIPTIONS = {
    "datetime": "Current date and time",
    "date": "Current date (YYYY-MM-DD)",
    "time": "Current time (HH:MM:SS)",
    "width": "Playblast width in pixels",
    "height": "Playblast height in pixels",
    "file_name": "Name of the output file without extension",
    "file_version": "Version string of the output file",
    "file_ext": "File extension of the output file",
    "file_full_name": "Full name of the output file with extension",
    "blend_file": "Name of the current blend file",
    "scene_name": "Name of the current scene",
    "view_layer": "Name of the active view layer",
    "frame_current": "Current frame number",
    "frame_start": "Start frame of the playblast",
    "frame_end": "End frame of the playblast",
    "frame_total": "Total number of frames in the playblast",
    "frame_rate": "Frame rate of the playblast",
    "timecode": "Current frame as timecode (HH:MM:SS:FF)",
    "marker": "Name of the nearest timeline marker at or before the current frame",
    "camera_name": "Name of the active camera",
    "camera_focal": "Focal length of the active camera in mm",
    "camera_lens_unit": "Lens type of the active camera (PERSP/ORTHO/PANO)",
    "user": "Name of the current computer user",
    "blender_version": "Blender version",
}


def frame_to_timecode(frame: int, fps: float) -> str:
    """Convert a frame number to a HH:MM:SS:FF timecode string."""
    if fps <= 0:
        fps = 24

    total_seconds = int(frame // fps)
    frames = int(frame % fps)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}"


def get_nearest_marker(scene: bpy.types.Scene, frame: int) -> str:
    """Get the name of the nearest timeline marker at or before the given frame."""
    best_name = ""
    best_frame = None

    for marker in scene.timeline_markers:
        if marker.frame <= frame and (best_frame is None or marker.frame > best_frame):
            best_frame = marker.frame
            best_name = marker.name

    return best_name


def get_metadata(context: bpy.types.Context, is_rendering: bool = False) -> MetaData:
    """Get the metadata for current frame in the given context."""

    scene = context.scene
    render = scene.render
    playblaster = scene.playblaster

    # Get Resolution Info
    if is_rendering:
        # When rendering, the resolution already changed to the render size
        res_x = render.resolution_x
        res_y = render.resolution_y
    else:
        # When not rendering, calculate the resolution with scale and make sure it's even
        scale = playblaster.override.scale

        res_x = int(render.resolution_x * scale / 100)
        res_y = int(render.resolution_y * scale / 100)

        res_x += res_x % 2
        res_y += res_y % 2

    # Get frame range info
    if playblaster.override.use_frame_range:
        frame_start = playblaster.override.frame_start
        frame_end = playblaster.override.frame_end
    elif scene.use_preview_range:
        frame_start = scene.frame_preview_start
        frame_end = scene.frame_preview_end
    else:
        frame_start = scene.frame_start
        frame_end = scene.frame_end

    # Get camera info
    camera = scene.camera
    if camera and camera.type == "CAMERA":
        camera_focal = f"{camera.data.lens:.2f}"
        camera_name = camera.name
        camera_lens_unit = camera.data.type
    else:
        camera_focal = ""
        camera_name = ""
        camera_lens_unit = ""

    # Get view layer info
    view_layer = context.view_layer
    view_layer_name = view_layer.name if view_layer else ""

    # Get blend file info
    blend_file = os.path.basename(bpy.data.filepath) if bpy.data.filepath else "unsaved"

    fps = render.fps / render.fps_base

    now = datetime.now()

    metadata: MetaData = {
        "datetime": now.isoformat(sep=" ", timespec="seconds"),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "width": res_x,
        "height": res_y,
        "file_name": playblaster.file.name,
        "file_version": playblaster.file.version_str,
        "file_ext": playblaster.file.extension,
        "file_full_name": os.path.basename(playblaster.file.full_path),
        "blend_file": blend_file,
        "scene_name": scene.name,
        "view_layer": view_layer_name,
        "frame_current": scene.frame_current,
        "frame_start": frame_start,
        "frame_end": frame_end,
        "frame_total": frame_end - frame_start + 1,
        "frame_rate": int(render.fps),
        "timecode": frame_to_timecode(scene.frame_current, fps),
        "marker": get_nearest_marker(scene, scene.frame_current),
        "camera_name": camera_name,
        "camera_focal": camera_focal,
        "camera_lens_unit": camera_lens_unit,
        "user": getpass.getuser(),
        "blender_version": bpy.app.version_string,
    }

    return defaultdict(str, metadata)
