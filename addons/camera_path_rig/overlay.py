"""3D Viewport path and direction-chevron overlay."""

import bpy
import gpu
from gpu_extras.batch import batch_for_shader
from mathutils import Vector

from .common import *

_overlay_handle = None

def _curve_polyline(path, depsgraph):
    """Return the evaluated path as ordered world-space points."""
    try:
        evaluated = path.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        if mesh is None:
            return []
        matrix = evaluated.matrix_world
        points = [matrix @ vertex.co for vertex in mesh.vertices]
        evaluated.to_mesh_clear()
        if (
            len(path.data.splines) == 1
            and path.data.splines[0].use_cyclic_u
            and points
        ):
            points.append(points[0].copy())
        return points
    except Exception:
        return []


def _direction_chevrons(points, spacing, half_size):
    """Build V-shaped line segments pointing from path start to path end."""
    output = []
    walked = 0.0
    next_distance = spacing * 0.5
    for start, finish in zip(points, points[1:]):
        segment = finish - start
        segment_length = segment.length
        if segment_length < 1e-8:
            continue
        tangent = segment / segment_length
        while next_distance <= walked + segment_length:
            center = start + tangent * (next_distance - walked)
            side = tangent.cross(WORLD_UP)
            if side.length_squared < 1e-8:
                side = tangent.cross(ALT_UP)
            side.normalize()
            tip = center + tangent * half_size
            back = center - tangent * half_size
            output.extend((back + side * half_size, tip, tip, back - side * half_size))
            next_distance += spacing
        walked += segment_length
    return output


def _viewport_overlays_visible(context):
    space = getattr(context, "space_data", None)
    viewport_overlay = getattr(space, "overlay", None)
    return viewport_overlay is None or bool(viewport_overlay.show_overlays)


def _draw_direction_overlay():
    """Draw camera and optional Aim paths with start-to-end chevrons."""
    try:
        context = bpy.context
        if not _viewport_overlays_visible(context):
            return
        path = _active_path(context)
        if path is None or not path.cpr_rig.show_direction:
            return
        preferences = _addon_preferences(context)
        camera_color = tuple(
            preferences.overlay_color if preferences else DEFAULT_OVERLAY_COLOR
        )
        aim_color = tuple(
            preferences.aim_overlay_color
            if preferences else DEFAULT_AIM_OVERLAY_COLOR
        )
        line_width = (
            preferences.overlay_line_width if preferences else DEFAULT_LINE_WIDTH
        )
        path_opacity = (
            preferences.path_opacity if preferences else DEFAULT_PATH_OPACITY
        )
        chevron_scale = (
            preferences.chevron_scale if preferences else DEFAULT_CHEVRON_SCALE
        )
        chevron_count = (
            preferences.chevron_count if preferences else DEFAULT_CHEVRON_COUNT
        )
        aim_path = path.cpr_rig.aim_path or _object_for_role(path, ROLE_AIM_PATH)
        paths = [(path, camera_color)]
        if aim_path is not None:
            paths.append((aim_path, aim_color))

        shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        gpu.state.blend_set('ALPHA')
        gpu.state.depth_test_set('NONE')
        try:
            for curve, color in paths:
                points = _curve_polyline(
                    curve,
                    context.evaluated_depsgraph_get(),
                )
                if len(points) < 2:
                    continue
                total_length = sum(
                    (b - a).length for a, b in zip(points, points[1:])
                )
                if total_length < 1e-6:
                    continue
                spacing = max(total_length / max(1, chevron_count), 0.25)
                half_size = (
                    max(min(total_length * 0.018, 0.75), 0.08)
                    * chevron_scale
                )
                chevrons = _direction_chevrons(points, spacing, half_size)

                gpu.state.line_width_set(line_width)
                line_batch = batch_for_shader(
                    shader,
                    'LINE_STRIP',
                    {"pos": points},
                )
                shader.bind()
                shader.uniform_float(
                    "color",
                    (color[0], color[1], color[2], path_opacity),
                )
                line_batch.draw(shader)

                if chevrons:
                    gpu.state.line_width_set(max(1.0, line_width * 0.8))
                    chevron_batch = batch_for_shader(
                        shader,
                        'LINES',
                        {"pos": chevrons},
                    )
                    shader.bind()
                    shader.uniform_float("color", color)
                    chevron_batch.draw(shader)
        finally:
            gpu.state.line_width_set(1.0)
            gpu.state.depth_test_set('NONE')
            gpu.state.blend_set('NONE')
    except Exception:
        # A viewport callback must not raise on every redraw if a file is
        # loading or the active rig is being deleted.
        pass


def _ensure_overlay():
    global _overlay_handle
    if _overlay_handle is None:
        _overlay_handle = bpy.types.SpaceView3D.draw_handler_add(
            _draw_direction_overlay,
            (),
            'WINDOW',
            'POST_VIEW',
        )


def _remove_overlay():
    global _overlay_handle
    if _overlay_handle is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_overlay_handle, 'WINDOW')
        except Exception:
            pass
        _overlay_handle = None




__all__ = (
    "_curve_polyline",
    "_direction_chevrons",
    "_viewport_overlays_visible",
    "_ensure_overlay",
    "_remove_overlay",
)
