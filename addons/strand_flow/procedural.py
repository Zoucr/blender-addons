"""Live Geometry Nodes strand generation. No frame handlers or per-frame caches."""
import math
import bpy

MODIFIER = 'Strand Flow V4'
GRAPH_REVISION = 3
# Values are driven from the object's settings and evaluated for every frame.
CONTROLS = {
 'count':('NodeSocketInt',1,20000), 'preview':('NodeSocketFloat',1,100),
 'points':('NodeSocketInt',8,1024), 'seed':('NodeSocketInt',0,100000),
 'spread':('NodeSocketFloat',0,10000), 'depth':('NodeSocketFloat',0,10000),
 'concentration':('NodeSocketFloat',1,12), 'radius':('NodeSocketFloat',.00001,10000),
 'sides':('NodeSocketInt',3,16), 'thickness_random':('NodeSocketFloat',0,1),
 'taper':('NodeSocketFloat',0,.5), 'trim':('NodeSocketFloat',0,.45),
 'noise':('NodeSocketFloat',0,10000), 'frequency':('NodeSocketFloat',0,100),
 'twist':('NodeSocketFloat',-1000,1000),
 'wake_amount':('NodeSocketFloat',0,1), 'wake_spread':('NodeSocketFloat',0,10000),
 'wake_start':('NodeSocketFloat',0,1), 'wake_end':('NodeSocketFloat',0,1),
 'wake_fade_in':('NodeSocketFloat',.001,1), 'wake_fade_out':('NodeSocketFloat',0,1),
 'wake_noise':('NodeSocketFloat',0,10000), 'wake_frequency':('NodeSocketFloat',0,100),
 'wake_phase':('NodeSocketFloat',-100000,100000),
 'clearance':('NodeSocketFloat',0,10000), 'fade':('NodeSocketFloat',.0001,10000),
}

class Graph:
    def __init__(self,tree):self.tree=tree;self.nodes=tree.nodes;self.links=tree.links;self.section=None
    def node(self,kind,label='',**properties):
        n=self.nodes.new(kind);n.label=label
        if label:n.name=label
        for k,v in properties.items():
            if k=='mode' and not hasattr(n,k) and 'Mode' in n.inputs:
                n.inputs['Mode'].default_value=v.replace('_',' ').title()
            else:setattr(n,k,v)
        # Leave layout to the user; assigning parents and locations per node is costly.
        return n
    def wire(self,value,socket):
        if isinstance(value,bpy.types.NodeSocket):self.links.new(value,socket)
        else:socket.default_value=value
    def calc(self,op,a,b=0):
        n=self.node('ShaderNodeMath',operation=op);self.wire(a,n.inputs[0]);self.wire(b,n.inputs[1]);return n.outputs[0]
    def vec(self,op,a,b=(0,0,0)):
        n=self.node('ShaderNodeVectorMath',operation=op);self.wire(a,n.inputs[0])
        self.wire(b,n.inputs['Scale'] if op=='SCALE' else n.inputs[1])
        return n.outputs['Value'] if op in {'DOT_PRODUCT','LENGTH','DISTANCE'} else n.outputs['Vector']
    def mix(self,a,b,f,vector=False):
        return self.vec('ADD',a,self.vec('SCALE',self.vec('SUBTRACT',b,a),f)) if vector else self.calc('ADD',a,self.calc('MULTIPLY',self.calc('SUBTRACT',b,a),f))
    def clamp(self,a):return self.calc('MINIMUM',1,self.calc('MAXIMUM',0,a))
    def smooth(self,a):
        a=self.clamp(a);return self.calc('MULTIPLY',self.calc('MULTIPLY',a,a),self.calc('SUBTRACT',3,self.calc('MULTIPLY',2,a)))
    def switch(self,typ,cond,a,b):
        n=self.node('GeometryNodeSwitch',input_type=typ);self.wire(cond,n.inputs['Switch']);self.wire(a,n.inputs['False']);self.wire(b,n.inputs['True']);return n.outputs[0]
    def store(self,geo,name,value,typ='FLOAT',domain='POINT'):
        n=self.node('GeometryNodeStoreNamedAttribute',name,data_type=typ,domain=domain)
        self.wire(geo,n.inputs['Geometry']);n.inputs['Name'].default_value=name;self.wire(value,n.inputs['Value']);return n.outputs['Geometry']
    def attr(self,name,typ='FLOAT'):
        n=self.node('GeometryNodeInputNamedAttribute',name,data_type=typ);n.inputs['Name'].default_value=name;return n.outputs['Attribute']
    def rand(self,id,seed,salt):
        n=self.node('FunctionNodeRandomValue',data_type='FLOAT')
        n.inputs['Min'].default_value=0;n.inputs['Max'].default_value=1
        self.wire(id,n.inputs['ID']);self.wire(self.calc('ADD',seed,salt),n.inputs['Seed']);return n.outputs['Value']
    def frame(self,tangent,axis):
        tangent=self.vec('NORMALIZE',tangent)
        up={'X':(1,0,0),'Y':(0,1,0),'Z':(0,0,1)}[axis]
        alt=(0,1,0) if axis!='Y' else (0,0,1)
        near=self.calc('GREATER_THAN',self.calc('ABSOLUTE',self.vec('DOT_PRODUCT',tangent,up)),.99)
        ref=self.switch('VECTOR',near,up,alt)
        n=self.vec('NORMALIZE',self.vec('SUBTRACT',ref,self.vec('SCALE',tangent,self.vec('DOT_PRODUCT',tangent,ref))))
        v=self.vec('NORMALIZE',self.vec('CROSS_PRODUCT',tangent,n))
        return n,v

def descriptors(s):
    groups={}
    for row in s.guides:
        if not row.enabled or not row.obj:continue
        a=row.obj
        if a.type!='CURVE':raise ValueError(f'{a.name}: use a curve guide')
        if a.data.bevel_depth or a.data.extrude or a.data.bevel_object:
            raise ValueError(f'{a.name}: guide bevel/extrusion must be zero for live curves')
        for i,sa in enumerate(a.data.splines):
            def usable(sp):return len(sp.bezier_points if sp.type=='BEZIER' else sp.points)>=2
            if not usable(sa):continue
            if sa.use_cyclic_u:raise ValueError('Use open guides')
            if sa.type not in {'BEZIER','POLY'}:raise ValueError('Use Bezier or Poly guides')
            groups.setdefault(row.group,[]).append((a,i,row.reverse))
    if not groups:raise ValueError('No usable guide splines with at least two points')
    if s.mode!='AROUND' and any(len(v)<2 for v in groups.values()):raise ValueError('Fill modes require two guides in every group')
    return groups

def signature(s):
    return repr((GRAPH_REVISION,[(r.obj.name_full if r.obj else None,r.enabled,r.reverse,r.group,
                   len(r.obj.data.splines) if r.obj else 0) for r in s.guides],
                 s.mode,s.shape,s.up,s.exclusions.name_full if s.exclusions else None,s.exclusion_mode,
                 s.material.name_full if s.material else None))

def slot_tree(system,s,ds,group_index):
    """Build the expensive strand graph once for all intervals in a guide group."""
    tree=bpy.data.node_groups.new(system.name+f' / Strands Group {group_index}','GeometryNodeTree')
    g=Graph(tree)
    try:
        for key,(kind,low,high) in CONTROLS.items():
            item=tree.interface.new_socket(name=key,in_out='INPUT',socket_type=kind)
            item.default_value=getattr(s,key);item.min_value=low;item.max_value=high
        for name,kind in [('active_count','NodeSocketInt'),('slot','NodeSocketInt'),('slots','NodeSocketInt'),
                          ('a_guide','NodeSocketObject'),('b_guide','NodeSocketObject'),
                          ('a_index','NodeSocketInt'),('b_index','NodeSocketInt'),
                          ('a_reverse','NodeSocketBool'),('b_reverse','NodeSocketBool')]:
            tree.interface.new_socket(name=name,in_out='INPUT',socket_type=kind)
        tree.interface.new_socket(name='Geometry',in_out='OUTPUT',socket_type='NodeSocketGeometry')
        inp=g.node('NodeGroupInput');out=g.node('NodeGroupOutput')
        c={key:inp.outputs[key] for key in CONTROLS}
        c.update({key:inp.outputs[key] for key in ('active_count','slot','slots','a_guide','b_guide',
                                                 'a_index','b_index','a_reverse','b_reverse')})
        active_count=c['active_count']
        object_geometry={}
        def objgeo(obj):
            if obj not in object_geometry:
                n=g.node('GeometryNodeObjectInfo',obj.name,transform_space='RELATIVE')
                n.inputs['Object'].default_value=obj;n.inputs['As Instance'].default_value=False
                object_geometry[obj]=n.outputs['Geometry']
            return object_geometry[obj]
        mesh=g.node('GeometryNodeMeshLine','Strand seeds',mode='OFFSET')
        count=g.calc('MAXIMUM',1,g.calc('CEIL',g.calc('DIVIDE',g.calc('SUBTRACT',active_count,c['slot']),c['slots'])))
        g.wire(count,mesh.inputs['Count'])
        index=g.node('GeometryNodeInputIndex').outputs[0]
        sid=g.calc('ADD',g.calc('MULTIPLY',index,c['slots']),c['slot'])
        geo=g.store(mesh.outputs['Mesh'],'sf_id',sid,'INT')
        delete=g.node('GeometryNodeDeleteGeometry',domain='POINT',mode='ALL')
        g.wire(geo,delete.inputs['Geometry']);g.wire(g.calc('GREATER_THAN',sid,g.calc('SUBTRACT',active_count,.5)),delete.inputs['Selection'])
        line=g.node('GeometryNodeCurvePrimitiveLine');line.inputs['Start'].default_value=(0,0,0);line.inputs['End'].default_value=(1,0,0)
        inst=g.node('GeometryNodeInstanceOnPoints');g.wire(delete.outputs[0],inst.inputs['Points']);g.wire(line.outputs[0],inst.inputs['Instance'])
        real=g.node('GeometryNodeRealizeInstances');g.wire(inst.outputs[0],real.inputs[0])
        res=g.node('GeometryNodeResampleCurve',mode='COUNT');g.wire(real.outputs[0],res.inputs['Curve']);g.wire(c['points'],res.inputs['Count'])
        geo=res.outputs[0];id=g.attr('sf_id','INT')
        random=lambda salt:g.rand(id,c['seed'],salt)
        param=g.node('GeometryNodeSplineParameter')
        start=g.calc('MULTIPLY',random(21),c['trim']);end=g.calc('SUBTRACT',1,g.calc('MULTIPLY',random(22),c['trim']))
        u=g.mix(start,end,param.outputs['Factor']);geo=g.store(geo,'sf_u',u)
        u=g.attr('sf_u')
        cache={}
        def sample(d):
            if d in cache:return cache[d]
            if d in {'A','B'}:
                tag=d.lower()
                info=g.node('GeometryNodeObjectInfo',transform_space='RELATIVE')
                g.wire(c[tag+'_guide'],info.inputs['Object'])
                info.inputs['As Instance'].default_value=False
                curve=info.outputs['Geometry']
                index=c[tag+'_index'];reverse=c[tag+'_reverse']
                factor=g.switch('FLOAT',reverse,u,g.calc('SUBTRACT',1,u))
                sign=g.switch('FLOAT',reverse,1,-1)
            else:
                obj,index,reverse=d
                curve=objgeo(obj)
                factor=g.calc('SUBTRACT',1,u) if reverse else u
                sign=-1 if reverse else 1
            n=g.node('GeometryNodeSampleCurve',mode='FACTOR');n.use_all_curves=False
            g.wire(curve,n.inputs['Curves']);g.wire(index,n.inputs['Curve Index'])
            g.wire(factor,n.inputs['Factor'])
            cache[d]=(n.outputs['Position'],g.vec('SCALE',n.outputs['Tangent'],sign))
            return cache[d]
        f=random(1)
        if s.mode=='HYBRID':
            low=g.calc('MULTIPLY',.5,g.calc('POWER',g.calc('MULTIPLY',2,f),c['concentration']))
            high=g.calc('SUBTRACT',1,g.calc('MULTIPLY',.5,g.calc('POWER',g.calc('MULTIPLY',2,g.calc('SUBTRACT',1,f)),c['concentration'])))
            f=g.switch('FLOAT',g.calc('GREATER_THAN',f,.5),low,high)
        pa,ta=sample('A');pb,tb=sample('B')
        base=g.mix(pa,pb,f,True);tangent=g.mix(ta,tb,f,True);n,v=g.frame(tangent,s.up)
        theta=g.calc('MULTIPLY',random(2),math.tau)
        radial=g.calc('POWER',random(3),g.calc('DIVIDE',c['concentration'],2) if s.mode=='AROUND' else .5)
        lateral=g.calc('MULTIPLY',g.calc('MULTIPLY',g.calc('COSINE',theta),radial),c['spread']) if s.mode=='AROUND' else 0
        depth=g.calc('MULTIPLY',g.calc('MULTIPLY',g.calc('SINE',theta),radial),c['spread'] if s.mode=='AROUND' else c['depth'])
        phase=g.calc('ADD',g.calc('MULTIPLY',g.calc('MULTIPLY',u,c['frequency']),math.tau),theta)
        wave=g.calc('MULTIPLY',c['noise'],g.calc('SINE',g.calc('MULTIPLY',u,math.pi)))
        pos=g.vec('ADD',base,g.vec('ADD',g.vec('SCALE',n,g.calc('ADD',depth,g.calc('MULTIPLY',wave,g.calc('SINE',phase)))),g.vec('SCALE',v,g.calc('ADD',lateral,g.calc('MULTIPLY',wave,g.calc('MULTIPLY',.5,g.calc('COSINE',g.calc('MULTIPLY',phase,.73))))))))
        center=(0,0,0);ct=(0,0,0)
        for d in ds:
            p,t=sample(d);center=g.vec('ADD',center,p);ct=g.vec('ADD',ct,t)
        center=g.vec('SCALE',center,1/len(ds));wn,wv=g.frame(ct,s.up)
        delta=g.vec('SUBTRACT',pos,center)
        radialvec=g.vec('ADD',g.vec('SCALE',wn,g.vec('DOT_PRODUCT',delta,wn)),g.vec('SCALE',wv,g.vec('DOT_PRODUCT',delta,wv)))
        fallback=g.vec('ADD',g.vec('SCALE',wn,g.calc('COSINE',theta)),g.vec('SCALE',wv,g.calc('SINE',theta)))
        direction=g.vec('NORMALIZE',g.vec('ADD',radialvec,g.vec('SCALE',fallback,g.calc('MAXIMUM',.00001,g.calc('MULTIPLY',c['wake_spread'],.02)))))
        span=g.calc('SUBTRACT',c['wake_end'],c['wake_start'])
        local=g.calc('DIVIDE',g.calc('SUBTRACT',u,c['wake_start']),g.calc('MAXIMUM',span,.000001))
        enter=g.smooth(g.calc('DIVIDE',local,g.calc('MAXIMUM',c['wake_fade_in'],.000001)))
        leave=g.switch('FLOAT',g.calc('GREATER_THAN',c['wake_fade_out'],0),1,g.smooth(g.calc('DIVIDE',g.calc('SUBTRACT',1,local),g.calc('MAXIMUM',c['wake_fade_out'],.000001))))
        inside=g.calc('MULTIPLY',g.calc('LESS_THAN',u,g.calc('ADD',c['wake_end'],.000001)),g.calc('GREATER_THAN',span,.000001))
        weight=g.calc('MULTIPLY',c['wake_amount'],g.calc('MULTIPLY',inside,g.calc('MULTIPLY',enter,leave)))
        phase=g.calc('ADD',theta,g.calc('MULTIPLY',math.tau,g.calc('SUBTRACT',g.calc('MULTIPLY',u,c['wake_frequency']),c['wake_phase'])))
        perturb=g.vec('ADD',g.vec('SCALE',wn,g.calc('SINE',phase)),g.vec('SCALE',wv,g.calc('MULTIPLY',.65,g.calc('SINE',g.calc('ADD',theta,g.calc('MULTIPLY',phase,1.71))))))
        pos=g.vec('ADD',pos,g.vec('SCALE',g.vec('ADD',g.vec('SCALE',direction,c['wake_spread']),g.vec('SCALE',perturb,c['wake_noise'])),weight))
        setpos=g.node('GeometryNodeSetPosition');g.wire(geo,setpos.inputs['Geometry']);g.wire(pos,setpos.inputs['Position']);geo=setpos.outputs[0]
        p=g.node('GeometryNodeSplineParameter');length=g.node('GeometryNodeSplineLength').outputs['Length']
        taper=g.smooth(g.calc('MINIMUM',g.calc('DIVIDE',p.outputs['Factor'],g.calc('MAXIMUM',c['taper'],.000001)),g.calc('DIVIDE',g.calc('SUBTRACT',1,p.outputs['Factor']),g.calc('MAXIMUM',c['taper'],.000001))))
        taper=g.switch('FLOAT',g.calc('GREATER_THAN',c['taper'],0),1,taper)
        radius=g.calc('MULTIPLY',c['radius'],g.calc('SUBTRACT',1,g.calc('MULTIPLY',random(10),c['thickness_random'])))
        geo=g.store(geo,'sf_random',random(11));geo=g.store(geo,'sf_endfade',taper)
        geo=g.store(geo,'sf_brightness',g.calc('MULTIPLY',taper,g.calc('ADD',.08,g.calc('MULTIPLY',.92,g.calc('POWER',random(12),2)))))
        # Curve length is in system-local units. Object scale should remain applied/identity.
        geo=g.store(geo,'sf_distance',p.outputs['Length']);geo=g.store(geo,'sf_length',length)
        geo=g.store(geo,'sf_radius',g.calc('MULTIPLY',radius,g.calc('MAXIMUM',taper,.001)))
        g.wire(geo,out.inputs['Geometry'])
        for i,node in enumerate(tree.nodes):node.location=((i%6)*230,-(i//6)*180)
        return tree
    except Exception:
        bpy.data.node_groups.remove(tree)
        raise

def build(system,force=False):
    from . import make_material
    s=system.sf
    mod=system.modifiers.get(MODIFIER)
    sig=signature(s)
    if not force and mod and mod.node_group and mod.node_group.get('sf_signature')==sig:return
    groups=descriptors(s)
    if s.exclusions and system in s.exclusions.all_objects:raise ValueError('The exclusion collection must not contain the output system')
    material=make_material(system)
    tree=bpy.data.node_groups.new(system.name+' / Live Strands','GeometryNodeTree');tree.is_modifier=True
    g=Graph(tree)
    templates=[]
    try:
        tree.interface.new_socket(name='Geometry',in_out='INPUT',socket_type='NodeSocketGeometry')
        tree.interface.new_socket(name='Geometry',in_out='OUTPUT',socket_type='NodeSocketGeometry')
        out=g.node('NodeGroupOutput','Final strands')
        c={}
        for key in CONTROLS:
            node=g.node('ShaderNodeValue','Animate '+key)
            node.outputs[0].default_value=getattr(s,key)
            driver=node.outputs[0].driver_add('default_value').driver
            variable=driver.variables.new();variable.name='value';variable.type='SINGLE_PROP'
            variable.targets[0].id=system;variable.targets[0].data_path='sf.'+key
            driver.expression='value'
            c[key]=node.outputs[0]
        viewport=g.node('GeometryNodeIsViewport').outputs[0]
        lod=g.calc('MAXIMUM',1,g.calc('CEIL',g.calc('MULTIPLY',c['count'],g.calc('DIVIDE',c['preview'],100))))
        active_count=g.switch('INT',viewport,c['count'],lod)
        joined=g.node('GeometryNodeJoinGeometry','Join strand groups')
        slots_total=sum(len(v) if s.mode=='AROUND' else len(v)-1 for v in groups.values())
        slot=0
        for group_index,ds in enumerate(groups.values()):
            tree_slot=slot_tree(system,s,ds,group_index)
            templates.append(tree_slot)
            intervals=[(d,d) for d in ds] if s.mode=='AROUND' else list(zip(ds,ds[1:]))
            for da,db in intervals:
                instance=g.node('GeometryNodeGroup','Guide interval')
                instance.node_tree=tree_slot
                for key in CONTROLS:g.wire(c[key],instance.inputs[key])
                g.wire(active_count,instance.inputs['active_count'])
                instance.inputs['slot'].default_value=slot
                instance.inputs['slots'].default_value=slots_total
                for prefix,d in (('a',da),('b',db)):
                    instance.inputs[prefix+'_guide'].default_value=d[0]
                    instance.inputs[prefix+'_index'].default_value=d[1]
                    instance.inputs[prefix+'_reverse'].default_value=d[2]
                g.wire(instance.outputs['Geometry'],joined.inputs['Geometry'])
                slot+=1
        geo=joined.outputs[0]
        if s.exclusions:
            info=g.node('GeometryNodeCollectionInfo','Exclusion meshes',transform_space='RELATIVE');info.inputs['Collection'].default_value=s.exclusions
            real=g.node('GeometryNodeRealizeInstances');g.wire(info.outputs['Instances'],real.inputs[0]);obstacles=real.outputs[0]
            position=g.node('GeometryNodeInputPosition').outputs[0]
            near=g.node('GeometryNodeProximity',target_element='FACES');g.wire(obstacles,near.inputs['Geometry']);g.wire(position,near.inputs['Sample Position'])
            normal=g.node('GeometryNodeSampleNearestSurface',data_type='FLOAT_VECTOR');g.wire(obstacles,normal.inputs['Mesh']);g.wire(g.node('GeometryNodeInputNormal').outputs[0],normal.inputs['Value']);g.wire(position,normal.inputs['Sample Position'])
            signed=g.vec('DOT_PRODUCT',g.vec('SUBTRACT',position,near.outputs['Position']),normal.outputs['Value'])
            clearance=g.calc('ADD',c['clearance'],g.attr('sf_radius'))
            blocked=g.calc('MAXIMUM',g.calc('LESS_THAN',signed,0),g.calc('LESS_THAN',near.outputs['Distance'],clearance))
            if s.exclusion_mode=='REMOVE':
                accum=g.node('GeometryNodeAccumulateField',data_type='FLOAT',domain='POINT');g.wire(blocked,accum.inputs['Value']);g.wire(g.attr('sf_id','INT'),accum.inputs['Group ID']);blocked=accum.outputs['Total']
            geo=g.store(geo,'sf_block',blocked)
            if s.exclusion_mode=='FADE':
                fade=g.clamp(g.calc('DIVIDE',g.calc('SUBTRACT',near.outputs['Distance'],clearance),c['fade']))
                fade=g.calc('MULTIPLY',fade,g.calc('SUBTRACT',1,g.clamp(blocked)))
                for name in ['sf_radius','sf_brightness','sf_endfade']:geo=g.store(geo,name,g.calc('MULTIPLY',g.attr(name),fade))
        normal=g.node('GeometryNodeSetCurveNormal');normal.inputs['Mode'].default_value='Free'
        tangent=g.node('GeometryNodeInputTangent').outputs[0];n,v=g.frame(tangent,s.up)
        p=g.node('GeometryNodeSplineParameter').outputs['Factor'];tw=g.calc('MULTIPLY',p,c['twist'])
        normalvec=g.vec('ADD',g.vec('SCALE',n,g.calc('COSINE',tw)),g.vec('SCALE',v,g.calc('SINE',tw)))
        g.wire(geo,normal.inputs['Curve']);g.wire(normalvec,normal.inputs['Normal']);geo=normal.outputs[0]
        rad=g.node('GeometryNodeSetCurveRadius');g.wire(geo,rad.inputs['Curve']);g.wire(g.attr('sf_radius'),rad.inputs['Radius']);geo=rad.outputs[0]
        if s.shape=='TUBE':
            profile=g.node('GeometryNodeCurvePrimitiveCircle',mode='RADIUS');g.wire(c['sides'],profile.inputs['Resolution']);profile.inputs['Radius'].default_value=1
            profile_geo=g.store(profile.outputs['Curve'],'sf_across',0)
        else:
            profile=g.node('GeometryNodeCurvePrimitiveLine');profile.inputs['Start'].default_value=(-1,0,0);profile.inputs['End'].default_value=(1,0,0)
            sep=g.node('ShaderNodeSeparateXYZ');g.wire(g.node('GeometryNodeInputPosition').outputs[0],sep.inputs[0])
            profile_geo=g.store(profile.outputs['Curve'],'sf_across',sep.outputs['X'])
        mesh=g.node('GeometryNodeCurveToMesh');g.wire(geo,mesh.inputs['Curve']);g.wire(profile_geo,mesh.inputs['Profile Curve']);g.wire(g.attr('sf_radius'),mesh.inputs['Scale']);geo=mesh.outputs['Mesh']
        if s.exclusions:
            delete=g.node('GeometryNodeDeleteGeometry',domain='FACE',mode='ALL');g.wire(geo,delete.inputs[0]);g.wire(g.calc('GREATER_THAN',g.attr('sf_block'),.00001),delete.inputs['Selection']);geo=delete.outputs[0]
        smooth=g.node('GeometryNodeSetShadeSmooth',domain='FACE');g.wire(geo,smooth.inputs['Geometry']);geo=smooth.outputs[0]
        mat=g.node('GeometryNodeSetMaterial');g.wire(geo,mat.inputs['Geometry']);mat.inputs['Material'].default_value=material
        g.wire(mat.outputs[0],out.inputs['Geometry'])
        for i,node in enumerate(tree.nodes):node.location=((i%6)*230,-(i//6)*180)
        old=mod.node_group if mod else None
        if not mod:mod=system.modifiers.new(MODIFIER,'NODES')
        mod.node_group=tree
        tree['sf_signature']=signature(s)
        if old and old.users==0:
            old_templates={node.node_tree for node in old.nodes if node.bl_idname=='GeometryNodeGroup' and node.node_tree}
            bpy.data.node_groups.remove(old)
            for sub in old_templates:
                if sub.users==0:bpy.data.node_groups.remove(sub)
        s.status='LIVE V5: preview density in viewport, full density in render'
        system.update_tag()
    except Exception:
        if tree.users==0:bpy.data.node_groups.remove(tree)
        for sub in templates:
            if sub.users==0:bpy.data.node_groups.remove(sub)
        raise

class SF_OT_live_copy(bpy.types.Operator):
    bl_idname='sf.live_copy';bl_label='Create V5 Live Copy';bl_options={'REGISTER','UNDO'}
    def execute(self,context):
        from . import current_system
        old=current_system(context)
        if not old or context.mode!='OBJECT':return {'CANCELLED'}
        if old.sf.bake_collection:
            self.report({'ERROR'},'Clear the V3 bake before creating a live copy');return {'CANCELLED'}
        obj=old.copy();obj.data=bpy.data.meshes.new('Strand Flow V5 Source');obj.name=old.name+' V5'
        obj.modifiers.clear();context.collection.objects.link(obj)
        if obj.animation_data and obj.animation_data.action:obj.animation_data.action=obj.animation_data.action.copy()
        if old.sf.material:obj.sf.material=old.sf.material.copy()
        obj.sf.engine='GN';obj.sf.guide_animation='WAKE';obj.sf.live=False;obj.sf.morph_preview=False
        for guide in obj.sf.guides:guide.target=None
        try:build(obj,True)
        except Exception as exc:
            mesh=obj.data;material=obj.sf.material
            bpy.data.objects.remove(obj,do_unlink=True)
            if mesh.users==0:bpy.data.meshes.remove(mesh)
            if material and material!=old.sf.material and material.users==0:bpy.data.materials.remove(material)
            self.report({'ERROR'},str(exc));return {'CANCELLED'}
        old.hide_render=True;old.hide_set(True)
        for selected in context.selected_objects:selected.select_set(False)
        obj.hide_render=False;obj.hide_set(False);obj.select_set(True)
        context.view_layer.objects.active=obj;context.scene.sf_system=obj
        self.report({'INFO'},'Live copy created. Original hidden and retained in the Outliner.')
        return {'FINISHED'}

CLASSES=(SF_OT_live_copy,)
