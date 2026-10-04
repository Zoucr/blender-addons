"""Final RGBA opacity and independent gradient visibility controls."""
import bpy

NODE_NAME = 'SF Output Alpha'


def ensure_gradient_controls(material):
    """Upgrade the generated gradient in place without replacing its palette or keyframes."""
    if not material or not material.use_nodes:return
    nodes,links=material.node_tree.nodes,material.node_tree.links
    emission=nodes.get('Emission')
    bright=nodes.get('Strand Brightness')
    if emission and emission.type=='EMISSION' and not nodes.get('SF Color Boost'):
        source=emission.inputs['Color'].links[0].from_socket if emission.inputs['Color'].is_linked else None
        boost=nodes.new('ShaderNodeValue');boost.name=boost.label='SF Color Boost'
        boost.outputs[0].default_value=1;boost.location=(emission.location.x-420,emission.location.y+220)
        color=nodes.new('ShaderNodeVectorMath');color.operation='SCALE';color.name=color.label='SF Boost Color'
        color.location=(emission.location.x-200,emission.location.y+180)
        if source:links.new(source,color.inputs[0])
        else:color.inputs[0].default_value=emission.inputs['Color'].default_value[:3]
        links.new(boost.outputs[0],color.inputs['Scale'])
        links.new(color.outputs['Vector'],emission.inputs['Color'])
    if bright and bright.type=='MATH' and not nodes.get('SF Brightness Floor'):
        source=bright.inputs[0].links[0].from_socket if bright.inputs[0].is_linked else None
        floor=nodes.new('ShaderNodeValue');floor.name=floor.label='SF Brightness Floor'
        floor.outputs[0].default_value=0;floor.location=(bright.location.x-380,bright.location.y-240)
        minimum=nodes.new('ShaderNodeMath');minimum.operation='MAXIMUM'
        minimum.name=minimum.label='SF Brightness Minimum'
        minimum.location=(bright.location.x-170,bright.location.y-150)
        if source:links.new(source,minimum.inputs[0])
        else:minimum.inputs[0].default_value=bright.inputs[0].default_value
        links.new(floor.outputs[0],minimum.inputs[1])
        links.new(minimum.outputs[0],bright.inputs[0])


def ensure_alpha(material):
    if not material or not material.use_nodes:return None
    nodes,links=material.node_tree.nodes,material.node_tree.links
    existing=nodes.get(NODE_NAME)
    if existing:return existing
    output=next((n for n in nodes if n.type=='OUTPUT_MATERIAL' and n.is_active_output),None)
    if not output or not output.inputs['Surface'].is_linked:return None
    source=output.inputs['Surface'].links[0].from_socket
    tree=bpy.data.node_groups.new(material.name+' / Output Alpha','ShaderNodeTree')
    try:
        interface=tree.interface
        interface.new_socket(name='Surface',in_out='INPUT',socket_type='NodeSocketShader')
        for name,default in [('Output Opacity',1),('Alpha from Brightness',0),('Minimum Alpha',.2)]:
            sock=interface.new_socket(name=name,in_out='INPUT',socket_type='NodeSocketFloat')
            sock.default_value=default;sock.min_value=0;sock.max_value=1
        interface.new_socket(name='Surface',in_out='OUTPUT',socket_type='NodeSocketShader')
        n,l=tree.nodes,tree.links
        inp=n.new('NodeGroupInput');inp.location=(-620,180)
        out=n.new('NodeGroupOutput');out.location=(480,120)
        attr=n.new('ShaderNodeAttribute');attr.attribute_name='sf_brightness';attr.location=(-620,-190)
        minimum=n.new('ShaderNodeMath');minimum.operation='MAXIMUM';minimum.location=(-400,-160)
        l.new(attr.outputs['Fac'],minimum.inputs[0]);l.new(inp.outputs['Minimum Alpha'],minimum.inputs[1])
        variation=n.new('ShaderNodeMix');variation.data_type='FLOAT';variation.location=(-170,-130)
        variation.inputs['A'].default_value=1
        l.new(inp.outputs['Alpha from Brightness'],variation.inputs['Factor'])
        l.new(minimum.outputs[0],variation.inputs['B'])
        # Factor 0 means constant opacity; Factor 1 lets strand brightness control alpha.
        opacity=n.new('ShaderNodeMath');opacity.operation='MULTIPLY';opacity.location=(50,-130)
        l.new(variation.outputs['Result'],opacity.inputs[0]);l.new(inp.outputs['Output Opacity'],opacity.inputs[1])
        transparent=n.new('ShaderNodeBsdfTransparent');transparent.location=(-30,-350)
        mix=n.new('ShaderNodeMixShader');mix.location=(260,120)
        l.new(opacity.outputs[0],mix.inputs[0])
        l.new(transparent.outputs[0],mix.inputs[1]);l.new(inp.outputs['Surface'],mix.inputs[2])
        l.new(mix.outputs[0],out.inputs['Surface'])
        group=nodes.new('ShaderNodeGroup');group.node_tree=tree;group.name=group.label=NODE_NAME
        group.location=(output.location.x,output.location.y-260)
        output.location.x+=250
        links.new(source,group.inputs['Surface']);links.new(group.outputs['Surface'],output.inputs['Surface'])
        if hasattr(material,'surface_render_method'):material.surface_render_method='DITHERED'
        return group
    except Exception:
        if tree.users==0:bpy.data.node_groups.remove(tree)
        raise


class SF_OT_strong_rgba(bpy.types.Operator):
    bl_idname='sf.strong_rgba';bl_label='Strong RGBA Preset';bl_options={'REGISTER','UNDO'}
    def execute(self,context):
        from . import current_system,make_material
        obj=current_system(context)
        if not obj:return {'CANCELLED'}
        material=make_material(obj)
        group=ensure_alpha(material)
        if not group:
            self.report({'ERROR'},'Material needs an active connected Surface output');return {'CANCELLED'}
        group.inputs['Output Opacity'].default_value=1
        group.inputs['Alpha from Brightness'].default_value=0
        style=material.node_tree.nodes.get('SF Surface Style')
        if style and style.inputs['Airflow'].default_value>.5:
            style.inputs['Opacity'].default_value=1
        else:
            boost=material.node_tree.nodes.get('SF Color Boost')
            floor=material.node_tree.nodes.get('SF Brightness Floor')
            if boost:boost.outputs[0].default_value=3
            if floor:floor.outputs[0].default_value=.35
        return {'FINISHED'}

CLASSES=(SF_OT_strong_rgba,)
