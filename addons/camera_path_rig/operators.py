"""Rig creation, timing, path, switching, baking, and cleanup operators."""

import bpy
from bpy.props import EnumProperty
from bpy.types import Operator
from mathutils import Matrix, Vector

from .common import *

class CPR_OT_create_rig(Operator):
    bl_idname = "cpr.create_rig"
    bl_label = "Generate Camera Path Rig"
    bl_description = "Create a uniquely named camera, rig, aim control, and editable starter curve"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        settings = scene.cpr_settings
        source_curve = None
        if settings.path_preset == 'SELECTED':
            source_curve = context.object
            if source_curve is None or source_curve.type != 'CURVE':
                self.report({'ERROR'}, "Select a Curve object before generating the rig")
                return {'CANCELLED'}
            point_count = sum(
                len(spline.bezier_points) if spline.type == 'BEZIER'
                else len(spline.points)
                for spline in source_curve.data.splines
            )
            if point_count < 2:
                self.report({'ERROR'}, "The selected Curve needs at least two control points")
                return {'CANCELLED'}
            if source_curve.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')

        number, base = _unique_rig_base(scene)
        scene_uid = _scene_uid(scene)

        master = _master_collection(scene)
        collection = bpy.data.collections.new(base)
        rig_id = collection.name
        collection[TAG_SCENE_ID] = scene_uid
        collection[TAG_COLLECTION_ROLE] = COLLECTION_ROLE_RIG
        master.children.link(collection)
        try:
            collection.color_tag = 'COLOR_05'
        except Exception:
            pass

        cursor = scene.cursor.location.copy()
        if source_curve is not None:
            path = _copy_curve_for_rig(
                source_curve,
                f"{base}_Path",
                collection,
                rig_id,
            )
        elif settings.path_preset == 'STRAIGHT':
            points = _starter_path_points(settings.path_length)
            # Keep the straight path behind the Cursor so the camera never
            # occupies the same point as its new Cursor-based Aim target.
            path_origin = cursor + Vector((
                0.0,
                -max(settings.path_length * 0.5, 1.0),
                0.0,
            ))
            path = _create_curve(
                f"{base}_Path", points, path_origin, collection, rig_id
            )
        else:
            path = _create_circle_preset(
                f"{base}_Path",
                settings.preset_radius,
                cursor,
                collection,
                rig_id,
                full_circle=(settings.path_preset == 'FULL_CIRCLE'),
            )
        path["cpr_display_name"] = f"Rig {number:03d}"
        path[TAG_RIG_NUMBER] = number

        context.view_layer.update()
        path_extent = max(path.dimensions.length, 0.1)
        scale = max(0.12, min(2.5, path_extent / 20.0))
        dolly = _make_wire_object(
            f"{base}_Dolly",
            *_dolly_geometry(scale * 0.65),
            collection,
            rig_id,
            ROLE_DOLLY,
            (1.0, 0.45, 0.08, 1.0),
        )

        follow = dolly.constraints.new('FOLLOW_PATH')
        follow.name = FOLLOW_PATH_NAME
        follow.target = path
        if hasattr(follow, "use_fixed_location"):
            follow.use_fixed_location = True
        follow.use_curve_follow = False
        follow.offset_factor = 0.0

        gimbal = bpy.data.objects.new(f"{base}_Gimbal", None)
        collection.objects.link(gimbal)
        gimbal.empty_display_type = 'PLAIN_AXES'
        gimbal.empty_display_size = scale * 0.25
        gimbal.hide_render = True
        gimbal.show_in_front = True
        gimbal.parent = dolly
        gimbal.location = (0.0, 0.0, 0.0)
        _tag(gimbal, rig_id, ROLE_GIMBAL)

        aim = _make_wire_object(
            f"{base}_Aim",
            *_aim_geometry(scale * 0.75),
            collection,
            rig_id,
            ROLE_AIM,
            (0.95, 0.12, 0.12, 1.0),
        )
        aim.location = cursor
        aim.show_name = True

        focus = _make_wire_object(
            f"{base}_Focus",
            *_focus_geometry(scale * 0.35),
            collection,
            rig_id,
            ROLE_FOCUS,
            (0.3, 1.0, 0.3, 1.0),
        )
        focus.parent = aim
        focus.location = (0.0, 0.0, 0.0)

        track = gimbal.constraints.new('TRACK_TO')
        track.name = TRACK_TO_NAME
        track.target = aim
        track.track_axis = 'TRACK_NEGATIVE_Z'
        track.up_axis = 'UP_Y'

        camera_data = bpy.data.cameras.new(f"{base}_Camera_Data")
        _tag_owned_data(camera_data, rig_id, ROLE_CAMERA)
        camera_data.lens = settings.camera_lens
        camera_data.display_size = scale * 1.2
        camera_data.dof.use_dof = True
        camera_data.dof.focus_object = focus
        camera = bpy.data.objects.new(f"{base}_Camera", camera_data)
        collection.objects.link(camera)
        camera.parent = gimbal
        camera.location = (0.0, 0.0, 0.0)
        camera.rotation_euler = (0.0, 0.0, 0.0)
        camera.show_name = True
        camera.color = (0.25, 0.55, 1.0, 1.0)
        _tag(camera, rig_id, ROLE_CAMERA)

        rig = path.cpr_rig
        rig.is_rig = True
        rig.start_frame = scene.frame_current
        rig.duration_mode = settings.duration_mode
        rig.duration_frames = settings.duration_frames
        rig.duration_seconds = settings.duration_seconds
        rig.set_scene_range = settings.set_scene_range
        rig.dolly = dolly
        rig.camera = camera
        rig.aim = aim
        rig.focus = focus

        for ob in collection.objects:
            ob[TAG_SCENE_ID] = scene_uid
            ob[TAG_RIG_NUMBER] = number

        try:
            start, end = _set_timing(path, scene)
        except RuntimeError as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}

        _set_active_rig(scene, path)
        scene.camera = camera
        scene.frame_set(start)
        _select_only(context, aim)
        _collapse_ui_sections(settings)
        self.report({'INFO'}, f"Created {base}: frames {start} to {end}")
        return {'FINISHED'}


class CPR_OT_apply_timing(Operator):
    bl_idname = "cpr.apply_timing"
    bl_label = "Apply Timing"
    bl_description = "Rebuild this rig's path progress keys from the displayed start and duration"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _active_path(context) is not None

    def execute(self, context):
        path = _active_path(context)
        try:
            start, end = _set_timing(path, context.scene)
        except RuntimeError as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self.report({'INFO'}, f"Timing updated: frames {start} to {end}")
        return {'FINISHED'}


class CPR_OT_select_control(Operator):
    bl_idname = "cpr.select_control"
    bl_label = "Select Rig Control"
    bl_options = {'REGISTER', 'UNDO'}

    role: EnumProperty(
        items=(
            (ROLE_PATH, "Path", "Select the path"),
            (ROLE_DOLLY, "Dolly", "Select the dolly"),
            (ROLE_CAMERA, "Camera", "Select the camera"),
            (ROLE_AIM, "Aim", "Select the aim target"),
            (ROLE_FOCUS, "Focus", "Select the depth-of-field target"),
            (ROLE_AIM_PATH, "Aim Path", "Select the Aim Path curve"),
            (ROLE_AIM_DOLLY, "Aim Dolly", "Select the Aim Path dolly"),
        )
    )

    @classmethod
    def poll(cls, context):
        return _active_path(context) is not None

    def execute(self, context):
        path = _active_path(context)
        ob = path if self.role == ROLE_PATH else _object_for_role(path, self.role)
        if ob is None:
            self.report({'ERROR'}, "That rig control is missing")
            return {'CANCELLED'}
        if self.role in {ROLE_PATH, ROLE_AIM_PATH}:
            _make_existing_handles_rotatable(ob)
        _select_only(context, ob)
        return {'FINISHED'}


def _aim_path_for_rig(path):
    return path.cpr_rig.aim_path or _object_for_role(path, ROLE_AIM_PATH)


def _aim_dolly_for_rig(path):
    return path.cpr_rig.aim_dolly or _object_for_role(path, ROLE_AIM_DOLLY)


def _copy_camera_path_data(path, rig_id, name):
    data = path.data.copy()
    data.name = name
    data.animation_data_clear()
    _tag_owned_data(data, rig_id, ROLE_AIM_PATH)
    if hasattr(data, "bevel_depth"):
        data.bevel_depth = 0.0
    if hasattr(data, "extrude"):
        data.extrude = 0.0
    if hasattr(data, "bevel_object"):
        data.bevel_object = None
    if hasattr(data, "taper_object"):
        data.taper_object = None
    return data


class CPR_OT_create_aim_path(Operator):
    bl_idname = "cpr.create_aim_path"
    bl_label = "Create Aim Path"
    bl_description = (
        "Copy the camera path beside it and give the Aim an independent "
        "path-progress animation"
    )
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _active_path(context) is not None

    def execute(self, context):
        scene = context.scene
        path = _active_path(context)
        rig = path.cpr_rig
        rig_id = path.get(TAG_RIG_ID)
        camera_dolly = rig.dolly or _object_for_role(path, ROLE_DOLLY)
        aim = rig.aim or _object_for_role(path, ROLE_AIM)
        aim_path = _aim_path_for_rig(path)
        aim_dolly = _aim_dolly_for_rig(path)
        if camera_dolly is None or aim is None:
            self.report({'ERROR'}, "The camera dolly or Aim control is missing")
            return {'CANCELLED'}

        if context.object and context.object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        context.view_layer.update()
        depsgraph = context.evaluated_depsgraph_get()
        camera_position = camera_dolly.evaluated_get(
            depsgraph
        ).matrix_world.translation.copy()

        replacing = aim_path is not None and aim_dolly is not None
        if replacing:
            anchor_position = aim_dolly.evaluated_get(
                depsgraph
            ).matrix_world.translation.copy()
            old_data = aim_path.data
            aim_path.data = _copy_camera_path_data(
                path,
                rig_id,
                f"{rig_id}_AimPath_Data",
            )
            if (
                old_data.users == 0
                and old_data.get(TAG_DATA_OWNER) == rig_id
            ):
                bpy.data.curves.remove(old_data)
        else:
            anchor_position = aim.evaluated_get(
                depsgraph
            ).matrix_world.translation.copy()
            collection = next(iter(path.users_collection), None)
            if collection is None:
                self.report({'ERROR'}, "The rig collection is missing")
                return {'CANCELLED'}

            aim_path = bpy.data.objects.new(
                f"{rig_id}_AimPath",
                _copy_camera_path_data(path, rig_id, f"{rig_id}_AimPath_Data"),
            )
            collection.objects.link(aim_path)
            aim_path.hide_render = True
            aim_path.show_in_front = True
            aim_path.color = DEFAULT_AIM_OVERLAY_COLOR
            _tag(aim_path, rig_id, ROLE_AIM_PATH)
            aim_path[TAG_SCENE_ID] = path.get(TAG_SCENE_ID, "")
            aim_path[TAG_RIG_NUMBER] = path.get(TAG_RIG_NUMBER, 0)

            aim_dolly = bpy.data.objects.new(f"{rig_id}_AimDolly", None)
            collection.objects.link(aim_dolly)
            aim_dolly.empty_display_type = 'PLAIN_AXES'
            aim_dolly.empty_display_size = max(0.1, camera_dolly.dimensions.length * 0.3)
            aim_dolly.hide_render = True
            aim_dolly.hide_viewport = False
            _tag(aim_dolly, rig_id, ROLE_AIM_DOLLY)
            aim_dolly[TAG_SCENE_ID] = path.get(TAG_SCENE_ID, "")
            aim_dolly[TAG_RIG_NUMBER] = path.get(TAG_RIG_NUMBER, 0)

            follow = aim_dolly.constraints.new('FOLLOW_PATH')
            follow.name = FOLLOW_AIM_PATH_NAME
            follow.target = aim_path
            if hasattr(follow, "use_fixed_location"):
                follow.use_fixed_location = True
            follow.use_curve_follow = False
            follow.offset_factor = 0.0

        # Pre-multiplying keeps the copied path shape and offsets it in world
        # space so its current progress point sits exactly under the Aim.
        offset = anchor_position - camera_position
        aim_path.matrix_world = Matrix.Translation(offset) @ path.matrix_world

        if not replacing:
            camera_follow = next(
                (
                    constraint for constraint in camera_dolly.constraints
                    if constraint.type == 'FOLLOW_PATH'
                    and constraint.target == path
                ),
                None,
            )
            aim_follow = next(
                constraint for constraint in aim_dolly.constraints
                if constraint.type == 'FOLLOW_PATH'
            )
            source_action = (
                camera_dolly.animation_data.action
                if camera_dolly.animation_data else None
            )
            source_fcurve = None
            if source_action is not None and camera_follow is not None:
                source_path = _constraint_data_path(camera_follow)
                source_fcurve = next(
                    (
                        fcurve for fcurve in _iter_action_fcurves(source_action)
                        if fcurve.data_path == source_path
                    ),
                    None,
                )

            target_path = _constraint_data_path(aim_follow)
            if source_fcurve is not None and source_fcurve.keyframe_points:
                for source_key in source_fcurve.keyframe_points:
                    aim_follow.offset_factor = source_key.co.y
                    aim_dolly.keyframe_insert(
                        data_path=target_path,
                        frame=source_key.co.x,
                    )
                target_action = aim_dolly.animation_data.action
                target_action.name = f"{rig_id}_AimPath_Action"
                target_fcurve = next(
                    fcurve for fcurve in _iter_action_fcurves(target_action)
                    if fcurve.data_path == target_path
                )
                for source_key, target_key in zip(
                    source_fcurve.keyframe_points,
                    target_fcurve.keyframe_points,
                ):
                    target_key.co = source_key.co
                    target_key.handle_left = source_key.handle_left
                    target_key.handle_right = source_key.handle_right
                    target_key.handle_left_type = source_key.handle_left_type
                    target_key.handle_right_type = source_key.handle_right_type
                    target_key.interpolation = source_key.interpolation
                target_fcurve.update()
            else:
                start = rig.start_frame
                duration = (
                    max(1, round(rig.duration_seconds * _fps(scene)))
                    if rig.duration_mode == 'SECONDS'
                    else max(1, rig.duration_frames)
                )
                aim_follow.offset_factor = 0.0
                aim_dolly.keyframe_insert(data_path=target_path, frame=start)
                aim_follow.offset_factor = 1.0
                aim_dolly.keyframe_insert(
                    data_path=target_path,
                    frame=start + duration,
                )
                _set_all_key_interpolation(aim_dolly, rig.interpolation)
                aim_dolly.animation_data.action.name = f"{rig_id}_AimPath_Action"

            scene.frame_set(scene.frame_current)
            context.view_layer.update()
            aim_world = aim.matrix_world.copy()
            aim.parent = aim_dolly
            aim.matrix_parent_inverse = aim_dolly.matrix_world.inverted_safe()
            aim.matrix_world = aim_world
            rig.aim_path = aim_path
            rig.aim_dolly = aim_dolly
            focus = rig.focus or _object_for_role(path, ROLE_FOCUS)
            if focus is not None:
                _set_parent_preserve_world(
                    focus,
                    aim_dolly if rig.focus_follows_aim_path else None,
                )

        context.view_layer.update()
        self.report(
            {'INFO'},
            "Replaced Aim Path geometry; timing and Aim keys preserved"
            if replacing else
            "Created an independent Aim Path from the current camera path",
        )
        return {'FINISHED'}


class CPR_OT_remove_aim_path(Operator):
    bl_idname = "cpr.remove_aim_path"
    bl_label = "Remove Aim Path"
    bl_description = "Remove Aim Path motion while preserving the Aim's manual keyframes"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        path = _active_path(context)
        return bool(path and _aim_path_for_rig(path) and _aim_dolly_for_rig(path))

    def execute(self, context):
        path = _active_path(context)
        rig = path.cpr_rig
        rig_id = path.get(TAG_RIG_ID)
        aim = rig.aim or _object_for_role(path, ROLE_AIM)
        focus = rig.focus or _object_for_role(path, ROLE_FOCUS)
        aim_path = _aim_path_for_rig(path)
        aim_dolly = _aim_dolly_for_rig(path)
        if context.object and context.object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        if aim is not None:
            aim_world = aim.matrix_world.copy()
            aim.parent = None
            aim.matrix_parent_inverse.identity()
            aim.matrix_world = aim_world
        if focus is not None:
            _set_parent_preserve_world(focus, aim)

        data = aim_path.data
        action = (
            aim_dolly.animation_data.action
            if aim_dolly.animation_data else None
        )
        rig.aim_path = None
        rig.aim_dolly = None
        bpy.data.objects.remove(aim_dolly, do_unlink=True)
        bpy.data.objects.remove(aim_path, do_unlink=True)
        if data.users == 0 and data.get(TAG_DATA_OWNER) == rig_id:
            bpy.data.curves.remove(data)
        if action is not None and action.users == 0:
            bpy.data.actions.remove(action)

        if aim is not None:
            _select_only(context, aim)
        self.report({'INFO'}, "Removed Aim Path; manual Aim keyframes were preserved")
        return {'FINISHED'}


class CPR_OT_edit_path(Operator):
    bl_idname = "cpr.edit_path"
    bl_label = "Edit Path"
    bl_description = "Select the path and enter Edit Mode with all Bezier points selected"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _active_path(context) is not None

    def execute(self, context):
        path = _active_path(context)
        _select_only(context, path)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.curve.select_all(action='SELECT')
        return {'FINISHED'}


class CPR_OT_extend_path(Operator):
    bl_idname = "cpr.extend_path"
    bl_label = "Extend End"
    bl_description = "Add one smoothly continued Bezier point to the end of the path"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        path = _active_path(context)
        return bool(path and path.data.splines and path.data.splines[0].type == 'BEZIER')

    def execute(self, context):
        path = _active_path(context)
        if context.object and context.object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        spline = path.data.splines[0]
        points = spline.bezier_points
        if len(points) < 2:
            self.report({'ERROR'}, "The path needs at least two points")
            return {'CANCELLED'}
        direction = points[-1].co - points[-2].co
        if direction.length < 0.0001:
            direction = Vector((3.0, 0.0, 0.0))
        for bp in points:
            bp.select_control_point = False
            bp.select_left_handle = False
            bp.select_right_handle = False
        points.add(1)
        new_point = points[-1]
        new_point.co = points[-2].co + direction
        new_point.handle_left_type = 'AUTO'
        new_point.handle_right_type = 'AUTO'
        new_point.select_control_point = True
        _select_only(context, path)
        context.view_layer.update()
        self.report({'INFO'}, "Extended the path by one point")
        return {'FINISHED'}


class CPR_OT_shorten_path(Operator):
    bl_idname = "cpr.shorten_path"
    bl_label = "Shorten End"
    bl_description = "Remove the final Bezier point while keeping the rest of the path"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        path = _active_path(context)
        if not path or not path.data.splines:
            return False
        spline = path.data.splines[0]
        return spline.type == 'BEZIER' and len(spline.bezier_points) > 2

    def execute(self, context):
        path = _active_path(context)
        if context.object and context.object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        records = [_copy_bezier_point(bp) for bp in path.data.splines[0].bezier_points[:-1]]
        _restore_bezier_spline(path.data, records)
        _select_only(context, path)
        context.view_layer.update()
        self.report({'INFO'}, "Removed the final path point")
        return {'FINISHED'}


class CPR_OT_smooth_path(Operator):
    bl_idname = "cpr.smooth_path"
    bl_label = "Smooth Path"
    bl_description = "Reduce bumps by averaging neighboring path points; open-path endpoints stay fixed"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        path = _active_path(context)
        return bool(path and path.type == 'CURVE')

    def execute(self, context):
        path = _active_path(context)
        if context.object and context.object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        strength = path.cpr_rig.smooth_strength
        changed = 0
        for spline in path.data.splines:
            if spline.type != 'BEZIER' or len(spline.bezier_points) < 3:
                continue
            points = spline.bezier_points
            original = [point.co.copy() for point in points]
            indices = (
                range(len(points)) if spline.use_cyclic_u
                else range(1, len(points) - 1)
            )
            for index in indices:
                previous = original[(index - 1) % len(points)]
                following = original[(index + 1) % len(points)]
                neighbor_average = (previous + following) * 0.5
                points[index].co = original[index].lerp(neighbor_average, strength)
                changed += 1
            _rebuild_aligned_handles(spline)

        if not changed:
            self.report({'WARNING'}, "No Bezier spline with interior points was found")
            return {'CANCELLED'}
        context.view_layer.update()
        self.report({'INFO'}, f"Smoothed {changed} interior path points")
        return {'FINISHED'}


class CPR_OT_make_camera_active(Operator):
    bl_idname = "cpr.make_camera_active"
    bl_label = "Make Camera Active"
    bl_description = "Use this rig's camera as the scene camera"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _active_path(context) is not None

    def execute(self, context):
        path = _active_path(context)
        camera = path.cpr_rig.camera or _object_for_role(path, ROLE_CAMERA)
        if camera is None:
            self.report({'ERROR'}, "This rig's camera is missing")
            return {'CANCELLED'}
        context.scene.camera = camera
        self.report({'INFO'}, f"Active camera: {camera.name}")
        return {'FINISHED'}


class CPR_OT_add_camera_cut(Operator):
    bl_idname = "cpr.add_camera_cut"
    bl_label = "Add Camera Cut Here"
    bl_description = "Bind this rig's camera to a timeline marker at the current frame"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _active_path(context) is not None

    def execute(self, context):
        scene = context.scene
        path = _active_path(context)
        camera = path.cpr_rig.camera or _object_for_role(path, ROLE_CAMERA)
        if camera is None:
            self.report({'ERROR'}, "This rig's camera is missing")
            return {'CANCELLED'}
        frame = scene.frame_current
        for old_marker in list(scene.timeline_markers):
            if old_marker.frame == frame and old_marker.name.startswith("CPR Cut "):
                scene.timeline_markers.remove(old_marker)
        marker_name = f"CPR Cut {frame} - {camera.name}"
        marker = scene.timeline_markers.new(marker_name, frame=frame)
        marker.camera = camera
        scene.camera = camera
        self.report({'INFO'}, f"Camera cut added at frame {frame}")
        return {'FINISHED'}


class CPR_OT_bake_camera(Operator):
    bl_idname = "cpr.bake_camera"
    bl_label = "Bake Current Rig to New Camera"
    bl_description = "Create an independent camera with per-frame transform, lens, and focus-distance keys"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _active_path(context) is not None

    def execute(self, context):
        scene = context.scene
        path = _active_path(context)
        rig = path.cpr_rig
        source = rig.camera or _object_for_role(path, ROLE_CAMERA)
        focus = rig.focus or _object_for_role(path, ROLE_FOCUS)
        if source is None:
            self.report({'ERROR'}, "This rig's camera is missing")
            return {'CANCELLED'}

        try:
            start, end = _set_timing(path, scene)
        except RuntimeError as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}

        collection = _bakes_collection(scene)
        data = source.data.copy()
        data.name = f"{path.get(TAG_RIG_ID, path.name)}_Baked_Camera_Data"
        data.animation_data_clear()
        data.dof.focus_object = None
        baked = bpy.data.objects.new(
            f"{path.get(TAG_RIG_ID, path.name)}_Baked_Camera",
            data,
        )
        collection.objects.link(baked)
        baked.rotation_mode = 'QUATERNION'
        baked["cpr_baked_from"] = path.get(TAG_RIG_ID, path.name)
        baked["cpr_bake_start"] = start
        baked["cpr_bake_end"] = end

        previous_frame = scene.frame_current
        try:
            for frame in range(start, end + 1):
                scene.frame_set(frame)
                depsgraph = context.evaluated_depsgraph_get()
                evaluated_camera = source.evaluated_get(depsgraph)
                baked.matrix_world = evaluated_camera.matrix_world.copy()
                baked.keyframe_insert(data_path="location", frame=frame)
                baked.keyframe_insert(data_path="rotation_quaternion", frame=frame)

                data.lens = evaluated_camera.data.lens
                data.keyframe_insert(data_path="lens", frame=frame)
                if focus is not None:
                    evaluated_focus = focus.evaluated_get(depsgraph)
                    data.dof.focus_distance = (
                        evaluated_focus.matrix_world.translation
                        - evaluated_camera.matrix_world.translation
                    ).length
                    data.keyframe_insert(data_path="dof.focus_distance", frame=frame)
        except Exception as exc:
            bpy.data.objects.remove(baked, do_unlink=True)
            if data.users == 0:
                bpy.data.cameras.remove(data)
            self.report({'ERROR'}, f"Bake failed: {exc}")
            return {'CANCELLED'}
        finally:
            scene.frame_set(previous_frame)

        _set_all_key_interpolation(baked, 'LINEAR')
        _set_all_key_interpolation(data, 'LINEAR')
        scene.camera = baked
        _select_only(context, baked)
        self.report({'INFO'}, f"Baked {end - start + 1} frames to {baked.name}")
        return {'FINISHED'}


def _delete_rig_contents(scene, path):
    """Delete one precisely scoped rig and return camera/cleanup statistics."""
    rig_id = path.get(TAG_RIG_ID)
    camera = path.cpr_rig.camera or _object_for_role(path, ROLE_CAMERA)
    was_scene_camera = scene.camera == camera
    objects = _objects_for_rig(path)
    collections = {
        collection for ob in objects for collection in ob.users_collection
    }

    # Collect candidates only by walking this rig. This is intentionally
    # narrower than Blender's orphan purge, which could remove unrelated data.
    data_candidates = {}
    action_candidates = {}
    supported_data_types = (bpy.types.Curve, bpy.types.Mesh, bpy.types.Camera)
    for ob in objects:
        data = getattr(ob, "data", None)
        if isinstance(data, supported_data_types):
            data_candidates[data.as_pointer()] = (
                data,
                data.users,
                data.get(TAG_DATA_OWNER) == rig_id,
            )
        for owner in (ob, data):
            animation_data = getattr(owner, "animation_data", None)
            action = animation_data.action if animation_data else None
            if action is not None:
                action_candidates[action.as_pointer()] = action

    for marker in list(scene.timeline_markers):
        if marker.camera == camera and marker.name.startswith("CPR Cut "):
            scene.timeline_markers.remove(marker)
    for ob in objects:
        bpy.data.objects.remove(ob, do_unlink=True)

    cleaned_data = 0
    for data, original_users, is_tagged_owner in data_candidates.values():
        # Tagged data is owned by this rig. Legacy data is eligible only when
        # it was exclusively attached to one of this rig's objects.
        if data.users != 0 or not (is_tagged_owner or original_users == 1):
            continue
        if isinstance(data, bpy.types.Curve):
            bpy.data.curves.remove(data)
        elif isinstance(data, bpy.types.Mesh):
            bpy.data.meshes.remove(data)
        elif isinstance(data, bpy.types.Camera):
            bpy.data.cameras.remove(data)
        cleaned_data += 1

    cleaned_actions = 0
    for action in action_candidates.values():
        if action.users == 0:
            bpy.data.actions.remove(action)
            cleaned_actions += 1

    for collection in collections:
        if (
            collection.get(TAG_COLLECTION_ROLE) != COLLECTION_ROLE_MASTER
            and not collection.objects
        ):
            bpy.data.collections.remove(collection)
    return was_scene_camera, cleaned_data + cleaned_actions


class CPR_OT_delete_rig(Operator):
    bl_idname = "cpr.delete_rig"
    bl_label = "Delete This Rig"
    bl_description = (
        "Delete the selected rig and its unused owned data without purging "
        "unrelated Blender data"
    )
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _active_path(context) is not None

    def invoke(self, context, event):
        path = _active_path(context)
        label = path.get("cpr_display_name", path.name) if path else "this rig"
        try:
            return context.window_manager.invoke_confirm(
                self,
                event,
                title="Delete Camera Path Rig?",
                message=f"Permanently delete {label} from this scene?",
                confirm_text="Delete Rig",
                icon='ERROR',
            )
        except TypeError:
            return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        scene = context.scene
        path = _active_path(context)
        was_scene_camera, total_cleaned = _delete_rig_contents(scene, path)

        remaining = _rig_paths(scene)
        if remaining:
            _set_active_rig(scene, remaining[0])
            if was_scene_camera or scene.camera is None:
                scene.camera = remaining[0].cpr_rig.camera
        else:
            _set_active_rig(scene, None)
            if was_scene_camera:
                scene.camera = None
        self.report(
            {'INFO'},
            f"Deleted this rig and cleaned {total_cleaned} unused owned datablocks",
        )
        return {'FINISHED'}


class CPR_OT_delete_all_rigs(Operator):
    bl_idname = "cpr.delete_all_rigs"
    bl_label = "Delete All Rigs"
    bl_description = "Delete every Camera Path Rig in the current scene only"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return bool(_rig_paths(context.scene))

    def invoke(self, context, event):
        count = len(_rig_paths(context.scene))
        try:
            return context.window_manager.invoke_confirm(
                self,
                event,
                title="Delete All Camera Path Rigs?",
                message=(
                    f"Permanently delete all {count} Camera Path Rigs "
                    f"from {context.scene.name}?"
                ),
                confirm_text="Delete All Rigs",
                icon='ERROR',
            )
        except TypeError:
            return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        scene = context.scene
        paths = list(_rig_paths(scene))
        deleted_scene_camera = False
        total_cleaned = 0
        for path in paths:
            was_scene_camera, cleaned = _delete_rig_contents(scene, path)
            deleted_scene_camera = deleted_scene_camera or was_scene_camera
            total_cleaned += cleaned
        _set_active_rig(scene, None)
        if deleted_scene_camera:
            scene.camera = None
        self.report(
            {'INFO'},
            f"Deleted {len(paths)} rigs and cleaned {total_cleaned} owned datablocks",
        )
        return {'FINISHED'}




CLASSES = (
    CPR_OT_create_rig,
    CPR_OT_apply_timing,
    CPR_OT_select_control,
    CPR_OT_create_aim_path,
    CPR_OT_remove_aim_path,
    CPR_OT_smooth_path,
    CPR_OT_make_camera_active,
    CPR_OT_add_camera_cut,
    CPR_OT_bake_camera,
    CPR_OT_delete_rig,
    CPR_OT_delete_all_rigs,
)
