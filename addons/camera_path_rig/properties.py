"""Add-on preferences plus per-scene and per-rig properties."""

import bpy
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)
from bpy.types import AddonPreferences, PropertyGroup

from .common import *


def _update_active_rig_index(self, _context):
    scene = getattr(self, "id_data", None)
    if scene is None:
        return
    index = self.active_rig_index
    if not 0 <= index < len(scene.objects):
        return
    candidate = scene.objects[index]
    if candidate in _rig_paths(scene):
        self.active_rig = candidate.name


def _update_focus_follows_aim_path(self, _context):
    path = getattr(self, "id_data", None)
    if path is None or getattr(path, "type", None) != 'CURVE':
        return
    aim_path = self.aim_path or _object_for_role(path, ROLE_AIM_PATH)
    aim_dolly = self.aim_dolly or _object_for_role(path, ROLE_AIM_DOLLY)
    focus = self.focus or _object_for_role(path, ROLE_FOCUS)
    if aim_path is None or aim_dolly is None or focus is None:
        return
    _set_parent_preserve_world(
        focus,
        aim_dolly if self.focus_follows_aim_path else None,
    )

class CPR_Preferences(AddonPreferences):
    bl_idname = ADDON_ID

    overlay_color: FloatVectorProperty(
        name="Camera Path Color",
        description="Viewport color used for the camera path and direction arrows",
        subtype='COLOR',
        size=4,
        min=0.0,
        max=1.0,
        default=DEFAULT_OVERLAY_COLOR,
    )
    aim_overlay_color: FloatVectorProperty(
        name="Aim Path Color",
        description="Viewport color used for the Aim Path and its direction arrows",
        subtype='COLOR',
        size=4,
        min=0.0,
        max=1.0,
        default=DEFAULT_AIM_OVERLAY_COLOR,
    )
    overlay_line_width: FloatProperty(
        name="Line Width",
        description="Width of the blue path overlay in pixels",
        default=DEFAULT_LINE_WIDTH,
        min=1.0,
        max=8.0,
    )
    path_opacity: FloatProperty(
        name="Path Opacity",
        description="Opacity of the path line; direction arrows remain fully visible",
        default=DEFAULT_PATH_OPACITY,
        min=0.05,
        max=1.0,
        subtype='FACTOR',
    )
    chevron_scale: FloatProperty(
        name="Arrow Size",
        description="Size multiplier for the V-shaped direction arrows",
        default=DEFAULT_CHEVRON_SCALE,
        min=0.15,
        max=3.0,
    )
    chevron_count: IntProperty(
        name="Arrow Count",
        description="Approximate number of direction arrows distributed along the path",
        default=DEFAULT_CHEVRON_COUNT,
        min=1,
        max=50,
    )

    def draw(self, _context):
        layout = self.layout
        layout.label(text="Viewport Path Direction")
        layout.prop(self, "overlay_color")
        layout.prop(self, "aim_overlay_color")
        layout.prop(self, "overlay_line_width")
        layout.prop(self, "path_opacity")
        layout.prop(self, "chevron_scale")
        layout.prop(self, "chevron_count")
        layout.label(text="The master Viewport Overlays toggle also hides this display.", icon='INFO')


class CPR_PG_scene(PropertyGroup):
    show_creation: BoolProperty(name="Creation", default=False)
    show_creation_settings: BoolProperty(name="Rig Settings", default=False)
    show_timing: BoolProperty(name="Timing", default=False)
    show_path_controls: BoolProperty(name="Path Controls", default=False)
    show_animation: BoolProperty(name="Animation", default=False)
    show_camera_switching: BoolProperty(name="Camera Switching", default=False)
    show_preset_settings: BoolProperty(name="Preset Settings", default=False)
    active_rig: StringProperty(name="Rig")
    active_rig_index: IntProperty(
        name="Active Rig Index",
        default=0,
        min=0,
        update=_update_active_rig_index,
    )
    path_preset: EnumProperty(
        name="Path Preset",
        items=(
            ('STRAIGHT', "Line", "Create a straight three-point line path"),
            ('HALF_CIRCLE', "Half Circle", "Create an open 180-degree path around the 3D Cursor"),
            ('FULL_CIRCLE', "Full Circle", "Create a closed 360-degree path around the 3D Cursor"),
            ('SELECTED', "Selected Curve", "Copy the selected Curve object into the new rig"),
        ),
        default='STRAIGHT',
    )
    duration_mode: EnumProperty(
        name="Duration Unit",
        items=(
            ('FRAMES', "Frames", "Set duration in frames"),
            ('SECONDS', "Seconds", "Set duration in seconds using the scene FPS"),
        ),
        default='FRAMES',
    )
    duration_frames: IntProperty(name="Duration", default=120, min=1, soft_max=10000)
    duration_seconds: FloatProperty(name="Duration", default=5.0, min=0.01, soft_max=600.0)
    path_length: FloatProperty(name="Path Length", default=12.0, min=0.1, unit='LENGTH')
    preset_radius: FloatProperty(name="Radius", default=6.0, min=0.1, unit='LENGTH')
    camera_lens: FloatProperty(name="Lens", default=50.0, min=1.0, max=500.0, unit='CAMERA')
    set_scene_range: BoolProperty(
        name="Set Scene Range",
        description="Set the scene start and end frames to this new rig",
        default=False,
    )


class CPR_PG_rig(PropertyGroup):
    is_rig: BoolProperty(default=False)
    start_frame: IntProperty(name="Start Frame", default=1)
    duration_mode: EnumProperty(
        name="Duration Unit",
        items=(
            ('FRAMES', "Frames", "Set duration in frames"),
            ('SECONDS', "Seconds", "Set duration in seconds using the scene FPS"),
        ),
        default='FRAMES',
    )
    duration_frames: IntProperty(name="Duration", default=120, min=1, soft_max=10000)
    duration_seconds: FloatProperty(name="Duration", default=5.0, min=0.01, soft_max=600.0)
    interpolation: EnumProperty(
        name="Motion",
        items=(
            ('BEZIER', "Smooth Start/End", "Ease in and out"),
            ('LINEAR', "Constant Speed", "Move at a constant rate"),
        ),
        default='BEZIER',
    )
    set_scene_range: BoolProperty(
        name="Set Scene Range",
        description="Make this rig's timing the scene playback range when timing is applied",
        default=False,
    )
    smooth_strength: FloatProperty(
        name="Smooth Amount",
        description="Move interior path points toward their neighbors; endpoints stay fixed",
        default=0.5,
        min=0.0,
        max=1.0,
        subtype='FACTOR',
    )
    show_direction: BoolProperty(
        name="Show Direction",
        description="Draw the active path in blue with chevrons pointing from start to end",
        default=True,
    )
    focus_follows_aim_path: BoolProperty(
        name="Move Focus with Aim Path",
        description=(
            "Parent Focus to the Aim Dolly; disable to animate Focus "
            "independently in world space"
        ),
        default=True,
        update=_update_focus_follows_aim_path,
    )
    dolly: PointerProperty(type=bpy.types.Object)
    camera: PointerProperty(type=bpy.types.Object)
    aim: PointerProperty(type=bpy.types.Object)
    focus: PointerProperty(type=bpy.types.Object)
    aim_path: PointerProperty(type=bpy.types.Object)
    aim_dolly: PointerProperty(type=bpy.types.Object)




CLASSES = (CPR_Preferences, CPR_PG_scene, CPR_PG_rig)
