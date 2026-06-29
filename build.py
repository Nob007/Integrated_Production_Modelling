"""
PyInstaller Build Script for PROPMAS

This script automates the process of building the IPM Suite application into a
standalone executable using PyInstaller. It cleans previous builds, runs
PyInstaller with the specified .spec file, and organizes the output.

To run this script:
1. Make sure you have PyInstaller installed (`pip install pyinstaller`).
2. Execute from the project root directory: `python build.py`

The final executable will be located in the `dist/` directory.
"""

import os
import shutil
import PyInstaller.__main__

SPEC_FILE = "PROPMAS.spec"
APP_NAME = "PROPMAS"

if __name__ == "__main__":
    print(f"--- Starting build for {APP_NAME} ---")

    # 1. Clean previous builds
    print("1. Cleaning previous build directories...")
    if os.path.exists("build"):
        shutil.rmtree("build")
    if os.path.exists("dist"):
        shutil.rmtree("dist")

    # 2. Run PyInstaller
    print(f"2. Running PyInstaller with '{SPEC_FILE}'...")
    PyInstaller.__main__.run([
        SPEC_FILE,
        '--noconfirm',  # Overwrite output directory without asking
    ])

    print("\n--- Build Complete ---")
    print(f"Executable is located in the '{os.path.abspath('dist')}' directory.")