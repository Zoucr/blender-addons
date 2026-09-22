bl_info = {
    'name': 'Strand Flow', 'author': 'Lucca / OpenAI', 'version': (2, 0, 0),
    'blender': (5, 0, 0), 'location': 'View3D > Sidebar > Strand Flow',
    'description': 'Guide-driven 3D strand bundles, ribbons, exclusion zones and gradient material',
    'category': 'Add Curve',
}
import bpy
import math
import random
import bisect
from .particles import ensure_particles, NODE_NAME
import time
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from bpy.props import (BoolProperty, IntProperty, FloatProperty, EnumProperty,
                       PointerProperty, CollectionProperty, StringProperty)
from bpy.app.handlers import persistent

_BUSY = False
_PENDING = {}

def dirty(self, context):
    owner = self.id_data
    if isinstance(owner, bpy.types.Object) and hasattr(owner, 'sf'):
        owner.sf.status = 'Changes pending: Update or enable Live'
        if owner.sf.live:
            _PENDING[owner.name] = time.monotonic()

def curve_poll(self, obj):
    return obj.type == 'CURVE'

class SFGuide(bpy.types.PropertyGroup):
    obj: PointerProperty(type=bpy.types.Object, poll=curve_poll, update=dirty)
    enabled: BoolProperty(default=True, update=dirty)
    reverse: BoolProperty(name='Reverse', default=False, update=dirty)
    group: IntProperty(name='Group', default=0, min=0, max=99, update=dirty)

class SFSettings(bpy.types.PropertyGroup):
    is_system: BoolProperty(default=False)
    guides: CollectionProperty(type=SFGuide)
    active_guide: IntProperty()
    live: BoolProperty(name='Live Update', default=False, update=dirty)
    mode: EnumProperty(name='Distribution', items=[('BETWEEN','Between Guides','Fill ordered guide gaps'),('AROUND','Around Guides','Bundles around each guide'),('HYBRID','Hybrid','Fill gaps with concentration near guides')], default='HYBRID', update=dirty)
    count: IntProperty(name='Strands (total)', default=240, min=1, max=20000, update=dirty)
    preview: FloatProperty(name='Preview %', default=35, min=1, max=100, update=dirty)
    points: IntProperty(name='Points / Strand', default=96, min=8, max=1024, update=dirty)
    seed: IntProperty(name='Seed', default=7, min=0, update=dirty)
    spread: FloatProperty(name='Guide Spread', default=.12, min=0, subtype='DISTANCE', update=dirty)
    depth: FloatProperty(name='Depth Spread', default=.12, min=0, subtype='DISTANCE', update=dirty)
    concentration: FloatProperty(name='Guide Concentration', default=2.5, min=1, max=12, update=dirty)
    shape: EnumProperty(name='Strand Shape', items=[('TUBE','Tube','Round cross section'),('RIBBON','Ribbon','Flat two-sided strip')], default='TUBE', update=dirty)
    radius: FloatProperty(name='Radius / Half Width', default=.006, min=.00001, soft_max=.1, subtype='DISTANCE', update=dirty)
    sides: IntProperty(name='Tube Sides', default=6, min=3, max=16, update=dirty)
    thickness_random: FloatProperty(name='Width Variation', default=.65, min=0, max=1, update=dirty)
    taper: FloatProperty(name='End Taper', default=.12, min=0, max=.5, update=dirty)
    trim: FloatProperty(name='Random End Trim', default=.22, min=0, max=.45, update=dirty)
    noise: FloatProperty(name='Waviness', default=.035, min=0, subtype='DISTANCE', update=dirty)
    frequency: FloatProperty(name='Wave Frequency', default=1.5, min=0, max=30, update=dirty)
    twist: FloatProperty(name='Ribbon Twist', default=0, subtype='ANGLE', update=dirty)
    up: EnumProperty(name='Orientation Axis', items=[('Z','Z',''),('Y','Y',''),('X','X','')], default='Z', update=dirty)
    exclusions: PointerProperty(name='Exclusion Collection', type=bpy.types.Collection, update=dirty)
    exclusion_mode: EnumProperty(name='Exclusion', items=[('REMOVE','Remove Strand','Discard intersecting strands'),('CUT','Cut Inside','Omit intersecting segments'),('FADE','Soft Fade','Collapse width and brightness inside; fade outside')], default='CUT', update=dirty)
    clearance: FloatProperty(name='Clearance', default=.02, min=0, subtype='DISTANCE', update=dirty)
    fade: FloatProperty(name='Fade Distance', default=.2, min=.0001, subtype='DISTANCE', update=dirty)
    status: StringProperty(default='Ready')
    material: PointerProperty(type=bpy.types.Material)

def resample(poly, count):
    distances = [0.0]
    for a,b in zip(poly, poly[1:]):
        distances.append(distances[-1] + (b-a).length)
    if distances[-1] < 1e-8:
        raise ValueError('A guide has zero length')
    result=[]
    for j in range(count):
        target=distances[-1]*j/(count-1)
        i=min(max(bisect.bisect_right(distances,target)-1,0),len(poly)-2)
        length=distances[i+1]-distances[i]
        result.append(poly[i].lerp(poly[i+1], (target-distances[i])/length if length else 0))
    return result

def read_guides(system):
    groups={}
    inv=system.matrix_world.inverted_safe()
    for entry in system.sf.guides:
        obj=entry.obj
        if not entry.enabled or not obj: continue
        if obj.mode == 'EDIT': obj.update_from_editmode()
        matrix=inv @ obj.matrix_world
        for spline in obj.data.splines:
            if spline.use_cyclic_u:
                raise ValueError('V1 needs open guides; disable Cyclic on '+obj.name)
            poly=[]
            if spline.type == 'BEZIER':
                pts=spline.bezier_points
                if len(pts)<2: continue
                for a,b in zip(pts,pts[1:]):
                    for k in range(24):
                        t=k/24; s=1-t
                        poly.append(matrix @ (s**3*a.co+3*s*s*t*a.handle_right+3*s*t*t*b.handle_left+t**3*b.co))
                poly.append(matrix @ pts[-1].co)
            elif spline.type == 'POLY':
                poly=[matrix @ Vector(p.co[:3]) for p in spline.points]
            else:
                raise ValueError('Use Bezier or Poly guides; NURBS is not supported in V1')
            if len(poly)<2: continue
            if entry.reverse: poly.reverse()
            groups.setdefault(entry.group,[]).append(resample(poly,system.sf.points))
    if not groups: raise ValueError('Add at least one enabled Bezier or Poly guide')
    return groups

def sample(path,t):
    q=max(0,min(1,t))*(len(path)-1)
    i=min(int(q),len(path)-2)
    return path[i].lerp(path[i+1],q-i)

def frames(path, axis):
    up=Vector({'Z':(0,0,1),'Y':(0,1,0),'X':(1,0,0)}[axis])
    result=[]; previous=None
    for i,p in enumerate(path):
        t=path[min(i+1,len(path)-1)]-path[max(i-1,0)]
        if t.length<1e-9: t=Vector((1,0,0))
        t.normalize()
        n=(previous if previous is not None else up)
        n=n-t*n.dot(t)
        if n.length<1e-6:
            alt=Vector((0,1,0)) if abs(t.y)<.9 else Vector((1,0,0))
            n=alt-t*alt.dot(t)
        n.normalize(); previous=n
        result.append((n,t.cross(n).normalized()))
    return result

def obstacle_trees(system, depsgraph):
    collection=system.sf.exclusions
    if not collection: return []
    result=[]; inv=system.matrix_world.inverted_safe()
    for obj in collection.all_objects:
        if obj.type!='MESH' or obj==system: continue
        evaluated=obj.evaluated_get(depsgraph)
        mesh=evaluated.to_mesh()
        try:
            if not mesh.polygons: continue
            matrix=inv @ obj.matrix_world
            tree=BVHTree.FromPolygons([matrix@v.co for v in mesh.vertices], [list(p.vertices) for p in mesh.polygons])
            result.append(tree)
        finally: evaluated.to_mesh_clear()
    return result

def inside(tree,p):
    # Ray parity, independent of face winding. Closed manifold meshes required.
    direction=Vector((.923,.317,.217)).normalized(); origin=p.copy(); hits=0
    for _ in range(256):
        hit,normal,index,distance=tree.ray_cast(origin,direction)
        if hit is None: break
        hits+=1; origin=hit+direction*1e-5
    return hits%2==1

def exclusion_weights(path,trees,s,radius):
    weights=[1.0]*len(path); blocked=[False]*(len(path)-1)
    for tree in trees:
        for i,p in enumerate(path):
            hit,normal,index,distance=tree.find_nearest(p)
            d=distance if hit is not None else 1e10
            excluded=inside(tree,p) or d<=s.clearance+radius
            weight=0 if excluded else min(1,max(0,(d-s.clearance-radius)/s.fade))
            weights[i]=min(weights[i], weight if s.exclusion_mode=='FADE' else (0 if excluded else 1))
        for i,(a,b) in enumerate(zip(path,path[1:])):
            delta=b-a
            if delta.length>1e-9:
                hit,*_=tree.ray_cast(a,delta.normalized(),delta.length)
                if hit is not None: blocked[i]=True
    return weights,blocked

def make_material(system):
    mat=system.sf.material
    if mat:
        ensure_particles(mat, bpy.context.scene)
        return mat
    mat=bpy.data.materials.new(system.name+' / Flow Gradient'); mat.use_nodes=True
    n=mat.node_tree.nodes; l=mat.node_tree.links; n.clear()
    def node(kind,name,x,y):
        o=n.new(kind); o.name=name; o.label=name; o.location=(x,y); return o
    def attr(name,x,y):
        o=node('ShaderNodeAttribute',name,x,y); o.attribute_name=name; return o.outputs['Fac']
    def value(name,v,x,y):
        o=node('ShaderNodeValue',name,x,y); o.outputs[0].default_value=v; return o.outputs[0]
    def mathnode(op,name,a,b,x,y):
        o=node('ShaderNodeMath',name,x,y); o.operation=op
        for i,v in enumerate((a,b)):
            if isinstance(v,(int,float)): o.inputs[i].default_value=v
            else: l.new(v,o.inputs[i])
        return o.outputs[0]
    u=attr('sf_u',-1000,280); rnd=attr('sf_random',-1000,80)
    scale=value('Gradient Scale',.65,-1000,500)
    scale_random=value('Random Scale',.5,-1250,700)
    offset=value('Random Offset',.8,-1000,-100)
    travel=value('Travel',0,-750,600)
    varied=mathnode('MULTIPLY_ADD','Strand Scale Variation',rnd,scale_random,-1000,760)
    n['Strand Scale Variation'].inputs[2].default_value=1
    varied=mathnode('MULTIPLY','Final Gradient Scale',scale,varied,-740,800)
    x=mathnode('MULTIPLY','Along Strand',u,varied,-740,320)
    r=mathnode('MULTIPLY','Per Strand Offset',rnd,offset,-740,100)
    x=mathnode('ADD','Combine',x,r,-520,300)
    x=mathnode('ADD','Travel Offset',x,travel,-320,300)
    x=mathnode('PINGPONG','Gradient Repeat',x,1,-120,300)
    ramp=node('ShaderNodeValToRGB','Flow Palette',80,300); l.new(x,ramp.inputs[0])
    colors=[(0,(.012,.002,.05,1)),(.35,(.09,.008,.36,1)),(.7,(.025,.006,.12,1)),(.86,(.025,.35,.13,1)),(1,(.35,.55,.65,1))]
    cr=ramp.color_ramp
    cr.elements.remove(cr.elements[1]); cr.elements[0].color=colors[0][1]
    for pos,col in colors[1:]: cr.elements.new(pos).color=col
    brightness=attr('sf_brightness',-300,-200)
    strength=value('Emission Strength',2,-300,-400)
    bright=mathnode('MULTIPLY','Strand Brightness',brightness,strength,0,-160)
    # Noise uses curve coordinates so patches travel with the strand, not through world space.
    xyz=node('ShaderNodeCombineXYZ','Strand Coordinates',-500,-600)
    l.new(u,xyz.inputs['X']); l.new(rnd,xyz.inputs['Y'])
    noise=node('ShaderNodeTexNoise','Light Patches',-250,-650); l.new(xyz.outputs[0],noise.inputs['Vector']); noise.inputs['Scale'].default_value=9
    patches=mathnode('MULTIPLY_ADD','Patch Contrast',noise.outputs['Fac'],.85,0,-400)
    n['Patch Contrast'].inputs[2].default_value=.15
    bright=mathnode('MULTIPLY','Patch Brightness',bright,patches,240,-140)
    emission=node('ShaderNodeEmission','Emission',480,220)
    l.new(ramp.outputs['Color'],emission.inputs['Color']); l.new(bright,emission.inputs['Strength'])
    out=node('ShaderNodeOutputMaterial','Output',710,220); l.new(emission.outputs[0],out.inputs['Surface'])
    system.sf.material=mat
    ensure_particles(mat, bpy.context.scene)
    return mat

def generate(system, full=False):
    global _BUSY
    if _BUSY: return
    _BUSY=True
    started=time.monotonic()
    try:
        s=system.sf; groups=read_guides(system)
        # Fixed slot allocation and independent seeds preserve existing strands when count grows.
        slots=[]
        for paths in groups.values():
            if s.mode=='AROUND': slots.extend((p,p) for p in paths)
            else:
                if len(paths)<2: raise ValueError('Each fill group needs at least two guides')
                slots.extend(zip(paths,paths[1:]))
        count=s.count if full else max(1,math.ceil(s.count*s.preview/100))
        ring=s.sides if s.shape=='TUBE' else 2
        if count*s.points*ring>2200000: raise ValueError('Over 2.2 million vertices: lower count, points or sides')
        trees=obstacle_trees(system,bpy.context.evaluated_depsgraph_get())
        vertices=[]; faces=[]; us=[]; randoms=[]; brights=[]; ids=[]; distances=[]; lengths=[]
        surviving=0
        for sid in range(count):
            rng=random.Random((s.seed<<32)+sid)
            a,b=slots[sid%len(slots)]
            f=rng.random()
            if s.mode=='HYBRID': f=.5*(2*f)**s.concentration if f<.5 else 1-.5*(2*(1-f))**s.concentration
            base=[pa.lerp(pb,f) for pa,pb in zip(a,b)]
            basis=frames(base,s.up)
            theta=rng.random()*math.tau
            radial=rng.random()**(s.concentration/2 if s.mode=='AROUND' else .5)
            lateral=math.cos(theta)*radial*s.spread if s.mode=='AROUND' else 0
            depth=math.sin(theta)*radial*(s.spread if s.mode=='AROUND' else s.depth)
            phase=rng.random()*math.tau
            path=[]
            for i,(p,(n,v)) in enumerate(zip(base,basis)):
                t=i/(s.points-1); envelope=math.sin(math.pi*t)
                wave=s.noise*envelope
                path.append(p+n*(depth+wave*math.sin(t*math.tau*s.frequency+phase))+v*(lateral+wave*.5*math.cos(t*math.tau*s.frequency*.73+phase)))
            start=rng.random()*s.trim; end=1-rng.random()*s.trim
            coords=[start+(end-start)*i/(s.points-1) for i in range(s.points)]
            path=[sample(path,t) for t in coords]
            basis=frames(path,s.up)
            arc=[0.0]
            world_matrix=system.matrix_world.to_3x3()
            for pa,pb in zip(path,path[1:]):
                arc.append(arc[-1]+(world_matrix @ (pb-pa)).length)
            radius=s.radius*(1-s.thickness_random*rng.random())
            strand_random=rng.random(); bright=.08+.92*rng.random()**2
            weights,blocked=exclusion_weights(path,trees,s,radius) if trees else ([1.0]*len(path),[False]*(len(path)-1))
            if s.exclusion_mode=='REMOVE' and (min(weights)==0 or any(blocked)): continue
            start_index=len(vertices)
            face_start=len(faces)
            for i,(p,(n,v)) in enumerate(zip(path,basis)):
                local=i/(len(path)-1)
                fade=min(1,local/max(s.taper,1e-6),(1-local)/max(s.taper,1e-6)) if s.taper else 1
                fade=fade*fade*(3-2*fade)
                width=radius*max(.001,fade)* (weights[i] if s.exclusion_mode=='FADE' else 1)
                for k in range(ring):
                    angle=(math.tau*k/ring if s.shape=='TUBE' else math.pi*k)+s.twist*local
                    vertices.append(p+width*(n*math.cos(angle)+v*math.sin(angle)))
                    us.append(coords[i]); randoms.append(strand_random); brights.append(bright*fade*weights[i]); ids.append(sid)
                    distances.append(arc[i]); lengths.append(arc[-1])
                if i:
                    cut=s.exclusion_mode in {'CUT','FADE'} and (weights[i]==0 or weights[i-1]==0 or blocked[i-1])
                    if not cut:
                        prev=start_index+(i-1)*ring; cur=prev+ring
                        for k in range(ring if s.shape=='TUBE' else 1):
                            nxt=(k+1)%ring
                            faces.append((prev+k,prev+nxt,cur+nxt,cur+k))
            if len(faces)>face_start:
                surviving+=1
            else:
                for values in (vertices,us,randoms,brights,ids,distances,lengths): del values[start_index:]
        mesh=bpy.data.meshes.new(system.name+' Geometry')
        try:
            mesh.from_pydata(vertices,[],faces); mesh.update()
            for name,values,kind in [('sf_u',us,'FLOAT'),('sf_random',randoms,'FLOAT'),('sf_brightness',brights,'FLOAT'),('sf_id',ids,'INT'),('sf_distance',distances,'FLOAT'),('sf_length',lengths,'FLOAT')]:
                attribute=mesh.attributes.new(name,kind,'POINT'); attribute.data.foreach_set('value',values)
            mesh.polygons.foreach_set('use_smooth',[True]*len(mesh.polygons))
            mesh.materials.append(make_material(system))
            old=system.data; system.data=mesh
            if old.users==0: bpy.data.meshes.remove(old)
        except Exception:
            if mesh.users==0: bpy.data.meshes.remove(mesh)
            raise
        s.status=f'{"FULL" if full else "PREVIEW"}: {surviving:,} strands, {len(vertices):,} verts ({time.monotonic()-started:.1f}s)'
    finally: _BUSY=False

class SF_OT_create(bpy.types.Operator):
    bl_idname='sf.create'; bl_label='Create from Selected Guides'; bl_options={'REGISTER','UNDO'}
    def execute(self,context):
        if context.mode!='OBJECT':
            self.report({'ERROR'},'Switch to Object Mode to create a system'); return {'CANCELLED'}
        selected=sorted([o for o in context.selected_objects if o.type=='CURVE'],key=lambda o:o.name)
        if not selected:
            self.report({'ERROR'},'Select Bezier or Poly curve objects first'); return {'CANCELLED'}
        obj=bpy.data.objects.new('Strand Flow',bpy.data.meshes.new('Strand Flow Geometry'))
        context.collection.objects.link(obj); obj.sf.is_system=True
        context.scene.sf_system=obj
        for guide in selected: obj.sf.guides.add().obj=guide
        if sum(len(o.data.splines) for o in selected)<2: obj.sf.mode='AROUND'
        for o in context.selected_objects: o.select_set(False)
        obj.select_set(True); context.view_layer.objects.active=obj
        try: generate(obj)
        except Exception as e: obj.sf.status=str(e); self.report({'WARNING'},str(e))
        return {'FINISHED'}

class SF_OT_update(bpy.types.Operator):
    bl_idname='sf.update'; bl_label='Update Strands'; bl_options={'REGISTER','UNDO'}
    full: BoolProperty(default=False)
    def execute(self,context):
        obj=current_system(context)
        if not obj: return {'CANCELLED'}
        _PENDING.pop(obj.name,None)
        if self.full:
            obj.sf.live=False
        try: generate(obj,self.full)
        except Exception as e:
            obj.sf.status=str(e); self.report({'ERROR'},str(e)); return {'CANCELLED'}
        return {'FINISHED'}

class SF_OT_guide(bpy.types.Operator):
    bl_idname='sf.guide'; bl_label='Edit Guide List'; bl_options={'REGISTER','UNDO'}
    action: EnumProperty(items=[(v,v,'') for v in ['ADD','REMOVE','UP','DOWN','SELECT']])
    def execute(self,context):
        obj=current_system(context)
        if not obj: return {'CANCELLED'}
        s=obj.sf; i=s.active_guide
        if self.action=='ADD': s.guides.add()
        elif 0<=i<len(s.guides):
            if self.action=='REMOVE': s.guides.remove(i); s.active_guide=max(0,i-1)
            elif self.action=='SELECT':
                guide=s.guides[i].obj
                if guide:
                    for o in context.selected_objects: o.select_set(False)
                    guide.select_set(True); context.view_layer.objects.active=guide
            else:
                j=max(0,min(len(s.guides)-1,i+(-1 if self.action=='UP' else 1)))
                s.guides.move(i,j); s.active_guide=j
        dirty(s,context); return {'FINISHED'}

class SF_OT_demo(bpy.types.Operator):
    bl_idname='sf.demo'; bl_label='Create Reference Demo'; bl_options={'REGISTER','UNDO'}
    def execute(self,context):
        if context.mode!='OBJECT':
            self.report({'ERROR'},'Switch to Object Mode'); return {'CANCELLED'}
        for obj in context.selected_objects: obj.select_set(False)
        for i,height in enumerate([-2,-.75,.65,2.2]):
            data=bpy.data.curves.new(f'Flow Guide {i+1:02}','CURVE'); data.dimensions='3D'
            spline=data.splines.new('BEZIER'); spline.bezier_points.add(3)
            for p,co in zip(spline.bezier_points,[(-6,0,height*.15),(-2,.3*i,height),(2,-.2*i,height*.75),(6,0,0)]):
                p.co=co; p.handle_left_type='AUTO'; p.handle_right_type='AUTO'
            obj=bpy.data.objects.new(data.name,data); context.collection.objects.link(obj); obj.select_set(True)
        bpy.ops.sf.create()
        system=context.view_layer.objects.active
        system.sf.up='Y'
        generate(system)
        return {'FINISHED'}

def current_system(context):
    obj=context.object
    if obj and obj.sf.is_system: return obj
    chosen=context.scene.sf_system
    return chosen if chosen and chosen.sf.is_system else None

def system_poll(self,obj): return obj.type=='MESH' and obj.sf.is_system

class SF_UL_guides(bpy.types.UIList):
    def draw_item(self,context,layout,data,item,icon,active_data,active_propname,index):
        row=layout.row(align=True); row.prop(item,'enabled',text=''); row.prop(item,'obj',text=''); row.prop(item,'reverse',text='',icon='ARROW_LEFTRIGHT')

class SF_PT_main(bpy.types.Panel):
    bl_label='Strand Flow'; bl_idname='SF_PT_main'; bl_space_type='VIEW_3D'; bl_region_type='UI'; bl_category='Strand Flow'
    def draw(self,context):
        layout=self.layout
        layout.operator('sf.create',icon='CURVE_DATA'); layout.operator('sf.demo',icon='ADD')
        layout.prop(context.scene,'sf_system',text='Pinned System')
        obj=current_system(context)
        if not obj: return
        s=obj.sf
        layout.label(text=obj.name,icon='OUTLINER_OB_CURVES')
        row=layout.row(align=True); row.operator('sf.update',text='Update Preview'); row.operator('sf.update',text='Build Full').full=True
        layout.prop(s,'live'); layout.label(text=s.status)
        layout.label(text='Build Full before rendering',icon='INFO')

class SFPanel:
    bl_space_type='VIEW_3D'; bl_region_type='UI'; bl_category='Strand Flow'; bl_parent_id='SF_PT_main'; bl_options={'DEFAULT_CLOSED'}
    @classmethod
    def poll(cls,context): return current_system(context) is not None

class SF_PT_guides(SFPanel,bpy.types.Panel):
    bl_label='Guides'; bl_idname='SF_PT_guides'
    def draw(self,context):
        l=self.layout; s=current_system(context).sf
        l.template_list('SF_UL_guides','',s,'guides',s,'active_guide',rows=4)
        row=l.row(align=True)
        for action,icon in [('ADD','ADD'),('REMOVE','REMOVE'),('UP','TRIA_UP'),('DOWN','TRIA_DOWN'),('SELECT','RESTRICT_SELECT_OFF')]:
            row.operator('sf.guide',text='',icon=icon).action=action
        if 0<=s.active_guide<len(s.guides):
            entry=s.guides[s.active_guide]; l.prop(entry,'group'); l.prop(entry,'reverse')
        l.label(text='Order defines neighbours within each group.')

class SF_PT_distribution(SFPanel,bpy.types.Panel):
    bl_label='Distribution'; bl_idname='SF_PT_distribution'
    def draw(self,context):
        l=self.layout; s=current_system(context).sf
        for key in ['mode','count','preview','points','seed']: l.prop(s,key)
        if s.mode=='AROUND': l.prop(s,'spread')
        else: l.prop(s,'depth')
        if s.mode!='BETWEEN': l.prop(s,'concentration')

class SF_PT_shape(SFPanel,bpy.types.Panel):
    bl_label='Shape'; bl_idname='SF_PT_shape'
    def draw(self,context):
        l=self.layout; s=current_system(context).sf
        for key in ['shape','radius','thickness_random','taper','trim','noise','frequency','up']: l.prop(s,key)
        if s.shape=='TUBE': l.prop(s,'sides')
        else: l.prop(s,'twist')

class SF_PT_exclusions(SFPanel,bpy.types.Panel):
    bl_label='Exclusion Zones'; bl_idname='SF_PT_exclusions'
    def draw(self,context):
        l=self.layout; s=current_system(context).sf
        for key in ['exclusions','exclusion_mode','clearance']: l.prop(s,key)
        if s.exclusion_mode=='FADE': l.prop(s,'fade')
        l.label(text='Use closed meshes. Higher points = finer cuts.')

class SF_PT_material(SFPanel,bpy.types.Panel):
    bl_label='Gradient Material'; bl_idname='SF_PT_material'
    def draw(self,context):
        l=self.layout; mat=current_system(context).sf.material
        if not mat or not mat.use_nodes: return
        nodes=mat.node_tree.nodes
        ramp=nodes.get('Flow Palette')
        if ramp: l.template_color_ramp(ramp,'color_ramp',expand=True)
        for name in ['Gradient Scale','Random Scale','Random Offset','Travel','Emission Strength']:
            node=nodes.get(name)
            if node: l.prop(node.outputs[0],'default_value',text=name)
        noise=nodes.get('Light Patches')
        if noise: l.prop(noise.inputs['Scale'],'default_value',text='Patch Scale')
        l.label(text='Shader controls update instantly. Travel is keyframeable.')


class SF_OT_particle_mode(bpy.types.Operator):
    bl_idname='sf.particle_mode'; bl_label='Set Strand Appearance'; bl_options={'REGISTER','UNDO'}
    mode: EnumProperty(items=[('CONTINUOUS','Continuous',''),('PARTICLES','Trail Particles','')])
    def execute(self,context):
        obj=current_system(context)
        if not obj: return {'CANCELLED'}
        try:
            if not obj.data.attributes.get('sf_distance'):
                obj.sf.live=False
                generate(obj,True)
            mat=make_material(obj)
            node=ensure_particles(mat,context.scene)
            if not node:
                raise ValueError('The material needs an active Surface output connection')
            node.inputs['Enabled'].default_value=1 if self.mode=='PARTICLES' else 0
        except Exception as e:
            self.report({'ERROR'},str(e)); return {'CANCELLED'}
        return {'FINISHED'}

class SF_OT_particle_option(bpy.types.Operator):
    bl_idname='sf.particle_option'; bl_label='Set Trail Option'; bl_options={'REGISTER','UNDO'}
    option: EnumProperty(items=[(x,x,'') for x in ['WORLD','RELATIVE','FORWARD','REVERSE']])
    def execute(self,context):
        obj=current_system(context)
        if not obj or not obj.sf.material: return {'CANCELLED'}
        node=obj.sf.material.node_tree.nodes.get(NODE_NAME)
        if not node: return {'CANCELLED'}
        key='World Units' if self.option in {'WORLD','RELATIVE'} else 'Reverse'
        node.inputs[key].default_value=1 if self.option in {'WORLD','REVERSE'} else 0
        return {'FINISHED'}

class SF_OT_single_trail(bpy.types.Operator):
    bl_idname='sf.single_trail'; bl_label='Single Strand Preset'; bl_options={'REGISTER','UNDO'}
    def execute(self,context):
        obj=current_system(context)
        if not obj: return {'CANCELLED'}
        s=obj.sf
        s.live=False; s.mode='AROUND'; s.count=1; s.preview=100
        s.spread=0; s.depth=0; s.noise=0; s.trim=0
        try:
            generate(obj,True)
            node=ensure_particles(s.material,context.scene)
            if node: node.inputs['Enabled'].default_value=1
        except Exception as e:
            self.report({'ERROR'},str(e)); return {'CANCELLED'}
        return {'FINISHED'}

class SF_PT_particles(SFPanel,bpy.types.Panel):
    bl_label='Trail Particles'; bl_idname='SF_PT_particles'
    bl_options=set()
    def draw(self,context):
        l=self.layout; obj=current_system(context); mat=obj.sf.material
        node=mat.node_tree.nodes.get(NODE_NAME) if mat and mat.use_nodes else None
        enabled=node and node.inputs['Enabled'].default_value>.5
        row=l.row(align=True)
        row.operator('sf.particle_mode',text='Continuous',depress=not enabled).mode='CONTINUOUS'
        row.operator('sf.particle_mode',text='Trail Particles',depress=bool(enabled)).mode='PARTICLES'
        if not node or not obj.data.attributes.get('sf_distance'):
            l.label(text='Choose a mode to upgrade this V1 system.')
            return
        l.operator('sf.single_trail',icon='CURVE_DATA')
        if not enabled: return
        world=node.inputs['World Units'].default_value>.5
        row=l.row(align=True)
        row.operator('sf.particle_option',text='World Units',depress=world).option='WORLD'
        row.operator('sf.particle_option',text='Per Curve',depress=not world).option='RELATIVE'
        reverse=node.inputs['Reverse'].default_value>.5
        row=l.row(align=True)
        row.operator('sf.particle_option',text='Forward',depress=not reverse).option='FORWARD'
        row.operator('sf.particle_option',text='Reverse',depress=reverse).option='REVERSE'
        keys=['Length','Spacing','Speed'] if world else ['Amount','Relative Length','Relative Speed']
        for name in keys+['Length Variation','Speed Variation','Head Fade','Tail Falloff','Seed']:
            label={'Reverse':'Reverse (0 or 1)','Relative Length':'Length (curve fraction)','Relative Speed':'Speed (curves / sec)','Speed':'Speed (units / sec)'}.get(name,name)
            l.prop(node.inputs[name],'default_value',text=label)
        l.label(text='Press Play in Material Preview or Rendered view.')
        l.label(text='Lengths stay below spacing to preserve gaps.')

@persistent
def changed(scene,depsgraph):
    if _BUSY: return
    ids={u.id.original for u in depsgraph.updates}
    for obj in scene.objects:
        if not obj.sf.is_system or not obj.sf.live: continue
        watched=[g.obj for g in obj.sf.guides if g.obj]
        if obj.sf.exclusions: watched.extend(obj.sf.exclusions.all_objects)
        if any(o in ids or o.data in ids for o in watched): _PENDING[obj.name]=time.monotonic()

def tick():
    if not hasattr(bpy.types.Object,'sf'): return None
    now=time.monotonic()
    for name,stamp in list(_PENDING.items()):
        if now-stamp<.35: continue
        _PENDING.pop(name,None); obj=bpy.data.objects.get(name)
        if not obj or not obj.sf.live: continue
        if obj.mode!='OBJECT': continue
        try: generate(obj)
        except Exception as e: obj.sf.status=str(e)
    return .3

classes=(SFGuide,SFSettings,SF_OT_create,SF_OT_update,SF_OT_guide,SF_OT_demo,SF_UL_guides,SF_PT_main,SF_PT_guides,SF_PT_distribution,SF_PT_shape,SF_PT_exclusions,SF_PT_material,SF_OT_particle_mode,SF_OT_single_trail,SF_OT_particle_option,SF_PT_particles)
def register():
    for cls in classes: bpy.utils.register_class(cls)
    bpy.types.Object.sf=PointerProperty(type=SFSettings)
    bpy.types.Scene.sf_system=PointerProperty(type=bpy.types.Object,poll=system_poll)
    bpy.app.handlers.depsgraph_update_post.append(changed)
    bpy.app.timers.register(tick,persistent=True)

def unregister():
    if changed in bpy.app.handlers.depsgraph_update_post: bpy.app.handlers.depsgraph_update_post.remove(changed)
    if bpy.app.timers.is_registered(tick): bpy.app.timers.unregister(tick)
    _PENDING.clear()
    del bpy.types.Scene.sf_system; del bpy.types.Object.sf
    for cls in reversed(classes): bpy.utils.unregister_class(cls)

if __name__=='__main__': register()
