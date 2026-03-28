#!/usr/bin/env python3
"""List your uploaded talking photos on HeyGen (filters out presets)."""

import os
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / "config" / "api_keys.env")

key = os.getenv("HEYGEN_API_KEY")
if not key:
    print("[ERROR] HEYGEN_API_KEY not set")
    exit(1)

resp = requests.get(
    "https://api.heygen.com/v2/talking_photo.list",
    headers={"X-Api-Key": key},
)
data = resp.json()

photos = data.get("data", {}).get("talking_photos", [])
user_photos = [p for p in photos if not p.get("is_preset", True)]

print(f"Total photos: {len(photos)}")
print(f"Your uploads: {len(user_photos)}")
print()

if user_photos:
    for p in user_photos:
        print(f"  ID: {p.get('talking_photo_id')}")
        print(f"  Name: {p.get('talking_photo_name', 'unnamed')}")
        print(f"  URL: {p.get('talking_photo_url', 'N/A')[:80]}")
        print()
else:
    print("No user-uploaded photos found.")
    print("Showing first 5 presets:")
    for p in photos[:5]:
        print(f"  ID: {p.get('talking_photo_id')}")
        print(f"  Name: {p.get('talking_photo_name', 'unnamed')}")
        print()
