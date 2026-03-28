#!/usr/bin/env python3
"""Quick test: generate avatar photo → voice → 3s video."""

import os
import sys
import json
import time
import requests
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / "config" / "api_keys.env")

OUTPUT = PROJECT_ROOT / "output"
AVATAR_DIR = OUTPUT / "avatars"
AUDIO_DIR = OUTPUT / "audio"
VIDEO_DIR = OUTPUT / "videos"

for d in [AVATAR_DIR, AUDIO_DIR, VIDEO_DIR]:
    d.mkdir(parents=True, exist_ok=True)

SEED = 777

# ─── STEP 1: Generate Avatar via FLUX.1 ─────────────────────────────────────

def step1_avatar():
    import replicate
    print("\n[STEP 1] Generating avatar photo via FLUX.1...")

    prompt = (
        "Professional portrait photo of a beautiful young woman, 25 years old, "
        "light brown wavy hair, warm green eyes, soft smile, gentle expression, "
        "wearing a cozy cream sweater, natural soft lighting, shallow depth of field, "
        "clean minimal background, photorealistic, 8k, shot on Canon EOS R5"
    )

    print(f"  Prompt: {prompt[:80]}...")
    print(f"  Seed: {SEED}")

    output = replicate.run(
        "black-forest-labs/flux-1.1-pro",
        input={
            "prompt": prompt,
            "aspect_ratio": "2:3",
            "output_format": "jpg",
            "output_quality": 100,
            "safety_tolerance": 3,
            "prompt_upsampling": True,
            "seed": SEED
        }
    )

    image_url = str(output)
    print(f"  [OK] Image generated: {image_url[:80]}...")

    # Download
    img_path = AVATAR_DIR / f"avatar_test_{SEED}.jpg"
    resp = requests.get(image_url)
    if resp.status_code == 200:
        img_path.write_bytes(resp.content)
        print(f"  [OK] Saved: {img_path}")
    else:
        print(f"  [FAIL] Download failed: {resp.status_code}")
        sys.exit(1)

    return str(img_path), image_url


# ─── STEP 2: Generate Voice via ElevenLabs ───────────────────────────────────

def step2_voice():
    from elevenlabs.client import ElevenLabs
    print("\n[STEP 2] Generating voice via ElevenLabs...")

    text = "Привет! Я твой новый AI аватар. Рада познакомиться!"
    print(f"  Text: {text}")

    client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

    audio_gen = client.text_to_speech.convert(
        text=text,
        voice_id="Rachel",
        model_id="eleven_multilingual_v2",
        voice_settings={
            "stability": 0.71,
            "similarity_boost": 0.85,
            "style": 0.35,
            "use_speaker_boost": True
        }
    )

    audio_path = AUDIO_DIR / f"audio_test_rachel_ru.mp3"
    with open(audio_path, "wb") as f:
        for chunk in audio_gen:
            f.write(chunk)

    size_kb = os.path.getsize(audio_path) / 1024
    print(f"  [OK] Audio saved: {audio_path} ({size_kb:.1f} KB)")
    return str(audio_path)


# ─── STEP 3: Create Video via HeyGen ────────────────────────────────────────

def step3_video(avatar_image_url, audio_path):
    print("\n[STEP 3] Creating talking video via HeyGen...")

    heygen_key = os.getenv("HEYGEN_API_KEY")

    # First upload the audio to get a URL HeyGen can access
    # We'll use HeyGen's photo avatar with the image URL directly

    print("  Uploading avatar to HeyGen...")

    # Create video
    response = requests.post(
        "https://api.heygen.com/v2/video/generate",
        headers={
            "X-Api-Key": heygen_key,
            "Content-Type": "application/json"
        },
        json={
            "video_inputs": [{
                "character": {
                    "type": "talking_photo",
                    "talking_photo_url": avatar_image_url
                },
                "voice": {
                    "type": "text",
                    "input_text": "Привет! Я твой новый AI аватар. Рада познакомиться!",
                    "voice_id": "c19c75b03ea446a8b62b0b4e1e9c2fba"
                }
            }],
            "dimension": {"width": 1080, "height": 1920}
        }
    )

    result = response.json()
    print(f"  HeyGen response: {json.dumps(result, indent=2)[:300]}")

    video_id = result.get("data", {}).get("video_id")
    if not video_id:
        print(f"  [FAIL] No video_id. Response: {result}")
        return None

    print(f"  [OK] Job started: {video_id}")
    print("  Waiting for render", end="", flush=True)

    for i in range(60):
        time.sleep(5)
        print(".", end="", flush=True)

        status_resp = requests.get(
            "https://api.heygen.com/v1/video_status.get",
            headers={"X-Api-Key": heygen_key},
            params={"video_id": video_id}
        ).json()

        status = status_resp.get("data", {}).get("status")

        if status == "completed":
            video_url = status_resp["data"]["video_url"]
            print(f"\n  [OK] Video ready!")

            # Download
            out_path = VIDEO_DIR / f"video_test_{SEED}_tiktok.mp4"
            vid_resp = requests.get(video_url)
            if vid_resp.status_code == 200:
                out_path.write_bytes(vid_resp.content)
                size_mb = os.path.getsize(out_path) / 1024 / 1024
                print(f"  [OK] Saved: {out_path} ({size_mb:.1f} MB)")
            return str(out_path)

        elif status == "failed":
            error = status_resp.get("data", {}).get("error", "unknown")
            print(f"\n  [FAIL] Render failed: {error}")
            return None

    print("\n  [FAIL] Timeout")
    return None


# ─── MAIN ────────────────────────────────────────────────────────────────────

def main():
    print("=" * 55)
    print("  AI Avatar Pipeline — Test Run")
    print("=" * 55)

    # Check keys
    keys = ["REPLICATE_API_TOKEN", "ELEVENLABS_API_KEY", "HEYGEN_API_KEY"]
    missing = [k for k in keys if not os.getenv(k)]
    if missing:
        print(f"[ERROR] Missing: {', '.join(missing)}")
        sys.exit(1)
    print("[OK] All API keys loaded")

    # Step 1: Avatar
    img_path, img_url = step1_avatar()

    # Step 2: Voice
    audio_path = step2_voice()

    # Step 3: Video
    video_path = step3_video(img_url, audio_path)

    # Report
    print("\n" + "=" * 55)
    print("  TEST COMPLETE")
    print("=" * 55)
    print(f"  Avatar: {img_path}")
    print(f"  Audio:  {audio_path}")
    print(f"  Video:  {video_path or 'FAILED'}")
    print("=" * 55)


if __name__ == "__main__":
    main()
