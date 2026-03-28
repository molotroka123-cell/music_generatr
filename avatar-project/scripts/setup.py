#!/usr/bin/env python3
"""
AI Avatar Pipeline — Dependency Setup Script
Installs all required packages and checks system prerequisites.
"""

import subprocess
import sys
import shutil


PACKAGES = [
    ("replicate", "replicate"),
    ("elevenlabs", "elevenlabs"),
    ("requests", "requests"),
    ("jwt", "pyjwt"),
    ("obsws_python", "obsws-python"),
    ("cv2", "opencv-python"),
    ("ffmpeg", "ffmpeg-python"),
    ("dotenv", "python-dotenv"),
    ("psutil", "psutil"),
]


def install_package(pip_name):
    """Install a single pip package."""
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", pip_name, "-q"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def check_import(module_name):
    """Check if a Python module can be imported (in subprocess to isolate crashes)."""
    result = subprocess.run(
        [sys.executable, "-c", f"import {module_name}"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def check_binary(name):
    """Check if a system binary is available on PATH."""
    return shutil.which(name) is not None


def main():
    print("=" * 50)
    print("  AI Avatar Pipeline — Setup")
    print("=" * 50)
    print()

    # Install Python packages
    print("[1/3] Installing Python packages...")
    print("-" * 40)
    results = {}
    for module_name, pip_name in PACKAGES:
        if check_import(module_name):
            results[pip_name] = True
            print(f"  [OK]   {pip_name} (already installed)")
        else:
            success = install_package(pip_name)
            results[pip_name] = success
            status = "[OK]  " if success else "[FAIL]"
            print(f"  {status} {pip_name}")

    print()

    # Check system binaries
    print("[2/3] Checking system binaries...")
    print("-" * 40)
    binaries = {
        "ffmpeg": "Required for video processing",
        "python3": "Python interpreter",
        "git": "Version control",
    }
    for binary, description in binaries.items():
        found = check_binary(binary)
        status = "[OK]  " if found else "[MISS]"
        print(f"  {status} {binary} — {description}")
        if not found and binary == "ffmpeg":
            print("         Install: https://ffmpeg.org/download.html")

    print()

    # Check config
    print("[3/3] Checking configuration...")
    print("-" * 40)
    import os

    env_example = os.path.join(
        os.path.dirname(__file__), "..", "config", "api_keys.env.example"
    )
    env_file = os.path.join(os.path.dirname(__file__), "..", "config", "api_keys.env")

    if os.path.exists(env_file):
        print("  [OK]   config/api_keys.env found")
    else:
        print("  [MISS] config/api_keys.env not found")
        print("         Copy api_keys.env.example -> api_keys.env and fill in keys")

    # Summary
    print()
    print("=" * 50)
    failed = [name for name, ok in results.items() if not ok]
    if failed:
        print(f"  SETUP INCOMPLETE — Failed: {', '.join(failed)}")
    else:
        print("  SETUP COMPLETE — All packages installed!")
    print("=" * 50)


if __name__ == "__main__":
    main()
