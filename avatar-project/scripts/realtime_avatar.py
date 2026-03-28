#!/usr/bin/env python3
"""AI Avatar Pipeline - Realtime Avatar Launcher."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path
import psutil

PROJECT_ROOT = Path(__file__).parent.parent
AVATAR_LIBRARY = PROJECT_ROOT / "avatar_library.json"

def check_gpu_available():
    try:
        result = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.free", "--format=csv,noheader"],
            capture_output=True, text=True)
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, "nvidia-smi failed"
    except FileNotFoundError:
        return False, "nvidia-smi not found"

def check_obs_running():
    for proc in psutil.process_iter(["name"]):
        if "obs" in proc.info["name"].lower():
            return True, "Running"
    return False, "Not running"

def check_liveportrait():
    lp_paths = [Path.home() / "LivePortrait", Path("C:/LivePortrait"),
                Path.home() / "Documents" / "LivePortrait"]
    for p in lp_paths:
        if p.exists():
            return True, str(p)
    return False, "Not found"

def preflight_check():
    print("[PRE-FLIGHT] Running system check...")
    checks = {"GPU": check_gpu_available, "OBS Studio": check_obs_running,
              "LivePortrait": check_liveportrait}
    all_ok = True
    for name, check_fn in checks.items():
        ok, detail = check_fn()
        status = "[OK]  " if ok else "[FAIL]"
        print(f"  {status} {name}: {detail}")
        if not ok:
            all_ok = False
    ram = psutil.virtual_memory()
    print(f"  {'[OK]  ' if ram.percent < 80 else '[WARN]'} RAM: {ram.percent}%")
    return all_ok

def select_avatar():
    if not AVATAR_LIBRARY.exists():
        print("[ERROR] No avatars. Run pipeline first.")
        sys.exit(1)
    library = json.loads(AVATAR_LIBRARY.read_text())
    if not library:
        sys.exit(1)
    for i, char in enumerate(library):
        print(f"  [{i+1}] {char['character_id']} - seed: {char['seed']}")
    choice = int(input(f"Select avatar (1-{len(library)}): ") or "1") - 1
    selected = library[max(0, min(choice, len(library)-1))]
    ref_image = PROJECT_ROOT / "output" / "avatars" / f"avatar_reference_{selected['seed']}.jpg"
    if not ref_image.exists():
        ref_image = Path(input("Enter path to avatar image: "))
    return str(ref_image)

def main():
    print("=" * 55)
    print("  AI Avatar Pipeline - Realtime Mode")
    print("=" * 55)
    all_ok = preflight_check()
    if not all_ok:
        if input("Continue anyway? (y/N): ").lower() != "y":
            sys.exit(0)
    avatar_path = select_avatar()
    ok, lp_path = check_liveportrait()
    if not ok:
        print(f"[FAIL] {lp_path}")
        sys.exit(1)
    process = subprocess.Popen([sys.executable, os.path.join(lp_path, "inference.py"),
        "--source", avatar_path, "--driving", "webcam", "--output", "virtual_cam"], cwd=lp_path)
    print("[LIVE] Pipeline active! Open Zoom -> select OBS Virtual Camera")
    try:
        while process.poll() is None:
            time.sleep(30)
    except KeyboardInterrupt:
        process.terminate()
        print("[DONE] Pipeline stopped.")

if __name__ == "__main__":
    main()
