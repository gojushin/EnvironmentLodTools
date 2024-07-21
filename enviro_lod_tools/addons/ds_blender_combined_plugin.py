import os
import bpy

from .ds_consts import CLEANUP_IDNAME, BAKE_IDNAME, UNWRAP_IDNAME, SLICE_IDNAME, COMB_IDNAME, LOD_IDNAME, COMB_LABEL, COMB_PANEL_LABEL, COMB_PANEL_IDNAME
from .ds_blender_baker_plug import PluginBakerSettings


bl_info = {
    "name": "Automated LOD Generation Tool",
    "author": "Nico Breycha",
    "version": (0, 0, 1),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > Tool Tab",
    "description": "Combines the Operator from all the other plugins.",
    "category": "Object",
}


def _execute_operator(op_string):
    def operation():
        try:
            # Split the operator string into its components
            area, op = op_string.split(".")

            # Dynamically access and call the operator from bpy.ops
            getattr(getattr(bpy.ops, area), op)()
            print(f"Operator {op_string} executed successfully.")
        except AttributeError:
            print(f"Error: Operator {op_string} does not exist.")
        except RuntimeError as e:
            print(f"Runtime Error: {e}")

    return operation


def _clear_initial_scene():
    # Deselect all objects
    bpy.ops.object.select_all(action='DESELECT')

    # Select all objects and delete
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

    # Remove all meshes, lamps, cameras and other data blocks still in memory and unused
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


cleanup_op = _execute_operator(CLEANUP_IDNAME)
slice_op = _execute_operator(SLICE_IDNAME)
lod_op = _execute_operator(LOD_IDNAME)
unwrap_op = _execute_operator(UNWRAP_IDNAME)
bake_op = _execute_operator(BAKE_IDNAME)


class OBJECT_OT_lod_pipeline(bpy.types.Operator):
    bl_idname = COMB_IDNAME
    bl_label = COMB_LABEL

    def execute(self, context):
        _clear_initial_scene()

        # IO
        import_fp_comb = context.scene.import_fp_comb
        export_fp_comb = context.scene.export_fp_comb

        # Cleanup Properties
        poly_count_comb = context.scene.poly_count_comb
        boundary_length_comb = context.scene.boundary_length_comb
        iterations_comb = context.scene.iterations_comb
        merge_threshold_comb = context.scene.merge_threshold_comb

        # Slice Properties
        num_of_modules_comb = context.scene.num_of_modules_comb

        # LoD Properties
        lod_count_comb = context.scene.lod_count_comb
        reduction_percentage_comb = context.scene.reduction_percentage_comb

        # Unwrap Properties
        # None for Now

        # Bake Properties
        baker_settings_comb: PluginBakerSettings = context.scene.baker_settings_comb

        blend_file_path = os.path.join(export_fp_comb, "bake_scene.blend")

        bpy.ops.wm.save_as_mainfile(filepath=blend_file_path, check_existing=False, compress=True)

        bpy.ops.object.select_all(action='DESELECT')
        # Import Model
        bpy.ops.wm.obj_import(filepath=import_fp_comb)

        bpy.ops.object.select_all(action='DESELECT')

        for obj in bpy.data.objects:
            if obj.type == 'MESH':
                obj.select_set(True)
                bpy.context.view_layer.objects.active = obj  # Set one of the meshes as active

        # Join them into a single object
        bpy.ops.object.join()

        original_mesh = bpy.context.active_object
        baker_settings_comb.highpoly_mesh_name = original_mesh.data.name

        # Duplicate the object
        bpy.ops.object.duplicate()

        working_mesh = bpy.context.active_object

        working_mesh.select_set(False)
        original_mesh.select_set(False)
        bpy.ops.object.select_all(action='DESELECT')

        working_mesh.select_set(True)
        bpy.context.view_layer.objects.active = working_mesh

        cleanup_op()
        slice_op()

        for obj in bpy.data.objects:
            if obj != original_mesh:
                obj.select_set(True)
            else:
                obj.select_set(False)

        lod_op()

        for obj in bpy.data.objects:
            if obj != original_mesh:
                obj.select_set(True)
            else:
                obj.select_set(False)

        unwrap_op()

        for obj in bpy.data.objects:
            if obj != original_mesh:
                obj.select_set(True)
            else:
                obj.select_set(False)

        bake_op()

        bpy.ops.wm.save_as_mainfile(filepath=blend_file_path, check_existing=False, compress=True)

        bpy.data.objects.remove(original_mesh)

        for tex in bpy.data.textures:
            if tex.users == 0:
                bpy.data.textures.remove(tex)

        for obj in bpy.data.objects:
            if obj.type == 'MESH':
                obj.select_set(True)
                export_path = os.path.join(export_fp_comb, obj.name + '.obj')
                bpy.ops.export_scene.obj(filepath=export_path, use_selection=True)

        self.report({'INFO'}, "Export completed successfully.")
        return {'FINISHED'}


class VIEW3D_PT_lod_pipeline(bpy.types.Panel):
    """Panel to set parameters and execute the pipeline cleaning"""
    bl_label = COMB_PANEL_LABEL
    bl_idname = COMB_PANEL_IDNAME
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Tools'

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        io_box = layout.box()
        io_box.prop(scene, "import_fp_comb", text="Import Filepath")
        io_box.prop(scene, "export_fp_comb", text="Export Filepath")

        # Create a box for Cleanup Properties and add labeled properties
        cleanup_box = layout.box()
        cleanup_box.label(text="Cleanup Properties")
        cleanup_box.prop(scene, "poly_count_comb", text="Vertex Threshold")
        cleanup_box.prop(scene, "boundary_length_comb", text="Boundary Length")
        cleanup_box.prop(scene, "iterations_comb", text="Iterations")
        cleanup_box.prop(scene, "merge_threshold_comb", text="Merge Threshold")

        # Create a box for Slice Properties and add labeled properties
        slice_box = layout.box()
        slice_box.label(text="Slice Properties")
        slice_box.prop(scene, "num_of_modules_comb", text="Number of Modules")

        # Create a box for LoD Properties and add labeled properties
        lod_box = layout.box()
        lod_box.label(text="Level of Detail Properties")
        lod_box.prop(scene, "lod_count_comb", text="Number of LODs")
        lod_box.prop(scene, "reduction_percentage_comb", text="Reduction %")

        # Bake Properties
        settings = context.scene.baker_settings

        layout.prop_search(settings, "highpoly_mesh_name", bpy.data, "objects")
        layout.prop(settings, "ray_distance_comb")
        layout.prop(settings, "texture_resolution_comb")
        layout.prop(settings, "texture_margin_comb")
        layout.prop(settings, "save_path_comb")
        layout.operator("object.bake_base_color_comb")
        layout.label(text=f"Lowpoly count: {len([obj for obj in bpy.context.selected_objects if obj.type == 'MESH' and obj.name != settings.highpoly_mesh_name])}")

        # Add a button to execute the LOD generation operator
        layout.operator(COMB_IDNAME, text="Generate LODs")


classes = (OBJECT_OT_lod_pipeline, VIEW3D_PT_lod_pipeline)


def register():
    from bpy.utils import register_class

    for cls in classes:
        register_class(cls)

    # Cleanup Properties
    bpy.types.Scene.poly_count_comb = bpy.props.IntProperty(name="Loose Component Vertex Thr", default=1000)
    bpy.types.Scene.boundary_length_comb = bpy.props.IntProperty(name="Max Boundary Length", default=1000)
    bpy.types.Scene.iterations_comb = bpy.props.IntProperty(name="Iterations", default=20)
    bpy.types.Scene.merge_threshold_comb = bpy.props.FloatProperty(name="Merge Threshold", default=0.000001)

    # Slice Properties
    bpy.types.Scene.num_of_modules_comb = bpy.props.IntProperty(name="Number of Modules", default=16, min=1)

    # LoD Properties
    bpy.types.Scene.lod_count_comb = bpy.props.IntProperty(name="Number of LODs", default=3, min=1)
    bpy.types.Scene.reduction_percentage_comb = bpy.props.FloatProperty(name="Reduction Percentage", default=50.0, min=1.0, max=99.0)

    # Unwrap Properties
    # None for Now

    # Bake Properties
    bpy.types.Scene.baker_settings_comb = bpy.props.PointerProperty(type=PluginBakerSettings)

    # Combined Properties
    bpy.types.Scene.import_fp_comb = bpy.props.StringProperty(name="Import FP")
    bpy.types.Scene.export_fp_comb = bpy.props.StringProperty(name="Export FP")


def unregister():
    from bpy.utils import unregister_class

    for cls in classes:
        unregister_class(cls)

    del bpy.types.Scene.baker_settings_comb
    del bpy.types.Scene.poly_count_comb
    del bpy.types.Scene.boundary_length_comb
    del bpy.types.Scene.iterations_comb
    del bpy.types.Scene.merge_threshold_comb
    del bpy.types.Scene.num_of_modules_comb
    del bpy.types.Scene.lod_count_comb
    del bpy.types.Scene.reduction_percentage_comb
    del bpy.types.Scene.import_fp_comb
    del bpy.types.Scene.export_fp_comb


if __name__ == "__main__":
    register()
