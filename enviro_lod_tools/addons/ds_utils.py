import sys
import os
import subprocess
import math
import importlib.util
from functools import wraps

import bpy
import bmesh

from .ds_consts import EXTERNAL_FOLDER

# region Math

def cubic_ease_out(t):
    """
    Cubic easing out function.

    :param t: Normalized time (between 0 and 1).
    :type t: float
    :return: Eased value.
    :rtype: float
    """
    return 1 - (1 - t) ** 3

# endregion

# region Package Management


def is_package_installed(package_name):
    """
    Check if a package is installed.

    :param package_name: The name of the package to check.
    :type package_name: str
    :return: True if the package is installed, False otherwise.
    :rtype: bool
    """
    package_spec = importlib.util.find_spec(package_name)
    return package_spec is not None


def install_package(package_name):
    """
    Install a package.

    :param package_name: The name of the package to install.
    :type package_name: str
    :return: None
    """
    python_executable = sys.executable
    try:
        # Execute the pip command to install the package
        subprocess.check_call([python_executable, "-m", "pip", "install", package_name])
        print(f"Successfully installed {package_name}")
    except subprocess.CalledProcessError as e:
        print(f"Failed to install {package_name}: {e}")


def ensure_package_installed(package_name):
    """
    Check if a package is installed, and if not, install it.

    :param package_name: The name of the package to check and install.
    :type package_name: str
    :return: None
    """
    if not is_package_installed(package_name):
        try:
            print(f"{package_name} is not installed. Installing now...")
            install_package(package_name)
        except subprocess.CalledProcessError as e:
            print(f"Failed to install {package_name}: {e}")
            install_local_package(package_name)
    else:
        print(f"{package_name} is already installed.")


def uninstall_package(package_name):
    """
    Uninstall a package.

    :param package_name: The name of the package to uninstall.
    :type package_name: str
    :return: None
    """
    if package_name in sys.modules:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "uninstall", "-y", package_name])
            print(f"Successfully uninstalled {package_name}")
        except subprocess.CalledProcessError as e:
            print(f"Failed to uninstall {package_name}: {e}")


def install_local_package(package_name):
    """
    Install a package from the external folder.

    :param package_name: The name of the package to install.
    :type package_name: str
    :return: None
    """
    src_path = os.path.join(EXTERNAL_FOLDER, package_name)

    python_executable = sys.executable
    try:
        # Check if the path exists
        if os.path.exists(src_path):
            subprocess.check_call([python_executable, "-m", "pip", "install", src_path])
            print(f"Successfully installed {package_name} from local source")
        else:
            print(f"Source path {src_path} does not exist")
    except subprocess.CalledProcessError as e:
        print(f"Failed to install {package_name} from local source: {e}")

# endregion

# region Blender Utility Functions

def launch_operator_by_name(op_str):
    """
    Launches an operator by name.
    :param op_str: The name of the operator.
    :type op_str: str
    :return: None
    """
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
    # Ensure the object is active
    bpy.context.view_layer.objects.active = obj

    # Switch to EDIT mode and create a BMesh representation
    bpy.ops.object.mode_set(mode="EDIT")
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
    bpy.ops.object.mode_set(mode="OBJECT")
    vg = obj.vertex_groups.new(name="PreserveEdges")
    vg.add(list(outer_loop_vertices), 1.0, "ADD")

    # Deselect everything and update the mesh
    bpy.ops.object.mode_set(mode="EDIT")
    bmesh.update_edit_mesh(obj.data)
    bpy.ops.mesh.select_all(action="DESELECT")
    bpy.ops.object.mode_set(mode="OBJECT")

    return vg.name


def clear_scene():
    """
    Clears the scene of all objects.
    :return: None
    """
    # Switch to Object Mode if not in it
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    # Select all objects and delete
    bpy.ops.object.select_all(action="SELECT")
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


def set_cpu_rendering():
    """
    Sets the CPU as the rendering device for Cycles.
    :return: None
    """
    # Set the render engine to Cycles if it's not already set
    bpy.context.scene.render.engine = "CYCLES"

    # Get Cycles preferences
    cycles_prefs = bpy.context.preferences.addons["cycles"].preferences

    # Ensure the compute device is set to None, indicating CPU usage
    if cycles_prefs.compute_device_type != "NONE":
        print(f"Changing compute device type to NONE (CPU).")
        cycles_prefs.compute_device_type = "NONE"
    else:
        print("Compute Device is already set to NONE (CPU).")

    # Set the device to CPU
    bpy.context.scene.cycles.device = "CPU"
    print("CPU rendering is set.")


def set_gpu_rendering():
    """
    Sets the GPU rendering engine to Cycles.
    :return: None
    """
    # Set the render engine to Cycles if it's not already set
    bpy.context.scene.render.engine = "CYCLES"

    # Get Cycles preferences
    cycles_prefs = bpy.context.preferences.addons["cycles"].preferences

    if cycles_prefs.compute_device_type != "NONE":
        print("Compute Device is already set.")
        return

    # Refresh devices, as they are never initialized when using bpy as a module only
    cycles_prefs.refresh_devices()

    # Initialize a variable to track if a suitable GPU has been found
    gpu_found = False

    # Preferred order of GPU compute device types
    preferred_devices = ["CUDA", "OPTIX", "OPENCL"]

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
        bpy.context.scene.cycles.device = "GPU"
        print("GPU rendering is set.")
    else:
        print("No compatible GPU found. Check your system configuration or Blender version.")

# endregion

# region BMesh Operations

def bmesh_wrapper(func):
    """
    Decorator to handle BMesh operations for Blender mesh data.

    This decorator manages the creation and freeing of BMesh objects based on the provided
    parameters. It ensures that the mesh is updated appropriately after operations.

    :param func: The function to be wrapped.
    :type func: callable
    :raises ValueError: If `mesh_data` is not provided when `bm` is `None`.
    :raises TypeError: If `mesh_data` is not of type 'MESH'.
    :return: A resolved bpy Object if return_bm is `False`, otherwise the BMesh data for further processing.
    :rtype: bpy.types.Object or bmesh.types.BMesh
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        mesh_data = args[0]

        if mesh_data is None:
            raise ValueError("Mesh Data must be provided.")

        # Ensure the object has a valid mesh
        if mesh_data.type != "MESH":
            raise TypeError("Mesh Data must be of type 'MESH'.")

        mesh = mesh_data.data
        bm = kwargs.pop("bm", None)
        return_bm = kwargs.pop("return_bm", False)

        if bm is None:
            bm = bmesh.new()
            bm.from_mesh(mesh)

        result = func(*args, bm=bm, **kwargs)

        if not return_bm:
            mesh_data = resolve_bmesh(mesh_data, bm=bm)
            return mesh_data

        return result

    return wrapper


def resolve_bmesh(mesh_data, bm=None):
    """
    Create a BMesh object from the provided mesh data.

    :param mesh_data: The mesh data to create the BMesh from.
    :type mesh_data: bpy.types.Object
    :param bm: The BMesh object to use. If None, a new BMesh object will be created.
    :type bm: bmesh.types.BMesh
    :return: The BMesh object.
    :rtype: bpy.types.Object
    """
    if bm is None:
        raise ValueError("BMesh must be provided.")

    if mesh_data is None:
        raise ValueError("Mesh Data must be provided.")

    if mesh_data.type != "MESH":
        raise TypeError("Mesh Data must be of type 'MESH'.")

    mesh = mesh_data.data

    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

    return mesh_data


@bmesh_wrapper
def delete_loose_geometry(mesh_data, bm=None, remove_faces=True):
    """
    Remove loose (disconnected) vertices, edges, and optionally faces from the object.

    :param mesh_data: The object whose loose geometry will be removed.
    :type mesh_data: bpy.types.Object
    :param bm: The BMesh object to operate on. If None, it will be created from the mesh data.
    :type bm: bmesh.types.BMesh
    :param remove_faces: If True, also removes loose faces. Default is True.
    :type remove_faces: bool
    :return: A resolved bpy Object if return_bm is `False`, otherwise the BMesh data for further processing.
    :rtype: bpy.types.Object or bmesh.types.BMesh
    """
    # Remove loose vertices (vertices not connected to any edge)
    loose_verts = [v for v in bm.verts if not v.link_edges]
    bmesh.ops.delete(bm, geom=loose_verts, context="VERTS")

    # Remove loose edges (edges not connected to any face)
    loose_edges = [e for e in bm.edges if not e.link_faces]
    bmesh.ops.delete(bm, geom=loose_edges, context="EDGES")

    loose_faces = []

    # Optionally remove loose faces (faces not connected to other faces via edges)
    if remove_faces:
        loose_faces = [f for f in bm.faces if not f.edges]
        bmesh.ops.delete(bm, geom=loose_faces, context="FACES")

    print(f"Removed {len(loose_verts)} loose vertices, {len(loose_edges)} loose edges, and {len(loose_faces)} loose faces on {mesh_data.name}.")

    return bm


@bmesh_wrapper
def merge_meshes(mesh_data, additional_objs, bm=None):
    """
    Merge all meshes in `additional_objs` into `base_obj` using BMesh.

    :param mesh_data: The object to merge the meshes into.
    :type mesh_data: bpy.types.Object
    :param additional_objs: The objects to merge into `base_obj`.
    :type additional_objs: list[bpy.types.Object]
    :param bm: The BMesh of `base_obj` to operate on, if provided. Defaults to None.
    :type bm: bmesh.types.BMesh, optional
    :return: A resolved bpy Object if return_bm is `False`, otherwise the BMesh data for further processing.
    :rtype: bpy.types.Object or bmesh.types.BMesh
    """
    # Loop through additional objects and merge their meshes
    for additional_obj in additional_objs:
        # Create a new BMesh for the additional mesh
        temp_bm = bmesh.new()
        temp_bm.from_mesh(additional_obj.data)

        # Transform the additional mesh into the base object's local space
        matrix = additional_obj.matrix_world @ mesh_data.matrix_world.inverted()
        bmesh.ops.transform(temp_bm, matrix=matrix, verts=temp_bm.verts)

        # Merge the temporary BMesh into the base BMesh
        bm.from_mesh(additional_obj.data)

        # Free the temporary BMesh
        temp_bm.free()

        # Remove the additional object's mesh data and object itself
        bpy.data.meshes.remove(additional_obj.data)
        bpy.data.objects.remove(additional_obj)

    print(f"All meshes merged into {mesh_data.name}")
    return bm


@bmesh_wrapper
def keep_largest_component(mesh_data, bm=None):
    """
    Remove all but the largest connected component in the mesh.

    :param mesh_data: The object to remove components from.
    :type mesh_data: bpy.types.Object
    :param bm: The BMesh to operate on. If None, it will be created from the mesh data. Defaults to None.
    :type bm: bmesh.types.BMesh, optional
    :return: A resolved bpy Object if return_bm is `False`, otherwise the BMesh data for further processing.
    :rtype: bpy.types.Object or bmesh.types.BMesh
    """
    # Find connected components
    verts = set(bm.verts)
    processed_verts = 0
    components = []

    while verts:
        v = verts.pop()
        stack = [v]
        component = {v}
        processed_verts += 1

        while stack:
            current = stack.pop()
            for edge in current.link_edges:
                linked_vert = edge.other_vert(current)
                if linked_vert in verts:
                    verts.remove(linked_vert)
                    stack.append(linked_vert)
                    component.add(linked_vert)
                    processed_verts += 1

        components.append(component)

    # Find the largest component
    largest_component = max(components, key=len)

    # Delete other components
    verts_to_delete = [v for component in components if component != largest_component for v in component]
    print(f"Deleting {len(verts_to_delete)} vertices.")
    bmesh.ops.delete(bm, geom=verts_to_delete, context="VERTS")

    return bm


@bmesh_wrapper
def merge_doubles(mesh_data, merge_threshold, bm=None):
    """
    Merge vertices that are within the merge threshold.

    :param merge_threshold: The distance threshold for merging vertices.
    :type merge_threshold: float
    :param bm: The BMesh to operate on. If None, it will be created from the mesh data.
    :return: A resolved bpy Object if return_bm is `False`, otherwise the BMesh data for further processing.
    :rtype: bpy.types.Object or bmesh.types.BMesh
    """
    # Remove doubles
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=merge_threshold)
    print(f"Merged vertices with a threshold of {merge_threshold}.")
    return bm


@bmesh_wrapper
def clean_mesh_geometry(mesh_data, merge_threshold, bm=None):
    """
    Clean the mesh geometry by filling holes, dissolving degenerate geometry,
    and removing doubles using BMesh operations.

    :param mesh_data: The object whose geometry will be cleaned.
    :type mesh_data: bpy.types.Object
    :param merge_threshold: The distance threshold for merging vertices.
    :type merge_threshold: float
    :param bm: The BMesh to operate on. If None, it will be created from the mesh data.
    :return: A resolved bpy Object if return_bm is `False`, otherwise the BMesh data for further processing.
    :rtype: bpy.types.Object or bmesh.types.BMesh
    """
    def fill_holes(boundary_edges):
        """
        Fills holes in the BMesh by identifying boundary edge loops and creating faces.
        """
        # Find boundary edges (edges with only one connected face)
        if not boundary_edges:
            print("No holes detected.")
            return

        # Find boundary edge loops (holes)
        loops = []
        visited_edges = set()

        for edge in boundary_edges:
            if edge in visited_edges:
                continue

            loop = []
            stack = [edge]
            while stack:
                current_edge = stack.pop()
                if current_edge in visited_edges:
                    continue
                visited_edges.add(current_edge)
                loop.append(current_edge)

                for vert in current_edge.verts:
                    for linked_edge in vert.link_edges:
                        if linked_edge in boundary_edges and linked_edge not in visited_edges:
                            stack.append(linked_edge)
            loops.append(loop)

        # Exclude the largest loop (assumed to be the outer boundary)
        loops.sort(key=lambda l: len(l), reverse=True)
        loops.pop(0)

        num_holes = len(loops)
        holes = [edge for loop in loops for edge in loop]

        # Fill holes
        result = bmesh.ops.edgenet_fill(bm, edges=holes)
        num_faces_created = len(result.get('faces', []))

        print(f"Filled {num_holes} holes, created {num_faces_created} new faces.")

    bmesh.ops.triangulate(bm, faces=bm.faces, quad_method="BEAUTY", ngon_method="BEAUTY")

    hole_edges = [e for e in bm.edges if len(e.link_faces) == 1]

    # Fill holes
    fill_holes(hole_edges)

    # Dissolve degenerate geometry
    bmesh.ops.dissolve_degenerate(bm, dist=merge_threshold)

    # Remove doubles
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=merge_threshold)

    print("Mesh geometry cleaned.")

    # Call delete_loose_geometry
    bm = delete_loose_geometry(mesh_data, bm=bm, return_bm=True)

    return bm


# endregion

# region Simplification

@bmesh_wrapper
def decimate_with_pyqmfr(mesh_data, target_face_count, bm=None, max_iterations=80,
                         preserve_border=True, merge_threshold=0.0001):
    """
    Simplifies a Blender object's mesh using pyfqmr to reduce its complexity to a specified
    percentage. All operations are performed using a single bmesh object to minimize memory usage.

    :param mesh_data: The Blender object to simplify.
    :type mesh_data: bpy.types.Object
    :param target_face_count: The face count the mesh should be reduced to.
    :type target_face_count: int
    :param max_iterations: The maximum number of iterations to run, defaults to 80.
    :type max_iterations: int, optional
    :param preserve_border: Whether to preserve the border of the mesh, defaults to True.
    :type preserve_border: bool, optional
    :param merge_threshold: The threshold for merging vertices, defaults to 0.0001.
    :type merge_threshold: float, optional
    :return: A resolved bpy Object if return_bm is `False`, otherwise the BMesh data for further processing.
    :rtype: bpy.types.Object or bmesh.types.BMesh
    """
    import numpy as np
    import pyfqmr

    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=merge_threshold)

    # Triangulate the mesh using bmesh
    bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method='BEAUTY', ngon_method='BEAUTY')

    # Ensure the BMesh is up to date
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    # Get vertices as a numpy array
    vertices = np.array([v.co[:] for v in bm.verts], dtype=np.float64)

    # Get faces as a numpy array
    faces = np.array([[v.index for v in f.verts] for f in bm.faces], dtype=np.int32)

    starting_face_count = len(faces)

    target_face_count = max(target_face_count, 4)  # Ensure minimum face count

    # Initialize the simplifier
    mesh_simplifier = pyfqmr.Simplify()
    mesh_simplifier.setMesh(vertices, faces)

    # Simplify the mesh
    mesh_simplifier.simplify_mesh(
        target_count=target_face_count,
        aggressiveness=7,
        max_iterations=max_iterations,
        preserve_border=preserve_border,
        verbose=10,
    )

    # Retrieve the simplified mesh
    vertices_out, faces_out, normals_out = mesh_simplifier.getMesh()

    # Clear the existing BMesh to reuse it
    bm.clear()

    # Add the simplified vertices to the BMesh
    for co in vertices_out:
        bm.verts.new(co)
    bm.verts.ensure_lookup_table()

    # Add the simplified faces to the BMesh
    for face_indices in faces_out:
        try:
            bm.faces.new([bm.verts[i] for i in face_indices])
        except ValueError:
            # Face already exists; skip it
            pass
    bm.faces.ensure_lookup_table()

    # Remove doubles (merge vertices)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=merge_threshold)

    # Update normals
    bm.normal_update()

    print(f"Simplification complete. Original faces: {starting_face_count}, Reduced faces: {len(faces_out)}")
    return bm


# Unused
@bmesh_wrapper
def simplify_flat_areas(mesh_data, target_face_count=1000, curvature_threshold=0.05, bm=None, vertex_group_name=None):
    """
    Simplify the mesh by merging lower curvature vertices into higher curvature ones.

    :param mesh_data: The object whose mesh is to be simplified.
    :type mesh_data: bpy.types.Object
    :param target_face_count: Desired number of faces after simplification.
    :type target_face_count: int
    :param curvature_threshold: Curvature threshold for vertex merging.
    :type curvature_threshold: float
    :param vertex_group_name: Name of the vertex group to protect during simplification.
    :type vertex_group_name: str or None
    :return: None
    """
    # Get the vertex group that defines protected vertices, if any
    protected_vertices = set()
    if vertex_group_name and vertex_group_name in mesh_data.vertex_groups:
        vg = mesh_data.vertex_groups[vertex_group_name]
        protected_vertices.update(
            v.index for v in mesh_data.data.vertices if vg.index in [g.group for g in v.groups]
        )

    # Triangulate the mesh to ensure all faces are triangles
    bmesh.ops.triangulate(bm, faces=bm.faces[:])

    initial_face_count = len(bm.faces)
    if initial_face_count <= target_face_count:
        print(f"Current face count ({initial_face_count}) is already less than or equal to target face count ({target_face_count}).")
        bm.free()
        return

    # Function to compute curvature at a vertex using the angle deficit method
    def compute_vertex_curvature(vert):
        angle_sum = sum((loop.calc_angle() or 0.0) for loop in vert.link_loops)
        return abs(2 * math.pi - angle_sum)

    # Compute curvature for all vertices once and store in a dictionary
    curvature_dict = {
        vert: compute_vertex_curvature(vert)
        for vert in bm.verts
        if vert.is_valid and vert.index not in protected_vertices
    }

    # Early exit if no vertices meet the curvature criteria
    if not any(curv < curvature_threshold for curv in curvature_dict.values()):
        print("No vertices with curvature below the threshold.")
        bm.free()
        return

    # Adjust positions of low curvature vertices
    for vert in curvature_dict:
        if curvature_dict[vert] < curvature_threshold:
            # Find neighboring vertices with higher curvature
            high_curvature_neighbors = [
                v for v in vert.link_edges
                if v.other_vert(vert).is_valid
                and curvature_dict.get(v.other_vert(vert), curvature_threshold) >= curvature_threshold
                and v.other_vert(vert).index not in protected_vertices
            ]
            if high_curvature_neighbors:
                # Move vertex to the position of the neighbor with the highest curvature
                target_vert = max(
                    (v.other_vert(vert) for v in high_curvature_neighbors),
                    key=lambda v: curvature_dict.get(v, 0.0)
                )
                vert.co = target_vert.co

    # Note: The methodology of moving the vertices to the highest curvature neighbor has been chosen
    # to merge them in bulk by calling the bmesh.ops.remove_doubles function. This is tremendously faster than
    # iterating through a list of all candidates and merging them one by one with bmesh.ops.pointmerge

    # Remove duplicate vertices
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0001)

    # Remove degenerate geometry (if any)
    bmesh.ops.dissolve_degenerate(bm, dist=0.0001)

    # Update face count
    current_face_count = len(bm.faces)
    print(f"Face count after vertex adjustment: {current_face_count} faces.")

    return bm


def decimate_object(mesh_data, target_ratio, iterations=5, vg_name=None, merge_threshold = 0.0001):
    """
    Applies a decimate modifier iteratively to a Blender object to reduce its complexity by a specified
    percentage after a given number of iterations.

    :param mesh_data: The Blender object to which the decimate modifier will be applied.
    :type mesh_data: bpy.types.Object
    :param target_ratio: The ratio at which the object should be reduced to.
    :type target_ratio: float
    :param iterations: The number of times the decimate modifier should be applied, defaults to 5.
    :type iterations: int, optional
    :param vg_name: The name of the vertex group to use for the decimation, defaults to None.
    :type vg_name: str, optional
    :param merge_threshold: The threshold for merging vertices between iterations, defaults to 0.0005.
    :type merge_threshold: float, optional
    :return: The decimated Blender object.
    :rtype: bpy.types.Object
    """
    bpy.context.view_layer.objects.active = mesh_data

    # Calc merge distance.
    max_dimension = max(mesh_data.dimensions)
    merge_distance = max_dimension * merge_threshold # Adjust the factor as needed

    # Get the initial vertex count
    initial_vertex_count = len(mesh_data.data.vertices)
    current_face_count = len(mesh_data.data.polygons)
    target_face_count = current_face_count * target_ratio

    # Initialize cumulative ratio
    cumulative_ratio = 1.0

    for iteration in range(1, iterations + 1):
        if current_face_count <= target_face_count:
            print(f"Target face count reached: {current_face_count} faces.")
            break  # Target reached already, return early.

        # Normalize the current iteration to a value between 0 and 1
        t = iteration / iterations

        # Apply the cubic easing function to smooth the decimation progress
        eased_t = cubic_ease_out(t)

        # Compute the desired cumulative ratio for this iteration
        desired_cumulative_ratio = 1 - eased_t * (1 - target_ratio)

        # Adjust per-step ratio based on actual cumulative ratio achieved so far
        per_step_ratio = desired_cumulative_ratio / cumulative_ratio

        # Ensure the per-step ratio does not drop below a minimum threshold
        per_step_ratio = max(per_step_ratio, 0.0001)

        # Add a decimate modifier to the object
        decimate_modifier = mesh_data.modifiers.new(name=f"Decimate_{iteration}", type="DECIMATE")
        decimate_modifier.ratio = per_step_ratio
        decimate_modifier.use_collapse_triangulate = True

        # Set vertex group and inversion if specified
        if vg_name:
            decimate_modifier.vertex_group = vg_name
            decimate_modifier.invert_vertex_group = True

        # Apply the decimate modifier
        bpy.ops.object.modifier_apply(modifier=decimate_modifier.name)

        # Merge by distance (remove doubles)
        mesh_data = merge_doubles(mesh_data, merge_distance, return_bm=False)

        # Update the cumulative ratio based on the actual vertex count
        current_vertex_count = len(mesh_data.data.vertices)
        current_face_count = len(mesh_data.data.polygons)
        cumulative_ratio = current_vertex_count / initial_vertex_count

        # Print debug information
        print(f"Iteration {iteration}/{iterations}:")
        print(f"  Desired Cumulative Ratio: {desired_cumulative_ratio:.6f}")
        print(f"  Actual Cumulative Ratio: {cumulative_ratio:.6f}")
        print(f"  Per-Step Ratio Used: {per_step_ratio:.6f}")
        print(f"  Vertex Count: {current_vertex_count}")
        print(f"  Face Count: {current_face_count}")

        if target_face_count < current_face_count and iteration < iterations:
            face_target = int(target_face_count * target_ratio)
            simplify_flat_areas(mesh_data, face_target, 0.01, vg_name)
            old_curr_face_ct = current_face_count
            current_face_count = len(mesh_data.data.polygons)
            print(f"Removed an additional {old_curr_face_ct - current_face_count} faces.")

    return mesh_data

# endregion
