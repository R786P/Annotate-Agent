from pathlib import Path
import re

path = Path("android/app/src/main/java/com/r786p/annotateagent/live/LiveScreenService.kt")
s = path.read_text()

if "bubbleParams: WindowManager.LayoutParams" not in s:
    s = s.replace(
        "private var bubble: PandaBubbleView? = null",
        "private var bubble: PandaBubbleView? = null\n    private var bubbleParams: WindowManager.LayoutParams? = null",
        1,
    )

if "setOnDragListener" not in s:
    old_show = '''    private fun showOverlay() {
        if (bubble != null) return
        windowManager = getSystemService(WINDOW_SERVICE) as WindowManager
        bubble = PandaBubbleView(this).apply {
            setOnBubbleClickListener { togglePanel() }
            setOnMicClickListener { startVoiceInput() }
        }
        val params = WindowManager.LayoutParams(
            88, 88,
            if (Build.VERSION.SDK_INT >= 26) WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY else WindowManager.LayoutParams.TYPE_PHONE,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
            PixelFormat.TRANSLUCENT
        ).apply { gravity = Gravity.CENTER_VERTICAL or Gravity.END; x = 12; y = 0 }
        try { windowManager?.addView(bubble, params) } catch (_: Exception) { stopSelf() }
    }
'''
    new_show = '''    private fun showOverlay() {
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
        val initialX = (dm.widthPixels - 100).coerceAtLeast(0)
        val initialY = ((dm.heightPixels - 88) / 2).coerceAtLeast(0)
        val params = WindowManager.LayoutParams(
            88, 88,
            if (Build.VERSION.SDK_INT >= 26) WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY else WindowManager.LayoutParams.TYPE_PHONE,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
            PixelFormat.TRANSLUCENT
        ).apply { gravity = Gravity.TOP or Gravity.START; x = initialX; y = initialY }
        bubbleParams = params
        try { windowManager?.addView(bubble, params) } catch (_: Exception) { stopSelf() }
    }

    private fun moveBubble(dx: Float, dy: Float) {
        val params = bubbleParams ?: return
        val dm = resources.displayMetrics
        val maxX = (dm.widthPixels - 88).coerceAtLeast(0)
        val maxY = (dm.heightPixels - 88).coerceAtLeast(0)
        params.x = (params.x + dx.toInt()).coerceIn(0, maxX)
        params.y = (params.y + dy.toInt()).coerceIn(0, maxY)
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
'''
    if old_show not in s:
        raise SystemExit("showOverlay block not found")
    s = s.replace(old_show, new_show, 1)

    fields = '''        private var onMicClick: (() -> Unit)? = null
        private var downX = 0f
        private var downY = 0f'''
    fields_new = '''        private var onMicClick: (() -> Unit)? = null
        private var onDrag: ((Float, Float) -> Unit)? = null
        private var onEdgeHide: ((Boolean) -> Unit)? = null
        private var onRestore: (() -> Unit)? = null
        private var downX = 0f
        private var downY = 0f
        private var lastX = 0f
        private var lastY = 0f
        private var dragging = false
        private var edgeHidden = false'''
    if fields not in s:
        raise SystemExit("bubble fields not found")
    s = s.replace(fields, fields_new, 1)

    listeners = '''        fun setOnBubbleClickListener(listener: () -> Unit) { onBubbleClick = listener }
        fun setOnMicClickListener(listener: () -> Unit) { onMicClick = listener }
        fun setListening(value: Boolean) { listening = value; invalidate() }'''
    listeners_new = '''        fun setOnBubbleClickListener(listener: () -> Unit) { onBubbleClick = listener }
        fun setOnMicClickListener(listener: () -> Unit) { onMicClick = listener }
        fun setOnDragListener(listener: (Float, Float) -> Unit) { onDrag = listener }
        fun setOnEdgeHideListener(listener: (Boolean) -> Unit) { onEdgeHide = listener }
        fun setOnRestoreListener(listener: () -> Unit) { onRestore = listener }
        fun setListening(value: Boolean) { listening = value; invalidate() }'''
    if listeners not in s:
        raise SystemExit("bubble listeners not found")
    s = s.replace(listeners, listeners_new, 1)

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
    path.write_text(s)

print("Panda overlay patch applied")
