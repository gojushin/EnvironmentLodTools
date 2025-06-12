import os
import sys
import time
import platform
import glob

from PySide6.QtGui import QIcon, QTextCursor
from PySide6.QtCore import Signal, Qt, QThread
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton,
    QFileDialog, QLabel, QSpinBox, QDoubleSpinBox, QComboBox,
    QMessageBox, QGroupBox, QHBoxLayout, QFrame, QLineEdit, QCheckBox,
    QPlainTextEdit, QSplitter
)

sys.path.insert(0, os.getcwd())

from plugin_src.ds_utils import launch_operator_by_name
from plugin_src.ds_consts  import COMB_IDNAME

SCRIPT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__)))
PLUGIN_NAME_EXTENSION = "bl_ext"
PLUGIN_REPO = "user_default"
PLUGIN_BASENAME = "enviro_lod_tools"
FULL_PLUGIN_NAME = f"{PLUGIN_NAME_EXTENSION}.{PLUGIN_REPO}.{PLUGIN_BASENAME}"

PLUGIN_SUFFIXES = {
    "Windows": "windows_x64.zip",
    "Darwin": "macos_arm64.zip",
    "Linux": "linux_x64.zip"
}


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

    with open(file_path, 'rb') as f:
        content = f.read()
        count = content.count(b'\nf ')
        if content[:2] == b'f ':
            count += 1
        return count


class ConsoleOutputWidget(QWidget):
    """Console output widget with background thread for stdout/stderr capture."""
    class ConsoleWorker(QThread):
        output_signal = Signal(str)
        error_signal = Signal(str)

        def run(self):
            class ThreadedRedirector:
                def __init__(self, emit_func):
                    self.emit_func = emit_func

                def write(self, text):
                    if text.strip():
                        self.emit_func(text.rstrip())

                def flush(self):
                    pass

            # Redirect stdout/stderr within the thread
            sys.stdout = ThreadedRedirector(self.output_signal.emit)
            sys.stderr = ThreadedRedirector(self.error_signal.emit)

            # Keep thread alive
            while True:
                time.sleep(0.1)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.auto_scroll = True
        self.capture_enabled = True

        layout = QVBoxLayout()
        console_group = QGroupBox("Console Output")
        console_layout = QVBoxLayout()

        controls_layout = QHBoxLayout()
        self.auto_scroll_cb = QCheckBox("Auto-scroll")
        self.auto_scroll_cb.setChecked(self.auto_scroll)
        self.auto_scroll_cb.toggled.connect(self.toggle_auto_scroll)

        self.capture_cb = QCheckBox("Capture Console")
        self.capture_cb.setChecked(self.capture_enabled)
        self.capture_cb.toggled.connect(self.toggle_console_capture)

        clear_btn = QPushButton("Clear")
        clear_btn.setFixedWidth(80)
        clear_btn.clicked.connect(self.clear_output)

        controls_layout.addWidget(self.auto_scroll_cb)
        controls_layout.addWidget(self.capture_cb)
        controls_layout.addStretch()
        controls_layout.addWidget(clear_btn)

        self.console_text = QPlainTextEdit()
        self.console_text.setReadOnly(True)
        self.console_text.setMaximumBlockCount(10000)

        console_layout.addLayout(controls_layout)
        console_layout.addWidget(self.console_text)
        console_group.setLayout(console_layout)
        layout.addWidget(console_group)
        self.setLayout(layout)

        # Start threaded console capture
        self.console_thread = self.ConsoleWorker()
        self.console_thread.output_signal.connect(self.handle_stdout)
        self.console_thread.error_signal.connect(self.handle_stderr)
        self.console_thread.start()

        # Initial setup
        self.clear_output()
        self.append_text(">>> Ready")

    def toggle_auto_scroll(self, enabled):
        self.auto_scroll = enabled

    def toggle_console_capture(self, enabled):
        self.capture_enabled = enabled
        if enabled:
            self.append_text(">>> Console capture enabled")
        else:
            self.append_text(">>> Console capture disabled")

    def handle_stdout(self, text):
        self.append_text(text, is_error=False)

    def handle_stderr(self, text):
        self.append_text(text, is_error=True)

    def append_text(self, text, is_error=False):
        cursor = self.console_text.textCursor()
        cursor.movePosition(QTextCursor.End)

        if is_error:
            cursor.insertHtml(f'<span style="color: #f44747;">{text}</span><br>')
        else:
            cursor.insertText(text + "\n")

        if self.auto_scroll:
            self.console_text.verticalScrollBar().setValue(
                self.console_text.verticalScrollBar().maximum()
            )

    def clear_output(self):
        self.console_text.clear()

    def closeEvent(self, event):
        if self.console_thread and self.console_thread.isRunning():
            self.console_thread.terminate()
            self.console_thread.wait()
        event.accept()

class ModelProcessorGUI(QWidget):
    def __init__(self, blender_plugin: str = None):
        super().__init__()

        self.blender_plugin = blender_plugin
        # Styling
        self.setWindowTitle("Environment LOD Tools")
        self.resize(900, 600)
        self.setMinimumWidth(800)

        self.setWindowIcon(QIcon("icon.ico"))

        try:
            with open("style.qss", "r") as f:
                _style = f.read()
                app.setStyleSheet(_style)
        except FileNotFoundError:
            pass

        # Create main layout
        main_layout = QVBoxLayout()

        # Create splitter to divide main controls and console horizontally
        splitter = QSplitter(Qt.Horizontal)

        # Create main controls widget
        controls_widget = QWidget()
        controls_layout = QVBoxLayout()
        controls_widget.setLayout(controls_layout)

        # Set minimum and default width for controls (settings) widget
        controls_widget.setMinimumWidth(320)

        # IO Section
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
        self.export_path_btn = QPushButton("Select Export Path")
        self.export_path_btn.setFixedWidth(175)
        self.export_path_btn.clicked.connect(self.select_export_path)
        export_path_layout.addWidget(self.export_path_line_edit)
        export_path_layout.addWidget(self.export_path_btn)
        io_layout.addLayout(export_path_layout)

        # Cleanup Properties Section
        cleanup_group = QGroupBox("Cleanup Properties")
        cleanup_layout = QVBoxLayout()

        self.initial_reduction_polycount = QSpinBox()
        self.initial_reduction_polycount.setRange(0, 10000000)
        self.initial_reduction_polycount.setValue(1000000)
        self.initial_reduction_polycount.setToolTip("Set the initial reduction target.\n"
                                                    "(This will be the polycount for LOD 0)")
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
        self.merge_threshold.setValue(0.001)

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
        self.reduction_percentage.setSuffix(" %")
        self.reduction_percentage.setToolTip("Percentage by which to reduce the mesh complexity in each LOD.\n"
                                             "(0.00 % = no reduction, 100.00 % = full reduction)")

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

        self.render_device = QComboBox()
        self.render_device.setToolTip("Select the render device to use. If not enough GPU Memory is available,\n"
                                      "it is recommended to use CPU.")
        self.render_device.addItems(["CPU", "GPU"])
        self.render_device.setCurrentText("GPU")
        render_device_layout = QHBoxLayout()
        render_device_layout.addWidget(QLabel("Render Device"))
        render_device_layout.addWidget(self.render_device)

        self.lower_res_by_lod = QCheckBox()
        self.lower_res_by_lod.setChecked(True)
        self.lower_res_by_lod.setToolTip("Reduce the resolution of the baked textures in power of 2 steps for each LODs.")
        lower_res_by_lod_layout = QHBoxLayout()
        lower_res_by_lod_layout.addWidget(QLabel("Lower Res. per LOD"))
        lower_res_by_lod_layout.addWidget(self.lower_res_by_lod)

        self.texture_resolution = QComboBox()
        self.texture_resolution.addItems(["256", "512", "1024", "2048", "4096", "8192"])
        self.texture_resolution.setCurrentText("1024")
        texture_resolution_layout = QHBoxLayout()
        texture_resolution_layout.addWidget(QLabel("Texture Resolution"))
        texture_resolution_layout.addWidget(self.texture_resolution)

        self.ray_distance = QDoubleSpinBox()
        self.ray_distance.setToolTip("The distance at which the rays will be cast. Value depends of the WS size of the mesh.")
        self.ray_distance.setRange(0.01, 100.0)
        self.ray_distance.setValue(0.1)
        self.ray_distance.setSingleStep(0.01)
        ray_distance_layout = QHBoxLayout()
        ray_distance_layout.addWidget(QLabel("Ray Distance"))
        ray_distance_layout.addWidget(self.ray_distance)

        bake_layout.addLayout(render_device_layout)
        bake_layout.addLayout(texture_resolution_layout)
        bake_layout.addLayout(lower_res_by_lod_layout)
        bake_layout.addLayout(ray_distance_layout)
        bake_group.setLayout(bake_layout)

        # Start Button
        start_btn = QPushButton("Start")
        start_btn.clicked.connect(self.start_pipeline)

        # Add all groups to the controls layout
        controls_layout.addWidget(io_group)
        controls_layout.addWidget(cleanup_group)
        controls_layout.addWidget(slice_group)
        controls_layout.addWidget(lod_group)
        controls_layout.addWidget(bake_group)
        controls_layout.addWidget(start_btn)

        # Create console output widget
        self.console_widget = ConsoleOutputWidget()

        # Set minimum and default width for console widget
        self.console_widget.setMinimumWidth(480)

        # Add both widgets to splitter
        splitter.addWidget(controls_widget)
        splitter.addWidget(self.console_widget)

        # Set initial splitter sizes (settings: 320, console: 560)
        splitter.setSizes([320, 480])

        # Add splitter to main layout
        main_layout.addWidget(splitter)

        self.setLayout(main_layout)

    def select_highpoly_model(self):
        """Open a file dialog to select a high-poly model and update related UI elements."""
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(self, "Select Highpoly Model", "", "OBJ Files (*.obj)")

        if file_path:
            self.highpoly_model_line_edit.setText(file_path)
            self.update_polycount(file_path)
            print(f"Selected highpoly model: {file_path}")

            mtl_path = file_path.replace(".obj", ".mtl")
            if not os.path.exists(mtl_path):
                print("Warning: No .mtl file found alongside the .obj file.")
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
        print(f"Polycount calculated: {polycount}")

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
            print(f"Updated texture paths: {change_report}")
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
            print(f"Selected export path: {directory}")
            if os.listdir(directory):
                print("Warning: Selected export folder is not empty.")
                QMessageBox.warning(self, "Warning", "The selected export folder is not empty.")

    def ensure_plugin(self):
        import bpy
        if FULL_PLUGIN_NAME in bpy.context.preferences.addons.keys():
            if FULL_PLUGIN_NAME in bpy.context.preferences.addons:
                return True
            else:
                bpy.ops.preferences.addon_enable(module=FULL_PLUGIN_NAME)
                return FULL_PLUGIN_NAME in bpy.context.preferences.addons
        else:
            bpy.ops.extensions.package_install_files(filepath=self.blender_plugin,
                                                 enable_on_install=True,
                                                 repo=PLUGIN_REPO)
            if FULL_PLUGIN_NAME in bpy.context.preferences.addons:
                return True
            else:
                bpy.ops.preferences.addon_enable(module=FULL_PLUGIN_NAME)
                return FULL_PLUGIN_NAME in bpy.context.preferences.addons

    def setup_blender(self, values):
        """
        Set up a clean Blender Scene with the provided configuration values.
        :param values: A dictionary containing configuration values for the Blender setup.
        :type values: dict
        :returns: None
        """
        import bpy
        print("Creating new Blender scene...")
        # Create a new scene
        bpy.ops.wm.read_factory_settings(use_empty=True)

        if not self.ensure_plugin():
            return False

        print("Setting up Blender variables...")
        # Setup all the variables.
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
        bpy.data.scenes["Scene"].baker_settings_comb.render_device = values["render_device"]
        bpy.data.scenes["Scene"].baker_settings_comb.texture_resolution = values["texture_resolution"]
        bpy.data.scenes["Scene"].baker_settings_comb.lower_res_by_lod = values["lower_res_by_lod"]
        bpy.data.scenes["Scene"].baker_settings_comb.save_path = values["export_path"]
        bpy.data.scenes["Scene"].baker_settings_comb.ray_distance = values["ray_distance"]

        print("Blender setup complete.")
        return True

    def start_pipeline(self):
        """Starts the pipeline with the current configuration values."""
        start_time = time.time()

        sys.stdout.write("="*50)
        sys.stdout.write("Starting Environment LOD Tools Pipeline")
        sys.stdout.write("="*50)

        highpoly_model_path = self.highpoly_model_line_edit.text()
        rot_correction = self.rotation_correction.currentText()
        if rot_correction == "No Rotation":
            rot_correction = [0, 0, 0]
        elif rot_correction == "-90 on X (Metashape)":
            rot_correction = [-90, 0, 0]

        export_path = self.export_path_line_edit.text()

        if not os.path.isfile(highpoly_model_path):
            print(f"Error: Highpoly model file not found: {highpoly_model_path}")
            QMessageBox.critical(self, "Error", "Highpoly model file not found. Can NOT continue")
            return

        if not os.path.isdir(export_path):
            print(f"Error: Export path not found: {export_path}")
            QMessageBox.critical(self, "Error", "Export path not found. Can NOT continue")
            return

        print(f"Input Model: {highpoly_model_path}")
        print(f"Export Path: {export_path}")
        print(f"Rotation Correction: {rot_correction}")

        initial_reduction_polycount = self.initial_reduction_polycount.value()
        vertex_threshold = self.loose_comp_threshold.value()
        boundary_length = self.boundary_length.value()
        merge_threshold = self.merge_threshold.value()
        num_modules = int(self.num_modules.currentText())
        num_lods = self.num_lods.value()
        reduction_percentage = self.reduction_percentage.value()
        render_device = self.render_device.currentText()
        texture_resolution = int(self.texture_resolution.currentText())
        lower_res_by_lod = self.lower_res_by_lod.isChecked()
        ray_distance = self.ray_distance.value()

        print(f"Initial Reduction Polycount: {initial_reduction_polycount}")
        print(f"Number of Modules: {num_modules}")
        print(f"Number of LODs: {num_lods}")
        print(f"Reduction Percentage: {reduction_percentage}%")
        print(f"Render Device: {render_device}")
        print(f"Texture Resolution: {texture_resolution}")

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
            "render_device": render_device,
            "texture_resolution": texture_resolution,
            "lower_res_by_lod": lower_res_by_lod,
            "ray_distance": ray_distance,
            "rot_correction": rot_correction
        }

        # Enable console capture to catch Blender output
        self.console_widget.capture_cb.setChecked(True)
        print("Enabling console capture for Blender operations...")

        print("Setting up Blender environment...")
        if not self.setup_blender(values):
            print("Error: Failed to set up Blender environment")
            QMessageBox.warning(self, "Error", "Failed to set up Blender.")
            return

        # Run the operators
        print("Launching Blender operators...")
        launch_operator_by_name(COMB_IDNAME)

        # Disable console capture
        self.console_widget.capture_cb.setChecked(False)

        # Open the export folder
        print(f"Opening export folder: {export_path}")
        os.startfile(export_path)

        end_time = time.time()
        print("="*50)
        print(f"Processing completed successfully in {end_time - start_time:.2f} seconds.")
        print("="*50)

        QMessageBox.information(self, "Processing Done",
                                f"Processing completed in {end_time - start_time:.2f} seconds.")


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()

    plugin_to_load = None

    try:
        system = platform.system()
        plugin_suffix = PLUGIN_SUFFIXES.get(system)

        if not plugin_suffix:
            raise FileNotFoundError("Platform is not supported.")

        plugins = glob.glob(f"*{plugin_suffix}", root_dir=SCRIPT_DIR)

        if not plugins:
            raise FileNotFoundError("Blender Plugin is missing.")

        plugins = sorted(plugins)
        plugin_to_load = os.path.abspath(plugins[0])

    except Exception as e:
        app = QApplication(sys.argv)

        error_dialog = QMessageBox()
        error_dialog.setIcon(QMessageBox.Icon.Critical)
        error_dialog.setWindowTitle("Error")
        error_dialog.setText("An error occurred:")
        error_dialog.setInformativeText(str(e))
        error_dialog.exec()

        sys.exit(1)

    if not os.path.exists(plugin_to_load):
        sys.exit(1)

    app = QApplication(sys.argv)
    window = ModelProcessorGUI(plugin_to_load)
    window.show()

    sys.exit(app.exec())