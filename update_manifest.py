import os
import re

# Paths
WHEEL_DIR = "./plugin_src/wheels"
TOML_FILE = "./plugin_src/blender_manifest.toml"

# Get all wheel filenames with "./wheels/" prefix
wheel_files = [f'"./wheels/{f}"' for f in os.listdir(WHEEL_DIR) if f.endswith(".whl")]
wheel_list_str = "wheels = [\n    " + ",\n    ".join(wheel_files) + "\n]"

# Read the existing TOML content
with open(TOML_FILE, "r", encoding="utf-8") as file:
    toml_content = file.read()

# Replace the entire wheels = [...] block (even if multiline)
new_toml_content = re.sub(
    r"wheels\s*=\s*\[[^]]*]",
    wheel_list_str,
    toml_content,
    flags=re.DOTALL
)

# Write the updated content back to the file
with open(TOML_FILE, "w", encoding="utf-8") as file:
    file.write(new_toml_content)

print(f"Updated wheels list with {len(wheel_files)} entries.")
