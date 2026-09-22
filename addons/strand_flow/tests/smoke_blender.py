"""Run with Blender --background --factory-startup --python /absolute/path/to/this_file.py.
Creates temporary scene objects. Intended for a factory-startup test session only.
"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import bpy
import strand_flow
strand_flow.register()
bpy.ops.sf.demo()
obj=bpy.context.object
assert obj.sf.is_system
assert bpy.context.scene.sf_system==obj
assert len(obj.data.vertices)>0
assert obj.sf.material.node_tree.nodes.get('Flow Palette')
obj.sf.count=20
obj.sf.points=24
for mode in ('BETWEEN','AROUND','HYBRID'):
    obj.sf.mode=mode
    for shape in ('TUBE','RIBBON'):
        obj.sf.shape=shape
        strand_flow.generate(obj,True)
        assert len(obj.data.polygons)>0
        assert len(obj.data.attributes['sf_u'].data)==len(obj.data.vertices)
        assert not obj.data.validate()
mat=obj.sf.material
strand_flow.generate(obj,True)
assert obj.sf.material==mat
# A closed enclosure must remove all generated strands in all exclusion modes.
collection=bpy.data.collections.new('Smoke Exclusions')
bpy.context.scene.collection.children.link(collection)
bpy.ops.mesh.primitive_cube_add(size=100)
obstacle=bpy.context.object
for c in list(obstacle.users_collection): c.objects.unlink(obstacle)
collection.objects.link(obstacle)
obj.sf.exclusions=collection
for mode in ('REMOVE','CUT','FADE'):
    obj.sf.exclusion_mode=mode
    strand_flow.generate(obj,True)
    assert len(obj.data.polygons)==0, mode
obj.sf.exclusions=None
strand_flow.generate(obj,True)
assert len(obj.data.polygons)>0
strand_flow.unregister()
print('STRAND FLOW: native smoke tests passed')
# V2: node creation, migration, and time-driver verification.
strand_flow.register()
bpy.context.scene.sf_system=obj
bpy.context.view_layer.objects.active=obj
obj.select_set(True)
node=obj.sf.material.node_tree.nodes.get('SF Trail Particles')
assert node and node.inputs['Enabled'].default_value==0
bpy.context.scene.render.fps=24
bpy.context.scene.render.fps_base=1
bpy.context.scene.frame_set(25)
bpy.context.view_layer.update()
assert abs(node.inputs['Time'].default_value-1)<1e-5
assert obj.data.attributes.get('sf_distance')
assert obj.data.attributes.get('sf_length')
assert bpy.ops.sf.particle_mode(mode='PARTICLES')=={'FINISHED'}
assert node.inputs['Enabled'].default_value==1
palette=obj.sf.material.node_tree.nodes['Flow Palette']
colour=tuple(palette.color_ramp.elements[0].color)
# Simulate a V1 surface and mesh to exercise the upgrade path.
nt=obj.sf.material.node_tree
surface=node.inputs['Surface'].links[0].from_socket
output=next(n for n in nt.nodes if n.type=='OUTPUT_MATERIAL' and n.is_active_output)
nt.links.new(surface,output.inputs['Surface'])
nt.nodes.remove(node)
obj.data.attributes.remove(obj.data.attributes['sf_distance'])
assert bpy.ops.sf.particle_mode(mode='PARTICLES')=={'FINISHED'}
assert tuple(palette.color_ramp.elements[0].color)==colour
assert obj.data.attributes.get('sf_distance')
assert bpy.ops.sf.single_trail()=={'FINISHED'}
assert obj.sf.count==1
assert obj.sf.material.node_tree.nodes.get('SF Trail Particles')
strand_flow.unregister()
print('STRAND FLOW V2: native migration and time-driver tests passed')
