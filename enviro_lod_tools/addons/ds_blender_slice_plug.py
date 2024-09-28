import gc

import numpy as np
import bpy
import bmesh
from bmesh.utils import edge_split, face_split
from mathutils import Vector

from enviro_lod_tools.addons.ds_utils import clean_mesh_geometry
from .ds_consts import SLICE_IDNAME, SLICE_LABEL, SLICE_PANEL_LABEL, SLICE_PANEL_IDNAME

X_VEC = Vector((1, 0, 0))  # Vec into X Direction
Y_VEC = Vector((0, 1, 0))  # Vec into Y Direction

bl_info = {
    "name": "Mesh Slicer",
    "author": "Nico Breycha",
    "version": (0, 1, 3),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > Tool Tab",
    "description": "Cut's a Mesh into a user-defined amount of square slices, "
                   "by referencing the longest side of the AABB.",
    "category": "Object",
}


def calculate_intersection_factor(vert1, vert2, ip):
    """
    Calculate the intersection factor of a point on the edge defined by two vertices.
    :param vert1: The first vertex of the edge
    :type vert1: Vector or bmesh.types.BMVert
    :param vert2: The second vertex of the edge
    :type vert2: Vector or bmesh.types.BMVert
    :param ip: The coordinates of the intersection point.
    :type ip: Vector or bmesh.types.BMVert
    :return: The intersection factor ``i_fac``, which ranges between 0.0001 and 0.9999. This value represents the
             normalized position of the intersection point along the edge.
    :rtype: float
    :raises TypeError: If ``vert1`` or ``vert2`` or ``ip`` are not a Vector or a BMVert
    """
    # Convert vertex positions / vectors to numpy arrays
    if isinstance(vert1, bmesh.types.BMVert):
        v1 = np.array(vert1.co)
    elif isinstance(vert1, Vector):
        v1 = np.array(vert1)
    else:
        raise TypeError("vert1 must be a Vector or a BMVert")

    if isinstance(vert2, bmesh.types.BMVert):
        v2 = np.array(vert2.co)
    elif isinstance(vert2, Vector):
        v2 = np.array(vert2)
    else:
        raise TypeError("vert2 must be a Vector or a BMVert")

    if isinstance(ip, bmesh.types.BMVert):
        ip = np.array(ip.co)
    elif isinstance(ip, Vector):
        ip = np.array(ip)
    else:
        raise TypeError("intersect_point must be a Vector or a BMVert")

    # Calculate vectors
    edge_vector = v2 - v1
    intersect_vector = ip - v1

    # Calculate the length of the edge_vector
    edge_length = np.linalg.norm(edge_vector)

    # Avoid division by zero by checking if the edge_length is very small
    if edge_length < 1e-8:
        return 0.0

    # Project intersect_vector onto edge_vector to find the scalar projection
    i_fac = np.dot(intersect_vector, edge_vector) / edge_length**2

    # Ensure e_fac is within the expected range / Avoid vertices are at the exact same position.
    i_fac = max(0.0001, min(0.9999, i_fac))

    return i_fac


def find_line_plane_intersection_point(line_vert_1, line_vert_2, plane_point, plane_normal):
    """
    Finds the intersection point of a line and a plane.

    :param line_vert_1: First point on the line.
    :type line_vert_1: Vector
    :param line_vert_2: Second point on the line.
    :type line_vert_2: Vector
    :param plane_point: A point on the plane.
    :type plane_point: Vector
    :param plane_normal: The normal vector of the plane.
    :type plane_normal: Vector
    :return: The intersection point or None if there is no intersection.
    :rtype: Vector or None
    """
    line_dir = line_vert_2 - line_vert_1
    plane_d = plane_normal.dot(plane_point)
    denom = plane_normal.dot(line_dir)

    # Check if the line is parallel to the plane
    if abs(denom) < 1e-6:  # using a small tolerance to handle floating-point precision
        return None

    t = (plane_d - plane_normal.dot(line_vert_1)) / denom
    if 0.0 <= t <= 1.0:
        return line_vert_1 + t * line_dir

    return None


def calc_cut_list(mesh, target_amount_of_slices):
    """Calculate a list of cut positions (in relative space) along the longest side of a Blender object's aabb,
    that divides it into equal sections, based on the square root of the target number of slices.
    Note: This function assumes that the target number of slices should form a perfect square.

    :param mesh: The Blender context containing the object to be sliced.
    :type mesh: bpy.types.Object
    :param target_amount_of_slices: The target number of slices, which must be a perfect square to ensure even slicing.
    :type target_amount_of_slices: int
    :return: A tuple containing a list of cut positions along the longest dimension of the object's AABB
             and the coordinates of the middle point of the bounding box.
    :rtype: tuple[list[float], Vector]
    :raises ValueError: If the target amount of slices is not a perfect square (n^2)
    """
    def calc_aabb(vertices):
        """
        Calculate the axis-aligned bounding box (AABB) of a Blender object.

        :param vertices: The vertices of the object.
        :type vertices: list[bpy.types.MeshVertex]
        :return: A tuple of numpy arrays (min_vec, max_vec), where each vector is represented
                 as numpy.float64 and contains the coordinates (x, y, z) of the minimum and
                 maximum points of the bounding box and the middle of the aabb.
        :rtype: tuple[np.ndarray, np.ndarray, np.ndarray]
        """
        # Initialize min and max coordinates with extreme values
        min_vec = np.array([np.inf, np.inf, np.inf], dtype=np.float64)
        max_vec = np.array([-np.inf, -np.inf, -np.inf], dtype=np.float64)

        # Update min and max coordinates by comparing each vertex
        for vertex in vertices:
            coords = np.array(vertex.co, dtype=np.float64)
            min_vec = np.minimum(min_vec, coords)
            max_vec = np.maximum(max_vec, coords)

        aabb_mid = (min_vec + max_vec) / 2

        return min_vec, max_vec, aabb_mid

    no_slices = int(np.sqrt(target_amount_of_slices))
    if no_slices * no_slices != target_amount_of_slices:
        raise ValueError("Target amount of slices must be a perfect square.")

    # Calculate the length of the longest side of the AABB
    min_bound, max_bound, mid_point = calc_aabb(mesh.vertices)
    longest_side_idx = np.argmax(max_bound - min_bound)
    longest_side = max_bound[longest_side_idx] - min_bound[longest_side_idx]

    # Calculate the relative cut positions
    cut_len = longest_side / no_slices
    absolute_cuts = [min_bound[longest_side_idx] + i * cut_len for i in range(1, no_slices)]
    relative_cuts = [cut - mid_point[longest_side_idx] for cut in absolute_cuts]

    return relative_cuts, mid_point


def better_bisect(mesh, cut_pos, direction, middle_point=None):
    """
    Slices the given mesh object at the specified position along the specified direction.
    Functionally mirrors how the built-in bisect works, but keeps both the positive and negative half of the mesh.

    See also: https://github.com/blender/blender/blob/main/source/blender/bmesh/tools/bmesh_bisect_plane.cc

    :param mesh: The mesh object to slice.
    :type mesh: bpy.types.Object
    :param cut_pos: The position along the specified direction where the mesh should be sliced.
    :type cut_pos: float
    :param direction: The normal vector to slice the mesh along.
    :type direction: Vector
    :param middle_point: The middle point of the object's axis-aligned bounding box.
    :type middle_point: Vector
    :return: A tuple containing the two parts resulting from the slice, or None if the operation fails.
    :rtype: tuple[bpy.types.Object]
    """
    if middle_point is None:
        middle_point = Vector((0, 0, 0))

    direction = Vector(direction)
    plane_point = Vector(middle_point + direction * cut_pos)

    bm = bmesh.new()
    bm.from_mesh(mesh.data)
    bmesh.ops.transform(bm, matrix=mesh.matrix_world, verts=bm.verts)

    # Collect all intersected edges.
    face_inters, verts_inters, verts_pos, verts_neg = set(), set(), set(), set()

    edge_snapshot = set(bm.edges)

    bm.faces.ensure_lookup_table()
    bm.verts.ensure_lookup_table()

    for edge in edge_snapshot:
        # Extract the edges vertices
        vert1, vert2 = edge.verts

        # Find a possible intersection of the edge and the cutting plane
        intersect_point = find_line_plane_intersection_point(vert1.co, vert2.co, plane_point, direction)

        if intersect_point:
            inter_fac = calculate_intersection_factor(vert1, vert2, intersect_point)

            face_inters.update(edge.link_faces)

            # Perform the split and store the newly created vertex
            new_edge, inter_vert = edge_split(edge, vert1, inter_fac)
            verts_inters.add(inter_vert)

    del edge_snapshot
    gc.collect()

    # Split the faces
    for face in face_inters:
        split_verts = [vert for vert in face.verts if vert in verts_inters]

        if len(split_verts) != 2:
            print(f"Failed to split face {face.index}")
            continue

        new_face, new_loop = face_split(face, split_verts[0], split_verts[1])

        verts_pos.update(split_verts)
        verts_neg.update(new_loop.edge.verts)

    del verts_inters
    del face_inters
    gc.collect()

    # We MUST update the indices, otherwise new faces and vertices are unknown when rebuilding the new meshes.
    bm.faces.index_update()
    bm.verts.index_update()

    # Create vertex maps from the old vertices to the new vertices, sorted by the side they are on.
    for vert in bm.verts:
        if (vert.co - plane_point).dot(direction) >= 0:
            verts_pos.add(vert)
        else:
            verts_neg.add(vert)

    # Create new bmeshes for the positive and negative half of the mesh
    bm_pos = bmesh.new()
    bm_neg = bmesh.new()

    # Create and map old vertex indices to new vertices in bm_pos and bm_neg
    pos_map = {vert.index: bm_pos.verts.new(vert.co) for vert in verts_pos}
    neg_map = {vert.index: bm_neg.verts.new(vert.co) for vert in verts_neg}

    # Store original vertex normals
    original_normals = {v.index: v.normal.copy() for v in bm.verts}

    # Transfer Normals. NOTE: From here on we should not call "recalculate_normals" anymore!!
    for old_index, new_vert in pos_map.items():
        new_vert.normal = original_normals[old_index]

    for old_index, new_vert in neg_map.items():
        new_vert.normal = original_normals[old_index]

    double_faces = 0

    # Recreate the faces in bm_pos and bm_neg
    for face in bm.faces:
        pos_face_verts = [pos_map[vert.index] for vert in face.verts if vert.index in pos_map]
        neg_face_verts = [neg_map[vert.index] for vert in face.verts if vert.index in neg_map]

        try:
            if len(pos_face_verts) == len(face.verts):
                bm_pos.faces.new(pos_face_verts)
            elif len(neg_face_verts) == len(face.verts):
                bm_neg.faces.new(neg_face_verts)
        except ValueError as err:
            print(f"Failed to create face {face.index}: {err}")
            double_faces += 1
            pass

    bm.free()
    del verts_pos
    del verts_neg
    gc.collect()

    # Convert bmesh to mesh
    mesh_data_pos = bpy.data.meshes.new(mesh.name + "_pos")
    bm_pos.to_mesh(mesh_data_pos)
    bm_pos.free()

    mesh_data_neg = bpy.data.meshes.new(mesh.name + "_neg")
    bm_neg.to_mesh(mesh_data_neg)
    bm_neg.free()

    # Create new objects
    mesh_pos = bpy.data.objects.new(mesh.name + "_pos", mesh_data_pos)
    mesh_neg = bpy.data.objects.new(mesh.name + "_neg", mesh_data_neg)

    # Link objects to the scene
    bpy.context.collection.objects.link(mesh_pos)
    bpy.context.collection.objects.link(mesh_neg)

    return mesh_pos, mesh_neg


class MESH_OT_quadrant_slicer(bpy.types.Operator):
    """Operator to slice the mesh and unwrap UVs, ensuring normal continuity."""
    bl_idname = SLICE_IDNAME
    bl_label = SLICE_LABEL

    @staticmethod
    def remove_part(part):
        """Removes the mesh part from the scene."""
        # Unlink the original mesh
        bpy.context.collection.objects.unlink(part)

        # Delete the original mesh data
        bpy.data.meshes.remove(part.data)

    @staticmethod
    def recalculate_normals(mesh):
        """Recalculates the normals of the mesh."""
        bm = bmesh.new()
        bm.from_mesh(mesh)

        # Ensure lookup table is populated for indexed access
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        # Recalculate normals
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

        # Write back to the mesh and release memory
        bm.to_mesh(mesh)
        bm.free()

    def execute(self, context):
        number_of_modules = context.scene.number_of_modules

        obj = context.object

        if obj is None or obj.type != 'MESH':
            self.report({'ERROR'}, "No mesh object is active.")
            return {'CANCELLED'}

        if number_of_modules < 1:
            self.report({'ERROR'}, "Number of modules must be greater than 0.")
            return {'CANCELLED'}

        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

        try:
            cut_list, aabb_middle = calc_cut_list(obj.data, number_of_modules)
        except ValueError:
            self.report({'ERROR'}, "Number of modules must be a power of two.")
            return {'CANCELLED'}

        x_sliced_meshes = []

        for part in x_sliced_meshes:
            print(f"Part: {part.name}")
        xy_sliced_meshes = []

        for part in xy_sliced_meshes:
            print(f"Part: {part.name}")

        next_part_to_cut = obj

        for idx, cut_pos in enumerate(cut_list):
            pos_part, neg_part = better_bisect(next_part_to_cut, cut_pos, X_VEC, aabb_middle)
            x_sliced_meshes.append(neg_part)

            # Set next part in operation active, since we unlink the previous part
            bpy.context.view_layer.objects.active = pos_part

            # Remove the original mesh
            self.remove_part(next_part_to_cut)

            if idx == len(cut_list) - 1:
                x_sliced_meshes.append(pos_part)
            else:
                next_part_to_cut = pos_part

        for x_part in x_sliced_meshes:
            next_part_to_cut = x_part

            for idx, cut_pos in enumerate(cut_list):
                pos_part, neg_part = better_bisect(next_part_to_cut, cut_pos, Y_VEC, aabb_middle)
                xy_sliced_meshes.append(neg_part)

                # Set next part in operation active, since we unlink the previous part
                bpy.context.view_layer.objects.active = pos_part

                # Remove the original mesh
                self.remove_part(next_part_to_cut)

                if idx == len(cut_list) - 1:
                    xy_sliced_meshes.append(pos_part)
                else:
                    next_part_to_cut = pos_part

                next_part_to_cut = pos_part

        # Recalculate normals for the final mesh parts
        for i, part in enumerate(xy_sliced_meshes):
            part = clean_mesh_geometry(part, 0.00001, return_bm=False)
            part.name = part.name.replace("_neg", "")
            part.name = part.name.replace("_pos", "")
            suffix = f"_{i + 1:03d}"
            part.name = part.name + suffix

        self.report({'INFO'}, "Slicing completed")
        return {'FINISHED'}


class VIEW3D_PT_quadrant_slicer(bpy.types.Panel):
    """Panel for controlling the Mesh Slicer in the 3D View's UI."""
    bl_label = SLICE_PANEL_LABEL
    bl_idname = SLICE_PANEL_IDNAME
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Tool'

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        layout.prop(scene, 'number_of_modules')
        layout.operator(SLICE_IDNAME)


classes = (MESH_OT_quadrant_slicer, VIEW3D_PT_quadrant_slicer)


def register():
    from bpy.utils import register_class

    for cls in classes:
        register_class(cls)

    bpy.types.Scene.number_of_modules = bpy.props.IntProperty(name="Number of Modules", default=16, min=1)


def unregister():
    from bpy.utils import unregister_class

    for cls in reversed(classes):
        unregister_class(cls)

    if hasattr(bpy.types, "number_of_modules"):
        del bpy.types.Scene.number_of_modules


if __name__ == "__main__":
    register()
