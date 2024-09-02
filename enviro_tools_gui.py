import os
import sys
import time
from importlib.metadata import distribution, PackageNotFoundError

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton,
    QFileDialog, QLabel, QSpinBox, QDoubleSpinBox, QComboBox,
    QMessageBox, QGroupBox, QHBoxLayout, QFrame, QLineEdit
)

from enviro_lod_tools.addons.ds_utils import launch_operator_by_name
from enviro_lod_tools.addons.ds_consts import COMB_IDNAME
import deploy

SCRIPT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__)))
PLUGIN_BASENAME = "enviro_lod_tools"
PLUGIN_FILE = os.path.join(SCRIPT_DIR, f"{PLUGIN_BASENAME}.zip")
PLUGIN_DIR = os.path.join(SCRIPT_DIR, PLUGIN_BASENAME)


def calculate_polycount(file_path):
    """
    Calculates the number of polygons in a .obj file
    :param file_path: The path to the .obj file
    :type file_path: str
    :return: The number of polygons
    :rtype: int
    """
    if not os.path.isfile(file_path):
        return 0

    polycount = 0
    with open(file_path, "r") as file:
        for line in file:
            if line.startswith("f "):
                polycount += 1
    return polycount


class ModelProcessorGUI(QWidget):
    def __init__(self):
        super().__init__()

        # Styling
        self.setWindowTitle("Environment LOD Tools")
        self.resize(450, 600)
        self.setMinimumWidth(450)

        self.setWindowIcon(QIcon("elt_icon.png"))
        with open("style.qss", "r") as f:
            _style = f.read()
            app.setStyleSheet(_style)

        # Content

        layout = QVBoxLayout()

        # IO Section

        # IO Group Box
        io_group = QGroupBox("IO")
        io_layout = QVBoxLayout()
        io_group.setLayout(io_layout)

        # Highpoly Model Selection
        highpoly_layout = QHBoxLayout()
        self.highpoly_model_line_edit = QLineEdit("No file selected")
        highpoly_model_btn = QPushButton("Select Highpoly Model")
        highpoly_model_btn.setFixedWidth(175)
        highpoly_model_btn.clicked.connect(self.select_highpoly_model)
        self.polycount_label = QLabel("N/A")
        highpoly_layout.addWidget(self.highpoly_model_line_edit)
        highpoly_layout.addWidget(highpoly_model_btn)
        io_layout.addLayout(highpoly_layout)
        io_layout.addWidget(self.polycount_label)

        # Rotate Highpoly Input
        rotate_layout = QHBoxLayout()
        self.rotate_label = QLabel("Rotate Highpoly Input:")
        self.rotation_correction = QComboBox()
        self.rotation_correction.addItems(["No Rotation", "-90 on X (Metashape)"])
        rotate_layout.addWidget(self.rotate_label)
        rotate_layout.addWidget(self.rotation_correction)
        io_layout.addLayout(rotate_layout)

        # Horizontal Line as Separator
        h_line = QFrame()
        h_line.setFrameShape(QFrame.HLine)
        h_line.setFrameShadow(QFrame.Sunken)
        io_layout.addWidget(h_line)

        # Export Path Selection
        export_path_layout = QHBoxLayout()
        self.export_path_line_edit = QLineEdit("No path selected")
        export_path_btn = QPushButton("Select Export Path")
        export_path_btn.setFixedWidth(175)
        export_path_btn.clicked.connect(self.select_export_path)
        export_path_layout.addWidget(self.export_path_line_edit)
        export_path_layout.addWidget(export_path_btn)
        io_layout.addLayout(export_path_layout)  # Add the horizontal layout to the vertical layout

        # Cleanup Properties Section
        cleanup_group = QGroupBox("Cleanup Properties")
        cleanup_layout = QVBoxLayout()

        self.initial_reduction_polycount = QSpinBox()
        self.initial_reduction_polycount.setRange(0, 10000000)
        self.initial_reduction_polycount.setValue(1000000)
        self.loose_comp_threshold = QSpinBox()
        self.loose_comp_threshold.setRange(0, 10000)
        self.loose_comp_threshold.setValue(1000)
        self.boundary_length = QSpinBox()
        self.boundary_length.setRange(1, 100000)
        self.boundary_length.setValue(1000)
        self.merge_threshold = QDoubleSpinBox()
        self.merge_threshold.setRange(0.0001, 0.1)
        self.merge_threshold.setDecimals(4)
        self.merge_threshold.setSingleStep(0.0001)
        self.merge_threshold.setValue(0.0001)

        # Create Horizontal Layouts for each set of controls
        for label_text, widget in [("Initial Reduction Polycount", self.initial_reduction_polycount),
                                   ("Vertex Threshold", self.loose_comp_threshold),
                                   ("Boundary Length", self.boundary_length),
                                   ("Merge Threshold", self.merge_threshold)]:
            h_layout = QHBoxLayout()
            h_layout.addWidget(QLabel(label_text))
            h_layout.addWidget(widget)
            cleanup_layout.addLayout(h_layout)

        cleanup_group.setLayout(cleanup_layout)

        # Slice Properties Section
        slice_group = QGroupBox("Slice Properties")
        slice_layout = QVBoxLayout()

        self.num_modules = QComboBox()
        self.num_modules.addItems(["1", "4", "9", "16", "64", "256"])
        self.num_modules.setCurrentText("16")
        num_modules_layout = QHBoxLayout()
        num_modules_layout.addWidget(QLabel("Number of Modules"))
        num_modules_layout.addWidget(self.num_modules)
        slice_layout.addLayout(num_modules_layout)

        slice_group.setLayout(slice_layout)

        # Level of Detail Properties Section
        lod_group = QGroupBox("Level of Detail Properties")
        lod_layout = QVBoxLayout()

        self.num_lods = QSpinBox()
        self.num_lods.setRange(0, 3)
        self.num_lods.setValue(2)
        self.reduction_percentage = QDoubleSpinBox()
        self.reduction_percentage.setRange(0.0, 100.0)
        self.reduction_percentage.setValue(50.0)

        for label_text, widget in [("Number of LODs", self.num_lods),
                                   ("Reduction Percentage", self.reduction_percentage)]:
            h_layout = QHBoxLayout()
            h_layout.addWidget(QLabel(label_text))
            h_layout.addWidget(widget)
            lod_layout.addLayout(h_layout)

        lod_group.setLayout(lod_layout)

        # Bake Settings Section
        bake_group = QGroupBox("Bake Settings")
        bake_layout = QVBoxLayout()

        self.texture_resolution = QComboBox()
        self.texture_resolution.addItems(["256", "512", "1024", "2048", "4096"])
        self.texture_resolution.setCurrentText("1024")
        texture_resolution_layout = QHBoxLayout()
        texture_resolution_layout.addWidget(QLabel("Texture Resolution"))
        texture_resolution_layout.addWidget(self.texture_resolution)

        self.ray_distance = QDoubleSpinBox()
        self.ray_distance.setRange(0.01, 1)
        self.ray_distance.setValue(0.1)
        self.ray_distance.setSingleStep(0.01)
        ray_distance_layout = QHBoxLayout()
        ray_distance_layout.addWidget(QLabel("Ray Distance"))
        ray_distance_layout.addWidget(self.ray_distance)

        bake_layout.addLayout(texture_resolution_layout)
        bake_layout.addLayout(ray_distance_layout)
        bake_group.setLayout(bake_layout)

        # Start Button
        start_btn = QPushButton("Start")
        start_btn.clicked.connect(self.start_pipeline)

        module_found_layout = QHBoxLayout()
        module_found_layout.setAlignment(Qt.AlignCenter)

        self.numpy_found_label = QLabel("Checking...")
        self.bpy_found_label = QLabel("Checking...")
        self.xatlas_found_label = QLabel("Checking...")
        module_found_layout.addWidget(self.numpy_found_label)
        module_found_layout.addSpacing(20)
        module_found_layout.addWidget(self.bpy_found_label)
        module_found_layout.addSpacing(20)
        module_found_layout.addWidget(self.xatlas_found_label)

        # Add all groups to the main layout
        layout.addWidget(io_group)
        layout.addWidget(cleanup_group)
        layout.addWidget(slice_group)
        layout.addWidget(lod_group)
        layout.addWidget(bake_group)
        layout.addWidget(start_btn)
        layout.addLayout(module_found_layout)

        self.setLayout(layout)

        self.all_modules_installed = True
        self.all_modules_installed &= self.check_module("numpy")
        self.all_modules_installed &= self.check_module("bpy")
        self.all_modules_installed &= self.check_module("xatlas")

    def check_module(self, module_name):
        """
        Check if a given module is installed and update the corresponding label.

        :param module_name: The name of the module to check.
        :type module_name: str
        :returns: True if the module is found, False otherwise.
        :rtype: bool
        :raises PackageNotFoundError: If the module is not found.
        :raises Exception: For any other issues that arise during the check.
        """
        label_name = module_name + "_found_label"
        try:
            # Attempt to get the distribution information directly using importlib.metadata
            dist = distribution(module_name)
            version = dist.version
            getattr(self, label_name).setText(f"{module_name} {version}")
            getattr(self, label_name).setStyleSheet("color: green;")
            return True
        except PackageNotFoundError:
            # Handle the case where the package is not found
            getattr(self, label_name).setText(f"{module_name} not found")
            getattr(self, label_name).setStyleSheet("color: red;")
            return False
        except Exception as e:
            # General exception handling for any other issues that arise
            getattr(self, label_name).setText("Error checking module")
            getattr(self, label_name).setStyleSheet("color: red;")
            return False

    def select_highpoly_model(self):
        """Open a file dialog to select a high-poly model and update related UI elements."""
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(self, "Select Highpoly Model", "", "OBJ Files (*.obj)")

        if file_path:
            self.highpoly_model_line_edit.setText(file_path)
            self.update_polycount(file_path)
            mtl_path = file_path.replace(".obj", ".mtl")

            if not os.path.exists(mtl_path):
                QMessageBox.warning(self, "Warning", "No .mtl file found alongside the .obj file.")

            # Check texture references in .mtl file
            if os.path.exists(mtl_path):
                self.check_texture_references(mtl_path, os.path.dirname(file_path))

    def update_polycount(self, file_path):
        """Update the polygon count display and settings based on the selected model file."""
        polycount = calculate_polycount(file_path)
        self.polycount_label.setText(f"Polycount: {str(polycount)}")
        self.initial_reduction_polycount.setRange(0, polycount)
        self.initial_reduction_polycount.setValue(polycount)

    def check_texture_references(self, mtl_path, directory):
        """
        Check and update texture file references in a .mtl file.

        :param mtl_path: The path to the .mtl file to be checked.
        :type mtl_path: str
        :param directory: The directory where the texture files are expected to be located.
        :type directory: str
        :return:
        """
        changes = []
        with open(mtl_path, "r") as file:
            lines = file.readlines()

        for i, line in enumerate(lines):
            if line.startswith("map_Kd"):  # Assuming 'map_Kd' indicates a texture file
                texture_file = line.split()[1]
                texture_path = os.path.join(directory, texture_file)
                if not os.path.exists(texture_path):
                    new_texture_path = self.find_texture_file(directory, texture_file)
                    if new_texture_path:
                        lines[i] = f"map_Kd {new_texture_path}\n"
                        changes.append((texture_file, new_texture_path))

        if changes:
            with open(mtl_path, "w") as file:
                file.writelines(lines)
            change_report = "\n".join([f"{old} -> {new}" for old, new in changes])
            QMessageBox.information(self, "Texture Paths Updated", f"Updated texture paths:\n{change_report}")

    @staticmethod
    def find_texture_file(directory, filename):
        """
        Search for a texture file in the given directory and its subdirectories.

        :param directory: The root directory to start the search.
        :type directory: str
        :param filename: The name of the texture file to find.
        :type filename: str
        :returns: The relative path to the found texture file or None if not found.
        :rtype: str or None
        """
        for root, _, files in os.walk(directory):
            if filename in files:
                return os.path.relpath(os.path.join(root, filename), directory)
        return None

    def select_export_path(self):
        """Open a dialog to select an export directory and update the corresponding UI element."""
        directory = QFileDialog.getExistingDirectory(self, "Select Export Directory")
        if directory:
            self.export_path_line_edit.setText(directory)
            if os.listdir(directory):
                QMessageBox.warning(self, "Warning", "The selected export folder is not empty.")

    def setup_blender(self, values):
        """
        Set up a clean Blender Scene with the provided configuration values.
        :param values: A dictionary containing configuration values for the Blender setup.
        :type values: dict
        :returns: None
        """
        import bpy

        # Create a new scene
        bpy.ops.wm.read_factory_settings(use_empty=True)

        # Check if the plugin is installed
        if PLUGIN_BASENAME not in bpy.context.preferences.addons.keys():
            print(f"{PLUGIN_BASENAME} not installed. Attempting install.")
            # Create a .zip file for the plugin if not already existing
            if not os.path.isfile(PLUGIN_FILE):
                deploy.zip_directory(PLUGIN_DIR)

            if not os.path.isfile(PLUGIN_FILE):
                QMessageBox.critical(self, "Error", "Failed to create plugin. Can NOT continue")
                return

            # Install the plugin
            bpy.ops.preferences.addon_install(filepath=PLUGIN_FILE)
        else:
            print(f"{PLUGIN_BASENAME} already installed")

        # Check if the plugin is enabled
        if PLUGIN_BASENAME not in bpy.context.preferences.addons:
            print(f"{PLUGIN_BASENAME} not enabled. Enabling...")
            bpy.ops.preferences.addon_enable(module=PLUGIN_BASENAME)
        else:
            print(f"{PLUGIN_BASENAME} already enabled.")

        if PLUGIN_BASENAME not in bpy.context.preferences.addons:
            QMessageBox.critical(self, "Error", "Failed to enable plugin. Can NOT continue")
            return

        # Run the pipeline
        bpy.types.Scene.import_fp_comb = values["highpoly_model_path"]
        bpy.types.Scene.rot_correction_comb = values["rot_correction"]
        bpy.types.Scene.export_fp_comb = values["export_path"]

        bpy.types.Scene.initial_reduction_comb = values["initial_reduction_polycount"]
        bpy.types.Scene.loose_threshold_comb = values["loose_threshold"]
        bpy.types.Scene.boundary_length_comb = values["boundary_length"]
        bpy.types.Scene.merge_threshold_comb = values["merge_threshold"]

        bpy.types.Scene.num_of_modules_comb = values["num_modules"]

        bpy.types.Scene.lod_count_comb = values["num_lods"]
        bpy.types.Scene.reduction_percentage_comb = values["reduction_percentage"]

        bpy.data.scenes["Scene"].baker_settings_comb.highpoly_mesh_name = values["highpoly_model_path"]
        bpy.data.scenes["Scene"].baker_settings_comb.texture_resolution = values["texture_resolution"]
        bpy.data.scenes["Scene"].baker_settings_comb.save_path = values["export_path"]
        bpy.data.scenes["Scene"].baker_settings_comb.ray_distance = values["ray_distance"]

    def start_pipeline(self):
        """Starts the pipeline with the current configuration values."""
        start_time = time.time()
        if not self.all_modules_installed:
            QMessageBox.critical(self, "Error", "Not all modules that are required are installed.\n"
                                                "Please install the missing dependencies using PIP to your "
                                                "local Python environment and try again. "
                                                "You can see what modules are missing by checking "
                                                "the red labels below the start button.")
            return

        highpoly_model_path = self.highpoly_model_line_edit.text()
        rot_correction = self.rotation_correction.currentText()
        if rot_correction == "No Rotation":
            rot_correction = [0, 0, 0]
        elif rot_correction == "-90 on X (Metashape)":
            rot_correction = [-90, 0, 0]

        export_path = self.export_path_line_edit.text()

        if not os.path.isfile(highpoly_model_path):
            QMessageBox.critical(self, "Error", "Highpoly model file not found. Can NOT continue")
            return

        if not os.path.isdir(export_path):
            QMessageBox.critical(self, "Error", "Export path not found. Can NOT continue")
            return

        initial_reduction_polycount = self.initial_reduction_polycount.value()
        vertex_threshold = self.loose_comp_threshold.value()
        boundary_length = self.boundary_length.value()
        merge_threshold = self.merge_threshold.value()
        num_modules = int(self.num_modules.currentText())
        num_lods = self.num_lods.value()
        reduction_percentage = self.reduction_percentage.value()
        texture_resolution = int(self.texture_resolution.currentText())
        ray_distance = self.ray_distance.value()

        values = {
            "initial_reduction_polycount": initial_reduction_polycount,
            "highpoly_model_path": highpoly_model_path,
            "export_path": export_path,
            "loose_threshold": vertex_threshold,
            "boundary_length": boundary_length,
            "merge_threshold": merge_threshold,
            "num_modules": num_modules,
            "num_lods": num_lods,
            "reduction_percentage": reduction_percentage,
            "texture_resolution": texture_resolution,
            "ray_distance": ray_distance,
            "rot_correction": rot_correction
        }

        self.setup_blender(values)

        # Run the operators
        launch_operator_by_name(COMB_IDNAME)

        # Open the export folder
        os.startfile(export_path)

        end_time = time.time()
        QMessageBox.information(self, "Processing Done",
                                f"Processing completed in {end_time - start_time:.2f} seconds.")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = ModelProcessorGUI()
    window.show()
    sys.exit(app.exec())
