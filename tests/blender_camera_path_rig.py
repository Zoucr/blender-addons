"""Run in factory-startup Blender: --python-exit-code 1 --python this_file.py.

Creates disposable test scenes only. Does not save files or user preferences.
"""
from pathlib import Path
import importlib

import addon_utils
import bpy


source = Path(__file__).resolve().parents[1] / "addons"
repo = bpy.context.preferences.extensions.repos.new(
    name="Camera Path Rig Test", module="cpr_import_test",
    custom_directory=str(source),
)
module_name = "bl_ext.cpr_import_test.camera_path_rig"
errors = []
addon_utils.enable(module_name, default_set=True, handle_error=lambda: errors.append(True))
assert not errors, "Extension failed to enable"
addon = importlib.import_module(module_name)
common = addon.common
assert bpy.context.preferences.addons.get(module_name), "Preferences were not registered under extension namespace"
assert common.ADDON_ID == module_name

scene = bpy.context.scene
unrelated = bpy.data.objects.get("Cube")
scene.cpr_settings.duration_mode = 'FRAMES'
scene.cpr_settings.duration_frames = 12
assert bpy.ops.cpr.create_rig() == {'FINISHED'}
paths = common._rig_paths(scene)
assert len(paths) == 1
path = paths[0]
assert scene.camera == path.cpr_rig.camera
follow = path.cpr_rig.dolly.constraints[common.FOLLOW_PATH_NAME]
start = path.cpr_rig.start_frame
scene.frame_set(start)
assert abs(follow.offset_factor) < 1e-5
scene.frame_set(start + 12)
assert abs(follow.offset_factor - 1) < 1e-5

assert bpy.ops.cpr.create_aim_path() == {'FINISHED'}
assert path.cpr_rig.aim_path is not None
assert bpy.ops.cpr.remove_aim_path() == {'FINISHED'}
assert path.cpr_rig.aim_path is None

# Deletion must leave another scene's rig and unrelated scene data intact.
other_scene = bpy.data.scenes.new("CPR Import Test Other Scene")
bpy.context.window.scene = other_scene
assert bpy.ops.cpr.create_rig() == {'FINISHED'}
other_path = common._rig_paths(other_scene)[0]
other_camera = other_path.cpr_rig.camera
bpy.context.window.scene = scene
assert bpy.ops.cpr.delete_all_rigs() == {'FINISHED'}
assert not common._rig_paths(scene)
assert len(common._rig_paths(other_scene)) == 1
assert other_path.cpr_rig.camera == other_camera
assert bpy.data.objects.get("Cube") == unrelated

# Check disable and re-enable, as used for updates.
addon_utils.disable(module_name, default_set=True)
assert not hasattr(bpy.types.Scene, "cpr_settings")
assert not hasattr(bpy.types.Object, "cpr_rig")
addon_utils.enable(module_name, default_set=True, handle_error=lambda: errors.append(True))
assert not errors
assert hasattr(bpy.types.Scene, "cpr_settings")
addon_utils.disable(module_name, default_set=True)
bpy.context.preferences.extensions.repos.remove(repo)
print("PASS: extension enable, preferences, rig creation, animation endpoints, aim path,")
print("scene-scoped deletion, preservation of unrelated objects, disable/re-enable")
