# AI Avatar Pipeline — Project Rules

## Stack
- Image: FLUX.1 via Replicate API
- Voice: ElevenLabs API
- Video: HeyGen API + Kling AI API
- Live: LivePortrait + OBS Virtual Camera
- Local GPU: RTX 4060, Windows

## Agent Routing Rules

Sequential (always in this order):
  @avatar-designer -> generate base images first
  @voice-producer  -> generate audio from script
  @video-generator -> combine into final video
  @qa-publisher    -> quality check and publish

Parallel (run simultaneously):
  @avatar-designer can generate all 5 image sets in parallel
  @voice-producer prepares voice while images are generating

Independent (runs separately):
  @realtime-streamer -> only for live video calls

## Quality Gates
- No video goes to output without @qa-publisher approval
- No live stream starts without @realtime-streamer health check
- All API errors must be logged to content_log.json

## File Naming Convention
avatars/    -> avatar_{character}_{angle}_{seed}.jpg
audio/      -> audio_{script_id}_{voice}_{lang}.mp3
videos/     -> video_{avatar_id}_{date}_{platform}.mp4
