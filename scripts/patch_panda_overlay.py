from pathlib import Path
import re

path = Path("android/app/src/main/java/com/r786p/annotateagent/live/LiveScreenService.kt")
s = path.read_text()

# Panda overlay: draggable + edge hide/restore.
if "bubbleParams: WindowManager.LayoutParams" not in s:
    s = s.replace(
        "private var bubble: PandaBubbleView? = null",
        "private var bubble: PandaBubbleView? = null\n    private var bubbleParams: WindowManager.LayoutParams? = null",
        1,
    )

show_re = re.compile(r"    private fun showOverlay\(\) \{.*?\n    \}\n\n    private fun togglePanel", re.S)
show_new = '''    private fun showOverlay() {
        if (bubble != null) return
        windowManager = getSystemService(WINDOW_SERVICE) as WindowManager
        bubble = PandaBubbleView(this).apply {
            setOnBubbleClickListener { togglePanel() }
            setOnMicClickListener { startVoiceInput() }
            setOnDragListener { dx, dy -> moveBubble(dx, dy) }
            setOnEdgeHideListener { toLeft -> hideBubbleToEdge(toLeft) }
            setOnRestoreListener { restoreBubbleFromEdge() }
        }
        val dm = resources.displayMetrics
        val params = WindowManager.LayoutParams(
            88, 88,
            if (Build.VERSION.SDK_INT >= 26) WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY else WindowManager.LayoutParams.TYPE_PHONE,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
            PixelFormat.TRANSLUCENT
        ).apply {
            gravity = Gravity.TOP or Gravity.START
            x = (dm.widthPixels - 100).coerceAtLeast(0)
            y = ((dm.heightPixels - 88) / 2).coerceAtLeast(0)
        }
        bubbleParams = params
        try { windowManager?.addView(bubble, params) } catch (_: Exception) { stopSelf() }
    }

    private fun moveBubble(dx: Float, dy: Float) {
        val params = bubbleParams ?: return
        val dm = resources.displayMetrics
        params.x = (params.x + dx.toInt()).coerceIn(0, (dm.widthPixels - 88).coerceAtLeast(0))
        params.y = (params.y + dy.toInt()).coerceIn(0, (dm.heightPixels - 88).coerceAtLeast(0))
        try { windowManager?.updateViewLayout(bubble, params) } catch (_: Exception) { }
    }

    private fun hideBubbleToEdge(toLeft: Boolean) {
        val params = bubbleParams ?: return
        val dm = resources.displayMetrics
        params.x = if (toLeft) -72 else dm.widthPixels - 16
        try { windowManager?.updateViewLayout(bubble, params) } catch (_: Exception) { }
    }

    private fun restoreBubbleFromEdge() {
        val params = bubbleParams ?: return
        val dm = resources.displayMetrics
        params.x = if (params.x < 0) 12 else (dm.widthPixels - 100).coerceAtLeast(0)
        try { windowManager?.updateViewLayout(bubble, params) } catch (_: Exception) { }
    }

    private fun togglePanel'''
s, count = show_re.subn(show_new, s, count=1)
if count != 1:
    raise SystemExit("showOverlay block not found")

# Gemini Live readiness state.
if "private var liveReady = false" not in s:
    s = s.replace(
        "private var listening = false",
        "private var listening = false\n    private var liveReady = false",
        1,
    )

s = s.replace(
    "override fun onOpen(webSocket: WebSocket, response: Response) {",
    "override fun onOpen(webSocket: WebSocket, response: Response) {\n                liveReady = false",
    1,
)

old_callbacks = '''            override fun onMessage(webSocket: WebSocket, text: String) { parseGeminiMessage(text) }
            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) { showAnswer("Gemini Live connection error: ${t.message ?: "unknown error"}") }
            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) { showAnswer("Live connection closed.") }'''
new_callbacks = '''            override fun onMessage(webSocket: WebSocket, text: String) {
                try {
                    val root = JSONObject(text)
                    if (root.has("setupComplete")) {
                        liveReady = true
                        showAnswer("🟢 Live connected. Screen dekh raha hoon. Panda bubble par 🎙️ dabakar bolo ya bubble tap karke chat kholo.")
                        return
                    }
                } catch (_: Exception) { }
                parseGeminiMessage(text)
            }
            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                liveReady = false
                showAnswer("Gemini Live connection error: ${t.message ?: "unknown error"}")
            }
            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                liveReady = false
                showAnswer("Live connection closed.")
            }'''
if old_callbacks not in s:
    raise SystemExit("websocket callbacks block not found")
s = s.replace(old_callbacks, new_callbacks, 1)

s = s.replace(
    "if (now - lastFrameAt < FRAME_INTERVAL_MS || webSocket == null) return",
    "if (now - lastFrameAt < FRAME_INTERVAL_MS || webSocket == null || !liveReady) return",
    1,
)

send_re = re.compile(r"    private fun sendText\(question: String\) \{.*?\n    \}\n\n    private fun showAnswer", re.S)
send_new = '''    private fun sendText(question: String) {
        val socket = webSocket
        if (socket == null || !liveReady) {
            showAnswer("🔴 Live connection abhi ready nahi hai. 1–2 second rukkar dobara Send karo.")
            return
        }
        val message = JSONObject().put("realtimeInput", JSONObject().put("text", question))
        if (socket.send(message.toString())) {
            showAnswer("You: $question")
        } else {
            showAnswer("🔴 Message send nahi hua. Live connection dobara start karo.")
        }
    }

    private fun showAnswer'''
s, count = send_re.subn(send_new, s, count=1)
if count != 1:
    raise SystemExit("sendText function not found")

s = s.replace(
    "private var onMicClick: (() -> Unit)? = null\n        private var downX = 0f",
    "private var onMicClick: (() -> Unit)? = null\n        private var onDrag: ((Float, Float) -> Unit)? = null\n        private var onEdgeHide: ((Boolean) -> Unit)? = null\n        private var onRestore: (() -> Unit)? = null\n        private var downX = 0f",
    1,
)
s = s.replace(
    "private var downY = 0f",
    "private var downY = 0f\n        private var lastX = 0f\n        private var lastY = 0f\n        private var dragging = false\n        private var edgeHidden = false",
    1,
)
s = s.replace(
    "fun setOnMicClickListener(listener: () -> Unit) { onMicClick = listener }\n        fun setListening(value: Boolean)",
    "fun setOnMicClickListener(listener: () -> Unit) { onMicClick = listener }\n        fun setOnDragListener(listener: (Float, Float) -> Unit) { onDrag = listener }\n        fun setOnEdgeHideListener(listener: (Boolean) -> Unit) { onEdgeHide = listener }\n        fun setOnRestoreListener(listener: () -> Unit) { onRestore = listener }\n        fun setListening(value: Boolean)",
    1,
)

touch_re = re.compile(r"        override fun onTouchEvent\(event: MotionEvent\): Boolean \{.*?        \}\n\n        override fun onDraw", re.S)
touch_new = '''        override fun onTouchEvent(event: MotionEvent): Boolean {
            when (event.actionMasked) {
                MotionEvent.ACTION_DOWN -> {
                    downX = event.rawX; downY = event.rawY
                    lastX = event.rawX; lastY = event.rawY
                    dragging = false
                    return true
                }
                MotionEvent.ACTION_MOVE -> {
                    if (edgeHidden) return true
                    val dx = event.rawX - lastX
                    val dy = event.rawY - lastY
                    if (dx * dx + dy * dy > 9f) dragging = true
                    if (dragging) onDrag?.invoke(dx, dy)
                    lastX = event.rawX; lastY = event.rawY
                    return true
                }
                MotionEvent.ACTION_UP -> {
                    if (edgeHidden) {
                        edgeHidden = false
                        onRestore?.invoke()
                        return true
                    }
                    val totalX = event.rawX - downX
                    val totalY = event.rawY - downY
                    if (dragging) {
                        if (kotlin.math.abs(totalX) > 150f && kotlin.math.abs(totalX) > kotlin.math.abs(totalY) * 1.3f) {
                            edgeHidden = true
                            onEdgeHide?.invoke(totalX < 0f)
                        }
                        return true
                    }
                    val cx = width * 0.72f; val cy = height * 0.78f
                    val r = width * 0.20f
                    if ((event.x - cx) * (event.x - cx) + (event.y - cy) * (event.y - cy) <= r * r) onMicClick?.invoke()
                    else onBubbleClick?.invoke()
                    return true
                }
                MotionEvent.ACTION_CANCEL -> { dragging = false; return true }
            }
            return true
        }

        override fun onDraw'''
s, count = touch_re.subn(touch_new, s, count=1)
if count != 1:
    raise SystemExit("touch handler not found")

s = s.replace("overlayView = null; bubble = null", "overlayView = null; bubble = null; bubbleParams = null", 1)
s = s.replace("webSocket?.close(1000, \"User stopped Live Screen\"); webSocket = null", "webSocket?.close(1000, \"User stopped Live Screen\"); webSocket = null; liveReady = false", 1)

path.write_text(s)
print("Panda overlay + Gemini Live patch applied")