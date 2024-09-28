import os
import copy
import math
from datetime import datetime

import bpy

from .ds_consts import (CLEANUP_IDNAME, BAKE_IDNAME, UNWRAP_IDNAME, SLICE_IDNAME, COMB_IDNAME, LOD_IDNAME, COMB_LABEL,
                        COMB_PANEL_LABEL, COMB_PANEL_IDNAME, ASCII_ART)
from .ds_blender_baker_plug import PluginBakerSettings
from .ds_utils import clear_scene, launch_operator_by_name, merge_meshes


bl_info = {
    "name": "Automated LOD Generation Tool",
    "author": "Nico Breycha",
    "version": (0, 0, 5),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > Tool Tab",
    "description": "Combines the Operator from all the other plugins.",
    "category": "Object",
}


class OBJECT_OT_lod_pipeline(bpy.types.Operator):
    bl_idname = COMB_IDNAME
    bl_label = COMB_LABEL

    def execute(self, context):
        def import_and_prepare_original_mesh(filepath, rotation_correction, keep_original_name = False):
            # Get list of existing objects before import
            existing_objects = set(bpy.data.objects)

            # Import the model
            bpy.ops.wm.obj_import(filepath=filepath)

            # Get the list of new objects
            imported_objects = [_obj for _obj in bpy.data.objects if _obj not in existing_objects]

            # Filter only meshes
            meshes = [_obj for _obj in imported_objects if _obj.type == "MESH"]

            if not meshes:
                raise ValueError("No meshes imported")

            # Use the first mesh as the base mesh, and merge others into it
            base_mesh = meshes[0]
            additional_meshes = meshes[1:]

            if additional_meshes:
                base_mesh = merge_meshes(base_mesh, additional_meshes, return_bm=False)

            # Apply rotation correction manually
            rotation_matrix = base_mesh.matrix_world.to_euler()
            rotation_matrix.x += math.radians(rotation_correction[0])
            rotation_matrix.y += math.radians(rotation_correction[1])
            rotation_matrix.z += math.radians(rotation_correction[2])
            base_mesh.matrix_world = rotation_matrix.to_matrix().to_4x4()

            # If name change is needed, change the object's name
            if not keep_original_name:
                base_mesh.name = "original_mesh"
                base_mesh.data.name = "original_mesh"

            return base_mesh

        clear_scene()

        # IO
        import_fp_comb = context.scene.import_fp_comb
        export_fp_comb = context.scene.export_fp_comb

        # Preprocessing
        rot_correction_comb = context.scene.rot_correction_comb

        # Cleanup Properties
        initial_reduction_comb = context.scene.initial_reduction_comb
        loose_threshold_comb = context.scene.loose_threshold_comb
        boundary_length_comb = context.scene.boundary_length_comb
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
        baker_settings_comb.save_path = export_fp_comb

        # Save Operator Properties for later restore

        restore_dict = {
            "initial_reduction": context.scene.initial_reduction,
            "loose_threshold": context.scene.loose_threshold,
            "boundary_length": context.scene.boundary_length,
            "merge_threshold": context.scene.merge_threshold,
            "number_of_modules": context.scene.number_of_modules,
            "lod_count": context.scene.lod_count,
            "reduction_percentage": context.scene.reduction_percentage,
            "baker_settings": context.scene.baker_settings
                         }

        # Preserve the original values of the properties with shallow copy.
        restore_dict = copy.copy(restore_dict)

        # Override Operator Properties for non-comb components
        context.scene.initial_reduction = initial_reduction_comb
        context.scene.loose_threshold = loose_threshold_comb
        context.scene.boundary_length = boundary_length_comb
        context.scene.merge_threshold = merge_threshold_comb
        context.scene.number_of_modules = num_of_modules_comb
        context.scene.lod_count = lod_count_comb
        context.scene.reduction_percentage = reduction_percentage_comb

        # Highpoly name is changed later, as we modify it later in the script
        context.scene.baker_settings.ray_distance = baker_settings_comb.ray_distance
        context.scene.baker_settings.render_device = baker_settings_comb.render_device
        context.scene.baker_settings.texture_resolution = baker_settings_comb.texture_resolution
        context.scene.baker_settings.lower_res_by_lod = baker_settings_comb.lower_res_by_lod
        context.scene.baker_settings.texture_margin = baker_settings_comb.texture_margin
        context.scene.baker_settings.save_path = baker_settings_comb.save_path

        working_mesh = import_and_prepare_original_mesh(import_fp_comb, rot_correction_comb, keep_original_name=True)

        # Make sure only the working mesh is selected.
        bpy.ops.object.select_all(action='DESELECT')
        working_mesh.select_set(True)
        bpy.context.view_layer.objects.active = working_mesh

        # Execute Operators
        print("Current time: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        print(ASCII_ART["CLEANUP"])
        launch_operator_by_name(CLEANUP_IDNAME)

        print("Current time: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        print(ASCII_ART["SLICING"])
        launch_operator_by_name(SLICE_IDNAME)

        blend_file_path = os.path.join(export_fp_comb, "sliced_scene.blend")
        bpy.ops.wm.save_as_mainfile(filepath=blend_file_path, check_existing=False, compress=True)

        # Ensure Target Poly Count set by the user as initial poly count.
        parts = set()

        for obj in bpy.data.objects:
            if obj.type == "MESH":
                parts.add(obj)

        for part in parts:
            part.select_set(True)

        print("Current time: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        print(ASCII_ART["LOD"])
        launch_operator_by_name(LOD_IDNAME)

        objects_to_bake = {obj for obj in bpy.data.objects if obj.type == "MESH"}

        for obj in objects_to_bake:
            obj.select_set(True)

        print("Current time: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        print(ASCII_ART["UNWRAPPING"])
        launch_operator_by_name(UNWRAP_IDNAME)

        original_mesh = import_and_prepare_original_mesh(import_fp_comb, rot_correction_comb, keep_original_name=False)
        context.scene.baker_settings.highpoly_mesh_name = original_mesh.name

        for obj in objects_to_bake:
            obj.vertex_groups.clear() # Clear a little non-relevant data along the way.
            obj.select_set(True)

        print("Current time: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        print(ASCII_ART["BAKING"])
        launch_operator_by_name(BAKE_IDNAME)

        print("Current time: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        print("Done Baking")

        # Remove the original mesh from the scene before export.
        original_mesh.select_set(True)
        bpy.ops.object.delete()

        # Export newly created objects.
        for obj in objects_to_bake:
            # Deselect all objects
            bpy.ops.object.select_all(action="DESELECT")

            # Select the object to export
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj

            export_path = os.path.join(export_fp_comb, obj.name + ".obj")
            bpy.ops.wm.obj_export(filepath=export_path, export_selected_objects=True)

        # Restore Operator Properties
        context.scene.initial_reduction = restore_dict["initial_reduction"]
        context.scene.loose_threshold = restore_dict["loose_threshold"]
        context.scene.boundary_length = restore_dict["boundary_length"]
        context.scene.merge_threshold = restore_dict["merge_threshold"]
        context.scene.number_of_modules = restore_dict["number_of_modules"]
        context.scene.lod_count = restore_dict["lod_count"]
        context.scene.reduction_percentage = restore_dict["reduction_percentage"]

        context.scene.baker_settings.highpoly_mesh_name = restore_dict["baker_settings"].highpoly_mesh_name
        context.scene.baker_settings.ray_distance = restore_dict["baker_settings"].ray_distance
        context.scene.baker_settings.render_device = restore_dict["baker_settings"].render_device
        context.scene.baker_settings.texture_resolution = restore_dict["baker_settings"].texture_resolution
        context.scene.baker_settings.lower_res_by_lod = restore_dict["baker_settings"].lower_res_by_lod
        context.scene.baker_settings.texture_margin = restore_dict["baker_settings"].texture_margin
        context.scene.baker_settings.save_path = restore_dict["baker_settings"].save_path

        blend_file_path = os.path.join(export_fp_comb, "cleaned_scene.blend")
        bpy.ops.wm.save_as_mainfile(filepath=blend_file_path, check_existing=False, compress=True)

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
        io_box.prop(scene, "rot_correction_comb", text="Rotation Correction")
        io_box.prop(scene, "export_fp_comb", text="Export Filepath")

        # Create a box for Cleanup Properties and add labeled properties
        cleanup_box = layout.box()
        cleanup_box.label(text="Cleanup Properties")
        cleanup_box.prop(scene, "initial_reduction_comb", text="First Reduction Target")
        cleanup_box.prop(scene, "loose_threshold_comb", text="Loose Component Threshold.")
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

    # Preprocessing Properties
    bpy.types.Scene.rot_correction_comb = bpy.props.FloatVectorProperty(name="Initial Rotation Correction",
                                                                        default=(0.0, 0.0, 0.0), subtype="EULER")

    # Cleanup Properties
    bpy.types.Scene.initial_reduction_comb = bpy.props.IntProperty(name="Initial Reduction", default=1000000)
    bpy.types.Scene.loose_threshold_comb = bpy.props.IntProperty(name="Loose Component Vertex Thr", default=1000)
    bpy.types.Scene.boundary_length_comb = bpy.props.IntProperty(name="Max Boundary Length", default=1000)
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

    for cls in reversed(classes):
        unregister_class(cls)

    # Cleanup Properties
    del bpy.types.Scene.rot_correction_comb
    del bpy.types.Scene.initial_reduction_comb
    del bpy.types.Scene.baker_settings_comb
    del bpy.types.Scene.loose_threshold_comb
    del bpy.types.Scene.boundary_length_comb
    del bpy.types.Scene.merge_threshold_comb
    del bpy.types.Scene.num_of_modules_comb
    del bpy.types.Scene.lod_count_comb
    del bpy.types.Scene.reduction_percentage_comb
    del bpy.types.Scene.import_fp_comb
    del bpy.types.Scene.export_fp_comb


if __name__ == "__main__":
    register()
