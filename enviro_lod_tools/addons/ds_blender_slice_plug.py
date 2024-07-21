import bpy
import math

from .ds_consts import SLICE_IDNAME, SLICE_LABEL, SLICE_PANEL_LABEL, SLICE_PANEL_IDNAME

bl_info = {
    "name": "Mesh Slicer",
    "author": "Nico Breycha",
    "version": (0, 0, 1),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > Tool Tab",
    "description": "Cut's a Mesh into a user-defined amount of square slices, by referencing the longest side of the AABB.",
    "category": "Object",
}


class MeshSlicer:
    """
    Class to handle slicing and UV unwrapping of mesh objects in Blender, ensuring normal continuity.
    """

    def __init__(self, number_of_modules):
        """
        Initializes the MeshSlicer with the desired number of modules.

        :param number_of_modules: Desired number of modules to slice the mesh into.
        :type number_of_modules: int
        """
        self.number_of_modules = number_of_modules


    @staticmethod
    def is_power_of_two(n):
        """Check if a number is a power of two."""
        return n > 0 and (n & (n - 1)) == 0

    def slice_model(self, context):
        """
        Slices the active mesh object based on the specified number of modules, unwraps UVs, and recalculates normals.

        :param context: The context in which the operator is called.
        :type context: bpy.types.Context
        """
        if context.object is None or context.object.type != 'MESH':
            self.report_message(context, "Error: No mesh object is active.")
            return

        bpy.ops.object.mode_set(mode='OBJECT')
        context.view_layer.objects.active = context.object
        context.object.select_set(True)

        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        bpy.ops.object.join()
        bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='MEDIAN')

        dimensions = context.object.dimensions
        max_length = max(dimensions.x, dimensions.y)
        number_of_cuts = int(math.sqrt(self.number_of_modules)) - 1
        step = max_length / (number_of_cuts + 1)

        bpy.ops.object.mode_set(mode='EDIT')
        for cut in range(number_of_cuts):
            for axis in ['X', 'Y']:
                bpy.ops.mesh.select_all(action='SELECT')
                cut_location = (cut + 1) * step - (max_length / 2)
                plane_co = (cut_location, 0, 0) if axis == 'X' else (0, cut_location, 0)
                plane_no = (1, 0, 0) if axis == 'X' else (0, 1, 0)
                bpy.ops.mesh.bisect(plane_co=plane_co, plane_no=plane_no, use_fill=False)
                bpy.ops.mesh.edge_split(type='EDGE')
        bpy.ops.object.mode_set(mode='OBJECT')

        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.separate(type='LOOSE')
        bpy.ops.object.mode_set(mode='OBJECT')

        self.recalculate_normals(context)
        # self.unwrap_uv(context)
        # self.report_message(context, f"Model sliced and UV unwrapped into {self.number_of_modules} parts.")

    def recalculate_normals(self, context):
        """
        Recalculates normals for all objects in the scene to ensure smooth transitions between new edges.

        :param context: The context in which the operation is performed.
        :type context: bpy.types.Context
        """
        for obj in context.selected_objects:
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.shade_smooth()  # Apply smooth shading
            obj.data.use_auto_smooth = True
            obj.data.auto_smooth_angle = math.radians(30)  # Adjust as necessary for your mesh
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.normals_make_consistent(inside=False)
            bpy.ops.object.mode_set(mode='OBJECT')

    def unwrap_uv(self, context):
        """
        Unwraps UV for all selected mesh objects in the scene.

        :param context: The context in which the operation is performed.
        :type context: bpy.types.Context
        """
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.smart_project()
        bpy.ops.object.mode_set(mode='OBJECT')

    def report_message(self, context, message):
        """
        Report a message to Blender's interface.

        :param context: The context where the message should be reported.
        :type context: bpy.types.Context
        :param message: The message to report.
        :type message: str
        """
        self_operator = context.active_operator
        if self_operator:
            self_operator.report({'INFO'}, message)
        print(message)


class MESH_OT_quadrant_slicer(bpy.types.Operator):
    """Operator to slice the mesh and unwrap UVs, ensuring normal continuity."""
    bl_idname = SLICE_IDNAME
    bl_label = SLICE_LABEL

    @classmethod
    def poll(cls, context):
        return context.object is not None and context.object.type == 'MESH'

    def execute(self, context):
        number_of_modules = context.scene.number_of_modules

        # Check if chosen number is a power of two. Not a hard requirement per se,
        # but a condition for equally sized parts in one direction.
        if not MeshSlicer.is_power_of_two(number_of_modules):
            self.report({'ERROR'}, "Number of modules must be a power of two.")
            return {'CANCELLED'}

        slicer = MeshSlicer(number_of_modules)
        slicer.slice_model(context)
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

