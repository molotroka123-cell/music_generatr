#!/usr/bin/env python3
"""
AI Avatar Generator - Fully Automatic
Generates photo -> voice -> talking video
No manual steps required.
"""

import os
import sys
import json
import time
import requests
from pathlib import Path
from dotenv import load_dotenv

# Setup
PROJECT = Path(__file__).parent.parent
load_dotenv(PROJECT / "config" / "api_keys.env")

OUT = PROJECT / "output"
for d in [OUT/"avatars", OUT/"audio", OUT/"videos"]:
    d.mkdir(parents=True, exist_ok=True)


def generate_photo(description, seed=777):
    """Step 1: Generate avatar photo via FLUX.1, return public URL."""
    import replicate
    print("\n[1/3] Generating avatar photo...")
    print(f"  Description: {description[:60]}...")
    
    output = replicate.run("black-forest-labs/flux-1.1-pro", input={
        "prompt": description,
        "aspect_ratio": "2:3",
        "output_format": "jpg",
        "output_quality": 100,
        "safety_tolerance": 3,
        "prompt_upsampling": True,
        "seed": seed
    })
    
    image_url = str(output)
    
    # Save locally too
    local_path = OUT / "avatars" / f"avatar_{seed}.jpg"
    resp = requests.get(image_url)
    if resp.status_code == 200:
        local_path.write_bytes(resp.content)
    
    print(f"  [OK] Photo generated")
    print(f"  URL: {image_url[:80]}...")
    print(f"  Local: {local_path}")
    return image_url


def generate_voice(text):
    """Step 2: Generate voice via ElevenLabs, return local path."""
    from elevenlabs.client import ElevenLabs
    print("\n[2/3] Generating voice...")
    print(f"  Text: {text}")
    
    client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))
    
    # Find female voice automatically
    voices = client.voices.get_all()
    voice_id = None
    for v in voices.voices:
        if hasattr(v, 'labels') and v.labels and v.labels.get('gender') == 'female':
            voice_id = v.voice_id
            print(f"  Voice: {v.name}")
            break
    if not voice_id:
        voice_id = voices.voices[0].voice_id
    
    audio = client.text_to_speech.convert(
        text=text, voice_id=voice_id,
        model_id="eleven_multilingual_v2",
        voice_settings={"stability": 0.71, "similarity_boost": 0.85,
                        "style": 0.35, "use_speaker_boost": True}
    )
    
    audio_path = OUT / "audio" / f"voice_{int(time.time())}.mp3"
    with open(audio_path, "wb") as f:
        for chunk in audio:
            f.write(chunk)
    
    print(f"  [OK] Audio saved: {audio_path}")
    return str(audio_path)


def get_heygen_voice():
    """Get a female voice ID from HeyGen."""
    key = os.getenv("HEYGEN_API_KEY")
    r = requests.get("https://api.heygen.com/v2/voices",
                     headers={"X-Api-Key": key})
    if r.status_code == 200:
        voices = r.json().get("data", {}).get("voices", [])
        for v in voices:
            if v.get("gender") == "female":
                return v["voice_id"], v["name"].strip()
        if voices:
            return voices[0]["voice_id"], voices[0]["name"].strip()
    return None, None


def generate_video(image_url, text, seed=777):
    """Step 3: Create talking video via HeyGen using photo URL directly."""
    print("\n[3/3] Creating talking video...")
    key = os.getenv("HEYGEN_API_KEY")
    
    # Get HeyGen voice
    voice_id, voice_name = get_heygen_voice()
    if not voice_id:
        print("  [FAIL] No HeyGen voice found")
        return None
    print(f"  HeyGen voice: {voice_name}")
    
    # Send photo URL directly to HeyGen - no upload needed!
    r = requests.post(
        "https://api.heygen.com/v2/video/generate",
        headers={"X-Api-Key": key, "Content-Type": "application/json"},
        json={
            "video_inputs": [{
                "character": {
                    "type": "talking_photo",
                    "talking_photo_url": image_url
                },
                "voice": {
                    "type": "text",
                    "input_text": text,
                    "voice_id": voice_id
                }
            }],
            "dimension": {"width": 1080, "height": 1920}
        }
    )
    
    result = r.json()
    
    # Check for error
    if result.get("error"):
        err = result["error"]
        msg = err.get("message", str(err))
        
        # If talking_photo_url not supported, try with talking_photo_id
        if "talking_photo_id" in msg or "invalid_parameter" in str(err.get("code", "")):
            print("  talking_photo_url not supported, trying talking_photo_id...")
            
            # Try to find or use env photo ID
            photo_id = os.getenv("HEYGEN_PHOTO_ID")
            if not photo_id:
                # List photos and use last non-preset
                lr = requests.get("https://api.heygen.com/v1/talking_photo.list",
                                  headers={"X-Api-Key": key})
                photos = lr.json().get("data", []) if isinstance(lr.json().get("data"), list) else lr.json().get("data", {}).get("talking_photos", [])
                non_preset = [p for p in photos if not p.get("is_preset")]
                if non_preset:
                    photo_id = non_preset[-1].get("id")
            
            if photo_id:
                r = requests.post(
                    "https://api.heygen.com/v2/video/generate",
                    headers={"X-Api-Key": key, "Content-Type": "application/json"},
                    json={
                        "video_inputs": [{
                            "character": {
                                "type": "talking_photo",
                                "talking_photo_id": photo_id
                            },
                            "voice": {
                                "type": "text",
                                "input_text": text,
                                "voice_id": voice_id
                            }
                        }],
                        "dimension": {"width": 1080, "height": 1920}
                    }
                )
                result = r.json()
            else:
                print("  [FAIL] No photo ID available")
                print(f"  Error: {msg}")
                return None
    
    video_id = None
    if result.get("data"):
        video_id = result["data"].get("video_id")
    
    if not video_id:
        print(f"  [FAIL] {json.dumps(result, indent=2)[:300]}")
        return None
    
    print(f"  [OK] Rendering... (video_id: {video_id})")
    
    # Wait for render
    for i in range(60):
        time.sleep(5)
        print(".", end="", flush=True)
        sr = requests.get(
            "https://api.heygen.com/v1/video_status.get",
            headers={"X-Api-Key": key},
            params={"video_id": video_id}
        ).json()
        status = sr.get("data", {}).get("status")
        if status == "completed":
            video_url = sr["data"]["video_url"]
            out_path = OUT / "videos" / f"video_{seed}_{int(time.time())}.mp4"
            vr = requests.get(video_url)
            if vr.status_code == 200:
                out_path.write_bytes(vr.content)
                print(f"\n  [OK] Video saved: {out_path}")
                return str(out_path)
        elif status == "failed":
            error = sr.get("data", {}).get("error", "unknown")
            print(f"\n  [FAIL] {error}")
            return None
    
    print("\n  [FAIL] Timeout")
    return None


def main():
    print("=" * 50)
    print("  AI Avatar Generator")
    print("  Fully automatic: photo -> voice -> video")
    print("=" * 50)
    
    # Check keys
    required = ["REPLICATE_API_TOKEN", "ELEVENLABS_API_KEY", "HEYGEN_API_KEY"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        print(f"\n[ERROR] Missing keys: {', '.join(missing)}")
        print("Add them to config/api_keys.env")
        sys.exit(1)
    
    # Get user input or use defaults
    print("\n--- Settings ---")
    description = input("Describe avatar (or Enter for default):\n> ").strip()
    if not description:
        description = ("Professional portrait photo of a beautiful young woman, "
            "25 years old, light brown wavy hair, warm green eyes, "
            "soft smile, gentle expression, wearing a cozy cream sweater, "
            "natural soft lighting, shallow depth of field, "
            "clean minimal background, photorealistic, 8k")
    
    text = input("\nWhat should avatar say? (or Enter for default):\n> ").strip()
    if not text:
        text = "Hello! I am your new AI avatar. Nice to meet you!"
    
    seed_input = input("\nSeed number (or Enter for 777): ").strip()
    seed = int(seed_input) if seed_input else 777
    
    # Run pipeline
    print("\n" + "=" * 50)
    print("  Starting pipeline...")
    print("=" * 50)
    
    # Step 1: Photo
    image_url = generate_photo(description, seed)
    
    # Step 2: Voice (ElevenLabs - for local use)
    audio_path = generate_voice(text)
    
    # Step 3: Video (uses HeyGen's own voice + our photo)
    video_path = generate_video(image_url, text, seed)
    
    # Done
    print("\n" + "=" * 50)
    print("  DONE!")
    print("=" * 50)
    if video_path:
        print(f"  Video: {video_path}")
        print(f"\n  Open it: start {video_path}")
    else:
        print("  Video generation failed.")
        print(f"  But you have: photo + audio")
    print("=" * 50)


if __name__ == "__main__":
    main()
