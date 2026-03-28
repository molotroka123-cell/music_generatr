---
name: heygen-api
description: >
  HeyGen API for creating talking avatar videos. Use when
  creating Photo Avatars, generating videos with lip sync,
  translating videos to other languages, or setting up
  streaming avatars for live video calls.
---
# HeyGen API
Base URL: https://api.heygen.com
Auth: X-Api-Key header
Key endpoints:
  POST /v2/video/generate — create talking video
  POST /v2/photo_avatar/photo/generate — create avatar
  GET  /v1/video_status.get — check render status
  POST /v1/video_translate/translate — translate video
