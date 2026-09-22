"""Shader-only moving trails. Mesh attributes supply physical arc length."""
import bpy

NODE_NAME = 'SF Trail Particles'
CONTROLS = [
    ('Enabled', 0, 0, 1), ('World Units', 1, 0, 1),
    ('Length', .6, .0001, 1000), ('Spacing', 2.0, .001, 10000),
    ('Speed', 1.5, 0, 1000), ('Amount', 5, 1, 1000),
    ('Relative Length', .06, .0001, 1), ('Relative Speed', .15, 0, 100),
    ('Length Variation', .55, 0, .99), ('Speed Variation', .2, 0, .99),
    ('Reverse', 0, 0, 1), ('Head Fade', .05, .001, .95),
    ('Tail Falloff', 1.6, .05, 10), ('Seed', 0, 0, 10000),
    ('Time', 0, -1000000, 1000000),
]

def create_group(name):
    tree = bpy.data.node_groups.new(name, 'ShaderNodeTree')
    interface = tree.interface
    interface.new_socket(name='Surface', in_out='INPUT', socket_type='NodeSocketShader')
    for name, default, minimum, maximum in CONTROLS:
        socket = interface.new_socket(name=name, in_out='INPUT', socket_type='NodeSocketFloat')
        socket.default_value = default
        socket.min_value = minimum
        socket.max_value = maximum
    interface.new_socket(name='Surface', in_out='OUTPUT', socket_type='NodeSocketShader')
    interface.new_socket(name='Mask', in_out='OUTPUT', socket_type='NodeSocketFloat')
    nodes, links = tree.nodes, tree.links
    def node(kind, name):
        result = nodes.new(kind); result.name = result.label = name
        index = len(nodes)-1
        result.location = ((index//7)*230, -(index%7)*160)
        return result
    inputs = node('NodeGroupInput', 'Controls').outputs
    output = node('NodeGroupOutput', 'Output')
    def wire(value, socket):
        if isinstance(value, (float, int)): socket.default_value = value
        else: links.new(value, socket)
    def calc(op, name, a, b=0):
        result = node('ShaderNodeMath', name); result.operation = op
        wire(a,result.inputs[0]); wire(b,result.inputs[1]); return result.outputs[0]
    def attr(name):
        result = node('ShaderNodeAttribute', name); result.attribute_name = name
        return result.outputs['Fac']
    def blend(name, a, b, factor):
        return calc('ADD', name, a, calc('MULTIPLY', name+' Weight', calc('SUBTRACT',name+' Difference',b,a),factor))
    def clamp(name, a): return calc('MINIMUM',name,calc('MAXIMUM',name+' Lower',a,0),1)
    distance = attr('sf_distance')
    length = calc('MAXIMUM','Safe Strand Length',attr('sf_length'),.000001)
    relative = calc('DIVIDE','Relative Distance',distance,length)
    world = inputs['World Units']
    coordinate = blend('Coordinate Units',relative,distance,world)
    amount = calc('MAXIMUM','Whole Amount',calc('ROUND','Round Amount',inputs['Amount']),1)
    spacing = blend('Spacing Units',calc('DIVIDE','Relative Spacing',1,amount),inputs['Spacing'],world)
    spacing = calc('MAXIMUM','Safe Spacing',spacing,.000001)
    trail_length = blend('Length Units',inputs['Relative Length'],inputs['Length'],world)
    speed = blend('Speed Units',inputs['Relative Speed'],inputs['Speed'],world)
    strand = attr('sf_random')
    seed = calc('ADD','Strand Seed',calc('MULTIPLY','Spread Seeds',strand,1000),inputs['Seed'])
    random_speed = calc('FRACT','Speed Random',calc('MULTIPLY','Hash Speed',seed,7.317))
    speed = calc('MULTIPLY','Varied Speed',speed,calc('SUBTRACT','Speed Factor',1,calc('MULTIPLY','Speed Variation',random_speed,inputs['Speed Variation'])))
    direction = calc('SUBTRACT','Direction',1,calc('MULTIPLY','Reverse',inputs['Reverse'],2))
    coordinate = calc('MULTIPLY','Directed Distance',coordinate,direction)
    motion = calc('SUBTRACT','Moving Distance',coordinate,calc('MULTIPLY','Distance Travelled',inputs['Time'],speed))
    phase_coord = calc('ADD','Phase Coordinate',calc('DIVIDE','Spaced Coordinate',motion,spacing),seed)
    cell = calc('FLOOR','Particle ID',phase_coord)
    phase = calc('FRACT','Particle Phase',phase_coord)
    xyz = node('ShaderNodeCombineXYZ','Particle Seed')
    wire(cell,xyz.inputs['X']); wire(seed,xyz.inputs['Y'])
    random_node = node('ShaderNodeTexWhiteNoise','Particle Random'); random_node.noise_dimensions = '3D'
    wire(xyz.outputs[0],random_node.inputs['Vector'])
    length_factor = calc('SUBTRACT','Length Factor',1,calc('MULTIPLY','Length Variation',random_node.outputs['Value'],inputs['Length Variation']))
    trail_length = calc('MULTIPLY','Varied Trail Length',trail_length,length_factor)
    trail_length = calc('MINIMUM','Keep Gaps',trail_length,calc('MULTIPLY','Maximum Trail Length',spacing,.95))
    trail_length = calc('MAXIMUM','Safe Trail Length',trail_length,.000001)
    behind = calc('MULTIPLY','Behind Head',calc('SUBTRACT','Head Phase',1,phase),spacing)
    tail = clamp('Tail Ramp',calc('SUBTRACT','Tail Position',1,calc('DIVIDE','Trail Position',behind,trail_length)))
    tail = calc('POWER','Tail Falloff',tail,inputs['Tail Falloff'])
    head = clamp('Head Ramp',calc('DIVIDE','Head Position',behind,calc('MAXIMUM','Safe Head Fade',calc('MULTIPLY','Head Fade Length',trail_length,inputs['Head Fade']),.000001)))
    mask = calc('MULTIPLY','Trail Mask',tail,head)
    enabled_mask = blend('Continuous or Particles',1,mask,inputs['Enabled'])
    transparent = node('ShaderNodeBsdfTransparent','Transparent Gaps')
    mix = node('ShaderNodeMixShader','Visible Trail')
    wire(enabled_mask,mix.inputs[0]); wire(transparent.outputs[0],mix.inputs[1]); wire(inputs['Surface'],mix.inputs[2])
    wire(mix.outputs[0],output.inputs['Surface']); wire(mask,output.inputs['Mask'])
    output.location = (mix.location.x+250,0)
    return tree

def ensure_particles(material, scene):
    if not material.use_nodes: return None
    nodes, links = material.node_tree.nodes, material.node_tree.links
    existing = nodes.get(NODE_NAME)
    if existing: return existing
    outputs = [n for n in nodes if n.type=='OUTPUT_MATERIAL' and n.is_active_output]
    if not outputs: return None
    output = outputs[0]
    if not output.inputs['Surface'].is_linked: return None
    source = output.inputs['Surface'].links[0].from_socket
    group = nodes.new('ShaderNodeGroup'); group.name = group.label = NODE_NAME
    group.node_tree = create_group(material.name+' / Trail Particles')
    group.location = (output.location.x, output.location.y)
    output.location.x += 280
    links.new(source,group.inputs['Surface'])
    links.new(group.outputs['Surface'],output.inputs['Surface'])
    # Simple expression driver updates on timeline changes and during final rendering.
    driver = group.inputs['Time'].driver_add('default_value').driver
    for name,path in [('fps','render.fps'),('base','render.fps_base')]:
        var = driver.variables.new(); var.name = name; var.type = 'SINGLE_PROP'
        target = var.targets[0]; target.id_type = 'SCENE'; target.id = scene; target.data_path = path
    driver.expression = '(frame - 1) * base / fps'
    if hasattr(material,'surface_render_method'): material.surface_render_method = 'DITHERED'
    return group
