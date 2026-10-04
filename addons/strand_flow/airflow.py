"""Simple translucent airflow surface, inserted before the trail mask."""
import bpy

NODE_NAME = 'SF Surface Style'


def ensure_airflow(material):
    if not material or not material.use_nodes: return None
    nodes, links = material.node_tree.nodes, material.node_tree.links
    existing = nodes.get(NODE_NAME)
    if existing: return existing
    trail = nodes.get('SF Trail Particles')
    output = next((n for n in nodes if n.type == 'OUTPUT_MATERIAL' and n.is_active_output), None)
    target = trail.inputs['Surface'] if trail else (output.inputs['Surface'] if output else None)
    if target is None or not target.is_linked: return None
    original = target.links[0].from_socket
    tree = bpy.data.node_groups.new(material.name + ' / Surface Style', 'ShaderNodeTree')
    interface = tree.interface
    interface.new_socket(name='Gradient Surface', in_out='INPUT', socket_type='NodeSocketShader')
    for name, default, low, high in [('Airflow',0,0,1), ('Opacity',.5,0,1),
                                    ('Edge Softness',.65,.001,1), ('Roughness',.8,0,1),
                                    ('Emission',.15,0,10)]:
        socket = interface.new_socket(name=name, in_out='INPUT', socket_type='NodeSocketFloat')
        socket.default_value=default; socket.min_value=low; socket.max_value=high
    color = interface.new_socket(name='Color', in_out='INPUT', socket_type='NodeSocketColor')
    color.default_value=(.8,.9,1,1)
    interface.new_socket(name='Surface', in_out='OUTPUT', socket_type='NodeSocketShader')
    n,l=tree.nodes,tree.links
    inp=n.new('NodeGroupInput');inp.location=(-800,0)
    out=n.new('NodeGroupOutput');out.location=(650,0)
    def calc(op,name,a,b=0):
        node=n.new('ShaderNodeMath');node.operation=op;node.label=node.name=name
        node.location=(-550+(len(n)%3)*180,-200-(len(n)//3)*100)
        for i,value in enumerate((a,b)):
            if isinstance(value,(float,int)):node.inputs[i].default_value=value
            else:l.new(value,node.inputs[i])
        return node.outputs[0]
    across=n.new('ShaderNodeAttribute');across.attribute_name='sf_across';across.location=(-800,-250)
    ends=n.new('ShaderNodeAttribute');ends.attribute_name='sf_endfade';ends.location=(-800,-500)
    edge=calc('SUBTRACT','Distance from ribbon edge',1,calc('ABSOLUTE','Absolute width',across.outputs['Fac']))
    edge=calc('MINIMUM','Soft edge',1,calc('DIVIDE','Edge softness',edge,inp.outputs['Edge Softness']))
    alpha=calc('MULTIPLY','End fade',edge,ends.outputs['Fac'])
    alpha=calc('MULTIPLY','Opacity',alpha,inp.outputs['Opacity'])
    surface=n.new('ShaderNodeBsdfPrincipled');surface.location=(-100,180)
    l.new(inp.outputs['Color'],surface.inputs['Base Color'])
    l.new(inp.outputs['Color'],surface.inputs['Emission Color'])
    l.new(inp.outputs['Emission'],surface.inputs['Emission Strength'])
    l.new(inp.outputs['Roughness'],surface.inputs['Roughness'])
    surface.inputs['Specular IOR Level'].default_value=.15
    transparent=n.new('ShaderNodeBsdfTransparent');transparent.location=(0,-350)
    airy=n.new('ShaderNodeMixShader');airy.location=(220,0)
    l.new(alpha,airy.inputs[0]);l.new(transparent.outputs[0],airy.inputs[1]);l.new(surface.outputs[0],airy.inputs[2])
    style=n.new('ShaderNodeMixShader');style.location=(450,0)
    l.new(inp.outputs['Airflow'],style.inputs[0]);l.new(inp.outputs['Gradient Surface'],style.inputs[1]);l.new(airy.outputs[0],style.inputs[2])
    l.new(style.outputs[0],out.inputs[0])
    group=nodes.new('ShaderNodeGroup');group.node_tree=tree;group.name=group.label=NODE_NAME
    group.location=(original.node.location.x+220,original.node.location.y-120)
    links.new(original,group.inputs['Gradient Surface']);links.new(group.outputs['Surface'],target)
    if hasattr(material,'surface_render_method'):material.surface_render_method='DITHERED'
    return group


class SF_OT_surface_style(bpy.types.Operator):
    bl_idname='sf.surface_style';bl_label='Set Surface Style';bl_options={'REGISTER','UNDO'}
    mode:bpy.props.EnumProperty(items=[('GRADIENT','Gradient',''),('AIRFLOW','Airflow','')])
    def execute(self,context):
        from . import current_system, make_material, generate
        obj=current_system(context)
        if not obj:return {'CANCELLED'}
        try:
            if self.mode=='AIRFLOW' and obj.sf.engine!='GN' and not obj.data.attributes.get('sf_endfade'):
                if obj.sf.bake_collection:raise ValueError('Clear and rebuild the old bake to add airflow coordinates')
                generate(obj,False)
            node=ensure_airflow(make_material(obj))
            if not node:raise ValueError('Material needs an active connected Surface output')
            node.inputs['Airflow'].default_value=1 if self.mode=='AIRFLOW' else 0
        except Exception as exc:
            self.report({'ERROR'},str(exc));return {'CANCELLED'}
        return {'FINISHED'}


class SF_OT_airflow_ribbon(bpy.types.Operator):
    bl_idname='sf.airflow_ribbon';bl_label='Airflow Ribbon Preset';bl_options={'REGISTER','UNDO'}
    def execute(self,context):
        from . import current_system, generate
        obj=current_system(context)
        if not obj:return {'CANCELLED'}
        if obj.sf.bake_collection:
            self.report({'ERROR'},'Clear the bake before changing strand shape');return {'CANCELLED'}
        previous_shape=obj.sf.shape
        obj.sf.shape='RIBBON'
        try:
            generate(obj,False)
            node=ensure_airflow(obj.sf.material);node.inputs['Airflow'].default_value=1
            node.inputs['Color'].default_value=(.8,.9,1,1)
            node.inputs['Opacity'].default_value=.5
            node.inputs['Edge Softness'].default_value=.65
            node.inputs['Roughness'].default_value=.8
            node.inputs['Emission'].default_value=.15
            # Airflow defaults to continuous ribbons; particle mode can be enabled afterwards.
            trail=obj.sf.material.node_tree.nodes.get('SF Trail Particles')
            if trail:trail.inputs['Enabled'].default_value=0
        except Exception as exc:
            obj.sf.shape=previous_shape
            self.report({'ERROR'},str(exc));return {'CANCELLED'}
        return {'FINISHED'}


CLASSES=(SF_OT_surface_style,SF_OT_airflow_ribbon)
