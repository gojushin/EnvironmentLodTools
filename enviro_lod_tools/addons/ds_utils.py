import bpy


def launch_operator_by_name(op_str):
    try:
        category, operator_name = op_str.split(".")
        f = getattr(getattr(bpy.ops, category), operator_name)
        f()
    except AttributeError:
        print(f"Error: Operator {op_str} does not exist.")
    except RuntimeError as e:
        print(f"Runtime Error: {e}")


def vertex_group_from_outer_boundary(obj):
    """
    Creates a vertex group from the outer boundary to ensure it is preserved during decimation.
    This function selects only the outer boundary, excluding any holes or inner boundaries.
    :param obj: The object to process.
    :type obj: bpy.types.Object
    :returns: Name of the vertex group.
    :rtype: str
    """
    import bmesh

    # Ensure the object is active
    bpy.context.view_layer.objects.active = obj

    # Switch to EDIT mode and create a BMesh representation
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(obj.data)
    bm.edges.ensure_lookup_table()

    # Deselect all edges
    for edge in bm.edges:
        edge.select = False

    # Select boundary edges (edges with only one linked face)
    boundary_edges = [edge for edge in bm.edges if len(edge.link_faces) == 1]
    for edge in boundary_edges:
        edge.select = True

    # Build edge loops from the boundary edges
    unvisited_edges = set(boundary_edges)
    edge_loops = []

    while unvisited_edges:
        current_loop = set()
        edges_to_visit = {unvisited_edges.pop()}

        while edges_to_visit:
            edge = edges_to_visit.pop()
            current_loop.add(edge)
            for vert in edge.verts:
                connected_edges = set(e for e in vert.link_edges if e in unvisited_edges)
                edges_to_visit.update(connected_edges)
                unvisited_edges.difference_update(connected_edges)

        edge_loops.append(current_loop)

    # Calculate the perimeter of each edge loop
    loop_perimeters = []
    for loop in edge_loops:
        perimeter = sum(edge.calc_length() for edge in loop)
        loop_perimeters.append(perimeter)

    # Identify the edge loop with the largest perimeter (outer boundary)
    max_perimeter_index = loop_perimeters.index(max(loop_perimeters))
    outer_loop_edges = edge_loops[max_perimeter_index]

    # Collect vertices from the outer loop
    outer_loop_vertices = {vert.index for edge in outer_loop_edges for vert in edge.verts}

    # Create a vertex group and add the outer loop vertices
    bpy.ops.object.mode_set(mode='OBJECT')
    vg = obj.vertex_groups.new(name="PreserveEdges")
    vg.add(list(outer_loop_vertices), 1.0, 'ADD')

    # Deselect everything and update the mesh
    bpy.ops.object.mode_set(mode='EDIT')
    bmesh.update_edit_mesh(obj.data)
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.object.mode_set(mode='OBJECT')

    return vg.name


def decimate_object(obj, reduction_percentage, iterations=5, vg_name=None):
    """
    Applies a decimate modifier iteratively to a Blender object to reduce its complexity by a specified
    percentage after a given number of iterations.

    :param obj: The Blender object to which the decimate modifier will be applied.
    :type obj: bpy.types.Object
    :param reduction_percentage: The final desired reduction percentage of the original mesh.
    :type reduction_percentage: float
    :param iterations: The number of times the decimate modifier should be applied, defaults to 5.
    :type iterations: int, optional
    :param vg_name: The name of the vertex group to use for the decimation, defaults to None.
    :type vg_name: str, optional
    """
    bpy.context.view_layer.objects.active = obj
    current_ratio = 1.0

    # Calculate the per-step ratio for even distribution of reduction across iterations
    target_ratio = 1.0 - reduction_percentage / 100
    per_step_ratio = target_ratio ** (1 / iterations)

    for _ in range(iterations):
        current_ratio *= per_step_ratio

        # Add a decimate modifier to the object
        bpy.ops.object.modifier_add(type='DECIMATE')

        # Configure the decimate modifier
        decimate_modifier = obj.modifiers['Decimate']
        decimate_modifier.use_collapse_triangulate = True

        # Set vertex group and inversion if specified
        if vg_name:
            decimate_modifier.vertex_group = vg_name
            decimate_modifier.invert_vertex_group = True

        decimate_modifier.ratio = max(current_ratio, 0.01)  # Ensure ratio does not go below 1%

        # Apply the decimate modifier
        bpy.ops.object.modifier_apply(modifier='Decimate')


def clear_scene():
    # Switch to Object Mode if not in it
    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    # Select all objects and delete
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

    # Remove all meshes, lights, cameras and other data blocks still in memory and unused
    for block in bpy.data.meshes:
        bpy.data.meshes.remove(block)
    for block in bpy.data.cameras:
        bpy.data.cameras.remove(block)
    for block in bpy.data.lights:
        bpy.data.lights.remove(block)
    for block in bpy.data.materials:
        bpy.data.materials.remove(block)
    for block in bpy.data.textures:
        bpy.data.textures.remove(block)
    for block in bpy.data.curves:
        bpy.data.curves.remove(block)
    for block in bpy.data.metaballs:
        bpy.data.metaballs.remove(block)
    for block in bpy.data.armatures:
        bpy.data.armatures.remove(block)
    for block in bpy.data.particles:
        bpy.data.particles.remove(block)
    for block in bpy.data.grease_pencils:
        bpy.data.grease_pencils.remove(block)
    for block in bpy.data.images:
        bpy.data.images.remove(block)
    for block in bpy.data.fonts:
        bpy.data.fonts.remove(block)


def set_gpu_rendering():
    # Set the render engine to Cycles if it's not already set
    bpy.context.scene.render.engine = 'CYCLES'

    # Get Cycles preferences
    cycles_prefs = bpy.context.preferences.addons['cycles'].preferences

    if cycles_prefs.compute_device_type != 'NONE':
        print("Compute Device is already set.")
        return

    # Refresh devices, as they are never initialized when using bpy as a module only
    cycles_prefs.refresh_devices()

    # Initialize a variable to track if a suitable GPU has been found
    gpu_found = False

    # Preferred order of GPU compute device types
    preferred_devices = ['CUDA', 'OPTIX', 'OPENCL']

    # Try to set the GPU device type in order of preference
    for device_type in preferred_devices:
        try:
            print(f"Trying to set device type to: {device_type}")
            cycles_prefs.compute_device_type = device_type

            # Enable all devices of this type
            for device in cycles_prefs.devices:
                if device.type == device_type:
                    device.use = True
                    gpu_found = True

            if gpu_found:
                print(f"Successfully set to {device_type}")
                break  # Exit the loop if successfully set

        except Exception as e:
            print(f"Failed to set device type to {device_type}: {str(e)}")

    # If a GPU was successfully found and set
    if gpu_found:
        bpy.context.scene.cycles.device = 'GPU'
        print("GPU rendering is set.")
    else:
        print("No compatible GPU found. Check your system configuration or Blender version.")
