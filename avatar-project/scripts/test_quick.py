#!/usr/bin/env python3
"""Quick test: generate avatar photo -> voice -> 3s video.
Supports resuming from any step."""

import os
import sys
import json
import time
import base64
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

def get_key():
    return os.getenv("HEYGEN_API_KEY")

def step1_avatar():
    img_path = AVATAR_DIR / f"avatar_test_{SEED}.jpg"
    if img_path.exists() and img_path.stat().st_size > 0:
        print(f"\n[STEP 1] SKIP - avatar already exists: {img_path}")
        return str(img_path)

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
    return str(img_path)

def step2_voice():
    audio_path = AUDIO_DIR / "audio_test_voice_ru.mp3"
    if audio_path.exists() and audio_path.stat().st_size > 0:
        print(f"\n[STEP 2] SKIP - audio already exists: {audio_path}")
        return str(audio_path)

    from elevenlabs.client import ElevenLabs
    print("\n[STEP 2] Generating voice via ElevenLabs...")
    text = "Privet! Ya tvoy noviy AI avatar. Rada poznakomitsya!"
    client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

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

def get_talking_photo_id(local_image_path):
    """Upload image to HeyGen and get talking_photo_id."""
    key = get_key()

    # Step 1: List existing avatars
    print("  Checking existing talking photos...")
    try:
        r = requests.get(
            "https://api.heygen.com/v2/avatars",
            headers={"X-Api-Key": key, "Accept": "application/json"}
        )
        if r.status_code == 200:
            data = r.json()
            avatars = data.get("data", {}).get("avatars", [])
            for av in avatars:
                if av.get("avatar_type") == "talking_photo":
                    photo_id = av.get("avatar_id", av.get("talking_photo_id"))
                    if photo_id:
                        print(f"  [OK] Found existing talking photo: {photo_id}")
                        return photo_id
            print(f"  No talking photos found. Total avatars: {len(avatars)}")
            # Show what types exist
            types = set(av.get("avatar_type", "unknown") for av in avatars)
            if types:
                print(f"  Avatar types found: {types}")
    except Exception as e:
        print(f"  List failed: {e}")

    # Step 2: Try v1 talking photo list
    print("  Trying v1 talking photo list...")
    try:
        r = requests.get(
            "https://api.heygen.com/v1/talking_photo.list",
            headers={"X-Api-Key": key, "Accept": "application/json"}
        )
        print(f"  v1 list -> {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"  v1 response: {json.dumps(data, indent=2)[:500]}")
            photos = data.get("data", {}).get("talking_photos", data.get("data", {}).get("list", []))
            if isinstance(photos, list) and photos:
                photo_id = photos[0].get("talking_photo_id", photos[0].get("id"))
                if photo_id:
                    print(f"  [OK] Found: {photo_id}")
                    return photo_id
    except Exception as e:
        print(f"  v1 list failed: {e}")

    # Step 3: Upload via multiple methods
    print("  Uploading talking photo...")
    with open(local_image_path, "rb") as f:
        image_data = f.read()
    image_b64 = base64.b64encode(image_data).decode("utf-8")

    attempts = [
        # Method 1: upload.heygen.com multipart with 'image'
        {"url": "https://upload.heygen.com/v1/talking_photo",
         "method": "multipart", "field": "image", "desc": "upload.heygen multipart image"},
        # Method 2: upload.heygen.com multipart with 'file'
        {"url": "https://upload.heygen.com/v1/talking_photo",
         "method": "multipart", "field": "file", "desc": "upload.heygen multipart file"},
        # Method 3: api.heygen.com JSON with base64
        {"url": "https://api.heygen.com/v1/talking_photo",
         "method": "json_b64", "desc": "api.heygen json base64"},
        # Method 4: api.heygen.com JSON with image_url (use data URI)
        {"url": "https://api.heygen.com/v2/talking_photo",
         "method": "json_b64", "desc": "api.heygen v2 json base64"},
        # Method 5: upload asset then use it
        {"url": "https://upload.heygen.com/v1/asset",
         "method": "multipart", "field": "file", "desc": "upload asset"},
    ]

    for attempt in attempts:
        desc = attempt["desc"]
        url = attempt["url"]
        try:
            if attempt["method"] == "multipart":
                r = requests.post(url,
                    headers={"X-Api-Key": key, "Accept": "application/json"},
                    files={attempt["field"]: ("avatar.jpg", image_data, "image/jpeg")})
            elif attempt["method"] == "json_b64":
                r = requests.post(url,
                    headers={"X-Api-Key": key, "Content-Type": "application/json"},
                    json={"image": f"data:image/jpeg;base64,{image_b64}"})

            print(f"  [{desc}] -> {r.status_code}")
            if r.status_code in [200, 201]:
                data = r.json()
                print(f"  Response: {json.dumps(data, indent=2)[:400]}")
                d = data.get("data", data)
                for id_key in ["talking_photo_id", "id", "asset_id", "avatar_id"]:
                    if d.get(id_key):
                        print(f"  [OK] Got ID: {d[id_key]}")
                        return d[id_key]
        except Exception as e:
            print(f"  [{desc}] error: {e}")

    return None

def step3_video(local_image_path, audio_path):
    out_path = VIDEO_DIR / f"video_test_{SEED}_tiktok.mp4"
    if out_path.exists() and out_path.stat().st_size > 0:
        print(f"\n[STEP 3] SKIP - video already exists: {out_path}")
        return str(out_path)

    print("\n[STEP 3] Creating talking video via HeyGen...")
    key = get_key()

    # Check for manual photo ID in env
    photo_id_env = os.getenv("HEYGEN_PHOTO_ID")
    if photo_id_env:
        talking_photo_id = photo_id_env
        print(f"  Using HEYGEN_PHOTO_ID from env: {talking_photo_id}")
    else:
        talking_photo_id = get_talking_photo_id(local_image_path)

    if not talking_photo_id:
        print("  [FAIL] Could not get talking_photo_id")
        print("")
        print("  MANUAL FIX:")
        print("  1. Go to app.heygen.com -> Assets -> Talking Photos")
        print("  2. Upload avatar_test_777.jpg")
        print("  3. Click on it, copy the ID from the URL")
        print("  4. Add to config/api_keys.env:")
        print("     HEYGEN_PHOTO_ID=your_photo_id_here")
        print("  5. Re-run this script")
        return None

    print(f"  talking_photo_id: {talking_photo_id}")

    # Generate video
    response = requests.post(
        "https://api.heygen.com/v2/video/generate",
        headers={"X-Api-Key": key, "Content-Type": "application/json"},
        json={
            "video_inputs": [{
                "character": {
                    "type": "talking_photo",
                    "talking_photo_id": talking_photo_id
                },
                "voice": {
                    "type": "text",
                    "input_text": "Privet! Ya tvoy noviy AI avatar. Rada poznakomitsya!",
                    "voice_id": "c19c75b03ea446a8b62b0b4e1e9c2fba"
                }
            }],
            "dimension": {"width": 1080, "height": 1920}
        }
    )
    result = response.json()
    print(f"  HeyGen response: {json.dumps(result, indent=2)[:500]}")

    video_id = None
    if result.get("data"):
        video_id = result["data"].get("video_id")
    if not video_id:
        print(f"  [FAIL] No video_id")
        return None

    print(f"  [OK] Job started: {video_id}")
    print("  Waiting for render", end="", flush=True)
    for i in range(60):
        time.sleep(5)
        print(".", end="", flush=True)
        status_resp = requests.get(
            "https://api.heygen.com/v1/video_status.get",
            headers={"X-Api-Key": key},
            params={"video_id": video_id}
        ).json()
        status = status_resp.get("data", {}).get("status")
        if status == "completed":
            video_url = status_resp["data"]["video_url"]
            vid_resp = requests.get(video_url)
            if vid_resp.status_code == 200:
                out_path.write_bytes(vid_resp.content)
                print(f"\n  [OK] Video saved: {out_path}")
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
    img_path = step1_avatar()
    audio_path = step2_voice()
    video_path = step3_video(img_path, audio_path)
    print("\n" + "=" * 55)
    print("  TEST COMPLETE")
    print("=" * 55)
    print(f"  Avatar: {img_path}")
    print(f"  Audio:  {audio_path}")
    print(f"  Video:  {video_path or 'FAILED'}")
    print("=" * 55)

if __name__ == "__main__":
    main()
