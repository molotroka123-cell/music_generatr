# AI Avatar Production Pipeline

Full-stack AI avatar system: generate photorealistic avatars, voice them, animate into videos, and stream live.

## Stack

| Component | Service | Purpose |
|-----------|---------|---------|
| Image | FLUX.1 (Replicate) | Photorealistic avatar generation |
| Voice | ElevenLabs | Text-to-speech, voice cloning |
| Video | HeyGen | Talking head videos with lip sync |
| Motion | Kling AI | Body movement animation |
| Live | LivePortrait + OBS | Real-time avatar for video calls |
| GPU | RTX 4060 (local) | LivePortrait inference |

## Quick Start

### 1. Install Dependencies

```bash
python scripts/setup.py
```

### 2. Configure API Keys

```bash
cp config/api_keys.env.example config/api_keys.env
# Edit config/api_keys.env with your API keys
```

Get your keys:
- **Replicate**: [replicate.com/account/api-tokens](https://replicate.com/account/api-tokens)
- **ElevenLabs**: [elevenlabs.io/app/developers/api-keys](https://elevenlabs.io/app/developers/api-keys)
- **HeyGen**: app.heygen.com → Settings → API
- **Kling AI**: kling.ai → Developer → API Keys

### 3. Run Full Pipeline

```bash
python scripts/run_pipeline.py
```

This runs the complete sequence:
1. Generates avatar images (FLUX.1)
2. Creates voice audio (ElevenLabs)
3. Produces talking head video (HeyGen)
4. Runs QA checks (resolution, FPS, file size)

### 4. Live Avatar Mode

```bash
python scripts/realtime_avatar.py
```

Requirements for live mode:
- OBS Studio with Virtual Camera
- DroidCam (for phone as webcam) or built-in webcam
- LivePortrait installed locally

## Agents

| Agent | Role |
|-------|------|
| `@avatar-designer` | FLUX.1 image generation, character consistency |
| `@voice-producer` | ElevenLabs voice selection and audio generation |
| `@video-generator` | HeyGen + Kling video production |
| `@realtime-streamer` | Live pipeline, OBS, monitoring |
| `@qa-publisher` | Quality gates, compression, publishing |

## Pipeline Order

```
@avatar-designer → @voice-producer → @video-generator → @qa-publisher
```

`@realtime-streamer` runs independently for live video calls.

## Output Structure

```
output/
  avatars/   → avatar_{character}_{angle}_{seed}.jpg
  audio/     → audio_{script_id}_{voice}_{lang}.mp3
  videos/    → video_{avatar_id}_{date}_{platform}.mp4
  frames/    → motion frames for animation
```

## File Naming Convention

- Avatars: `avatar_{character}_{angle}_{seed}.jpg`
- Audio: `audio_{script_id}_{voice}_{lang}.mp3`
- Videos: `video_{avatar_id}_{date}_{platform}.mp4`
