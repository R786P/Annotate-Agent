from pathlib import Path
import re

p = Path("android/app/src/main/java/com/r786p/annotateagent/live/LiveScreenService.kt")
s = p.read_text()

s = s.replace("import android.view.WindowManager\n", "import android.view.WindowManager\nimport android.widget.FrameLayout\n", 1)
s = s.replace("private var overlayView: LinearLayout? = null", "private var overlayView: View? = null", 1)
if "private var panelParams: WindowManager.LayoutParams?" not in s:
    s = s.replace("private var questionInput: EditText? = null\n", "private var questionInput: EditText? = null\n    private var panelParams: WindowManager.LayoutParams? = null\n    private var panelRoot: FrameLayout? = null\n", 1)

# Make the panel window itself movable, resizable, and easy to dismiss/minimize.
toggle_re = re.compile(r"    private fun togglePanel\(\) \{.*?\n    \}\n\n    private fun buildPanel", re.S)
toggle_new = '''    private fun togglePanel() {
        val current = overlayView
        if (current?.parent != null) {
            windowManager?.removeView(current)
            return
        }
        if (current == null) buildPanel()
        val panel = overlayView ?: return
        val dm = resources.displayMetrics
        val params = WindowManager.LayoutParams(
            (dm.widthPixels * 0.88f).toInt(),
            (dm.heightPixels * 0.70f).toInt(),
            if (Build.VERSION.SDK_INT >= 26) WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY else WindowManager.LayoutParams.TYPE_PHONE,
            WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL or WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
            PixelFormat.TRANSLUCENT
        ).apply {
            gravity = Gravity.TOP or Gravity.START
            x = (dm.widthPixels * 0.06f).toInt()
            y = (dm.heightPixels * 0.14f).toInt()
            softInputMode = WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE
        }
        panelParams = params
        try { windowManager?.addView(panel, params) } catch (_: Exception) { }
    }

    private fun movePanel(dx: Float, dy: Float) {
        val p = panelParams ?: return
        val dm = resources.displayMetrics
        p.x = (p.x + dx.toInt()).coerceIn(0, (dm.widthPixels - p.width).coerceAtLeast(0))
        p.y = (p.y + dy.toInt()).coerceIn(0, (dm.heightPixels - p.height).coerceAtLeast(0))
        try { windowManager?.updateViewLayout(panelRoot, p) } catch (_: Exception) { }
    }

    private fun resizePanel(dx: Float, dy: Float) {
        val p = panelParams ?: return
        val dm = resources.displayMetrics
        val minW = (dm.widthPixels * 0.55f).toInt()
        val minH = (dm.heightPixels * 0.40f).toInt()
        val maxW = (dm.widthPixels * 0.96f).toInt()
        val maxH = (dm.heightPixels * 0.88f).toInt()
        p.width = (p.width + dx.toInt()).coerceIn(minW, maxW)
        p.height = (p.height + dy.toInt()).coerceIn(minH, maxH)
        p.x = p.x.coerceIn(0, (dm.widthPixels - p.width).coerceAtLeast(0))
        p.y = p.y.coerceIn(0, (dm.heightPixels - p.height).coerceAtLeast(0))
        try { windowManager?.updateViewLayout(panelRoot, p) } catch (_: Exception) { }
    }

    private fun closePanel() {
        overlayView?.let { if (it.parent != null) windowManager?.removeView(it) }
    }

    private fun minimizePanel() {
        closePanel()
    }

    private fun buildPanel'''
s, n = toggle_re.subn(toggle_new, s, count=1)
if n != 1:
    raise SystemExit("togglePanel block not found")

# patch_chat_panel creates overlayView = container. Wrap it in a native frame with a drag bar,
# minimize/close controls and a bottom-right resize handle.
old = "        overlayView = container\n"
new = '''        val density = resources.displayMetrics.density
        val root = FrameLayout(this).apply {
            setBackgroundColor(Color.rgb(25, 25, 28))
            setPadding(0, 0, 0, 0)
        }
        val contentLp = FrameLayout.LayoutParams(-1, -1).apply {
            topMargin = (46 * density).toInt()
            bottomMargin = (22 * density).toInt()
        }
        root.addView(container, contentLp)

        val dragBar = TextView(this).apply {
            text = "🐼  Panda Assistant     ↕  Drag"
            textSize = 14f
            setTextColor(Color.WHITE)
            setBackgroundColor(Color.rgb(34, 36, 45))
            gravity = Gravity.CENTER_VERTICAL
            setPadding((14 * density).toInt(), 0, (14 * density).toInt(), 0)
            var lastX = 0f
            var lastY = 0f
            setOnTouchListener { _, event ->
                when (event.actionMasked) {
                    MotionEvent.ACTION_DOWN -> { lastX = event.rawX; lastY = event.rawY; true }
                    MotionEvent.ACTION_MOVE -> {
                        val dx = event.rawX - lastX
                        val dy = event.rawY - lastY
                        movePanel(dx, dy)
                        lastX = event.rawX; lastY = event.rawY
                        true
                    }
                    else -> true
                }
            }
        }
        root.addView(dragBar, FrameLayout.LayoutParams(-1, (46 * density).toInt()).apply { gravity = Gravity.TOP })

        val minimize = Button(this).apply {
            text = "−"
            textSize = 18f
            setPadding(0, 0, 0, 0)
            setOnClickListener { minimizePanel() }
        }
        root.addView(minimize, FrameLayout.LayoutParams((48 * density).toInt(), (46 * density).toInt()).apply {
            gravity = Gravity.TOP or Gravity.END
            rightMargin = (48 * density).toInt()
        })

        val closeNative = Button(this).apply {
            text = "✕"
            textSize = 16f
            setPadding(0, 0, 0, 0)
            setOnClickListener { closePanel() }
        }
        root.addView(closeNative, FrameLayout.LayoutParams((48 * density).toInt(), (46 * density).toInt()).apply {
            gravity = Gravity.TOP or Gravity.END
        })

        val resize = TextView(this).apply {
            text = "↘"
            textSize = 20f
            setTextColor(Color.LTGRAY)
            gravity = Gravity.CENTER
            setBackgroundColor(Color.rgb(48, 50, 60))
            var lastX = 0f
            var lastY = 0f
            setOnTouchListener { _, event ->
                when (event.actionMasked) {
                    MotionEvent.ACTION_DOWN -> { lastX = event.rawX; lastY = event.rawY; true }
                    MotionEvent.ACTION_MOVE -> {
                        val dx = event.rawX - lastX
                        val dy = event.rawY - lastY
                        resizePanel(dx, dy)
                        lastX = event.rawX; lastY = event.rawY
                        true
                    }
                    else -> true
                }
            }
        }
        root.addView(resize, FrameLayout.LayoutParams((42 * density).toInt(), (22 * density).toInt()).apply {
            gravity = Gravity.BOTTOM or Gravity.END
        })

        panelRoot = root
        overlayView = root
'''
if old not in s:
    raise SystemExit("buildPanel assignment not found")
s = s.replace(old, new, 1)

s = s.replace("overlayView = null; bubble = null", "overlayView = null; panelRoot = null; panelParams = null; bubble = null", 1)
p.write_text(s)
print("Native Panda chat window: drag bar + minimize + close + resize handle")
