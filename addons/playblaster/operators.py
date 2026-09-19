import json
import os
import shutil
import subprocess
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import bpy
from bl_operators.presets import AddPresetBase
from bpy.app.translations import pgettext_rpt as rpt_
from bpy_extras.io_utils import ExportHelper, ImportHelper

from .metadata import get_metadata
from .paths import BFONT_PATH, TEMPLATE_ASS_PATH
from .utils import detect_ffmpeg, get_full_font_name, play_video


@contextmanager
def render_properties_override(context: bpy.types.Context):
    """Context manager for overriding render properties during playblast"""

    scene = context.scene
    render = scene.render
    playblaster = scene.playblaster
    metadata = get_metadata(context)

    space = context.space_data
    region = space.region_3d

    # Store original render properties
    resolution_x = render.resolution_x
    resolution_y = render.resolution_y
    resolution_percentage = render.resolution_percentage

    frame_current = scene.frame_current
    frame_start = scene.frame_start
    frame_end = scene.frame_end
    use_preview_range = scene.use_preview_range

    filepath = render.filepath
    use_file_extension = render.use_file_extension
    use_render_cache = render.use_render_cache

    if bpy.app.version >= (5, 0):
        media_type = render.image_settings.media_type
    file_format = render.image_settings.file_format
    color_mode = render.image_settings.color_mode
    color_depth = render.image_settings.color_depth
    compression = render.image_settings.compression
    multiview = render.use_multiview

    shading_type = space.shading.type
    show_xray = space.shading.show_xray
    show_overlays = space.overlay.show_overlays

    # Setup render properties for playblast
    render.resolution_x = metadata["width"]
    render.resolution_y = metadata["height"]
    render.resolution_percentage = 100

    # Use scene frame range instead of preview range
    # Audio range will always use scene frame range
    if playblaster.override.use_frame_range:
        scene.use_preview_range = False
        scene.frame_start = playblaster.override.frame_start
        scene.frame_end = playblaster.override.frame_end
    elif scene.use_preview_range:
        scene.frame_start = scene.frame_preview_start
        scene.frame_end = scene.frame_preview_end

    render.use_file_extension = True
    render.use_render_cache = False

    if bpy.app.version >= (5, 0):
        render.image_settings.media_type = "IMAGE"
    render.image_settings.file_format = "PNG"
    # Use RGBA so the alpha channel is preserved for background color compositing
    render.image_settings.color_mode = "RGBA"
    render.image_settings.color_depth = "8"
    render.image_settings.compression = 15
    render.use_multiview = False

    if playblaster.override.use_viewport_shading:
        space.shading.type = playblaster.override.viewport_shading
    space.shading.show_xray = False
    space.overlay.show_overlays = playblaster.override.show_overlays

    try:
        # Ensure the VIEW_3D area is in camera view
        region.view_perspective = "CAMERA"

        yield
    finally:
        # Restore original render properties
        render.resolution_x = resolution_x
        render.resolution_y = resolution_y
        render.resolution_percentage = resolution_percentage

        scene.frame_set(frame_current)
        scene.frame_start = frame_start
        scene.frame_end = frame_end
        scene.use_preview_range = use_preview_range

        render.filepath = filepath
        render.use_file_extension = use_file_extension
        render.use_render_cache = use_render_cache

        if bpy.app.version >= (5, 0):
            render.image_settings.media_type = media_type
        render.image_settings.file_format = file_format
        render.image_settings.color_mode = color_mode
        render.image_settings.color_depth = color_depth
        render.image_settings.compression = compression
        render.use_multiview = multiview

        space.shading.type = shading_type
        space.shading.show_xray = show_xray
        space.overlay.show_overlays = show_overlays


@contextmanager
def register_collect_metadata_handler(context: bpy.types.Context):
    """Register a handler to collect metadata durning playblast.

    The collected metadata will temporarily stored in `scene.playblaster["metadata"]`.
    """

    def handler(scene: bpy.types.Scene):
        metadata = get_metadata(bpy.context, is_rendering=True)
        scene.playblaster["metadata"][str(scene.frame_current)] = metadata

    context.scene.playblaster["metadata"] = {}
    bpy.app.handlers.frame_change_post.append(handler)

    try:
        yield
    finally:
        bpy.app.handlers.frame_change_post.remove(handler)
        del context.scene.playblaster["metadata"]


class PLAYBLASTER_OT_run(bpy.types.Operator):
    bl_idname = "render.playblaster"
    bl_label = "Playblast"
    bl_description = (
        "Create a playblast video of the current scene.\n"
        "Please ensure you have an active camera and ffmpeg is installed in your system."
    )

    launch_player: bpy.props.BoolProperty(
        name="Launch Player",
        description=(
            "Whether to open the video player after playblast. "
            "For batch scripts set to False to prevent popping up the player."
        ),
        default=True,
    )

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return (
            cls.get_view_3d_area(context) is not None
            and context.scene.camera is not None
        )

    @staticmethod
    def get_view_3d_area(context: bpy.types.Context) -> bpy.types.Area | None:
        """Auto-detect the 3D View area."""

        if context.area.type == "VIEW_3D":
            return context.area

        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                return area

        return None

    def execute(self, context: bpy.types.Context):
        # First detect whether ffmpeg is installed
        if not detect_ffmpeg():
            self.report(
                {"ERROR"},
                "FFmpeg is not installed or not found in PATH.",
            )
            return {"CANCELLED"}

        # Enter view 3D area to ensure correct context for rendering
        area = self.get_view_3d_area(context)
        region = next(r for r in area.regions if r.type == "WINDOW")

        with (
            bpy.context.temp_override(area=area, region=region),
            TemporaryDirectory(prefix="blender_playblaster_") as temp_dir,
            render_properties_override(context),
            register_collect_metadata_handler(context),
        ):
            self.temp_dir = Path(temp_dir)
            self.temp_png = self.temp_dir / "%04d.png"
            self.temp_sub = self.temp_dir / "subtitle.ass"
            self.temp_aud = self.temp_dir / "audio.mp3"
            self.temp_font = self.copy_font_to_temp(context)
            self.render_width = context.scene.render.resolution_x
            self.render_height = context.scene.render.resolution_y

            # Use OpenGL render to render frames
            context.scene.render.filepath = self.temp_dir.as_posix() + "/"
            bpy.ops.render.opengl(animation=True, view_context=True)

            # Keep date and time for each frame is the same
            now = datetime.now()
            for data in context.scene.playblaster["metadata"].values():
                data["datetime"] = now.isoformat(sep=" ", timespec="seconds")
                data["date"] = now.strftime("%Y-%m-%d")
                data["time"] = now.strftime("%H:%M:%S")

            # Get real frame range
            if context.scene.use_preview_range:
                self.frame_start = context.scene.frame_preview_start
                self.frame_end = context.scene.frame_preview_end
            else:
                self.frame_start = context.scene.frame_start
                self.frame_end = context.scene.frame_end

            self.build_subtitles(context)
            self.build_audio(context)
            success = self.build_video(context)

        # Bump the version so the next playblast doesn't overwrite this one
        file_props = context.scene.playblaster.file
        if success and file_props.use_version:
            file_props.version += 1

        return {"FINISHED"}

    def copy_font_to_temp(self, context: bpy.types.Context) -> Path:
        """Copy the specified font to temporary directory for ffmpeg usage.

        This can avoid many error logs for ffmpeg.
        """
        font_path: Path = context.scene.playblaster.burn_in.font_family
        if not font_path or not os.path.exists(font_path):
            font_path = BFONT_PATH
        else:
            font_path = Path(font_path)

        temp_font = Path(self.temp_dir, "font", font_path.name)
        temp_font.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(font_path, temp_font)
        return temp_font

    def build_subtitles(self, context: bpy.types.Context):
        """Build subtitles of metadata for the video."""

        def frame_to_timecode(frame, fps):
            """Convert frame number to ASS timecode format (H:MM:SS.cs)."""
            total_seconds = frame / fps
            hours = int(total_seconds // 3600)
            minutes = int((total_seconds % 3600) // 60)
            seconds = total_seconds % 60

            if frame != 0:
                seconds -= 0.01

            # ASS uses centiseconds (0.01s) for the fractional part
            return f"{hours}:{minutes:02d}:{seconds:06.2f}"

        def get_hex_color(color):
            """Get the color hex code that used in ASS subtitles."""
            color = list(color)

            # # Convert scene linear to srgb
            # color[0:3] = list(mathutils.Color(color[:3]).from_scene_linear_to_srgb())

            # ASS Subtitle use reversed alpha channel
            color[3] = 1 - color[3]

            # ASS Subtitle use reversed order, it is AABBGGRR
            color.reverse()

            for i, c in enumerate(color):
                # Convert color from 0~1 to 0~255
                cc = int(round(c * 255))

                # Convert color from dec to hex
                color[i] = f"{cc:02X}"

            return "".join(["&H", *color])

        scene = context.scene
        playblaster = scene.playblaster

        if not playblaster.burn_in.enable:
            return

        with open(TEMPLATE_ASS_PATH, "r", encoding="utf-8") as f:
            template_ass = f.read()

        res_x = scene.render.resolution_x
        res_y = scene.render.resolution_y
        fps = scene.render.fps

        # Get real name of font
        font_name = get_full_font_name(self.temp_font)

        # Keep text ratio regardless of resolution scale
        font_size = (
            playblaster.burn_in.font_size * playblaster.override.scale // 100
        )

        # Get correct color format
        font_color = get_hex_color(playblaster.burn_in.color)

        subtitles = template_ass.format_map(
            {
                "res_x": res_x,
                "res_y": res_y,
                "font_name": font_name,
                "font_size": font_size,
                "font_color": font_color,
            }
        )

        # Also scale margin to keep aspect ratio
        margin = playblaster.burn_in.margin * playblaster.override.scale // 100

        # Notice that the origin (0,0) is at the top-left corner for ass subtitles
        # pos, align, x, y
        vars = [
            (
                "top_left",
                "7",
                margin,
                margin,
            ),
            (
                "top_center",
                "8",
                res_x // 2,
                margin,
            ),
            (
                "top_right",
                "9",
                res_x - margin,
                margin,
            ),
            (
                "bottom_left",
                "1",
                margin,
                res_y - margin,
            ),
            (
                "bottom_center",
                "2",
                res_x // 2,
                res_y - margin,
            ),
            (
                "bottom_right",
                "3",
                res_x - margin,
                res_y - margin,
            ),
        ]

        dialogues = []
        template_dialogue = "Dialogue: 0,{start},{end},default,,0,0,0,,{{\\an{align}\\pos({x},{y})}}{text}"
        for frame in range(self.frame_start, self.frame_end + 1):
            metadata = scene.playblaster["metadata"][str(frame)]
            start = frame_to_timecode(frame - self.frame_start, fps)
            end = frame_to_timecode(frame - self.frame_start + 1, fps)

            for pos, align, x, y in vars:
                # Skip if this slot is disabled
                if not getattr(playblaster.burn_in, f"use_{pos}"):
                    continue
                text = getattr(playblaster.burn_in, pos)
                try:
                    text = text.format_map(metadata)
                except Exception:
                    self.report(f'Error burn in text in {pos}: "{text}"')
                    continue

                dialogue = template_dialogue.format(
                    start=start,
                    end=end,
                    align=align,
                    x=x,
                    y=y,
                    text=text,
                )
                dialogues.append(dialogue)

        subtitles += "\n".join(dialogues)

        # Save subtitles to temporary folder
        with open(self.temp_sub, "w", encoding="utf-8") as f:
            f.write(subtitles)

    def build_audio(self, context: bpy.types.Context):
        """Build audio file use blender's built-in tools."""

        if not context.scene.playblaster.video.include_audio:
            return

        # Render audio
        bpy.ops.sound.mixdown(
            filepath=self.temp_aud.as_posix(),
            container="MP3",
            codec="MP3",
        )

    def build_video(self, context: bpy.types.Context):
        """Build video from the rendered frames using ffmpeg."""

        playblaster = context.scene.playblaster
        output_path = playblaster.file.full_path
        codec = playblaster.video.codec
        include_audio = playblaster.video.include_audio
        enable_burn_in = playblaster.burn_in.enable
        use_bg_color = playblaster.override.use_background_color
        bg_color = playblaster.override.background_color

        # Get crf for different codecs
        match codec:
            case "libx264":
                crf = 23
            case "libx265":
                crf = 28
            case "mpeg4":
                crf = 5
            case "libsvtav1":
                crf = 35
            case _:
                crf = 23

        escape_font_path = self.temp_font.parent.as_posix().replace(":", "\\:")
        escape_sub_path = self.temp_sub.as_posix().replace(":", "\\:")

        # Ensure output path exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Determine audio input index (0=png, 1=audio or 1=color+audio when bg active)
        audio_index = 2 if (use_bg_color and include_audio) else 1

        # Build inputs
        inputs = (
            f"-framerate {context.scene.render.fps} "
            f"-start_number {self.frame_start} "
            f'-i "{self.temp_png.as_posix()}" '
        )

        if use_bg_color:
            # Convert float color (0–1) to ffmpeg hex color string
            r = int(round(bg_color[0] * 255))
            g = int(round(bg_color[1] * 255))
            b = int(round(bg_color[2] * 255))
            hex_color = f"0x{r:02X}{g:02X}{b:02X}"
            # Add a color source as second input, matching render resolution and framerate
            inputs += (
                f"-f lavfi -i "
                f'"color=c={hex_color}:s={self.render_width}x{self.render_height}'
                f':r={context.scene.render.fps}" '
            )

        if include_audio:
            inputs += f'-i "{self.temp_aud.as_posix()}" '

        # Build filter / map arguments
        if use_bg_color:
            # Composite: overlay RGBA frames (input 0) over solid color (input 1)
            # Result label [v]; then optionally pipe through subtitle filter
            composite = "[1:v][0:v]overlay=format=auto"
            if enable_burn_in:
                composite += f",subtitles='{escape_sub_path}':fontsdir='{escape_font_path}'"
            composite += "[v]"
            filter_arg = f'-filter_complex "{composite}" -map "[v]" '
        else:
            filter_arg = "-map 0:v:0 "
            if enable_burn_in:
                filter_arg += f"-vf \"subtitles='{escape_sub_path}':fontsdir='{escape_font_path}'\" "

        audio_map = f"-map {audio_index}:a:0 " if include_audio else ""

        ffmpeg_cmd = (
            "ffmpeg -y "
            + inputs
            + f"-c:v {codec} "
            + ("-c:a copy " if include_audio else "")
            + filter_arg
            + audio_map
            + f"-crf {crf} "
            + "-pix_fmt yuv420p "
            + f"-frames:v {self.frame_end - self.frame_start + 1} "
            + f'"{output_path}"'
        )

        try:
            print("\n=== PLAYBLASTER: FFmpeg command ===")
            print(ffmpeg_cmd)
            print("=====================================\n")
            result = subprocess.run(
                ffmpeg_cmd,
                shell=True,
                check=True,
                capture_output=True,
                text=True,
            )
            if result.stdout:
                print(result.stdout)
            if result.stderr:
                print(result.stderr)

            # Following launch_player logic to decide whether to open video after playblast
            if getattr(self, "launch_player", True):
                self.report(
                    {"INFO"},
                    rpt_(
                        msgid='Playblast completed, saved to "{}", opening video...'
                    ).format(output_path),
                )

                play_video(output_path)
            else:
                self.report(
                    {"INFO"},
                    rpt_(msgid='Playblast completed, saved to "{}"').format(
                        output_path
                    ),
                )

            if os.environ.get("OCIO") and bpy.app.version < (5, 0):
                self.report(
                    {"WARNING"},
                    rpt_(
                        "OCIO environment variable detected. Video playback may crash on Blender versions before 5.0\n"
                        "If you encounter a crash, please try to unset OCIO environment variable or upgrade to Blender 5.0 or later."
                    ),
                )

            return True
        except subprocess.CalledProcessError as e:
            print("\n=== PLAYBLASTER: FFmpeg FAILED ===")
            if e.stdout:
                print("STDOUT:", e.stdout)
            if e.stderr:
                print("STDERR:", e.stderr)
            print("=====================================\n")
            self.report(
                {"ERROR"},
                f"FFmpeg processing failed: {e.stderr.splitlines()[-1] if e.stderr else 'see console for details'}",
            )
            return False


class PLAYBLASTER_OT_import_settings(bpy.types.Operator, ImportHelper):
    bl_idname = "playblaster.import_settings"
    bl_label = "Import Settings"
    bl_description = "Import Playblaster settings from a file"

    filename_ext = ".json"
    filter_glob: bpy.props.StringProperty(default="*.json", options={"HIDDEN"})

    def execute(self, context):
        playblaster = context.scene.playblaster
        with open(self.filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Reuse the same data structure as preset
        for attr, value in data.items():
            _, prop_group, prop_name = attr.split(".")
            prop = getattr(playblaster, prop_group)

            # Convert list back to color property
            if isinstance(getattr(prop, prop_name), bpy.types.bpy_prop_array):
                value = tuple(value)

            setattr(prop, prop_name, value)

        return {"FINISHED"}


class PLAYBLASTER_OT_export_settings(bpy.types.Operator, ExportHelper):
    bl_idname = "playblaster.export_settings"
    bl_label = "Export Settings"
    bl_description = "Export current Playblaster settings to a file"

    filename_ext = ".json"
    filter_glob: bpy.props.StringProperty(default="*.json", options={"HIDDEN"})

    def execute(self, context: bpy.types.Context):
        playblaster = context.scene.playblaster

        # Reuse the same data structure as preset
        data = {}
        for attr in PLAYBLASTER_OT_preset_add.preset_values:
            _, prop_group, prop_name = attr.split(".")
            value = getattr(getattr(playblaster, prop_group), prop_name)

            # Convert color to list for json serialization
            if isinstance(value, bpy.types.bpy_prop_array):
                value = list(value)

            data[attr] = value

        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

        return {"FINISHED"}


class PLAYBLASTER_OT_preset_add(AddPresetBase, bpy.types.Operator):
    """Add a Playblaster Preset"""

    bl_idname = "playblaster.preset_add"
    bl_label = "Add Playblaster Preset"
    preset_menu = "PLAYBLASTER_PT_presets"
    preset_subdir = "playblaster"

    preset_defines = [
        "playblaster = bpy.context.scene.playblaster",
    ]

    preset_values = [
        "playblaster.video.include_audio",
        "playblaster.video.codec",
        "playblaster.override.scale",
        "playblaster.override.show_overlays",
        "playblaster.override.use_viewport_shading",
        "playblaster.override.viewport_shading",
        "playblaster.override.use_background_color",
        "playblaster.override.background_color",
        "playblaster.file.directory",
        "playblaster.file.name",
        "playblaster.file.use_version",
        "playblaster.file.extension",
        "playblaster.burn_in.enable",
        "playblaster.burn_in.preview",
        "playblaster.burn_in.font_family",
        "playblaster.burn_in.font_size",
        "playblaster.burn_in.margin",
        "playblaster.burn_in.color",
        "playblaster.burn_in.use_top_left",
        "playblaster.burn_in.top_left",
        "playblaster.burn_in.use_top_center",
        "playblaster.burn_in.top_center",
        "playblaster.burn_in.use_top_right",
        "playblaster.burn_in.top_right",
        "playblaster.burn_in.use_bottom_left",
        "playblaster.burn_in.bottom_left",
        "playblaster.burn_in.use_bottom_center",
        "playblaster.burn_in.bottom_center",
        "playblaster.burn_in.use_bottom_right",
        "playblaster.burn_in.bottom_right",
    ]


classes = (
    PLAYBLASTER_OT_run,
    PLAYBLASTER_OT_import_settings,
    PLAYBLASTER_OT_export_settings,
    PLAYBLASTER_OT_preset_add,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
