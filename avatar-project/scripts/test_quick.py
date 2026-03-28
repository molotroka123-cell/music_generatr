#!/usr/bin/env python3
"""Quick test: generate avatar photo -> voice -> 3s video.
Supports resuming from any step."""

import os
import sys
import json
import time
import requests
from pathlib import Path
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

def step1_avatar():
    # Check if already exists
    img_path = AVATAR_DIR / f"avatar_test_{SEED}.jpg"
    if img_path.exists() and img_path.stat().st_size > 0:
        print(f"\n[STEP 1] SKIP - avatar already exists: {img_path}")
        # We need the URL for HeyGen, re-generate it
        import replicate
        prompt = ("Professional portrait photo of a beautiful young woman, 25 years old, "
            "light brown wavy hair, warm green eyes, soft smile, gentle expression, "
            "wearing a cozy cream sweater, natural soft lighting, shallow depth of field, "
            "clean minimal background, photorealistic, 8k, shot on Canon EOS R5")
        output = replicate.run("black-forest-labs/flux-1.1-pro", input={
            "prompt": prompt, "aspect_ratio": "2:3", "output_format": "jpg",
            "output_quality": 100, "safety_tolerance": 3, "prompt_upsampling": True, "seed": SEED})
        return str(img_path), str(output)

    import replicate
    print("\n[STEP 1] Generating avatar photo via FLUX.1...")
    prompt = ("Professional portrait photo of a beautiful young woman, 25 years old, "
        "light brown wavy hair, warm green eyes, soft smile, gentle expression, "
        "wearing a cozy cream sweater, natural soft lighting, shallow depth of field, "
        "clean minimal background, photorealistic, 8k, shot on Canon EOS R5")
    print(f"  Seed: {SEED}")
    output = replicate.run("black-forest-labs/flux-1.1-pro", input={
        "prompt": prompt, "aspect_ratio": "2:3", "output_format": "jpg",
        "output_quality": 100, "safety_tolerance": 3, "prompt_upsampling": True, "seed": SEED})
    image_url = str(output)
    print(f"  [OK] Image generated")
    resp = requests.get(image_url)
    if resp.status_code == 200:
        img_path.write_bytes(resp.content)
        print(f"  [OK] Saved: {img_path}")
    else:
        print(f"  [FAIL] Download failed")
        sys.exit(1)
    return str(img_path), image_url

def step2_voice():
    # Check if already exists
    audio_path = AUDIO_DIR / "audio_test_voice_ru.mp3"
    if audio_path.exists() and audio_path.stat().st_size > 0:
        print(f"\n[STEP 2] SKIP - audio already exists: {audio_path}")
        return str(audio_path)

    from elevenlabs.client import ElevenLabs
    print("\n[STEP 2] Generating voice via ElevenLabs...")
    text = "Privet! Ya tvoy noviy AI avatar. Rada poznakomitsya!"
    client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

    # Get available voices and pick first female voice
    voices = client.voices.get_all()
    voice_id = None
    voice_name = None
    for v in voices.voices:
        if hasattr(v, 'labels') and v.labels and v.labels.get('gender') == 'female':
            voice_id = v.voice_id
            voice_name = v.name
            break
    if not voice_id:
        voice_id = voices.voices[0].voice_id
        voice_name = voices.voices[0].name

    print(f"  Voice: {voice_name} ({voice_id})")
    print(f"  Text: {text}")

    audio_gen = client.text_to_speech.convert(text=text, voice_id=voice_id,
        model_id="eleven_multilingual_v2", voice_settings={"stability": 0.71,
        "similarity_boost": 0.85, "style": 0.35, "use_speaker_boost": True})
    with open(audio_path, "wb") as f:
        for chunk in audio_gen:
            f.write(chunk)
    size_kb = os.path.getsize(audio_path) / 1024
    print(f"  [OK] Audio saved: {audio_path} ({size_kb:.1f} KB)")
    return str(audio_path)

def step3_video(avatar_image_url, audio_path):
    # Check if already exists
    out_path = VIDEO_DIR / f"video_test_{SEED}_tiktok.mp4"
    if out_path.exists() and out_path.stat().st_size > 0:
        print(f"\n[STEP 3] SKIP - video already exists: {out_path}")
        return str(out_path)

    print("\n[STEP 3] Creating talking video via HeyGen...")
    heygen_key = os.getenv("HEYGEN_API_KEY")
    response = requests.post("https://api.heygen.com/v2/video/generate",
        headers={"X-Api-Key": heygen_key, "Content-Type": "application/json"},
        json={"video_inputs": [{"character": {"type": "talking_photo",
            "talking_photo_url": avatar_image_url},
            "voice": {"type": "text",
            "input_text": "Privet! Ya tvoy noviy AI avatar. Rada poznakomitsya!",
            "voice_id": "c19c75b03ea446a8b62b0b4e1e9c2fba"}}],
            "dimension": {"width": 1080, "height": 1920}})
    result = response.json()
    print(f"  HeyGen response: {json.dumps(result, indent=2)[:500]}")
    video_id = result.get("data", {}).get("video_id")
    if not video_id:
        print(f"  [FAIL] No video_id")
        return None
    print(f"  [OK] Job started: {video_id}")
    print("  Waiting for render", end="", flush=True)
    for i in range(60):
        time.sleep(5)
        print(".", end="", flush=True)
        status_resp = requests.get("https://api.heygen.com/v1/video_status.get",
            headers={"X-Api-Key": heygen_key}, params={"video_id": video_id}).json()
        status = status_resp.get("data", {}).get("status")
        if status == "completed":
            video_url = status_resp["data"]["video_url"]
            vid_resp = requests.get(video_url)
            if vid_resp.status_code == 200:
                out_path.write_bytes(vid_resp.content)
                print(f"\n  [OK] Saved: {out_path}")
            return str(out_path)
        elif status == "failed":
            error = status_resp.get("data", {}).get("error", "unknown")
            print(f"\n  [FAIL] Render failed: {error}")
            return None
    print("\n  [FAIL] Timeout")
    return None

def main():
    print("=" * 55)
    print("  AI Avatar Pipeline - Test Run")
    print("  (auto-skips completed steps)")
    print("=" * 55)
    keys = ["REPLICATE_API_TOKEN", "ELEVENLABS_API_KEY", "HEYGEN_API_KEY"]
    missing = [k for k in keys if not os.getenv(k)]
    if missing:
        print(f"[ERROR] Missing: {', '.join(missing)}")
        sys.exit(1)
    print("[OK] All API keys loaded")
    img_path, img_url = step1_avatar()
    audio_path = step2_voice()
    video_path = step3_video(img_url, audio_path)
    print("\n" + "=" * 55)
    print("  TEST COMPLETE")
    print("=" * 55)
    print(f"  Avatar: {img_path}")
    print(f"  Audio:  {audio_path}")
    print(f"  Video:  {video_path or 'FAILED'}")
    print("=" * 55)

if __name__ == "__main__":
    main()
