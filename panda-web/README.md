# 🐼 Panda Assistant Web

Standalone Render-ready Panda chat panel. It is intentionally isolated from the Android APK UI so chat-panel changes can be deployed without rebuilding the APK.

## Features
- Beautiful floating chat panel
- Drag from the Panda header to move the panel
- Resizable corner
- Hindi text chat
- Copy / Paste / Upload / Voice controls
- Proxies chat requests to the existing Annotate Agent `/live-chat` endpoint
- Keeps the Gemini/API key on the backend instead of the browser

## Render
Create a Render Web Service from this repository and set:

`ANNOTATE_BACKEND_URL=https://YOUR-ANNOTATE-AGENT.onrender.com`

The service runs `gunicorn app:app` from `panda-web/`.

The Android app can later load this standalone URL for the Panda panel. This means panel UI changes do not require a new APK.
