import os

import bpy
from bpy.props import StringProperty, IntProperty, FloatProperty, PointerProperty, EnumProperty, BoolProperty

from .ds_consts import BAKE_IDNAME, BAKE_LABEL, BAKE_PANEL_IDNAME, BAKE_PANEL_LABEL, BAKE_SETTINGS_IDNAME
from .ds_utils import set_gpu_rendering, set_cpu_rendering


bl_info = {
    "name": "Baker Plugin",
    "author": "Nico Breycha",
    "version": (0, 0, 4),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > Tool Tab",
    "description": "Bakes the base color of a defined mesh onto one or multiple selected meshes.",
    "category": "Object",
}


def bake(highpoly, lowpoly, settings):
    """
    Bakes the base color of a defined mesh onto one or multiple selected meshes.

    :param highpoly: The highpoly mesh
    :type highpoly: bpy.types.Object
    :param lowpoly: The corresponding lowpoly mesh
    :type lowpoly: bpy.types.Object
    :param settings: The settings for the plugin
    :type settings: PluginBakerSettings
    :return:
    """
    # Enable both meshes required for baking.
    highpoly.select_set(True)
    lowpoly.select_set(True)
    bpy.context.view_layer.objects.active = lowpoly

    # Prepare material and image texture node for baking
    lowpoly.data.materials.clear()

    mat = bpy.data.materials.new(name=f"mat_{lowpoly.name}")
    lowpoly.data.materials.append(mat)

    if not mat.use_nodes:
        mat.use_nodes = True

    # Build Node Graph for baking
    nodes = mat.node_tree.nodes
    nodes.clear()

    principled_node = nodes.new("ShaderNodeBsdfPrincipled")
    principled_node.location = 200, 200

    image_node = nodes.new("ShaderNodeTexImage")
    image_node.location = 0, 200

    # Create Material Output node
    material_output = nodes.new("ShaderNodeOutputMaterial")
    material_output.location = 400, 200

    # Adjust texture resolution based on LOD setting
    resolution = settings.texture_resolution

    lod_factor = int(lowpoly.name[-1:])

    if settings.lower_res_by_lod:
        resolution = settings.texture_resolution >> lod_factor

    image_name = f"{lowpoly.name}_albedo"
    image_path = os.path.join(settings.save_path, f"{image_name}.png")
    image = bpy.data.images.new(image_name, width=resolution, height=resolution)
    image_node.image = image

    mat.node_tree.links.new(principled_node.inputs["Base Color"], image_node.outputs["Color"])
    mat.node_tree.links.new(material_output.inputs["Surface"], principled_node.outputs["BSDF"])

    # Set the image node we want to bake on.
    nodes.active = image_node

    # Perform the baking
    bpy.ops.object.bake(type="DIFFUSE", pass_filter={"COLOR"},
                        filepath=os.path.join(settings.save_path, f"{lowpoly.name}.png"),
                        width=resolution, height=resolution,
                        margin=settings.texture_margin, use_selected_to_active=True,
                        cage_extrusion=settings.ray_distance, save_mode="EXTERNAL")

    # Explicitly save the image
    if image.is_dirty:
        image.filepath_raw = image_path
        image.file_format = "PNG"
        image.save()

    # Deselect both meshes to ensure they are not baked in the next iteration
    lowpoly.select_set(False)
    highpoly.select_set(False)


class PluginBakerSettings(bpy.types.PropertyGroup):
    """Settings for the baker plugin."""
    bl_idname = BAKE_SETTINGS_IDNAME
    highpoly_mesh_name: StringProperty(name="Highpoly Mesh")
    ray_distance: FloatProperty(name="Ray Distance", default=0.1, min=0.0, max=100.0)
    texture_resolution: IntProperty(name="Texture Resolution", default=2048, min=512, max=8192)
    lower_res_by_lod: BoolProperty(
        name="Lower Resolution by LOD",
        description="Lower the texture resolution by half for lower levels of detail",
        default=True
    )
    texture_margin: IntProperty(name="Texture Margin", default=16, min=0, max=64)
    save_path: StringProperty(
        name="Save Path",
        subtype="DIR_PATH",
        default="//bakes")
    render_device: EnumProperty(
        name="Render Device",
        description="Choose whether to render using CPU or GPU",
        items=[
            ("GPU", "GPU", "Use GPU for rendering"),
            ("CPU", "CPU", "Use CPU for rendering")
        ],
        default="GPU"
    )


class OBJECT_OT_BakeBaseColor(bpy.types.Operator):
    bl_idname = BAKE_IDNAME
    bl_label = BAKE_LABEL
    bl_description = "Bakes the base color from the highpoly mesh to the selected lowpoly meshes"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.mode == "OBJECT"

    def execute(self, context):
        settings = context.scene.baker_settings
        highpoly = bpy.data.objects.get(settings.highpoly_mesh_name)

        if not highpoly:
            self.report({"ERROR"}, "Highpoly mesh not found")
            return {"CANCELLED"}

        # Store original renderer for later restore.
        original_renderer = bpy.context.scene.render.engine

        # Set the render device based on user settings
        if settings.render_device == "GPU":
            set_gpu_rendering()
        else:
            set_cpu_rendering()

        # Determine Meshes to be baked and disable all initially.
        lowpolys = [obj for obj in bpy.context.selected_objects if obj.type == "MESH" and obj != highpoly]
        bpy.ops.object.select_all(action="DESELECT")

        # Vars for tracking progress
        lowpoly_cnt = len(lowpolys)
        progress_cnt = 1

        # Bake the Lowpoly Meshes one by one.
        for lowpoly in lowpolys:
            # Skip empty meshes
            if len(lowpoly.data.polygons) == 0:
                continue

            print(f"Progress: {progress_cnt}/{lowpoly_cnt}")
            bake(highpoly, lowpoly, settings)
            progress_cnt += 1

        # Restore original render engine
        bpy.context.scene.render.engine = original_renderer
        self.report({"INFO"}, "Baking completed")
        return {"FINISHED"}


class VIEW3D_PT_texture_transfer(bpy.types.Panel):
    bl_label = BAKE_PANEL_LABEL
    bl_idname = BAKE_PANEL_IDNAME
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Tool"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.baker_settings

        layout.prop_search(settings, "highpoly_mesh_name", bpy.data, "objects")
        layout.prop(settings, "ray_distance")
        layout.prop(settings, "texture_resolution")
        layout.prop(settings, "lower_res_by_lod")
        layout.prop(settings, "texture_margin")
        layout.prop(settings, "save_path")
        layout.prop(settings, "render_device")
        layout.operator(BAKE_IDNAME)
        layout.label(
            text=f"Lowpoly count: {len([obj for obj in bpy.context.selected_objects if obj.type == 'MESH' and obj.name != settings.highpoly_mesh_name])}")


classes = (PluginBakerSettings, OBJECT_OT_BakeBaseColor, VIEW3D_PT_texture_transfer)


def register():
    from bpy.utils import register_class

    for cls in classes:
        register_class(cls)

    bpy.types.Scene.baker_settings = PointerProperty(type=PluginBakerSettings)


def unregister():
    from bpy.utils import unregister_class

    for cls in reversed(classes):
        unregister_class(cls)

    if hasattr(bpy.types.Scene, "baker_settings"):
        del bpy.types.Scene.baker_settings


if __name__ == "__main__":
    register()
