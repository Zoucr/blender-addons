"""Camera Path Rig 3D Viewport sidebar UI."""

import bpy
from bpy.types import Panel, UIList

from .common import *


class CPR_UL_rigs(UIList):
    """Compact scene-local browser for generated Camera Path Rigs."""

    def filter_items(self, context, data, property_name):
        items = getattr(data, property_name)
        scene = context.scene
        scene_uid = _scene_uid(scene)
        flags = []
        for ob in items:
            visible = (
                ob.type == 'CURVE'
                and ob.get(TAG_ROLE) == ROLE_PATH
                and (
                    not ob.get(TAG_SCENE_ID)
                    or ob.get(TAG_SCENE_ID) == scene_uid
                )
            )
            flags.append(self.bitflag_filter_item if visible else 0)
        return flags, []

    def draw_item(
        self,
        context,
        layout,
        _data,
        item,
        _icon,
        _active_data,
        _active_property,
        _index,
    ):
        if item is None or item.get(TAG_ROLE) != ROLE_PATH:
            return
        scene = context.scene
        settings = scene.cpr_settings
        row = layout.row(align=True)
        current_icon = (
            'RADIOBUT_ON' if settings.active_rig == item.name else 'RADIOBUT_OFF'
        )
        row.label(
            text=item.get("cpr_display_name", item.name),
            icon=current_icon,
        )
        camera = item.cpr_rig.camera or _object_for_role(item, ROLE_CAMERA)
        if camera is not None and scene.camera == camera:
            row.label(text="", icon='OUTLINER_OB_CAMERA')
        row.label(
            text=f"{item.cpr_rig.start_frame}-{_rig_end_frame(item, scene)}",
            icon='TIME',
        )

class CPR_PT_main(Panel):
    bl_label = "Camera Path Rig"
    bl_idname = "CPR_PT_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Camera Path"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        settings = scene.cpr_settings

        create = layout.box()
        header = create.row()
        header.prop(
            settings,
            "show_creation",
            text="Creation",
            emboss=False,
            icon='TRIA_DOWN' if settings.show_creation else 'TRIA_RIGHT',
        )
        if settings.show_creation:
            setting_box = create.box()
            setting_header = setting_box.row()
            setting_header.prop(
                settings,
                "show_creation_settings",
                text="Rig Settings",
                emboss=False,
                icon='TRIA_DOWN' if settings.show_creation_settings else 'TRIA_RIGHT',
            )
            if settings.show_creation_settings:
                start_frame = scene.frame_current
                setting_box.prop(settings, "path_preset", text="Path Preset")
                if settings.path_preset == 'SELECTED':
                    source = context.object
                    if source is not None and source.type == 'CURVE':
                        setting_box.label(text=f"Source: {source.name}", icon='CURVE_BEZCURVE')
                    else:
                        warning = setting_box.row()
                        warning.alert = True
                        warning.label(text="Select a Curve object", icon='ERROR')

                if settings.path_preset != 'SELECTED':
                    preset_box = setting_box.box()
                    preset_header = preset_box.row()
                    preset_header.prop(
                        settings,
                        "show_preset_settings",
                        text="Preset Settings",
                        emboss=False,
                        icon=(
                            'TRIA_DOWN' if settings.show_preset_settings
                            else 'TRIA_RIGHT'
                        ),
                    )
                    if settings.show_preset_settings:
                        if settings.path_preset == 'STRAIGHT':
                            preset_box.prop(settings, "path_length")
                        else:
                            preset_box.prop(settings, "preset_radius")

                setting_box.prop(settings, "duration_mode", text="Unit", expand=True)
                if settings.duration_mode == 'SECONDS':
                    setting_box.prop(settings, "duration_seconds")
                    frames = max(1, round(settings.duration_seconds * _fps(scene)))
                    setting_box.label(
                        text=f"End frame: {start_frame + frames} ({frames} frames)"
                    )
                else:
                    setting_box.prop(settings, "duration_frames")
                    setting_box.label(
                        text=f"End frame: {start_frame + settings.duration_frames}"
                    )
                setting_box.prop(settings, "camera_lens")
                setting_box.prop(settings, "set_scene_range")
            create.operator("cpr.create_rig", icon='OUTLINER_OB_CAMERA')

        if not _rig_paths(scene):
            layout.label(text="Each new rig is independent and uniquely named.", icon='INFO')
            return

        rig_box = layout.box()
        rig_box.label(text="Existing Rig", icon='CAMERA_DATA')
        rig_box.template_list(
            "CPR_UL_rigs",
            "scene_rigs",
            scene,
            "objects",
            settings,
            "active_rig_index",
            rows=min(5, max(2, len(_rig_paths(scene)))),
        )
        path = _active_path(context)
        if path is None:
            return
        rig = path.cpr_rig

        timing = rig_box.box()
        timing_header = timing.row()
        timing_header.prop(
            settings,
            "show_timing",
            text="Timing",
            emboss=False,
            icon='TRIA_DOWN' if settings.show_timing else 'TRIA_RIGHT',
        )
        if settings.show_timing:
            timing.prop(rig, "start_frame")
            timing.prop(rig, "duration_mode", text="Unit", expand=True)
            if rig.duration_mode == 'SECONDS':
                timing.prop(rig, "duration_seconds")
                frames = max(1, round(rig.duration_seconds * _fps(scene)))
            else:
                timing.prop(rig, "duration_frames")
                frames = rig.duration_frames
            timing.prop(rig, "interpolation")
            timing.prop(rig, "set_scene_range")
            timing.label(text=f"Start {rig.start_frame}  ->  End {rig.start_frame + frames}")
            timing.operator("cpr.apply_timing", icon='KEY_HLT')

        path_box = rig_box.box()
        path_header = path_box.row()
        path_header.prop(
            settings,
            "show_path_controls",
            text="Path Controls",
            emboss=False,
            icon='TRIA_DOWN' if settings.show_path_controls else 'TRIA_RIGHT',
        )
        if settings.show_path_controls:
            dolly = rig.dolly or _object_for_role(path, ROLE_DOLLY)
            follow = next(
                (
                    constraint for constraint in dolly.constraints
                    if constraint.type == 'FOLLOW_PATH'
                    and constraint.target == path
                ),
                None,
            ) if dolly is not None else None
            if follow is not None:
                path_box.use_property_split = True
                path_box.use_property_decorate = True
                path_box.prop(
                    follow,
                    "offset_factor",
                    text="Progress",
                    slider=True,
                )
            path_box.prop(rig, "show_direction")
            path_box.prop(rig, "smooth_strength")
            path_box.operator("cpr.smooth_path", icon='MOD_SMOOTH')

        animation_box = rig_box.box()
        animation_header = animation_box.row()
        animation_header.prop(
            settings,
            "show_animation",
            text="Aim Path",
            emboss=False,
            icon='TRIA_DOWN' if settings.show_animation else 'TRIA_RIGHT',
        )
        if settings.show_animation:
            aim_path = rig.aim_path or _object_for_role(path, ROLE_AIM_PATH)
            aim_dolly = rig.aim_dolly or _object_for_role(path, ROLE_AIM_DOLLY)
            if aim_path is None or aim_dolly is None:
                animation_box.operator(
                    "cpr.create_aim_path",
                    text="Create from Camera Path",
                    icon='CURVE_BEZCURVE',
                )
            else:
                select_row = animation_box.row(align=True)
                select = select_row.operator(
                    "cpr.select_control",
                    text="Curve",
                    icon='CURVE_BEZCURVE',
                )
                select.role = ROLE_AIM_PATH
                select = select_row.operator(
                    "cpr.select_control",
                    text="Dolly",
                    icon='EMPTY_AXIS',
                )
                select.role = ROLE_AIM_DOLLY
                follow = next(
                    (
                        constraint for constraint in aim_dolly.constraints
                        if constraint.type == 'FOLLOW_PATH'
                        and constraint.target == aim_path
                    ),
                    None,
                )
                if follow is not None:
                    animation_box.use_property_split = True
                    animation_box.use_property_decorate = True
                    animation_box.prop(
                        follow,
                        "offset_factor",
                        text="Progress",
                        slider=True,
                    )
                animation_box.prop(rig, "focus_follows_aim_path")
                row = animation_box.row(align=True)
                row.operator(
                    "cpr.create_aim_path",
                    text="Replace from Camera Path",
                    icon='FILE_REFRESH',
                )
                row.operator("cpr.remove_aim_path", text="Remove", icon='X')

        controls = rig_box.row(align=True)
        select = controls.operator("cpr.select_control", text="Curve")
        select.role = ROLE_PATH
        select = controls.operator("cpr.select_control", text="Aim")
        select.role = ROLE_AIM
        select = controls.operator("cpr.select_control", text="Focus")
        select.role = ROLE_FOCUS
        select = controls.operator("cpr.select_control", text="Cam")
        select.role = ROLE_CAMERA

        camera_box = rig_box.box()
        camera_header = camera_box.row()
        camera_header.prop(
            settings,
            "show_camera_switching",
            text="Camera Switching",
            emboss=False,
            icon='TRIA_DOWN' if settings.show_camera_switching else 'TRIA_RIGHT',
        )
        if settings.show_camera_switching:
            row = camera_box.row(align=True)
            row.operator("cpr.make_camera_active", icon='CAMERA_DATA')
            row.operator("cpr.add_camera_cut", icon='MARKER_HLT')

        rig_box.operator("cpr.bake_camera", icon='ACTION')

        danger = layout.box()
        delete_row = danger.row(align=True)
        delete_row.operator("cpr.delete_rig", text="Delete Rig", icon='TRASH')
        delete_all = delete_row.row(align=True)
        delete_all.alert = True
        delete_all.operator(
            "cpr.delete_all_rigs",
            text="Delete All",
            icon='CANCEL',
        )




CLASSES = (CPR_UL_rigs, CPR_PT_main)
