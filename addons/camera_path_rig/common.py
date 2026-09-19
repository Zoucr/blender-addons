"""Shared data, curve, rig-shape, selection, and timing helpers."""

import math
import re
import uuid

import bpy
from mathutils import Matrix, Vector

MASTER_COLLECTION = "Camera Path Rigs"
BAKES_COLLECTION = "Camera Path Bakes"
RIG_PREFIX = "CameraPath_Rig"
TAG_RIG_ID = "cpr_rig_id"
TAG_ROLE = "cpr_role"
TAG_DATA_OWNER = "cpr_owner_rig_id"
TAG_DATA_ROLE = "cpr_owned_data_role"
TAG_SCENE_ID = "cpr_scene_id"
TAG_RIG_NUMBER = "cpr_rig_number"
TAG_COLLECTION_ROLE = "cpr_collection_role"
FOLLOW_PATH_NAME = "Camera Path Progress"
TRACK_TO_NAME = "Camera Aim"
FOLLOW_AIM_PATH_NAME = "Aim Path Progress"

ROLE_PATH = "PATH"
ROLE_DOLLY = "DOLLY"
ROLE_GIMBAL = "GIMBAL"
ROLE_CAMERA = "CAMERA"
ROLE_AIM = "AIM"
ROLE_FOCUS = "FOCUS"
ROLE_AIM_PATH = "AIM_PATH"
ROLE_AIM_DOLLY = "AIM_DOLLY"
COLLECTION_ROLE_MASTER = "MASTER"
COLLECTION_ROLE_RIG = "RIG"
COLLECTION_ROLE_BAKES = "BAKES"

_enum_cache = []
_overlay_handle = None

ADDON_ID = __package__ or __name__
DEFAULT_OVERLAY_COLOR = (0.08, 0.42, 1.0, 1.0)
DEFAULT_AIM_OVERLAY_COLOR = (1.0, 0.28, 0.05, 1.0)
DEFAULT_LINE_WIDTH = 2.0
DEFAULT_PATH_OPACITY = 0.72
DEFAULT_CHEVRON_SCALE = 0.6
DEFAULT_CHEVRON_COUNT = 7
WORLD_UP = Vector((0.0, 0.0, 1.0))
ALT_UP = Vector((1.0, 0.0, 0.0))
UI_SECTION_PROPERTIES = (
    "show_creation",
    "show_creation_settings",
    "show_preset_settings",
    "show_timing",
    "show_path_controls",
    "show_animation",
    "show_camera_switching",
)


def _collapse_ui_sections(settings):
    for property_name in UI_SECTION_PROPERTIES:
        setattr(settings, property_name, False)


def _fps(scene):
    base = scene.render.fps_base or 1.0
    return scene.render.fps / base


def _addon_preferences(context=None):
    try:
        preferences = (context or bpy.context).preferences
        addon = preferences.addons.get(ADDON_ID)
        return addon.preferences if addon else None
    except Exception:
        return None


def _scene_uid(scene):
    """Return a stable owner ID, repairing duplicate IDs from copied scenes."""
    if scene is None:
        return ""
    uid = scene.get(TAG_SCENE_ID, "")
    if uid and not any(
        other is not scene and other.get(TAG_SCENE_ID, "") == uid
        for other in bpy.data.scenes
    ):
        return uid
    uid = uuid.uuid4().hex
    scene[TAG_SCENE_ID] = uid
    return uid


def _rig_paths(scene=None):
    scene = scene or getattr(bpy.context, "scene", None)
    scene_uid = _scene_uid(scene) if scene is not None else ""
    objects = scene.objects if scene is not None else bpy.data.objects
    return sorted(
        (
            ob for ob in objects
            if ob.type == 'CURVE' and ob.get(TAG_ROLE) == ROLE_PATH
            and (
                not ob.get(TAG_SCENE_ID)
                or ob.get(TAG_SCENE_ID) == scene_uid
            )
        ),
        key=lambda ob: (int(ob.get(TAG_RIG_NUMBER, 0)), ob.name),
    )


def _rig_enum_items(self, context):
    global _enum_cache
    scene = context.scene if context is not None else getattr(self, "id_data", None)
    paths = _rig_paths(scene)
    if not paths:
        _enum_cache = [("", "No rigs yet", "Create a camera path rig first")]
    else:
        _enum_cache = [
            (ob.name, ob.get("cpr_display_name", ob.name), ob.name, 'CAMERA_DATA', i)
            for i, ob in enumerate(paths)
        ]
    return _enum_cache


def _rig_end_frame(path, scene):
    rig = path.cpr_rig
    duration = (
        max(1, round(rig.duration_seconds * _fps(scene)))
        if rig.duration_mode == 'SECONDS'
        else max(1, rig.duration_frames)
    )
    return rig.start_frame + duration


def _scene_object_index(scene, ob):
    if scene is None or ob is None:
        return 0
    for index, candidate in enumerate(scene.objects):
        if candidate == ob:
            return index
    return 0


def _set_active_rig(scene, path):
    settings = getattr(scene, "cpr_settings", None)
    if settings is None:
        return
    settings.active_rig = path.name if path is not None else ""
    if path is not None:
        settings.active_rig_index = _scene_object_index(scene, path)


def _sync_active_rig_index(scene):
    settings = getattr(scene, "cpr_settings", None)
    if settings is None:
        return
    paths = _rig_paths(scene)
    current = bpy.data.objects.get(settings.active_rig) if settings.active_rig else None
    if current not in paths:
        current = paths[0] if paths else None
    _set_active_rig(scene, current)


def _path_from_rig_id(rig_id, scene=None, collections=None):
    if not rig_id:
        return None
    collection_set = set(collections or ())
    for ob in _rig_paths(scene):
        if (
            ob.get(TAG_RIG_ID) == rig_id
            and (
                not collection_set
                or collection_set.intersection(ob.users_collection)
            )
        ):
            return ob
    return None


def _path_from_object(ob, scene=None):
    if ob is None:
        return None
    if ob.get(TAG_ROLE) == ROLE_PATH and ob.type == 'CURVE':
        return ob
    return _path_from_rig_id(
        ob.get(TAG_RIG_ID),
        scene,
        collections=ob.users_collection,
    )


def _active_path(context):
    paths = _rig_paths(context.scene)
    settings = getattr(context.scene, "cpr_settings", None)
    if settings and settings.active_rig:
        ob = bpy.data.objects.get(settings.active_rig)
        if ob in paths:
            return ob
    selected = _path_from_object(context.object, context.scene)
    if selected:
        return selected
    return paths[0] if paths else None


def _tag(ob, rig_id, role):
    ob[TAG_RIG_ID] = rig_id
    ob[TAG_ROLE] = role


def _tag_owned_data(data, rig_id, role):
    """Mark an ID datablock created exclusively for one generated rig."""
    if data is None:
        return
    data[TAG_DATA_OWNER] = rig_id
    data[TAG_DATA_ROLE] = role


def _object_for_role(path, role):
    if not path:
        return None
    rig_id = path.get(TAG_RIG_ID)
    rig_collections = set(path.users_collection)
    for ob in bpy.data.objects:
        if (
            ob.get(TAG_RIG_ID) == rig_id
            and ob.get(TAG_ROLE) == role
            and (
                not rig_collections
                or rig_collections.intersection(ob.users_collection)
            )
        ):
            return ob
    return None


def _objects_for_rig(path):
    """Return only objects belonging to this path's own rig collection."""
    if path is None:
        return []
    rig_id = path.get(TAG_RIG_ID)
    rig_collections = set(path.users_collection)
    return [
        ob for ob in bpy.data.objects
        if ob.get(TAG_RIG_ID) == rig_id
        and (
            not rig_collections
            or rig_collections.intersection(ob.users_collection)
        )
    ]


def _set_parent_preserve_world(ob, parent):
    """Change parenting without touching animation data or jumping now."""
    if ob is None or ob.parent == parent:
        return
    world_matrix = ob.matrix_world.copy()
    ob.parent = parent
    ob.matrix_parent_inverse = (
        parent.matrix_world.inverted_safe() if parent is not None
        else Matrix.Identity(4)
    )
    ob.matrix_world = world_matrix


def _next_rig_number(scene):
    pattern = re.compile(r"(?:Rig |CameraPath_Rig_)(\d+)")
    highest = 0
    for path in _rig_paths(scene):
        number = int(path.get(TAG_RIG_NUMBER, 0))
        if not number:
            match = pattern.search(path.get("cpr_display_name", path.name))
            number = int(match.group(1)) if match else 0
        highest = max(highest, number)
    return highest + 1


def _unique_rig_base(scene):
    number = _next_rig_number(scene)
    return number, f"{RIG_PREFIX}_{number:03d}"


def _master_collection(scene):
    scene_uid = _scene_uid(scene)
    master = next(
        (
            collection for collection in bpy.data.collections
            if collection.get(TAG_SCENE_ID) == scene_uid
            and collection.get(TAG_COLLECTION_ROLE) == COLLECTION_ROLE_MASTER
        ),
        None,
    )
    if master is None:
        master = bpy.data.collections.new(f"{MASTER_COLLECTION} [{scene.name}]")
        master[TAG_SCENE_ID] = scene_uid
        master[TAG_COLLECTION_ROLE] = COLLECTION_ROLE_MASTER
    if master.name not in scene.collection.children:
        scene.collection.children.link(master)
    try:
        master.color_tag = 'COLOR_05'
    except Exception:
        pass
    return master


def _bakes_collection(scene):
    scene_uid = _scene_uid(scene)
    collection = next(
        (
            candidate for candidate in bpy.data.collections
            if candidate.get(TAG_SCENE_ID) == scene_uid
            and candidate.get(TAG_COLLECTION_ROLE) == COLLECTION_ROLE_BAKES
        ),
        None,
    )
    if collection is None:
        collection = bpy.data.collections.new(f"{BAKES_COLLECTION} [{scene.name}]")
        collection[TAG_SCENE_ID] = scene_uid
        collection[TAG_COLLECTION_ROLE] = COLLECTION_ROLE_BAKES
    if collection.name not in scene.collection.children:
        scene.collection.children.link(collection)
    try:
        collection.color_tag = 'COLOR_02'
    except Exception:
        pass
    return collection


def _make_wire_object(name, verts, edges, collection, rig_id, role, color):
    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    _tag_owned_data(mesh, rig_id, role)
    mesh.from_pydata(verts, edges, [])
    mesh.update()
    ob = bpy.data.objects.new(name, mesh)
    collection.objects.link(ob)
    ob.display_type = 'WIRE'
    ob.hide_render = True
    ob.show_in_front = True
    ob.color = color
    _tag(ob, rig_id, role)
    return ob


def _circle_geometry(radius, segments=32, plane='XY'):
    verts = []
    edges = []
    for index in range(segments):
        angle = index * math.tau / segments
        c = math.cos(angle) * radius
        s = math.sin(angle) * radius
        if plane == 'XY':
            verts.append((c, s, 0.0))
        elif plane == 'XZ':
            verts.append((c, 0.0, s))
        else:
            verts.append((0.0, c, s))
        edges.append((index, (index + 1) % segments))
    return verts, edges


def _merge_geometry(*parts):
    verts = []
    edges = []
    for part_verts, part_edges in parts:
        offset = len(verts)
        verts.extend(part_verts)
        edges.extend((a + offset, b + offset) for a, b in part_edges)
    return verts, edges


def _dolly_geometry(size):
    ring = _circle_geometry(size, plane='XY')
    cross = (
        [(-size * 0.3, 0, 0), (size * 0.3, 0, 0),
         (0, -size * 0.3, 0), (0, size * 0.3, 0)],
        [(0, 1), (2, 3)],
    )
    return _merge_geometry(ring, cross)


def _aim_geometry(size):
    xy = _circle_geometry(size, plane='XY')
    xz = _circle_geometry(size, plane='XZ')
    yz = _circle_geometry(size, plane='YZ')
    axes = (
        [(-size * 1.35, 0, 0), (size * 1.35, 0, 0),
         (0, -size * 1.35, 0), (0, size * 1.35, 0),
         (0, 0, -size * 1.35), (0, 0, size * 1.35)],
        [(0, 1), (2, 3), (4, 5)],
    )
    return _merge_geometry(xy, xz, yz, axes)


def _focus_geometry(size):
    verts = [
        (-size, 0, 0), (size, 0, 0),
        (0, -size, 0), (0, size, 0),
        (0, 0, -size), (0, 0, size),
    ]
    return verts, [(0, 1), (2, 3), (4, 5)]


def _starter_path_points(length):
    """Three evenly spaced points forming a straight local-X path."""
    return [
        Vector((-length * 0.5, 0.0, 0.0)),
        Vector((0.0, 0.0, 0.0)),
        Vector((length * 0.5, 0.0, 0.0)),
    ]


def _rebuild_aligned_handles(spline):
    """Give a Bezier spline smooth handles that remain manually rotatable."""
    if spline.type != 'BEZIER' or not spline.bezier_points:
        return
    points = spline.bezier_points
    coordinates = [point.co.copy() for point in points]
    cyclic = bool(spline.use_cyclic_u and len(points) > 2)
    for index, point in enumerate(points):
        previous = (
            coordinates[(index - 1) % len(points)]
            if cyclic or index > 0 else coordinates[index]
        )
        following = (
            coordinates[(index + 1) % len(points)]
            if cyclic or index + 1 < len(points) else coordinates[index]
        )
        if cyclic:
            tangent = following - previous
        elif index == 0:
            tangent = following - coordinates[index]
        elif index == len(points) - 1:
            tangent = coordinates[index] - previous
        else:
            tangent = following - previous
        if tangent.length_squared < 1e-10:
            tangent = Vector((1.0, 0.0, 0.0))
        else:
            tangent.normalize()

        left_distance = (coordinates[index] - previous).length
        right_distance = (following - coordinates[index]).length
        if not cyclic and index == 0:
            left_distance = right_distance
        if not cyclic and index == len(points) - 1:
            right_distance = left_distance
        point.handle_left_type = 'FREE'
        point.handle_right_type = 'FREE'
        point.handle_left = coordinates[index] - tangent * (left_distance / 3.0)
        point.handle_right = coordinates[index] + tangent * (right_distance / 3.0)
        point.handle_left_type = 'ALIGNED'
        point.handle_right_type = 'ALIGNED'


def _make_existing_handles_rotatable(path):
    """Convert automatic handles without changing their current curve shape."""
    if path is None or path.type != 'CURVE':
        return
    for spline in path.data.splines:
        if spline.type != 'BEZIER':
            continue
        for point in spline.bezier_points:
            if point.handle_left_type in {'AUTO', 'AUTO_CLAMPED'}:
                point.handle_left_type = 'ALIGNED'
            if point.handle_right_type in {'AUTO', 'AUTO_CLAMPED'}:
                point.handle_right_type = 'ALIGNED'


def _create_curve(name, points, location, collection, rig_id):
    data = bpy.data.curves.new(f"{name}_Data", 'CURVE')
    _tag_owned_data(data, rig_id, ROLE_PATH)
    data.dimensions = '3D'
    data.resolution_u = 16
    data.render_resolution_u = 24
    data.use_path = True
    if hasattr(data, "use_path_clamp"):
        data.use_path_clamp = True

    spline = data.splines.new('BEZIER')
    spline.bezier_points.add(len(points) - 1)
    for bp, point in zip(spline.bezier_points, points):
        bp.co = point
    _rebuild_aligned_handles(spline)

    ob = bpy.data.objects.new(name, data)
    collection.objects.link(ob)
    ob.location = location
    ob.color = (0.12, 0.55, 1.0, 1.0)
    ob.show_in_front = True
    _tag(ob, rig_id, ROLE_PATH)
    return ob


def _create_circle_preset(name, radius, location, collection, rig_id, full_circle):
    """Create an exact horizontal half- or full-circle Bezier path."""
    data = bpy.data.curves.new(f"{name}_Data", 'CURVE')
    _tag_owned_data(data, rig_id, ROLE_PATH)
    data.dimensions = '3D'
    data.resolution_u = 16
    data.render_resolution_u = 24
    data.use_path = True
    if hasattr(data, "use_path_clamp"):
        data.use_path_clamp = True

    if full_circle:
        angles = (-math.pi * 0.5, 0.0, math.pi * 0.5, math.pi)
    else:
        # Open rear semicircle: left -> rear -> right around the Cursor.
        angles = (math.pi, math.pi * 1.5, math.tau)

    spline = data.splines.new('BEZIER')
    spline.bezier_points.add(len(angles) - 1)
    spline.use_cyclic_u = full_circle
    handle_length = radius * (4.0 * (math.sqrt(2.0) - 1.0) / 3.0)
    for point, angle in zip(spline.bezier_points, angles):
        coordinate = Vector((
            math.cos(angle) * radius,
            math.sin(angle) * radius,
            0.0,
        ))
        tangent = Vector((-math.sin(angle), math.cos(angle), 0.0))
        point.co = coordinate
        point.handle_left_type = 'FREE'
        point.handle_right_type = 'FREE'
        point.handle_left = coordinate - tangent * handle_length
        point.handle_right = coordinate + tangent * handle_length
        point.handle_left_type = 'ALIGNED'
        point.handle_right_type = 'ALIGNED'

    path = bpy.data.objects.new(name, data)
    collection.objects.link(path)
    path.location = location
    path.color = (0.12, 0.55, 1.0, 1.0)
    path.show_in_front = True
    _tag(path, rig_id, ROLE_PATH)
    return path


def _copy_curve_for_rig(source, name, collection, rig_id):
    """Copy a source Curve into a rig without modifying the original."""
    path = source.copy()
    path.data = source.data.copy()
    path.name = name
    path.data.name = f"{name}_Data"
    _tag_owned_data(path.data, rig_id, ROLE_PATH)
    path.animation_data_clear()
    path.data.animation_data_clear()

    world_matrix = source.matrix_world.copy()
    path.parent = None
    for constraint in list(path.constraints):
        path.constraints.remove(constraint)
    collection.objects.link(path)
    path.matrix_world = world_matrix

    # The duplicated object is rig plumbing, not render geometry. Preserve
    # every spline and control point but remove appearance-only thickness.
    path.data.use_path = True
    if hasattr(path.data, "use_path_clamp"):
        path.data.use_path_clamp = True
    if hasattr(path.data, "bevel_depth"):
        path.data.bevel_depth = 0.0
    if hasattr(path.data, "extrude"):
        path.data.extrude = 0.0
    if hasattr(path.data, "bevel_object"):
        path.data.bevel_object = None
    if hasattr(path.data, "taper_object"):
        path.data.taper_object = None
    path.hide_render = True
    path.color = (0.12, 0.55, 1.0, 1.0)
    path.show_in_front = True
    _tag(path, rig_id, ROLE_PATH)
    return path


def _iter_action_fcurves(action):
    """Yield F-curves from legacy and Blender 5 layered actions."""
    if action is None:
        return
    legacy = getattr(action, "fcurves", None)
    if legacy is not None:
        yield from legacy
        return
    for layer in getattr(action, "layers", ()):
        for strip in getattr(layer, "strips", ()):
            for bag in getattr(strip, "channelbags", ()):
                yield from getattr(bag, "fcurves", ())


def _set_all_key_interpolation(owner, interpolation='LINEAR'):
    action = owner.animation_data.action if owner.animation_data else None
    for fcurve in _iter_action_fcurves(action):
        for point in fcurve.keyframe_points:
            point.interpolation = interpolation
        fcurve.update()


def _constraint_data_path(constraint):
    safe_name = constraint.name.replace('\\', '\\\\').replace('"', '\\"')
    return f'constraints["{safe_name}"].offset_factor'


def _set_timing(path, scene):
    rig = path.cpr_rig
    dolly = rig.dolly or _object_for_role(path, ROLE_DOLLY)
    if dolly is None:
        raise RuntimeError("The rig's dolly is missing")

    constraint = next(
        (
            c for c in dolly.constraints
            if c.type == 'FOLLOW_PATH' and c.target == path
        ),
        None,
    )
    if constraint is None:
        raise RuntimeError("The rig's Follow Path constraint is missing")

    fps = _fps(scene)
    if rig.duration_mode == 'SECONDS':
        duration = max(1, round(rig.duration_seconds * fps))
        rig.duration_frames = duration
    else:
        duration = max(1, rig.duration_frames)
        rig.duration_seconds = duration / fps

    start = rig.start_frame
    end = start + duration
    data_path = _constraint_data_path(constraint)

    action = dolly.animation_data.action if dolly.animation_data else None
    for fcurve in _iter_action_fcurves(action):
        if fcurve.data_path == data_path:
            fcurve.keyframe_points.clear()

    constraint.offset_factor = 0.0
    dolly.keyframe_insert(data_path=data_path, frame=start)
    constraint.offset_factor = 1.0
    dolly.keyframe_insert(data_path=data_path, frame=end)

    action = dolly.animation_data.action if dolly.animation_data else None
    for fcurve in _iter_action_fcurves(action):
        if fcurve.data_path != data_path:
            continue
        for point in fcurve.keyframe_points:
            point.interpolation = rig.interpolation
            if rig.interpolation == 'BEZIER':
                point.handle_left_type = 'AUTO_CLAMPED'
                point.handle_right_type = 'AUTO_CLAMPED'
        fcurve.update()

    constraint.offset_factor = 0.0
    if rig.set_scene_range:
        scene.frame_start = start
        scene.frame_end = end
    else:
        scene.frame_end = max(scene.frame_end, end)
    scene.frame_set(scene.frame_current)
    return start, end


def _select_only(context, ob):
    if context.object and context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    for selected in list(context.selected_objects):
        selected.select_set(False)
    ob.hide_set(False)
    ob.select_set(True)
    context.view_layer.objects.active = ob


def _copy_bezier_point(bp):
    return {
        "co": bp.co.copy(),
        "handle_left": bp.handle_left.copy(),
        "handle_right": bp.handle_right.copy(),
        "handle_left_type": bp.handle_left_type,
        "handle_right_type": bp.handle_right_type,
        "tilt": bp.tilt,
        "radius": bp.radius,
    }


def _restore_bezier_spline(data, records):
    data.splines.clear()
    spline = data.splines.new('BEZIER')
    spline.bezier_points.add(len(records) - 1)
    for bp, record in zip(spline.bezier_points, records):
        bp.co = record["co"]
        # Restore explicit handles before types; Blender may recalculate AUTO.
        bp.handle_left = record["handle_left"]
        bp.handle_right = record["handle_right"]
        bp.handle_left_type = record["handle_left_type"]
        bp.handle_right_type = record["handle_right_type"]
        bp.tilt = record["tilt"]
        bp.radius = record["radius"]
    return spline




# Internal names are intentionally exported for the focused add-on modules.
__all__ = [name for name in globals() if not name.startswith("__")]
