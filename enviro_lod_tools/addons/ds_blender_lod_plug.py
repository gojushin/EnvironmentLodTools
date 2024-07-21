import bpy

from .ds_consts import LOD_IDNAME, LOD_LABEL, LOD_PANEL_IDNAME, LOD_PANEL_LABEL

bl_info = {
    "name": "LOD Generator",
    "author": "Nico Breycha",
    "version": (0, 0, 1),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > Tool Tab",
    "description": "Generates levels of detail (LODs) for selected mesh objects.",
    "category": "Object",
}


class LODGenerator:
    """
    Class to generate Levels of Detail (LODs) for selected objects in Blender.
    """

    def __init__(self, lod_count, reduction_percentage):
        """
        Initializes the LODGenerator with the desired number of LODs and reduction percentage.

        :param lod_count: Number of LODs to generate.
        :type lod_count: int
        :param reduction_percentage: Percentage by which to reduce the mesh complexity in each LOD.
        :type reduction_percentage: float
        """
        self.lod_count = lod_count
        self.reduction_percentage = reduction_percentage

    def generate_lods(self, context):
        """
        Generates the specified number of LODs for each selected object.

        :param context: The context in which the operation is performed.
        :type context: bpy.types.Context
        """
        for obj in context.selected_objects:
            if obj.type == 'MESH':
                self._create_lods_for_object(obj, context)

    def _define_preserved_boundaries(self, obj):
        """
        Creates a vertex group from non-manifold edges to ensure they are preserved in decimation.
        :param obj: The object to process.
        :returns: Name of the vertex group.
        :rtype: str
        """
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.mesh.select_non_manifold(extend=False, use_wire=False, use_boundary=True)

        bpy.ops.object.mode_set(mode='OBJECT')
        # Create a vertex group
        vg = obj.vertex_groups.new(name="PreserveEdges")
        vg.add([v.index for v in obj.data.vertices if v.select], 1.0, 'ADD')
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.object.mode_set(mode='OBJECT')
        return vg.name  # Return the name of the vertex group for further use

    def _create_lods_for_object(self, obj, context):
        """
        Creates LODs for a single object and manages them within a dedicated collection.

        :param obj: The original object to generate LODs for.
        :type obj: bpy.types.Object
        :param context: The context in which the operation is performed.
        :type context: bpy.types.Context
        """
        # Ensure operation is performed in object mode
        bpy.ops.object.mode_set(mode='OBJECT')

        # Setup or retrieve the collection for LODs
        lod_collection_name = obj.name.split("_lod_")[0] + "_lods"
        if lod_collection_name not in bpy.data.collections:
            collection = bpy.data.collections.new(name=lod_collection_name)
            context.scene.collection.children.link(collection)
        else:
            collection = bpy.data.collections[lod_collection_name]

        # Manage the original object and its LODs
        base_name = obj.name.split("_lod_")[0]
        original_obj = obj
        original_obj.name = base_name + "_lod_0"

        # Link the original object if not already in the collection
        if original_obj not in collection.objects.values():
            if original_obj.name in context.collection.objects:
                context.collection.objects.unlink(original_obj)
            collection.objects.link(original_obj)

        # Generate additional LODs
        for i in range(1, self.lod_count + 1):
            new_obj_name = f"{base_name}_lod_{i}"

            # Skip creating LOD if it already exists in the collection
            if any(o.name == new_obj_name for o in collection.objects):
                continue

            # Duplicate and rename the object
            bpy.ops.object.select_all(action='DESELECT')
            original_obj.select_set(True)
            bpy.ops.object.duplicate(linked=False, mode='TRANSLATION')
            new_obj = context.selected_objects[0]
            new_obj.name = new_obj_name

            # Preserving outer boundaries
            vg_name = self._define_preserved_boundaries(new_obj)

            # Apply a Decimate modifier to simplify the mesh
            bpy.context.view_layer.objects.active = new_obj
            bpy.ops.object.modifier_add(type='DECIMATE')

            new_obj.modifiers['Decimate'].use_collapse_triangulate = True
            new_obj.modifiers['Decimate'].vertex_group = vg_name
            new_obj.modifiers['Decimate'].invert_vertex_group = True
            new_obj.modifiers['Decimate'].ratio = max((1.0 - self.reduction_percentage / 100) ** i, 0.01)
            bpy.ops.object.modifier_apply(modifier='Decimate')

            # Link new LOD to the LOD collection
            try:
                collection.objects.link(new_obj)
            except RuntimeError as e:
                print(f"Skipping linking {new_obj.name}: {e}")


class MESH_OT_lod_generator(bpy.types.Operator):
    """Operator to generate LODs for selected mesh objects."""
    bl_idname = LOD_IDNAME
    bl_label = LOD_LABEL

    def execute(self, context):
        """
        Execute the LOD generation process.

        :param context: Context in which the LODs are generated.
        :type context: bpy.types.Context
        :return: Status set indicating the outcome of the operation.
        :rtype: set
        """
        lod_count = context.scene.lod_count
        reduction_percentage = context.scene.reduction_percentage
        lod_generator = LODGenerator(lod_count, reduction_percentage)
        lod_generator.generate_lods(context)
        self.report({'INFO'}, "LOD Generation done.")
        return {'FINISHED'}


class VIEW3D_PT_lod_generator(bpy.types.Panel):
    """Panel for controlling LOD generation settings."""
    bl_label = LOD_PANEL_LABEL
    bl_idname = LOD_PANEL_IDNAME
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Tool'

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        layout.prop(scene, 'lod_count', text="Number of LODs")
        layout.prop(scene, 'reduction_percentage', text="Reduction % per LOD")
        layout.operator(LOD_IDNAME)


classes = (MESH_OT_GenerateLODs, VIEW3D_PT_lod_generator)

def register():
    from bpy.utils import register_class

    for cls in classes:
        register_class(cls)

    bpy.types.Scene.lod_count = bpy.props.IntProperty(name="Number of LODs", default=3, min=1)
    bpy.types.Scene.reduction_percentage = bpy.props.FloatProperty(name="Reduction Percentage", default=50.0, min=1.0,
                                                                   max=99.0)


def unregister():
    from bpy.utils import unregister_class

    for cls in classes:
        unregister_class(cls)

    if hasattr(bpy.types, "lod_count"):
        del bpy.types.Scene.lod_count

    if hasattr(bpy.types, "reduction_percentage"):
        del bpy.types.Scene.reduction_percentage


if __name__ == "__main__":
    register()
