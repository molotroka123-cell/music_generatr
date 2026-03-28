# AI Avatar Production Pipeline

Full-stack AI avatar system: generate photorealistic avatars, voice them, animate into videos, and stream live.

## Stack

| Component | Service | Purpose |
|-----------|---------|--------|
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

### 3. Run Full Pipeline
```bash
python scripts/run_pipeline.py
```

### 4. Live Avatar Mode
```bash
python scripts/realtime_avatar.py
```

## Agents

| Agent | Role |
|-------|------|
| @avatar-designer | FLUX.1 image generation, character consistency |
| @voice-producer | ElevenLabs voice selection and audio generation |
| @video-generator | HeyGen + Kling video production |
| @realtime-streamer | Live pipeline, OBS, monitoring |
| @qa-publisher | Quality gates, compression, publishing |

## Pipeline Order
```
@avatar-designer -> @voice-producer -> @video-generator -> @qa-publisher
```

@realtime-streamer runs independently for live video calls.
