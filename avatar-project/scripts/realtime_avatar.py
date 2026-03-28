#!/usr/bin/env python3
"""
AI Avatar Pipeline — Realtime Avatar Launcher

Launches the live avatar pipeline:
  Phone/Webcam → LivePortrait → OBS Virtual Camera → Zoom/Meet
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import psutil

PROJECT_ROOT = Path(__file__).parent.parent
AVATAR_LIBRARY = PROJECT_ROOT / "avatar_library.json"


# ─── System Checks ───────────────────────────────────────────────────────────


def check_gpu_available():
    """Check if NVIDIA GPU is accessible."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.free", "--format=csv,noheader"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, "nvidia-smi failed"
    except FileNotFoundError:
        return False, "nvidia-smi not found"


def check_obs_running():
    """Check if OBS Studio is running."""
    for proc in psutil.process_iter(["name"]):
        if "obs" in proc.info["name"].lower():
            return True, "Running"
    return False, "Not running — start OBS Studio first"


def check_droidcam():
    """Check if DroidCam virtual camera is available."""
    # On Windows, check for DroidCam process or device
    for proc in psutil.process_iter(["name"]):
        if "droidcam" in proc.info["name"].lower():
            return True, "Connected"
    return False, "Not detected — connect phone via USB and start DroidCam"


def check_liveportrait():
    """Check if LivePortrait is installed."""
    lp_paths = [
        Path.home() / "LivePortrait",
        Path("C:/LivePortrait"),
        Path.home() / "Documents" / "LivePortrait",
    ]
    for p in lp_paths:
        if p.exists():
            return True, str(p)
    return False, "Not found — clone from github.com/KwaiVGI/LivePortrait"


# ─── Pre-flight ──────────────────────────────────────────────────────────────


def preflight_check():
    """Run all pre-flight checks before going live."""
    print("[PRE-FLIGHT] Running system check...")
    print("-" * 40)

    checks = {
        "GPU": check_gpu_available,
        "OBS Studio": check_obs_running,
        "DroidCam": check_droidcam,
        "LivePortrait": check_liveportrait,
    }

    all_ok = True
    results = {}
    for name, check_fn in checks.items():
        ok, detail = check_fn()
        status = "[OK]  " if ok else "[FAIL]"
        print(f"  {status} {name}: {detail}")
        results[name] = ok
        if not ok:
            all_ok = False

    # RAM check
    ram = psutil.virtual_memory()
    ram_ok = ram.percent < 80
    status = "[OK]  " if ram_ok else "[WARN]"
    print(f"  {status} RAM: {ram.percent}% used ({ram.available // (1024**3)}GB free)")

    print("-" * 40)
    if all_ok:
        print("[READY] All systems green.")
    else:
        print("[BLOCKED] Fix failed checks before going live.")

    return all_ok, results


# ─── Avatar Selection ────────────────────────────────────────────────────────


def select_avatar():
    """Let user pick a character from avatar_library.json."""
    if not AVATAR_LIBRARY.exists():
        print("[ERROR] No avatars found. Run the pipeline first:")
        print("  python scripts/run_pipeline.py")
        sys.exit(1)

    library = json.loads(AVATAR_LIBRARY.read_text())
    if not library:
        print("[ERROR] Avatar library is empty.")
        sys.exit(1)

    print("\n--- Available Avatars ---")
    for i, char in enumerate(library):
        print(f"  [{i + 1}] {char['character_id']} — seed: {char['seed']}")
        print(f"      {char['base_prompt'][:60]}...")

    choice = int(input(f"\nSelect avatar (1-{len(library)}): ") or "1") - 1
    selected = library[max(0, min(choice, len(library) - 1))]

    # Find the reference image
    ref_image = PROJECT_ROOT / "output" / "avatars" / f"avatar_reference_{selected['seed']}.jpg"
    if not ref_image.exists():
        print(f"[WARN] Reference image not found: {ref_image}")
        alt = input("Enter path to avatar image: ")
        ref_image = Path(alt)

    print(f"\n[SELECTED] {selected['character_id']} — {ref_image.name}")
    return str(ref_image)


# ─── Pipeline Launch ─────────────────────────────────────────────────────────


def start_live_pipeline(avatar_image_path):
    """Launch LivePortrait with the selected avatar."""
    print("\n[LAUNCH] Starting live pipeline...")
    print(f"  Avatar: {avatar_image_path}")

    # Find LivePortrait installation
    ok, lp_path = check_liveportrait()
    if not ok:
        print(f"[FAIL] {lp_path}")
        sys.exit(1)

    # Launch LivePortrait
    print("  Starting LivePortrait...")
    process = subprocess.Popen(
        [
            sys.executable,
            os.path.join(lp_path, "inference.py"),
            "--source", avatar_image_path,
            "--driving", "webcam",
            "--output", "virtual_cam",
            "--flag_pasteback",
        ],
        cwd=lp_path,
    )

    print("[LIVE] Pipeline active!")
    print("  Open Zoom/Meet → select 'OBS Virtual Camera' as video source")
    print("  Press Ctrl+C to stop\n")

    return process


# ─── Monitoring ──────────────────────────────────────────────────────────────


def monitor(process, interval=30):
    """Monitor pipeline health during live session."""
    try:
        while process.poll() is None:
            # GPU stats
            gpu_ok, gpu_info = check_gpu_available()
            ram = psutil.virtual_memory()
            cpu = psutil.cpu_percent(interval=1)

            # Build status line
            parts = []
            if gpu_ok:
                parts.append(f"GPU: {gpu_info.split(',')[-1].strip()}")
            parts.append(f"RAM: {ram.percent}%")
            parts.append(f"CPU: {cpu}%")

            warn = ram.percent > 85 or cpu > 90
            status = "[WARN]" if warn else "[OK]  "
            print(f"  {status} {' | '.join(parts)}")

            time.sleep(interval)

    except KeyboardInterrupt:
        print("\n[STOP] Shutting down pipeline...")
        process.terminate()
        process.wait(timeout=10)
        print("[DONE] Pipeline stopped.")


# ─── Main ────────────────────────────────────────────────────────────────────


def main():
    print("=" * 55)
    print("  AI Avatar Pipeline — Realtime Mode")
    print("=" * 55)

    # Pre-flight
    all_ok, _ = preflight_check()
    if not all_ok:
        proceed = input("\nSome checks failed. Continue anyway? (y/N): ")
        if proceed.lower() != "y":
            print("Aborted.")
            sys.exit(0)

    # Select avatar
    avatar_path = select_avatar()

    # Launch
    process = start_live_pipeline(avatar_path)

    # Monitor
    monitor(process)


if __name__ == "__main__":
    main()
