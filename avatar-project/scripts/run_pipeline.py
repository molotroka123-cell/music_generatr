#!/usr/bin/env python3
"""AI Avatar Pipeline - Full Production Orchestrator."""

import json
import os
import sys
import time
import requests
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / "config" / "api_keys.env")

OUTPUT_DIR = PROJECT_ROOT / "output"
AUDIO_DIR = OUTPUT_DIR / "audio"
VIDEO_DIR = OUTPUT_DIR / "videos"
AVATAR_DIR = OUTPUT_DIR / "avatars"
FRAMES_DIR = OUTPUT_DIR / "frames"
AVATAR_LIBRARY = PROJECT_ROOT / "avatar_library.json"
CONTENT_LOG = PROJECT_ROOT / "content_log.json"

def generate_avatar_images(character_desc, seed=42):
    import replicate
    print("\n[STEP 1] Avatar Designer - Generating images...")
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
            output = replicate.run("black-forest-labs/flux-1.1-pro", input={
                "prompt": prompt, "aspect_ratio": "2:3", "output_format": "jpg",
                "output_quality": 100, "safety_tolerance": 3, "prompt_upsampling": True, "seed": seed})
            image_url = str(output)
            results[set_name] = [image_url]
            img_path = AVATAR_DIR / f"avatar_{set_name}_{seed}.jpg"
            response = requests.get(image_url)
            if response.status_code == 200:
                img_path.write_bytes(response.content)
                print(f"    [OK] Saved: {img_path.name}")
        except Exception as e:
            print(f"    [FAIL] {set_name}: {e}")
            results[set_name] = []
    character_id = f"char_{seed}"
    library = []
    if AVATAR_LIBRARY.exists():
        library = json.loads(AVATAR_LIBRARY.read_text())
    library.append({"character_id": character_id, "seed": seed, "base_prompt": character_desc,
                    "created_at": datetime.now().isoformat(), "images": results})
    AVATAR_LIBRARY.write_text(json.dumps(library, indent=2))
    print(f"  [OK] Avatar library updated: {character_id}")
    return character_id, results

def generate_voice_audio(script_text, voice_id="Rachel", language="ru"):
    from elevenlabs.client import ElevenLabs
    print("\n[STEP 2] Voice Producer - Generating audio...")
    client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))
    try:
        audio_gen = client.text_to_speech.convert(text=script_text, voice_id=voice_id,
            model_id="eleven_multilingual_v2", voice_settings={"stability": 0.71,
            "similarity_boost": 0.85, "style": 0.35, "use_speaker_boost": True})
        script_id = f"script_{int(time.time())}"
        audio_path = AUDIO_DIR / f"audio_{script_id}_{voice_id}_{language}.mp3"
        with open(audio_path, "wb") as f:
            for chunk in audio_gen:
                f.write(chunk)
        print(f"  [OK] Audio saved: {audio_path.name}")
        return str(audio_path)
    except Exception as e:
        print(f"  [FAIL] Voice generation: {e}")
        return None

def create_video(avatar_image_path, audio_path, platform="tiktok"):
    print("\n[STEP 3] Video Generator - Creating video...")
    heygen_key = os.getenv("HEYGEN_API_KEY")
    if not heygen_key:
        print("  [FAIL] HEYGEN_API_KEY not set")
        return None
    dimensions = {"tiktok": {"width": 1080, "height": 1920},
                  "youtube": {"width": 1920, "height": 1080},
                  "instagram": {"width": 1080, "height": 1080}}
    dim = dimensions.get(platform, dimensions["tiktok"])
    try:
        response = requests.post("https://api.heygen.com/v2/video/generate",
            headers={"X-Api-Key": heygen_key}, json={"video_inputs": [{
                "character": {"type": "talking_photo", "talking_photo_url": avatar_image_path},
                "voice": {"type": "audio", "audio_url": audio_path}}],
                "dimension": dim})
        result = response.json()
        video_id = result.get("data", {}).get("video_id")
        if not video_id:
            print(f"  [FAIL] No video_id: {result}")
            return None
        print(f"  [OK] Job started: {video_id}")
        for _ in range(30):
            time.sleep(10)
            status_resp = requests.get("https://api.heygen.com/v1/video_status.get",
                headers={"X-Api-Key": heygen_key}, params={"video_id": video_id}).json()
            status = status_resp.get("data", {}).get("status")
            if status == "completed":
                video_url = status_resp["data"]["video_url"]
                out_path = VIDEO_DIR / f"video_{video_id}_{platform}.mp4"
                vid_resp = requests.get(video_url)
                if vid_resp.status_code == 200:
                    out_path.write_bytes(vid_resp.content)
                    print(f"  [OK] Saved: {out_path.name}")
                return str(out_path)
            elif status == "failed":
                print("  [FAIL] Render failed")
                return None
        return None
    except Exception as e:
        print(f"  [FAIL] Video generation: {e}")
        return None

def main():
    print("=" * 55)
    print("  AI Avatar Pipeline - Full Production Run")
    print("=" * 55)
    for d in [AUDIO_DIR, VIDEO_DIR, AVATAR_DIR, FRAMES_DIR]:
        d.mkdir(parents=True, exist_ok=True)
    required_keys = ["REPLICATE_API_TOKEN", "ELEVENLABS_API_KEY", "HEYGEN_API_KEY"]
    missing = [k for k in required_keys if not os.getenv(k)]
    if missing:
        print(f"\n[ERROR] Missing API keys: {', '.join(missing)}")
        sys.exit(1)
    character = input("Describe your avatar character:\n> ") or "young woman, 25 years old, brown hair, green eyes"
    script = input("Enter the script:\n> ") or "Hello! Welcome to my channel."
    seed = int(input("Seed (default 42): ") or "42")
    voice = input("Voice (Rachel/Bella/Sarah/Elli): ") or "Rachel"
    platform = input("Platform (tiktok/youtube/instagram): ") or "tiktok"
    char_id, images = generate_avatar_images(character, seed)
    audio_path = generate_voice_audio(script, voice_id=voice)
    if not audio_path:
        sys.exit(1)
    reference_img = str(AVATAR_DIR / f"avatar_reference_{seed}.jpg")
    video_path = create_video(reference_img, audio_path, platform)
    print("\n" + "=" * 55)
    print("  PIPELINE COMPLETE")
    print("=" * 55)
    print(f"  Character: {char_id}")
    print(f"  Audio: {audio_path}")
    print(f"  Video: {video_path or 'FAILED'}")
    print("=" * 55)

if __name__ == "__main__":
    main()
