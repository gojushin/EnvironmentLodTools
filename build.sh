#!/bin/bash

# Default values
PYTHON_VERSION="3.11.9"

# Detect OS and set default Blender path
case "$(uname -s)" in
    MINGW*|MSYS*|CYGWIN*)
        BLENDER_EXE="C:/Program Files/Blender Foundation/Blender 4.4/blender.exe"
        ;;
    Darwin*)
        BLENDER_EXE="/Applications/Blender.app/Contents/MacOS/Blender"
        ;;
    Linux*)
        BLENDER_EXE="/usr/bin/blender"
        ;;
    *)
        BLENDER_EXE="blender"
        ;;
esac

# Parse command line arguments
COMMAND=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --blender)
            BLENDER_EXE="$2"
            shift 2
            ;;
        --python-version)
            PYTHON_VERSION="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [COMMAND] [OPTIONS]"
            echo "Commands:"
            echo "  build_plugins      Build only plugins"
            echo "  build_env          Build only Python environment"
            echo "  build_launcher     Build only launcher"
            echo "  (no command)       Build all components"
            echo ""
            echo "Options:"
            echo "  --blender          Path to Blender executable"
            echo "  --python-version   Python version (default: 3.11.9)"
            echo "  --help             Show this help message"
            exit 0
            ;;
        build_plugins|build_env|build_launcher)
            COMMAND="$1"
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Extract Python major.minor version
PYTHON_VERSION_SHORT=$(echo "$PYTHON_VERSION" | cut -d. -f1,2)

echo "Using Python version: $PYTHON_VERSION"
echo "Using Python short version: $PYTHON_VERSION_SHORT"
echo "Using Blender executable: $BLENDER_EXE"

# Function to build plugins
build_plugins() {
    echo "Building plugins..."
    
    # Create wheels directory if it doesn't exist
    mkdir -p ./plugin_src/wheels
    
    # Download pyfqmr wheels for different platforms
    pip download pyfqmr==0.2.0 --dest ./plugin_src/wheels --only-binary=:all: --python-version="$PYTHON_VERSION_SHORT" --platform=macosx_11_0_arm64
    pip download pyfqmr==0.2.0 --dest ./plugin_src/wheels --only-binary=:all: --python-version="$PYTHON_VERSION_SHORT" --platform=manylinux_2_17_x86_64
    pip download pyfqmr==0.2.0 --dest ./plugin_src/wheels --only-binary=:all: --python-version="$PYTHON_VERSION_SHORT" --platform=win_amd64
    
    # Download xatlas wheels for different platforms
    pip download xatlas==0.0.10 --dest ./plugin_src/wheels --only-binary=:all: --python-version="$PYTHON_VERSION_SHORT" --platform=macosx_11_0_arm64
    pip download xatlas==0.0.9 --dest ./plugin_src/wheels --only-binary=:all: --python-version="$PYTHON_VERSION_SHORT" --platform=manylinux_2_17_x86_64
    pip download xatlas==0.0.9 --dest ./plugin_src/wheels --only-binary=:all: --python-version="$PYTHON_VERSION_SHORT" --platform=win_amd64
    
    # Delete all entries with numpy (Blender already provides numpy 1.26.4)
    rm -f ./plugin_src/wheels/numpy*
    
    # Update manifest
    python update_manifest.py
    
    # Build extension with Blender
    "$BLENDER_EXE" --command extension build --split-platforms --source-dir ./plugin_src --output-dir ./
}

# Function to build environment
build_env() {
    echo "Building Python environment..."
    
    # Set variables
    PY_DIR="python_embed"
    PY_ZIP="python_embed.zip"
    
    # Determine platform and download URL
    case "$(uname -s)" in
        MINGW*|MSYS*|CYGWIN*)
            # Windows
            PY_EMBED_URL="https://www.python.org/ftp/python/$PYTHON_VERSION/python-$PYTHON_VERSION-embed-amd64.zip"
            
            # Download Python embeddable if not present
            if [ ! -f "$PY_ZIP" ]; then
                echo "Downloading Python $PYTHON_VERSION embeddable package..."
                curl -L "$PY_EMBED_URL" -o "$PY_ZIP"
            else
                echo "Python zip already downloaded."
            fi
            
            # Unzip if not already extracted
            if [ ! -f "$PY_DIR/python.exe" ]; then
                echo "Extracting Python embeddable..."
                mkdir -p "$PY_DIR"
                unzip -q "$PY_ZIP" -d "$PY_DIR"
            else
                echo "Python already extracted."
            fi
            
            # Enable site packages in ._pth file
            echo "Enabling site support..."
            sed -i 's/^#import site/import site/' $PY_DIR/python*._pth
            
            # Download get-pip.py
            echo "Downloading get-pip.py..."
            curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
            
            # Install pip into embeddable Python
            echo "Installing pip..."
            $PY_DIR/python.exe get-pip.py
            
            # Install dependencies
            echo "Installing Python requirements..."
            $PY_DIR/python.exe -m pip install -r requirements.txt

            # Clean up pip installer
            rm get-pip.py
            ;;
        *)
            echo "Unsupported platform: $(uname -s)"
            exit 1
            ;;
    esac
    
    # Copy style.qss if it exists
    if [ -f style.qss ]; then
        cp style.qss $PY_DIR/
    fi
    
    echo "Python environment is ready."
}

# Function to build launcher
build_launcher() {
    echo "Building launcher..."
    
    # Paths
    BUILD_DIR="build"
    EXECUTABLE="enviro_launcher"
    
    # Clear old build
    if [ -d "$BUILD_DIR" ]; then
        rm -rf "$BUILD_DIR"
    fi
    mkdir "$BUILD_DIR"
    cd "$BUILD_DIR" || exit
    
    # Detect platform and set appropriate generator
    case "$(uname -s)" in
        MINGW*|MSYS*|CYGWIN*)
            # Windows - use MinGW Makefiles
            CMAKE_GENERATOR="MinGW Makefiles"
            EXECUTABLE_EXT=".exe"
            ;;
        *)
            echo "Unsupported platform: $(uname -s)"
            exit 1
            ;;
    esac
    
    # Run CMake
    if command -v cmake &> /dev/null; then
        cmake -G "$CMAKE_GENERATOR" ..
        cmake --build . --target enviro_launcher
    else
        echo "CMake not found. Please install CMake to build the launcher."
        cd ..
        return 1
    fi
    
    cd ..
    
    # Copy executable into root
    if [ -f "$EXECUTABLE$EXECUTABLE_EXT" ]; then
        rm "$EXECUTABLE$EXECUTABLE_EXT"
    fi
    if [ -f "build/$EXECUTABLE$EXECUTABLE_EXT" ]; then
        cp "build/$EXECUTABLE$EXECUTABLE_EXT" .
        if [[ "$(uname -s)" != MINGW* && "$(uname -s)" != MSYS* && "$(uname -s)" != CYGWIN* ]]; then
            chmod +x "$EXECUTABLE$EXECUTABLE_EXT"
        fi
    fi
    
    # Clean up build directory
    rm -rf build
    
    echo "Build complete: $EXECUTABLE$EXECUTABLE_EXT"
}

# Main execution
echo "Starting build process..."

# Execute based on command
case "$COMMAND" in
    build_plugins)
        build_plugins
        ;;
    build_env)
        build_env
        ;;
    build_launcher)
        build_launcher
        ;;
    *)
        # Build all components
        build_plugins
        build_env
        build_launcher
        ;;
esac

echo "All builds completed successfully!"
