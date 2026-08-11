from pathlib import Path
import re

p = Path('android/app/src/main/java/com/r786p/annotateagent/live/LiveScreenService.kt')
s = p.read_text()

# Imports for HTTP fallback speech.
if 'import android.speech.tts.TextToSpeech' not in s:
    s = s.replace('import android.speech.RecognizerIntent\n', 'import android.speech.RecognizerIntent\nimport android.speech.tts.TextToSpeech\nimport java.util.Locale\n')

# Keep the most recent JPEG frame for the HTTP chat fallback.
if 'private var latestFrameBase64' not in s:
    s = s.replace('private var lastFrameAt = 0L\n', 'private var lastFrameAt = 0L\n    private var latestFrameBase64 = ""\n    private var tts: TextToSpeech? = null\n')

# Initialize Hindi TTS.
if 'tts = TextToSpeech(this' not in s:
    s = s.replace('createNotificationChannel()\n        createAudioTrack()', 'createNotificationChannel()\n        createAudioTrack()\n        tts = TextToSpeech(this) { status ->\n            if (status == TextToSpeech.SUCCESS) tts?.language = Locale("hi", "IN")\n        }')

# Save the current frame even when the Live socket is unavailable.
s = s.replace('if (now - lastFrameAt < FRAME_INTERVAL_MS || webSocket == null) return', 'if (now - lastFrameAt < FRAME_INTERVAL_MS) return')
s = s.replace('val encoded = Base64.encodeToString(output.toByteArray(), Base64.NO_WRAP)\n            webSocket?.send', 'val encoded = Base64.encodeToString(output.toByteArray(), Base64.NO_WRAP)\n            latestFrameBase64 = encoded\n            webSocket?.send')

# Replace socket-dependent sendText with the reliable Render HTTP endpoint.
pattern = re.compile(r'    private fun sendText\(question: String\) \{.*?\n    \}\n\n    private fun showAnswer', re.S)
replacement = r'''    private fun sendText(question: String) {
        if (backendUrl.isBlank()) {
            showAnswer("🔴 Backend URL available nahi hai.")
            return
        }
        showAnswer("You: $question\n\n⏳ Jawab aa raha hai...")
        val payload = JSONObject()
            .put("question", question)
            .put("image", latestFrameBase64)
            .put("mime_type", "image/jpeg")
        val request = Request.Builder()
            .url("$backendUrl/live-chat")
            .post(payload.toString().toRequestBody("application/json".toMediaType()))
            .build()
        httpClient.newCall(request).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                showAnswer("🔴 Reply nahi aa paya: ${e.message ?: "network error"}")
            }
            override fun onResponse(call: Call, response: Response) {
                response.use {
                    val body = it.body?.string().orEmpty()
                    if (!it.isSuccessful) {
                        showAnswer("🔴 Server error: HTTP ${it.code}\n$body")
                        return
                    }
                    try {
                        val reply = JSONObject(body).optString("reply", "").trim()
                        if (reply.isBlank()) {
                            showAnswer("🔴 Gemini ne empty reply diya.")
                            return
                        }
                        showAnswer(reply)
                        speakHindi(reply)
                    } catch (_: Exception) {
                        showAnswer("🔴 Reply parse nahi hua.")
                    }
                }
            }
        })
    }

    private fun speakHindi(text: String) {
        Handler(mainLooper).post {
            try {
                tts?.language = Locale("hi", "IN")
                tts?.speak(text, TextToSpeech.QUEUE_FLUSH, null, "panda-reply")
            } catch (_: Exception) { }
        }
    }

    private fun showAnswer'''
s2, n = pattern.subn(replacement, s, count=1)
if n != 1:
    raise SystemExit('sendText block not found')
s = s2

if 'tts?.shutdown()' not in s:
    s = s.replace('audioTrack?.release(); audioTrack = null', 'audioTrack?.release(); audioTrack = null\n        tts?.stop(); tts?.shutdown(); tts = null')

p.write_text(s)
print('HTTP Panda chat + Hindi TTS patch applied')
