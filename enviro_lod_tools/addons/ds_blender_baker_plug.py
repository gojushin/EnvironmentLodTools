import bpy
import os
from bpy.props import StringProperty, IntProperty, FloatProperty, PointerProperty
from bpy_extras.io_utils import ImportHelper

from .ds_consts import BAKE_IDNAME, BAKE_LABEL, BAKE_PANEL_IDNAME, BAKE_PANEL_LABEL, BAKE_SETTINGS_IDNAME

bl_info = {
    "name": "Baker Plugin",
    "author": "Nico Breycha",
    "version": (0, 0, 1),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > Tool Tab",
    "description": "Bakes the base color of a defined mesh onto one or multiple selected meshes.",
    "category": "Object",
}


class PluginBakerSettings(bpy.types.PropertyGroup):
    """Settings for the baker plugin."""
    bl_idname = BAKE_SETTINGS_IDNAME
    highpoly_mesh_name: StringProperty(name="Highpoly Mesh")
    ray_distance: FloatProperty(name="Ray Distance", default=0.1, min=0.0, max=10.0)
    texture_resolution: IntProperty(name="Texture Resolution", default=2048, min=512, max=8192)
    texture_margin: IntProperty(name="Texture Margin", default=16, min=0, max=64)
    save_path: StringProperty(
        name="Save Path",
        subtype='DIR_PATH',
        default="//bakes"
    )


class OBJECT_OT_BakeBaseColor(bpy.types.Operator):
    bl_idname = BAKE_IDNAME
    bl_label = BAKE_LABEL
    bl_description = "Bakes the base color from the highpoly mesh to the selected lowpoly meshes"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.mode == 'OBJECT'

    def execute(self, context):
        settings = context.scene.baker_settings
        highpoly = bpy.data.objects.get(settings.highpoly_mesh_name)
        if not highpoly:
            self.report({'ERROR'}, "Highpoly mesh not found")
            return {'CANCELLED'}

        original_renderer = bpy.context.scene.render.engine
        bpy.context.scene.render.engine = 'CYCLES'

        lowpolys = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH' and obj != highpoly]

        for lowpoly in lowpolys:
            self.bake(highpoly, lowpoly, settings)

        bpy.context.scene.render.engine = original_renderer
        self.report({'INFO'}, "Baking completed")
        return {'FINISHED'}

    def bake(self, highpoly, lowpoly, settings):
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
        # Ensure the lowpoly object is the active object
        bpy.context.view_layer.objects.active = lowpoly
        highpoly.select_set(True)
        lowpoly.select_set(True)

        # Prepare material and image texture node for baking
        lowpoly.data.materials.clear()

        mat = bpy.data.materials.new(name=f"{lowpoly.name}_Material")
        lowpoly.data.materials.append(mat)

        if not mat.use_nodes:
            mat.use_nodes = True

        nodes = mat.node_tree.nodes
        nodes.clear()  # Clear existing nodes to start fresh

        principled_node = nodes.new('ShaderNodeBsdfPrincipled')
        principled_node.location = 200, 200

        image_node = nodes.new('ShaderNodeTexImage')
        image_node.location = 0, 200

        # Create Material Output node
        material_output = nodes.new('ShaderNodeOutputMaterial')
        material_output.location = 400, 200

        image_name = f"{lowpoly.name}_Bake"
        image_path = os.path.join(settings.save_path, f"{image_name}.png")
        image = bpy.data.images.new(image_name, width=settings.texture_resolution, height=settings.texture_resolution)
        image_node.image = image

        mat.node_tree.links.new(principled_node.inputs['Base Color'], image_node.outputs['Color'])
        mat.node_tree.links.new(material_output.inputs['Surface'], principled_node.outputs['BSDF'])

        nodes.active = image_node

        # Perform the baking
        bpy.ops.object.bake(type='DIFFUSE', filepath=os.path.join(settings.save_path, f"{lowpoly.name}.png"),
                            width=settings.texture_resolution, height=settings.texture_resolution,
                            margin=settings.texture_margin, use_selected_to_active=True,
                            cage_extrusion=settings.ray_distance, save_mode='EXTERNAL',
                            cage_object=highpoly.name)

        # Explicitly save the image
        if image.is_dirty:
            image.filepath_raw = image_path
            image.file_format = 'PNG'
            image.save()

        lowpoly.select_set(False)
        highpoly.select_set(False)


class VIEW3D_PT_texture_transfer(bpy.types.Panel):
    bl_label = BAKE_PANEL_LABEL
    bl_idname = BAKE_PANEL_IDNAME
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Tool'

    def draw(self, context):
        layout = self.layout
        settings = context.scene.baker_settings

        layout.prop_search(settings, "highpoly_mesh_name", bpy.data, "objects")
        layout.prop(settings, "ray_distance")
        layout.prop(settings, "texture_resolution")
        layout.prop(settings, "texture_margin")
        layout.prop(settings, "save_path")
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

    if hasattr(bpy.types.Scene, 'baker_settings'):
        del bpy.types.Scene.baker_settings


if __name__ == "__main__":
    register()
