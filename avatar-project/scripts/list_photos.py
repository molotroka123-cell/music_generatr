#!/usr/bin/env python3
"""List all talking photos and find user uploads."""
import requests, json, os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent / "config" / "api_keys.env")
key = os.getenv("HEYGEN_API_KEY")

r = requests.get("https://api.heygen.com/v1/talking_photo.list",
    headers={"X-Api-Key": key})
data = r.json()

# Handle different response formats
if isinstance(data.get("data"), list):
    photos = data["data"]
elif isinstance(data.get("data"), dict):
    photos = data["data"].get("talking_photos", [])
else:
    print(f"Unexpected response: {json.dumps(data, indent=2)[:500]}")
    photos = []

print(f"Total talking photos: {len(photos)}")
print()

for i, p in enumerate(photos):
    preset = p.get("is_preset", False)
    tag = "PRESET" if preset else ">>> YOUR UPLOAD <<<"
    print(f"[{i}] {tag}")
    print(f"    id: {p.get('id', p.get('talking_photo_id', 'unknown'))}")
    if not preset:
        print(f"    image: {p.get('image_url','')[:100]}")
    print()
