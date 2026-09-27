"""Run with Blender 5.2: blender -b --factory-startup --python tests/live_blender.py."""
import sys
from pathlib import Path
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parents[1] / 'addons'))
import strand_flow
strand_flow.register()
assert bpy.ops.sf.demo()=={'FINISHED'}
obj=bpy.context.view_layer.objects.active
s=obj.sf
assert s.engine=='GN' and s.guide_animation=='WAKE' and len(s.guides)==4
assert len(obj.modifiers)==1 and obj.modifiers[0].type=='NODES'
s.points=24;s.count=240;s.preview=25;s.wake_start=.3;s.wake_end=1
s.wake_spread=2;s.wake_noise=.6;s.wake_amount=0
s.keyframe_insert(data_path='wake_amount',frame=1)
s.wake_amount=1;s.keyframe_insert(data_path='wake_amount',frame=10)
s.wake_phase=0;s.keyframe_insert(data_path='wake_phase',frame=1)
s.wake_phase=1;s.keyframe_insert(data_path='wake_phase',frame=10)
def evaluated(frame):
    bpy.context.scene.frame_set(frame)
    ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh()
    ids={item.value for item in mesh.attributes['sf_id'].data}
    required={'sf_u','sf_random','sf_endfade','sf_distance','sf_length','sf_radius','sf_across'}
    assert required.issubset(mesh.attributes.keys())
    result=(len(ids),len(mesh.vertices),tuple(mesh.vertices[-1].co))
    ev.to_mesh_clear();return result
first=evaluated(1);last=evaluated(10)
assert first[:2]==last[:2] and first[0]==60 and first[2]!=last[2],(first,last)
# A live guide transform propagates without generating a new frame's mesh in Python.
guide=s.guides[0].obj
before=evaluated(10)
guide.location.z+=1
bpy.context.view_layer.update()
after=evaluated(10)
assert before[2]!=after[2],(before,after)
# V4 ignores stale B settings from an older file.
s.guide_animation='MORPH';s.blend=.75
assert bpy.ops.sf.update()=={'FINISHED'}
assert evaluated(10)==after
# The conversion retains the V3 object and builds a separate live system.
obj.sf.engine='LEGACY'
assert bpy.ops.sf.live_copy()=={'FINISHED'}
new=bpy.context.view_layer.objects.active
assert new!=obj and obj.hide_render and new.sf.engine=='GN' and new.sf.guide_animation=='WAKE'
assert len(new.modifiers)==1 and new.modifiers[0].type=='NODES'
print('LIVE V4 PASSED',first,last)
