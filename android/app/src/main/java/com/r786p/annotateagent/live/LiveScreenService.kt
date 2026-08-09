package com.r786p.annotateagent.live

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.content.pm.ServiceInfo
import android.graphics.Bitmap
import android.graphics.Color
import android.graphics.PixelFormat
import android.hardware.display.DisplayManager
import android.hardware.display.VirtualDisplay
import android.media.Image
import android.media.ImageReader
import android.media.projection.MediaProjection
import android.media.projection.MediaProjectionManager
import android.os.Build
import android.os.Handler
import android.os.HandlerThread
import android.os.IBinder
import android.provider.Settings
import android.util.Base64
import android.view.Gravity
import android.view.WindowManager
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import okhttp3.Call
import okhttp3.Callback
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.io.IOException
import java.util.concurrent.TimeUnit

class LiveScreenService : Service() {
    companion object {
        const val EXTRA_RESULT_CODE = "result_code"
        const val EXTRA_RESULT_DATA = "result_data"
        const val EXTRA_BACKEND_URL = "backend_url"
        private const val CHANNEL_ID = "annotate_live_screen"
        private const val NOTIFICATION_ID = 7001
        private const val FRAME_INTERVAL_MS = 1200L
        private const val MAX_FRAME_WIDTH = 720
    }

    private val httpClient = OkHttpClient.Builder().connectTimeout(20, TimeUnit.SECONDS).readTimeout(30, TimeUnit.SECONDS).build()
    private var webSocket: WebSocket? = null
    private var mediaProjection: MediaProjection? = null
    private var virtualDisplay: VirtualDisplay? = null
    private var imageReader: ImageReader? = null
    private var captureThread: HandlerThread? = null
    private var captureHandler: Handler? = null
    private var windowManager: WindowManager? = null
    private var overlayView: LinearLayout? = null
    private var bubble: TextView? = null
    private var answerView: TextView? = null
    private var questionInput: EditText? = null
    private var backendUrl = ""
    private var lastFrameAt = 0L
    private var stopped = false

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (stopped) return START_NOT_STICKY
        val voiceQuestion = intent?.getStringExtra("voice_question")?.trim()
        if (!voiceQuestion.isNullOrBlank()) {
            sendText(voiceQuestion)
            return START_STICKY
        }
        val resultCode = intent?.getIntExtra(EXTRA_RESULT_CODE, 0) ?: 0
        val resultData = intent?.getParcelableExtra<Intent>(EXTRA_RESULT_DATA)
        backendUrl = intent?.getStringExtra(EXTRA_BACKEND_URL)?.trimEnd('/') ?: ""
        if (resultCode == 0 || resultData == null || backendUrl.isBlank()) {
            stopSelf()
            return START_NOT_STICKY
        }
        if (Build.VERSION.SDK_INT >= 29) {
            startForeground(NOTIFICATION_ID, buildNotification(), ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION)
        } else {
            startForeground(NOTIFICATION_ID, buildNotification())
        }
        if (!Settings.canDrawOverlays(this)) {
            stopSelf()
            return START_NOT_STICKY
        }
        startProjection(resultCode, resultData)
        fetchEphemeralTokenAndConnect()
        return START_STICKY
    }

    private fun startProjection(resultCode: Int, resultData: Intent) {
        val manager = getSystemService(MediaProjectionManager::class.java) ?: return
        mediaProjection = manager.getMediaProjection(resultCode, resultData)
        val metrics = resources.displayMetrics
        val width = metrics.widthPixels
        val height = metrics.heightPixels
        val density = metrics.densityDpi
        captureThread = HandlerThread("annotate-screen-capture").also { it.start() }
        captureHandler = Handler(captureThread!!.looper)
        imageReader = ImageReader.newInstance(width, height, PixelFormat.RGBA_8888, 2)
        imageReader?.setOnImageAvailableListener({ reader ->
            val image = try { reader.acquireLatestImage() } catch (_: Exception) { null }
            image?.let { handleImage(it) }
        }, captureHandler)
        virtualDisplay = mediaProjection?.createVirtualDisplay("AnnotateAgentLive", width, height, density,
            DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR, imageReader?.surface, null, captureHandler)
        mediaProjection?.registerCallback(object : MediaProjection.Callback() {
            override fun onStop() { stopSelf() }
        }, captureHandler)
        showOverlay()
    }

    private fun fetchEphemeralTokenAndConnect() {
        val request = Request.Builder().url("$backendUrl/live-token")
            .post(ByteArray(0).toRequestBody("application/json".toMediaType())).build()
        httpClient.newCall(request).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) { showAnswer("Live token error: ${e.message ?: "network error"}") }
            override fun onResponse(call: Call, response: Response) {
                response.use {
                    if (!it.isSuccessful) {
                        val detail = it.body?.string().orEmpty()
                        showAnswer("Live token error: HTTP ${it.code} ${detail.take(300)}")
                        return
                    }
                    try {
                        val json = JSONObject(it.body?.string().orEmpty())
                        connectGemini(json.getString("token"), json.optString("model", "gemini-3.1-flash-live-preview"))
                    } catch (_: Exception) { showAnswer("Live token response invalid hai.") }
                }
            }
        })
    }

    private fun connectGemini(token: String, model: String) {
        val wsUrl = "wss://generativelanguage.googleapis.com/ws/" +
            "google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContentConstrained" +
            "?access_token=$token"
        webSocket = httpClient.newWebSocket(Request.Builder().url(wsUrl).build(), object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                val setup = JSONObject().put("setup", JSONObject())
                setup.getJSONObject("setup").put("model", "models/$model")
                setup.getJSONObject("setup").put("generationConfig", JSONObject()
                    .put("responseModalities", org.json.JSONArray().put("TEXT"))
                    .put("temperature", 0.2))
                val instruction = JSONObject().put("parts", org.json.JSONArray().put(
                    JSONObject().put("text", "Tum Annotate Agent ho. User ke phone screen ke live frames ko dekho. User Hindi/Hinglish me sawaal kare to concise Hindi/Hinglish me jawab do. Visible buttons, errors, text aur UI ko explain karo. Passwords, OTPs, API keys aur private secrets ko repeat mat karo.")
                ))
                setup.getJSONObject("setup").put("systemInstruction", instruction)
                webSocket.send(setup.toString())
                showAnswer("🟢 Live connected. Ab bubble ya 🎤 se sawaal poochho.")
            }
            override fun onMessage(webSocket: WebSocket, text: String) { parseGeminiMessage(text) }
            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) { showAnswer("Gemini Live connection error: ${t.message ?: "unknown error"}") }
            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) { showAnswer("Live connection closed.") }
        })
    }

    private fun parseGeminiMessage(raw: String) {
        try {
            val root = JSONObject(raw)
            val serverContent = root.optJSONObject("serverContent") ?: return
            val modelTurn = serverContent.optJSONObject("modelTurn") ?: return
            val parts = modelTurn.optJSONArray("parts") ?: return
            val answer = StringBuilder()
            for (i in 0 until parts.length()) {
                val text = parts.optJSONObject(i)?.optString("text", "") ?: ""
                if (text.isNotBlank()) answer.append(text)
            }
            if (answer.isNotBlank()) showAnswer(answer.toString())
        } catch (_: Exception) { }
    }

    private fun handleImage(image: Image) {
        try {
            val now = System.currentTimeMillis()
            if (now - lastFrameAt < FRAME_INTERVAL_MS || webSocket == null) return
            lastFrameAt = now
            val plane = image.planes[0]
            val buffer = plane.buffer
            val pixelStride = plane.pixelStride
            val rowStride = plane.rowStride
            val rowPadding = rowStride - pixelStride * image.width
            val paddedWidth = image.width + rowPadding / pixelStride
            val bitmap = Bitmap.createBitmap(paddedWidth, image.height, Bitmap.Config.ARGB_8888)
            bitmap.copyPixelsFromBuffer(buffer)
            val cropped = if (paddedWidth != image.width) Bitmap.createBitmap(bitmap, 0, 0, image.width, image.height) else bitmap
            val scaled = if (cropped.width > MAX_FRAME_WIDTH) {
                Bitmap.createScaledBitmap(cropped, MAX_FRAME_WIDTH, cropped.height * MAX_FRAME_WIDTH / cropped.width, true)
            } else cropped
            val output = ByteArrayOutputStream()
            scaled.compress(Bitmap.CompressFormat.JPEG, 55, output)
            val encoded = Base64.encodeToString(output.toByteArray(), Base64.NO_WRAP)
            webSocket?.send(JSONObject().put("realtimeInput", JSONObject().put("video", JSONObject().put("mimeType", "image/jpeg").put("data", encoded))).toString())
            if (scaled !== cropped) scaled.recycle()
            if (cropped !== bitmap) cropped.recycle()
            bitmap.recycle()
        } catch (_: Exception) {
        } finally { image.close() }
    }

    private fun showOverlay() {
        if (overlayView != null) return
        windowManager = getSystemService(WINDOW_SERVICE) as WindowManager
        bubble = TextView(this).apply {
            text = "🤖"
            textSize = 22f
            gravity = Gravity.CENTER
            setTextColor(Color.WHITE)
            setBackgroundColor(Color.rgb(91, 91, 247))
            setPadding(14, 10, 14, 10)
            setOnClickListener { togglePanel() }
        }
        val container = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(12, 12, 12, 12)
            setBackgroundColor(Color.rgb(25, 25, 28))
        }
        answerView = TextView(this).apply { text = "Live screen active"; textSize = 14f; setTextColor(Color.WHITE); setPadding(10, 10, 10, 10) }
        container.addView(answerView, LinearLayout.LayoutParams(-1, 0, 1f))
        questionInput = EditText(this).apply { hint = "Kya poochna hai?"; setTextColor(Color.WHITE); setHintTextColor(Color.LTGRAY); setSingleLine(false) }
        container.addView(questionInput, LinearLayout.LayoutParams(-1, -2))
        val ask = Button(this).apply {
            text = "Ask"
            setOnClickListener { val q = questionInput?.text?.toString()?.trim().orEmpty(); if (q.isNotBlank()) { sendText(q); questionInput?.setText("") } }
        }
        container.addView(ask, LinearLayout.LayoutParams(-1, -2))
        val stop = Button(this).apply { text = "Stop Live"; setOnClickListener { stopSelf(); stopService(Intent(this@LiveScreenService, VoiceOverlayService::class.java)) } }
        container.addView(stop, LinearLayout.LayoutParams(-1, -2))
        overlayView = container
        val bubbleParams = WindowManager.LayoutParams(WindowManager.LayoutParams.WRAP_CONTENT, WindowManager.LayoutParams.WRAP_CONTENT,
            if (Build.VERSION.SDK_INT >= 26) WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY else WindowManager.LayoutParams.TYPE_PHONE,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS, PixelFormat.TRANSLUCENT).apply {
            gravity = Gravity.CENTER_VERTICAL or Gravity.END; x = 18; y = 0
        }
        windowManager?.addView(bubble, bubbleParams)
    }

    private fun togglePanel() {
        val current = overlayView ?: return
        if (current.parent != null) { windowManager?.removeView(current); return }
        val params = WindowManager.LayoutParams((resources.displayMetrics.widthPixels * 0.82).toInt(), WindowManager.LayoutParams.WRAP_CONTENT,
            if (Build.VERSION.SDK_INT >= 26) WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY else WindowManager.LayoutParams.TYPE_PHONE,
            WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS, PixelFormat.TRANSLUCENT).apply { gravity = Gravity.CENTER }
        windowManager?.addView(current, params)
    }

    private fun sendText(question: String) {
        webSocket?.send(JSONObject().put("realtimeInput", JSONObject().put("text", question)).toString())
        showAnswer("You: $question")
    }

    private fun showAnswer(text: String) { Handler(mainLooper).post { answerView?.text = text } }

    private fun buildNotification(): Notification = Notification.Builder(this, CHANNEL_ID)
        .setContentTitle("Annotate Agent Live").setContentText("Screen live analysis active")
        .setSmallIcon(android.R.drawable.ic_menu_view).setOngoing(true).build()

    private fun createNotificationChannel() {
        getSystemService(NotificationManager::class.java).createNotificationChannel(NotificationChannel(CHANNEL_ID, "Annotate Agent Live Screen", NotificationManager.IMPORTANCE_LOW))
    }

    override fun onDestroy() {
        stopped = true
        webSocket?.close(1000, "User stopped Live Screen")
        webSocket = null
        virtualDisplay?.release(); virtualDisplay = null
        imageReader?.close(); imageReader = null
        mediaProjection?.stop(); mediaProjection = null
        captureThread?.quitSafely(); captureThread = null; captureHandler = null
        try {
            overlayView?.let { if (it.parent != null) windowManager?.removeView(it) }
            bubble?.let { if (it.parent != null) windowManager?.removeView(it) }
        } catch (_: Exception) { }
        overlayView = null; bubble = null
        stopForeground(STOP_FOREGROUND_REMOVE)
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null
}
