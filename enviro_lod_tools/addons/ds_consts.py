import os.path

CLEANUP_IDNAME = "mesh.clean_mesh_operator"
CLEANUP_LABEL = "Clean selection"
CLEANUP_PANEL_IDNAME = "MESH_PT_clean"
CLEANUP_PANEL_LABEL = "Mesh Pre-Processing"

SLICE_IDNAME = "mesh.mesh_slicer_operator"
SLICE_LABEL = "Slice selection"
SLICE_PANEL_IDNAME = "MESH_PT_slice"
SLICE_PANEL_LABEL = "Mesh Slicing"

LOD_IDNAME = "mesh.lod_gen_operator"
LOD_LABEL = "Create LODs"
LOD_PANEL_IDNAME = "MESH_PT_lod"
LOD_PANEL_LABEL = "LOD Creation"

UNWRAP_IDNAME = "mesh.xatlas_unwrap_operator"
UNWRAP_LABEL = "Unwrap (xAtlas)"
UNWRAP_PANEL_IDNAME = "MESH_PT_xatlas_unwrap"
UNWRAP_PANEL_LABEL = "xAtlas Unwrapping"

BAKE_IDNAME = "mesh.multi_bake_operator"
BAKE_LABEL = "Bake selection"
BAKE_PANEL_IDNAME = "MESH_PT_bake"
BAKE_PANEL_LABEL = "Texture Transfer"
BAKE_SETTINGS_IDNAME = "prop.bake_settings"

COMB_IDNAME = "mesh.terrestrial_lod_gen_operator"
COMB_LABEL = "Run Pipeline"
COMB_PANEL_IDNAME = "MESH_PT_terrestrial_lod"
COMB_PANEL_LABEL = "Combined Pipeline"

EXTERNAL_FOLDER = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "external"))

XATLAS_MODULE_NAME = "xatlas"
PYFQMR_MODULE_NAME = "pyfqmr"

ASCII_ART = {
"CLEANUP":
"""
  _____ _                  _             
 / ____| |                (_)            
| |    | | ___  __ _ _ __  _ _ __   __ _ 
| |    | |/ _ \/ _` | '_ \| | '_ \ / _` |
| |____| |  __/ (_| | | | | | | | | (_| |
 \_____|_|\___|\__,_|_| |_|_|_| |_|\__, |
                                    __/ |
                                   |___/ 
""",
"SLICING": """
  _____ _ _      _             
 / ____| (_)    (_)            
| (___ | |_  ___ _ _ __   __ _ 
 \___ \| | |/ __| | '_ \ / _` |
 ____) | | | (__| | | | | (_| |
|_____/|_|_|\___|_|_| |_|\__, |
                          __/ |
                         |___/ 
""",
"LOD": """
 _      ____  _____     _____              
| |    / __ \|  __ \   / ____|             
| |   | |  | | |  | | | |  __  ___ _ __    
| |   | |  | | |  | | | | |_ |/ _ \ '_ \   
| |___| |__| | |__| | | |__| |  __/ | | |_ 
|______\____/|_____/   \_____|\___|_| |_(_)                  
""",
"UNWRAPPING": """
 _    _                               
| |  | |                              
| |  | |_ ____      ___ __ __ _ _ __  
| |  | | '_ \ \ /\ / / '__/ _` | '_ \ 
| |__| | | | \ V  V /| | | (_| | |_) |
 \____/|_| |_|\_/\_/ |_|  \__,_| .__/ 
                               | |    
                               |_|    
""",
"BAKING": """
 ____        _    _             
|  _ \      | |  (_)            
| |_) | __ _| | ___ _ __   __ _ 
|  _ < / _` | |/ / | '_ \ / _` |
| |_) | (_| |   <| | | | | (_| |
|____/ \__,_|_|\_\_|_| |_|\__, |
                           __/ |
                          |___/ 
"""
}
