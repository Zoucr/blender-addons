"""Run with Blender 5.2+: blender -b --factory-startup --python lighting_blender_test.py"""
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'addons'))
import strand_flow

strand_flow.register()

curve_data = bpy.data.curves.new('Animated light guide', 'CURVE')
curve_data.dimensions = '3D'
poly = curve_data.splines.new('POLY')
poly.points.add(1)
poly.points[0].co = (0, 0, 0, 1)
poly.points[1].co = (2, 0, 0, 1)
guide = bpy.data.objects.new('Guide', curve_data)
bpy.context.scene.collection.objects.link(guide)
guide.keyframe_insert('location', frame=1)

mesh = bpy.data.meshes.new('System Mesh')
system = bpy.data.objects.new('Light Test System', mesh)
bpy.context.scene.collection.objects.link(system)
system.sf.is_system = True
row = system.sf.guides.add()
row.obj = guide
system.sf.light_count = 2
system.sf.light_power = 20
system.sf.light_enabled = True

assert len(system.sf.light_rig.objects) == 8
lights = sorted(system.sf.light_rig.objects, key=lambda obj: obj.name)
assert all(light.constraints[0].target == guide for light in lights)

def energy(light):
    dg = bpy.context.evaluated_depsgraph_get()
    return light.evaluated_get(dg).data.energy

def location(light):
    dg = bpy.context.evaluated_depsgraph_get()
    return light.evaluated_get(dg).matrix_world.translation.copy()

bpy.context.scene.frame_set(1)
assert abs(energy(lights[0]) - 10) < .001, energy(lights[0])
assert abs(energy(lights[1]) - 10) < .001, energy(lights[1])
assert abs(energy(lights[2])) < .001, energy(lights[2])
first = location(lights[0])
assert 0 < first.x < 2, first

guide.location.x = 1
guide.keyframe_insert('location', frame=10)
bpy.context.scene.frame_set(10)
assert abs(location(lights[0]).x - first.x - 1) < .02

system.sf.light_enabled = False
bpy.context.scene.frame_set(11)
assert all(abs(energy(light)) < .001 for light in lights)
system.sf.light_enabled = True
bpy.context.scene.frame_set(12)
assert abs(energy(lights[0]) - 10) < .001
print('LIGHT_RIG_TEST_PASS')
strand_flow.unregister()
