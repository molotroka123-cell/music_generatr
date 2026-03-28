#!/usr/bin/env python3
"""
AI Avatar Pipeline — Full Production Orchestrator

Sequential pipeline:
  1. Avatar Designer  → generate images via FLUX.1
  2. Voice Producer   → generate audio via ElevenLabs
  3. Video Generator  → create video via HeyGen + Kling
  4. QA Publisher     → quality check and export
"""

import json
import os
import sys
import time
import requests
from datetime import datetime
from pathlib import Path

# Load environment
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / "config" / "api_keys.env")

# Output directories
OUTPUT_DIR = PROJECT_ROOT / "output"
AUDIO_DIR = OUTPUT_DIR / "audio"
VIDEO_DIR = OUTPUT_DIR / "videos"
AVATAR_DIR = OUTPUT_DIR / "avatars"
FRAMES_DIR = OUTPUT_DIR / "frames"

AVATAR_LIBRARY = PROJECT_ROOT / "avatar_library.json"
CONTENT_LOG = PROJECT_ROOT / "content_log.json"


# ─── Step 1: Avatar Generation (FLUX.1 via Replicate) ────────────────────────


def generate_avatar_images(character_desc, seed=42):
    """Generate all 5 image sets for a character via FLUX.1."""
    import replicate

    print("\n[STEP 1] Avatar Designer — Generating images...")
    print(f"  Character: {character_desc}")
    print(f"  Seed: {seed}")

    image_sets = {
        "reference": f"Professional headshot photo of {character_desc}, front facing, neutral expression, studio lighting, white background, photorealistic, 8k",
        "expressions": f"Portrait photo of {character_desc}, warm genuine smile, natural lighting, photorealistic, 8k",
        "lifestyle": f"Candid lifestyle photo of {character_desc}, casual outfit, coffee shop setting, natural daylight, photorealistic",
        "professional": f"Corporate headshot of {character_desc}, business attire, confident pose, clean background, photorealistic",
        "motion_frames": f"Close-up portrait of {character_desc}, slight head turn, neutral to smile transition, photorealistic",
    }

    results = {}
    for set_name, prompt in image_sets.items():
        print(f"  Generating {set_name}...")
        try:
            output = replicate.run(
                "black-forest-labs/flux-1.1-pro",
                input={
                    "prompt": prompt,
                    "aspect_ratio": "2:3",
                    "output_format": "jpg",
                    "output_quality": 100,
                    "safety_tolerance": 3,
                    "prompt_upsampling": True,
                    "seed": seed,
                },
            )
            # Save image URL
            image_url = str(output)
            results[set_name] = [image_url]

            # Download image
            img_path = AVATAR_DIR / f"avatar_{set_name}_{seed}.jpg"
            response = requests.get(image_url)
            if response.status_code == 200:
                img_path.write_bytes(response.content)
                print(f"    [OK] Saved: {img_path.name}")
            else:
                print(f"    [WARN] Could not download image")

        except Exception as e:
            print(f"    [FAIL] {set_name}: {e}")
            results[set_name] = []

    # Save to avatar library
    character_id = f"char_{seed}"
    library_entry = {
        "character_id": character_id,
        "seed": seed,
        "base_prompt": character_desc,
        "created_at": datetime.now().isoformat(),
        "images": results,
    }

    library = []
    if AVATAR_LIBRARY.exists():
        library = json.loads(AVATAR_LIBRARY.read_text())
    library.append(library_entry)
    AVATAR_LIBRARY.write_text(json.dumps(library, indent=2))

    print(f"  [OK] Avatar library updated: {character_id}")
    return character_id, results


# ─── Step 2: Voice Generation (ElevenLabs) ───────────────────────────────────


def generate_voice_audio(script_text, voice_id="Rachel", language="ru"):
    """Generate speech audio via ElevenLabs."""
    from elevenlabs.client import ElevenLabs

    print("\n[STEP 2] Voice Producer — Generating audio...")
    print(f"  Voice: {voice_id}")
    print(f"  Language: {language}")
    print(f"  Script: {script_text[:80]}...")

    client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

    try:
        audio_generator = client.text_to_speech.convert(
            text=script_text,
            voice_id=voice_id,
            model_id="eleven_multilingual_v2",
            voice_settings={
                "stability": 0.71,
                "similarity_boost": 0.85,
                "style": 0.35,
                "use_speaker_boost": True,
            },
        )

        # Save audio
        script_id = f"script_{int(time.time())}"
        audio_path = AUDIO_DIR / f"audio_{script_id}_{voice_id}_{language}.mp3"

        with open(audio_path, "wb") as f:
            for chunk in audio_generator:
                f.write(chunk)

        print(f"  [OK] Audio saved: {audio_path.name}")
        return str(audio_path)

    except Exception as e:
        print(f"  [FAIL] Voice generation: {e}")
        return None


# ─── Step 3: Video Generation (HeyGen + Kling) ──────────────────────────────


def create_video(avatar_image_path, audio_path, platform="tiktok"):
    """Create talking head video via HeyGen."""
    print("\n[STEP 3] Video Generator — Creating video...")
    print(f"  Avatar: {avatar_image_path}")
    print(f"  Audio: {audio_path}")
    print(f"  Platform: {platform}")

    heygen_key = os.getenv("HEYGEN_API_KEY")
    if not heygen_key:
        print("  [FAIL] HEYGEN_API_KEY not set")
        return None

    dimensions = {
        "tiktok": {"width": 1080, "height": 1920},
        "youtube": {"width": 1920, "height": 1080},
        "instagram": {"width": 1080, "height": 1080},
    }
    dim = dimensions.get(platform, dimensions["tiktok"])

    try:
        # Create video via HeyGen
        response = requests.post(
            "https://api.heygen.com/v2/video/generate",
            headers={"X-Api-Key": heygen_key},
            json={
                "video_inputs": [
                    {
                        "character": {
                            "type": "talking_photo",
                            "talking_photo_url": avatar_image_path,
                        },
                        "voice": {"type": "audio", "audio_url": audio_path},
                    }
                ],
                "dimension": dim,
            },
        )

        result = response.json()
        video_id = result.get("data", {}).get("video_id")

        if not video_id:
            print(f"  [FAIL] No video_id returned: {result}")
            return None

        print(f"  [OK] Video job started: {video_id}")
        print("  Waiting for render...")

        # Poll for completion
        for _ in range(30):
            time.sleep(10)
            status_resp = requests.get(
                "https://api.heygen.com/v1/video_status.get",
                headers={"X-Api-Key": heygen_key},
                params={"video_id": video_id},
            ).json()

            status = status_resp.get("data", {}).get("status")
            if status == "completed":
                video_url = status_resp["data"]["video_url"]
                print(f"  [OK] Video ready!")

                # Download video
                out_name = f"video_{video_id}_{platform}.mp4"
                out_path = VIDEO_DIR / out_name
                vid_resp = requests.get(video_url)
                if vid_resp.status_code == 200:
                    out_path.write_bytes(vid_resp.content)
                    print(f"  [OK] Saved: {out_name}")

                # Log to content_log
                log_entry = {
                    "video_id": video_id,
                    "created_at": datetime.now().isoformat(),
                    "audio_file": str(audio_path),
                    "heygen_job_id": video_id,
                    "status": "completed",
                    "platform": platform,
                    "output_path": str(out_path),
                }
                _append_content_log(log_entry)
                return str(out_path)

            elif status == "failed":
                print(f"  [FAIL] Render failed")
                return None

            print(f"    Status: {status}...")

        print("  [FAIL] Render timed out")
        return None

    except Exception as e:
        print(f"  [FAIL] Video generation: {e}")
        return None


# ─── Step 4: QA Check ────────────────────────────────────────────────────────


def run_qa_check(video_path):
    """Run quality assurance checks on the video."""
    import subprocess

    print("\n[STEP 4] QA Publisher — Running quality check...")
    print(f"  File: {video_path}")

    if not os.path.exists(video_path):
        print("  [FAIL] Video file not found")
        return False

    report = {"file": video_path, "timestamp": datetime.now().isoformat(), "checks": {}}

    # File size check
    size_mb = os.path.getsize(video_path) / 1024 / 1024
    report["checks"]["size"] = {
        "value": f"{size_mb:.1f}MB",
        "pass": size_mb < 50,
    }

    # Use ffprobe for video info
    try:
        probe = subprocess.run(
            [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_streams",
                video_path,
            ],
            capture_output=True,
            text=True,
        )
        info = json.loads(probe.stdout)
        video_stream = next(
            (s for s in info.get("streams", []) if s["codec_type"] == "video"), None
        )

        if video_stream:
            width = int(video_stream.get("width", 0))
            height = int(video_stream.get("height", 0))
            report["checks"]["resolution"] = {
                "value": f"{width}x{height}",
                "pass": min(width, height) >= 1080,
            }

            fps_parts = video_stream.get("r_frame_rate", "0/1").split("/")
            fps = int(fps_parts[0]) / int(fps_parts[1]) if len(fps_parts) == 2 else 0
            report["checks"]["fps"] = {
                "value": round(fps, 2),
                "pass": fps >= 29,
            }
    except Exception as e:
        print(f"  [WARN] Could not probe video: {e}")

    # Verdict
    all_passed = all(c["pass"] for c in report["checks"].values())
    verdict = "PASS" if all_passed else "FAIL"
    report["verdict"] = verdict

    print(f"\n  QA REPORT")
    print(f"  {'─' * 35}")
    for name, check in report["checks"].items():
        status = "[OK]  " if check["pass"] else "[FAIL]"
        print(f"  {status} {name}: {check['value']}")
    print(f"  {'─' * 35}")
    print(f"  VERDICT: {verdict}")

    return all_passed


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _append_content_log(entry):
    """Append an entry to content_log.json."""
    log = []
    if CONTENT_LOG.exists():
        log = json.loads(CONTENT_LOG.read_text())
    log.append(entry)
    CONTENT_LOG.write_text(json.dumps(log, indent=2))


# ─── Main Pipeline ───────────────────────────────────────────────────────────


def main():
    print("=" * 55)
    print("  AI Avatar Pipeline — Full Production Run")
    print("=" * 55)

    # Check API keys
    required_keys = ["REPLICATE_API_TOKEN", "ELEVENLABS_API_KEY", "HEYGEN_API_KEY"]
    missing = [k for k in required_keys if not os.getenv(k)]
    if missing:
        print(f"\n[ERROR] Missing API keys: {', '.join(missing)}")
        print("Copy config/api_keys.env.example -> config/api_keys.env")
        print("and fill in your API keys.")
        sys.exit(1)

    # Get input from user
    print("\n--- Character Description ---")
    character = input(
        "Describe your avatar character:\n> "
    ) or "young woman, 25 years old, brown hair, green eyes, warm smile"

    print("\n--- Script Text ---")
    script = input(
        "Enter the script for your avatar to speak:\n> "
    ) or "Hello! Welcome to my channel. Today I want to share something exciting with you."

    seed = int(input("\nSeed value (default 42): ") or "42")
    voice = input("Voice (Rachel/Bella/Sarah/Elli, default Rachel): ") or "Rachel"
    platform = input("Platform (tiktok/youtube/instagram, default tiktok): ") or "tiktok"

    # Run pipeline
    print("\n" + "=" * 55)
    print("  Starting pipeline...")
    print("=" * 55)

    # Step 1: Generate avatar
    char_id, images = generate_avatar_images(character, seed)

    # Step 2: Generate voice
    audio_path = generate_voice_audio(script, voice_id=voice)
    if not audio_path:
        print("\n[ABORT] Voice generation failed. Cannot continue.")
        sys.exit(1)

    # Step 3: Create video
    reference_img = str(AVATAR_DIR / f"avatar_reference_{seed}.jpg")
    video_path = create_video(reference_img, audio_path, platform)
    if not video_path:
        print("\n[ABORT] Video generation failed. Cannot continue.")
        sys.exit(1)

    # Step 4: QA check
    passed = run_qa_check(video_path)

    # Final report
    print("\n" + "=" * 55)
    print("  PIPELINE COMPLETE")
    print("=" * 55)
    print(f"  Character: {char_id}")
    print(f"  Audio: {audio_path}")
    print(f"  Video: {video_path}")
    print(f"  QA: {'PASSED' if passed else 'FAILED — review needed'}")
    print("=" * 55)


if __name__ == "__main__":
    main()
