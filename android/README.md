# Annotate Agent Live — Android companion

This companion app adds Android-only capabilities that a normal mobile browser cannot reliably provide:

- Android MediaProjection screen capture
- Foreground mediaProjection service
- Floating 🤖 bubble above other apps
- Live JPEG screen frames to Gemini Live
- Text questions from the bubble

## Setup

1. Open the `android/` folder in Android Studio.
2. Build/install the app on the Android phone.
3. On first launch, enter the public HTTPS Render URL for the existing Annotate Agent, for example `https://your-app.onrender.com`.
4. Tap **Start Live Screen**.
5. Grant overlay permission and Android's screen-capture permission.
6. Once started, leave the app and open Instagram, Chrome, YouTube, Settings, etc. The floating bubble stays visible.
7. Tap the bubble, type a question, and press **Ask**.

The existing web app and `/analyze` video workflow are not changed by this Android module.

## Gemini Live wire protocol

The service uses the Live API WebSocket constrained endpoint with the ephemeral token returned by `/live-token`. Screen frames are sent as realtime video input using `image/jpeg`. Google documents the Live WebSocket endpoint and realtime video input in the Live API reference.

## Important

The Render URL must be HTTPS and must already expose the `/live-token` endpoint from the main web app. Do not put `GEMINI_API_KEY` in the Android app.
