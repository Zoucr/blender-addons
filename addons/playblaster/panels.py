import bpy
from bl_ui.utils import PresetPanel

from .metadata import META_DATA_DESCRIPTIONS


class PLAYBLASTER_PT_presets(PresetPanel, bpy.types.Panel):
    bl_label = "Playblaster Presets"
    preset_subdir = "playblaster"
    preset_operator = "script.execute_preset"
    preset_add_operator = "playblaster.preset_add"

    @staticmethod
    def post_cb(context, _filepath):
        # Modify an arbitrary built-in scene property to force a depsgraph
        # update, because add-on properties don't. (see #62325)
        # This is derived from addons_core/cycles/ui.py
        scene = context.scene
        scene.frame_step = scene.frame_step


class PLAYBLASTER_PT_main(bpy.types.Panel):
    bl_idname = "PLAYBLASTER_PT_main"
    bl_label = "Playblaster"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Tool"
    bl_options = {"DEFAULT_CLOSED"}

    def draw_header_preset(self, context):
        PLAYBLASTER_PT_presets.draw_panel_header(self.layout)

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        video_props = context.scene.playblaster.video
        layout.operator(
            "render.playblaster", text="Playblast", icon="RENDER_ANIMATION"
        )
        layout.separator()

        col = layout.column()
        col.prop(video_props, "codec")


class PLAYBLASTER_PT_override(bpy.types.Panel):
    bl_idname = "PLAYBLASTER_PT_override"
    bl_label = "Override"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Tool"
    bl_parent_id = "PLAYBLASTER_PT_main"
    bl_order = 0

    def draw(self, context: bpy.types.Context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        override_props = context.scene.playblaster.override

        col = layout.column()

        col.prop(override_props, "scale")

        row = col.row(align=True, heading="Frame Range")
        row.prop(override_props, "use_frame_range", text="")
        sub = row.column()
        sub.active = override_props.use_frame_range
        sub.prop(override_props, "frame_start", text="Start")
        sub.prop(override_props, "frame_end", text="End")

        col.prop(override_props, "show_overlays", icon="OVERLAY")

        col = layout.column()
        row = col.row(align=True, heading="Viewport Shading")
        row.prop(override_props, "use_viewport_shading", text="")
        sub = row.row()
        sub.active = override_props.use_viewport_shading
        sub.prop(override_props, "viewport_shading", text="", expand=True)


        col = layout.column()
        row = col.row(align=True, heading="Background Color")
        row.prop(override_props, "use_background_color", text="")
        sub = row.row()
        sub.active = override_props.use_background_color
        sub.prop(override_props, "background_color", text="")


class PLAYBLASTER_PT_file(bpy.types.Panel):
    bl_idname = "PLAYBLASTER_PT_file"
    bl_label = "File"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Tool"
    bl_parent_id = "PLAYBLASTER_PT_main"
    bl_order = 1

    def draw(self, context: bpy.types.Context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        file_props = context.scene.playblaster.file

        col = layout.column()

        col.prop(
            file_props,
            "directory",
            placeholder="Default to Desktop",
        )
        col.prop(file_props, "name")

        row = col.row(align=True, heading="Version")
        row.prop(file_props, "use_version", text="")
        sub = row.row(align=True)
        sub.active = file_props.use_version
        sub.prop(file_props, "version", text="")

        col.prop(file_props, "extension")
        col.prop(file_props, "full_path")


class PLAYBLASTER_PT_burn_in(bpy.types.Panel):
    bl_idname = "PLAYBLASTER_PT_burn_in"
    bl_label = "Burn-In Data"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Tool"
    bl_parent_id = "PLAYBLASTER_PT_main"
    bl_order = 2

    def draw_header(self, context: bpy.types.Context):
        layout = self.layout

        burn_in_props = context.scene.playblaster.burn_in
        layout.prop(burn_in_props, "enable", text="")
        layout.popover(panel="PLAYBLASTER_PT_burn_in_help", text="", icon="QUESTION")

    def draw(self, context: bpy.types.Context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        burn_in_props = context.scene.playblaster.burn_in

        col = layout.column()
        col.enabled = burn_in_props.enable

        col = layout.column()
        col.enabled = burn_in_props.enable

        col.prop(burn_in_props, "preview")
        col.prop(burn_in_props, "font_family", placeholder="Default to Blender Font")
        col.prop(burn_in_props, "font_size")
        col.prop(burn_in_props, "margin")
        col.prop(burn_in_props, "color")
        for use_prop, text_prop, label in (
            ("use_top_left",     "top_left",     "Top Left"),
            ("use_top_center",   "top_center",   "Top Center"),
            ("use_top_right",    "top_right",    "Top Right"),
            ("use_bottom_left",  "bottom_left",  "Bottom Left"),
            ("use_bottom_center","bottom_center","Bottom Center"),
            ("use_bottom_right", "bottom_right", "Bottom Right"),
        ):
            row = col.row(align=True, heading=label)
            row.prop(burn_in_props, use_prop, text="")
            sub = row.row(align=True)
            sub.active = getattr(burn_in_props, use_prop)
            sub.prop(burn_in_props, text_prop, text="")


class PLAYBLASTER_PT_burn_in_help(bpy.types.Panel):
    bl_idname = "PLAYBLASTER_PT_burn_in_help"
    bl_label = "Burn-In Data Help"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Tool"
    bl_ui_units_x = 25
    bl_options = {"INSTANCED"}

    def draw(self, context: bpy.types.Context):
        layout = self.layout

        layout.label(
            text="Use curly braces {} to denote variables in text, for example {datetime} for the current time."
        )
        layout.label(text="The following variables are currently available:")

        grid = layout.grid_flow(row_major=True, columns=2)
        for key, description in META_DATA_DESCRIPTIONS.items():
            grid.label(text=f"{{{key}}}")
            grid.label(text=description)


class PLAYBLASTER_PT_settings(bpy.types.Panel):
    bl_idname = "PLAYBLASTER_PT_settings"
    bl_label = "Settings"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Tool"
    bl_parent_id = "PLAYBLASTER_PT_main"
    bl_order = 3

    def draw(self, context: bpy.types.Context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        video_props = context.scene.playblaster.video
        layout.prop(video_props, "include_audio")

        row = layout.row()
        row.operator("playblaster.import_settings", text="Import", icon="IMPORT")
        row.operator("playblaster.export_settings", text="Export", icon="EXPORT")


classes = (
    PLAYBLASTER_PT_presets,
    PLAYBLASTER_PT_main,
    PLAYBLASTER_PT_override,
    PLAYBLASTER_PT_file,
    PLAYBLASTER_PT_burn_in,
    PLAYBLASTER_PT_burn_in_help,
    PLAYBLASTER_PT_settings,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
