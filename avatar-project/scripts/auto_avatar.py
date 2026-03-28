#!/usr/bin/env python3
"""
Fully Autonomous AI Avatar Generator
=====================================
Generates avatar photo → voice → talking video automatically.
No manual steps required.

Usage:
    python auto_avatar.py
    python auto_avatar.py --description "young woman with blue eyes" --text "Hello!"
    python auto_avatar.py --seed 42
"""

import os
import sys
import json
import time
import argparse
import requests
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# ─── Setup ──────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / "config" / "api_keys.env")

OUTPUT = PROJECT_ROOT / "output"
AVATAR_DIR = OUTPUT / "avatars"
AUDIO_DIR = OUTPUT / "audio"
VIDEO_DIR = OUTPUT / "videos"

for d in [AVATAR_DIR, AUDIO_DIR, VIDEO_DIR]:
    d.mkdir(parents=True, exist_ok=True)


def check_keys():
    required = {
        "REPLICATE_API_TOKEN": os.getenv("REPLICATE_API_TOKEN"),
        "ELEVENLABS_API_KEY": os.getenv("ELEVENLABS_API_KEY"),
        "HEYGEN_API_KEY": os.getenv("HEYGEN_API_KEY"),
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        print(f"[ERROR] Missing API keys: {', '.join(missing)}")
        print("  Edit config/api_keys.env with your keys")
        sys.exit(1)
    print("[OK] All API keys loaded")
    return required


# ─── Step 1: Generate Avatar Photo (FLUX.1 via Replicate) ──────────────────

def generate_avatar(description, seed):
    import replicate

    prompt = (
        f"Professional portrait photo of {description}, "
        "natural soft lighting, shallow depth of field, "
        "clean minimal background, photorealistic, 8k, shot on Canon EOS R5"
    )

    print(f"\n[STEP 1] Generating avatar via FLUX.1...")
    print(f"  Prompt: {prompt[:80]}...")
    print(f"  Seed: {seed}")

    # Check if already generated (resume support)
    img_path = AVATAR_DIR / f"avatar_auto_{seed}.jpg"
    url_path = AVATAR_DIR / f"avatar_auto_{seed}.url"

    if img_path.exists() and url_path.exists():
        image_url = url_path.read_text().strip()
        print(f"  [SKIP] Already exists: {img_path}")
        print(f"  [SKIP] URL: {image_url[:60]}...")
        return str(img_path), image_url

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

    image_url = str(output)
    print(f"  [OK] Generated: {image_url[:60]}...")

    # Download
    resp = requests.get(image_url)
    if resp.status_code != 200:
        print(f"  [FAIL] Download failed: {resp.status_code}")
        sys.exit(1)

    img_path.write_bytes(resp.content)
    url_path.write_text(image_url)
    print(f"  [OK] Saved: {img_path} ({len(resp.content) / 1024:.0f} KB)")
    return str(img_path), image_url


# ─── Step 2: Generate Voice (ElevenLabs) ───────────────────────────────────

def generate_voice(text, seed):
    from elevenlabs.client import ElevenLabs

    print(f"\n[STEP 2] Generating voice via ElevenLabs...")
    print(f"  Text: {text}")

    # Resume support
    audio_path = AUDIO_DIR / f"audio_auto_{seed}.mp3"
    if audio_path.exists():
        print(f"  [SKIP] Already exists: {audio_path}")
        return str(audio_path)

    client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

    # Auto-detect a good female voice
    voice_id = None
    voice_name = None
    try:
        voices = client.voices.get_all()
        voice_list = voices.voices if hasattr(voices, "voices") else voices
        for v in voice_list:
            labels = getattr(v, "labels", {}) or {}
            gender = labels.get("gender", "").lower()
            if gender == "female":
                voice_id = v.voice_id
                voice_name = v.name
                break
        # Fallback: just pick the first voice
        if not voice_id and voice_list:
            v = voice_list[0]
            voice_id = v.voice_id
            voice_name = v.name
    except Exception as e:
        print(f"  [WARN] Could not list voices: {e}")

    # Ultimate fallback
    if not voice_id:
        voice_id = "21m00Tcm4TlvDq8ikWAM"  # Rachel
        voice_name = "Rachel (fallback)"

    print(f"  Voice: {voice_name} ({voice_id})")

    audio_gen = client.text_to_speech.convert(
        text=text,
        voice_id=voice_id,
        model_id="eleven_multilingual_v2",
        voice_settings={
            "stability": 0.71,
            "similarity_boost": 0.85,
            "style": 0.35,
            "use_speaker_boost": True,
        },
    )

    with open(audio_path, "wb") as f:
        for chunk in audio_gen:
            f.write(chunk)

    size_kb = os.path.getsize(audio_path) / 1024
    print(f"  [OK] Saved: {audio_path} ({size_kb:.1f} KB)")
    return str(audio_path)


# ─── Step 3: Auto-detect HeyGen voice ─────────────────────────────────────

def get_heygen_voice():
    """Get a working voice_id from HeyGen API."""
    key = os.getenv("HEYGEN_API_KEY")
    try:
        resp = requests.get(
            "https://api.heygen.com/v2/voices",
            headers={"X-Api-Key": key},
        )
        data = resp.json()
        voices = data.get("data", {}).get("voices", [])
        if voices:
            v = voices[0]
            vid = v.get("voice_id", "")
            name = v.get("name", "unknown")
            print(f"  HeyGen voice: {name} ({vid})")
            return vid
    except Exception as e:
        print(f"  [WARN] Could not get HeyGen voices: {e}")

    return None


# ─── Step 3: Upload photo to HeyGen and create video ──────────────────────

def upload_to_heygen(image_path):
    """Try to upload image to HeyGen as a talking photo, return talking_photo_id."""
    key = os.getenv("HEYGEN_API_KEY")

    # Method 1: Upload via /v1/talking_photo endpoint
    try:
        print("  Trying upload via /v1/talking_photo...")
        with open(image_path, "rb") as f:
            resp = requests.post(
                "https://upload.heygen.com/v1/talking_photo",
                headers={"X-Api-Key": key},
                files={"image": ("avatar.jpg", f, "image/jpeg")},
            )
        data = resp.json()
        tp_id = data.get("data", {}).get("talking_photo_id")
        if tp_id:
            print(f"  [OK] Upload success: {tp_id}")
            return tp_id
        print(f"  Upload response: {json.dumps(data)[:200]}")
    except Exception as e:
        print(f"  Upload method 1 failed: {e}")

    # Method 2: Upload via /v1/asset endpoint
    try:
        print("  Trying upload via /v1/asset...")
        with open(image_path, "rb") as f:
            resp = requests.post(
                "https://upload.heygen.com/v1/asset",
                headers={"X-Api-Key": key},
                files={"file": ("avatar.jpg", f, "image/jpeg")},
            )
        data = resp.json()
        asset_id = data.get("data", {}).get("asset_id") or data.get("data", {}).get("id")
        if asset_id:
            print(f"  [OK] Asset uploaded: {asset_id}")
            return asset_id
        print(f"  Asset response: {json.dumps(data)[:200]}")
    except Exception as e:
        print(f"  Upload method 2 failed: {e}")

    return None


def generate_video(image_url, image_path, text, seed):
    """Generate talking head video via HeyGen."""
    key = os.getenv("HEYGEN_API_KEY")

    print(f"\n[STEP 3] Creating talking video via HeyGen...")

    # Resume support
    video_path = VIDEO_DIR / f"video_auto_{seed}.mp4"
    if video_path.exists():
        print(f"  [SKIP] Already exists: {video_path}")
        return str(video_path)

    # Auto-detect voice
    voice_id = get_heygen_voice()
    if not voice_id:
        print("  [FAIL] No HeyGen voice found")
        return None

    # Strategy 1: Try talking_photo_url with the FLUX.1 URL directly
    print("  Strategy 1: Using FLUX.1 URL directly...")
    payload = {
        "video_inputs": [
            {
                "character": {
                    "type": "talking_photo",
                    "talking_photo_url": image_url,
                },
                "voice": {
                    "type": "text",
                    "input_text": text,
                    "voice_id": voice_id,
                },
            }
        ],
        "dimension": {"width": 1080, "height": 1920},
    }

    resp = requests.post(
        "https://api.heygen.com/v2/video/generate",
        headers={"X-Api-Key": key, "Content-Type": "application/json"},
        json=payload,
    )
    result = resp.json()
    video_id = result.get("data", {}).get("video_id")

    # Strategy 2: If URL method failed, try uploading the photo first
    if not video_id:
        print(f"  Strategy 1 failed: {json.dumps(result)[:200]}")
        print("  Strategy 2: Uploading photo to HeyGen...")

        tp_id = upload_to_heygen(image_path)
        if tp_id:
            payload["video_inputs"][0]["character"] = {
                "type": "talking_photo",
                "talking_photo_id": tp_id,
            }
            resp = requests.post(
                "https://api.heygen.com/v2/video/generate",
                headers={"X-Api-Key": key, "Content-Type": "application/json"},
                json=payload,
            )
            result = resp.json()
            video_id = result.get("data", {}).get("video_id")

    if not video_id:
        print(f"  [FAIL] Could not start video generation")
        print(f"  Response: {json.dumps(result, indent=2)[:500]}")
        return None

    print(f"  [OK] Video job started: {video_id}")
    print("  Waiting for render", end="", flush=True)

    # Poll for completion (up to 5 minutes)
    for i in range(60):
        time.sleep(5)
        print(".", end="", flush=True)

        status_resp = requests.get(
            "https://api.heygen.com/v1/video_status.get",
            headers={"X-Api-Key": key},
            params={"video_id": video_id},
        ).json()

        status = status_resp.get("data", {}).get("status")

        if status == "completed":
            video_url = status_resp["data"]["video_url"]
            print(f"\n  [OK] Video ready!")

            vid_resp = requests.get(video_url)
            if vid_resp.status_code == 200:
                video_path.write_bytes(vid_resp.content)
                size_mb = os.path.getsize(video_path) / 1024 / 1024
                print(f"  [OK] Saved: {video_path} ({size_mb:.1f} MB)")
                return str(video_path)
            else:
                print(f"  [FAIL] Download failed: {vid_resp.status_code}")
                return None

        elif status == "failed":
            error = status_resp.get("data", {}).get("error", "unknown")
            print(f"\n  [FAIL] Render failed: {error}")
            return None

    print("\n  [FAIL] Timeout after 5 minutes")
    return None


# ─── Main ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Autonomous AI Avatar Generator")
    parser.add_argument(
        "--description",
        default="a beautiful young woman, 25 years old, light brown wavy hair, "
        "warm green eyes, soft smile, wearing a cozy cream sweater",
        help="Avatar appearance description",
    )
    parser.add_argument(
        "--text",
        default="Привет! Я твой новый AI аватар. Рада познакомиться!",
        help="Text for the avatar to speak",
    )
    parser.add_argument("--seed", type=int, default=777, help="Seed for consistency")
    args = parser.parse_args()

    print("=" * 55)
    print("  AI Avatar — Fully Autonomous Generator")
    print("=" * 55)
    print(f"  Description: {args.description[:50]}...")
    print(f"  Text: {args.text}")
    print(f"  Seed: {args.seed}")
    print("=" * 55)

    check_keys()

    # Step 1: Generate avatar photo
    img_path, img_url = generate_avatar(args.description, args.seed)

    # Step 2: Generate voice audio
    audio_path = generate_voice(args.text, args.seed)

    # Step 3: Generate talking video
    video_path = generate_video(img_url, img_path, args.text, args.seed)

    # Summary
    print("\n" + "=" * 55)
    print("  RESULT")
    print("=" * 55)
    print(f"  Avatar: {img_path}")
    print(f"  Audio:  {audio_path}")
    if video_path:
        print(f"  Video:  {video_path}")
        print("  Status: SUCCESS")
    else:
        print("  Video:  FAILED")
        print("  Status: PARTIAL (photo + audio OK, video failed)")
        print("\n  The avatar photo and audio were generated successfully.")
        print("  HeyGen video generation failed — this may be an API limitation.")
        print("  You can try uploading the photo manually at app.heygen.com")
    print("=" * 55)


if __name__ == "__main__":
    main()
