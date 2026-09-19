"""Camera Path Rig - editable, independently timed camera-on-curve rigs."""

bl_info = {
    "name": "Camera Path Rig",
    "author": "Lucca / OpenAI Codex",
    "version": (1, 9, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > Camera Path",
    "description": "Create editable camera-on-curve rigs with precise timing",
    "category": "Animation",
    "license": "GPL-3.0-or-later",
}

import bpy
from bpy.app.handlers import persistent
from bpy.props import PointerProperty
from bpy.types import AddonPreferences, Operator, Panel, PropertyGroup, UIList

from . import operators, overlay, properties, ui
from .common import *
from .overlay import (
    _curve_polyline,
    _direction_chevrons,
    _viewport_overlays_visible,
)


CLASSES = properties.CLASSES + operators.CLASSES + ui.CLASSES
_UI_LAYOUT_VERSION = 160


def _registered_class(cls):
    return bool(getattr(cls, "is_registered", False))


def _stale_registered_classes():
    """Find registered classes left by an older/reloaded package instance."""
    current_classes = set(CLASSES)
    wanted_names = {cls.__name__ for cls in CLASSES}
    stale = []
    seen = set()
    pending = [AddonPreferences, PropertyGroup, Operator, Panel, UIList]
    while pending:
        base = pending.pop()
        for candidate in base.__subclasses__():
            if candidate in seen:
                continue
            seen.add(candidate)
            pending.append(candidate)
            if (
                candidate not in current_classes
                and candidate.__name__ in wanted_names
                and _registered_class(candidate)
            ):
                stale.append(candidate)
    return stale


def _remove_stale_registration():
    """Clean a partial hot-reload without touching unrelated add-ons."""
    stale = _stale_registered_classes()
    if not stale:
        return

    # Pointer properties can hold references to the old PropertyGroup classes.
    if hasattr(bpy.types.Object, "cpr_rig"):
        del bpy.types.Object.cpr_rig
    if hasattr(bpy.types.Scene, "cpr_settings"):
        del bpy.types.Scene.cpr_settings

    stale_by_name = {cls.__name__: cls for cls in stale}
    for current in reversed(CLASSES):
        old = stale_by_name.get(current.__name__)
        if old is not None and _registered_class(old):
            bpy.utils.unregister_class(old)

    # A reloaded package may also have left its old load handler behind.
    for handler in list(bpy.app.handlers.load_post):
        module_name = getattr(handler, "__module__", "")
        if (
            handler is not _load_post
            and getattr(handler, "__name__", "") == "_load_post"
            and "camera_path_rig" in module_name
        ):
            bpy.app.handlers.load_post.remove(handler)


def _collapse_ui_sections_once():
    """Give new and pre-1.6 scenes the tidy all-collapsed layout once."""
    scenes = getattr(bpy.data, "scenes", None)
    if scenes is None:
        return False
    for scene in scenes:
        if int(scene.get("cpr_ui_layout_version", 0)) < _UI_LAYOUT_VERSION:
            settings = getattr(scene, "cpr_settings", None)
            if settings is not None:
                _collapse_ui_sections(settings)
            scene["cpr_ui_layout_version"] = _UI_LAYOUT_VERSION
        _sync_active_rig_index(scene)
    return True


def _deferred_collapse_ui_sections():
    """Wait until Blender releases its restricted registration data context."""
    return None if _collapse_ui_sections_once() else 0.1


def _initialize_ui_layout():
    if _collapse_ui_sections_once():
        return
    if not bpy.app.timers.is_registered(_deferred_collapse_ui_sections):
        bpy.app.timers.register(_deferred_collapse_ui_sections, first_interval=0.0)


@persistent
def _load_post(_unused):
    _initialize_ui_layout()


def register():
    # Blender can keep Python classes alive after an in-place extension update.
    # Recover from that state, and make a repeated call harmless.
    _remove_stale_registration()
    for cls in CLASSES:
        if not _registered_class(cls):
            bpy.utils.register_class(cls)
    if not hasattr(bpy.types.Scene, "cpr_settings"):
        bpy.types.Scene.cpr_settings = PointerProperty(type=properties.CPR_PG_scene)
    if not hasattr(bpy.types.Object, "cpr_rig"):
        bpy.types.Object.cpr_rig = PointerProperty(type=properties.CPR_PG_rig)
    _collapse_ui_sections_once()
    if _load_post not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_load_post)
    overlay._ensure_overlay()


def unregister():
    overlay._remove_overlay()
    if bpy.app.timers.is_registered(_deferred_collapse_ui_sections):
        bpy.app.timers.unregister(_deferred_collapse_ui_sections)
    if _load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_load_post)
    if hasattr(bpy.types.Object, "cpr_rig"):
        del bpy.types.Object.cpr_rig
    if hasattr(bpy.types.Scene, "cpr_settings"):
        del bpy.types.Scene.cpr_settings
    for cls in reversed(CLASSES):
        if _registered_class(cls):
            bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
