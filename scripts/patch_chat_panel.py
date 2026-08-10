from pathlib import Path
import re

path = Path("android/app/src/main/java/com/r786p/annotateagent/live/LiveScreenService.kt")
s = path.read_text()

panel_re = re.compile(r"    private fun buildPanel\(\) \{.*?\n    \}\n\n    private fun startVoiceInput", re.S)
panel_new = '''    private fun buildPanel() {
        val dp = resources.displayMetrics.density
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding((20 * dp).toInt(), (18 * dp).toInt(), (20 * dp).toInt(), (14 * dp).toInt())
            setBackgroundColor(Color.rgb(18, 19, 24))
            elevation = 20f
        }

        val header = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        val title = TextView(this).apply {
            text = "🐼  Panda Assistant"
            textSize = 20f
            setTextColor(Color.WHITE)
            setTypeface(null, android.graphics.Typeface.BOLD)
        }
        val status = TextView(this).apply {
            text = "  •  Live Screen"
            textSize = 12f
            setTextColor(Color.rgb(145, 155, 180))
        }
        header.addView(title, LinearLayout.LayoutParams(0, -2, 1f))
        header.addView(status)
        root.addView(header)

        val divider = View(this).apply { setBackgroundColor(Color.rgb(55, 57, 68)) }
        root.addView(divider, LinearLayout.LayoutParams(-1, (1 * dp).toInt()).apply {
            topMargin = (12 * dp).toInt()
            bottomMargin = (8 * dp).toInt()
        })

        answerView = TextView(this).apply {
            text = "🟢 Live Screen active\\n\\nPanda ko bolo ya neeche message likho..."
            textSize = 15f
            setTextColor(Color.rgb(238, 240, 248))
            setPadding((14 * dp).toInt(), (14 * dp).toInt(), (14 * dp).toInt(), (14 * dp).toInt())
            setBackgroundColor(Color.rgb(29, 31, 39))
            setTextIsSelectable(true)
        }
        val answerScroll = android.widget.ScrollView(this)
        answerScroll.addView(answerView)
        root.addView(answerScroll, LinearLayout.LayoutParams(-1, 0, 1f).apply {
            bottomMargin = (10 * dp).toInt()
        })

        questionInput = EditText(this).apply {
            hint = "Message likho ya Paste karo..."
            textSize = 15f
            setTextColor(Color.WHITE)
            setHintTextColor(Color.rgb(145, 150, 165))
            setPadding((14 * dp).toInt(), (10 * dp).toInt(), (14 * dp).toInt(), (10 * dp).toInt())
            setSingleLine(false)
            setBackgroundColor(Color.rgb(35, 37, 47))
        }
        root.addView(questionInput, LinearLayout.LayoutParams(-1, (70 * dp).toInt()).apply {
            bottomMargin = (8 * dp).toInt()
        })

        val tools = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        fun tool(label: String, action: () -> Unit): Button = Button(this).apply {
            text = label
            textSize = 11f
            setOnClickListener { action() }
        }
        val copy = tool("📋 Copy") {
            val value = answerView?.text?.toString().orEmpty()
            val cm = getSystemService(CLIPBOARD_SERVICE) as android.content.ClipboardManager
            cm.setPrimaryClip(android.content.ClipData.newPlainText("Panda reply", value))
            showAnswer("✅ Reply copied")
        }
        val paste = tool("📥 Paste") {
            val cm = getSystemService(CLIPBOARD_SERVICE) as android.content.ClipboardManager
            val clip = cm.primaryClip
            val value = clip?.getItemAt(0)?.coerceToText(this)?.toString().orEmpty()
            if (value.isNotBlank()) questionInput?.append(value)
        }
        val upload = tool("📎 Upload") {
            try {
                val intent = Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
                    addCategory(Intent.CATEGORY_OPENABLE)
                    type = "*/*"
                    addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                }
                startActivity(intent)
            } catch (_: Exception) {
                showAnswer("📎 File picker open nahi hua.")
            }
        }
        val voice = tool("🎙️ Voice") { startVoiceInput() }
        tools.addView(copy, LinearLayout.LayoutParams(0, -2, 1f))
        tools.addView(paste, LinearLayout.LayoutParams(0, -2, 1f))
        tools.addView(upload, LinearLayout.LayoutParams(0, -2, 1f))
        tools.addView(voice, LinearLayout.LayoutParams(0, -2, 1f))
        root.addView(tools)

        val actions = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        val send = Button(this).apply {
            text = "➤  Send"
            textSize = 14f
            setOnClickListener {
                val q = questionInput?.text?.toString()?.trim().orEmpty()
                if (q.isNotBlank()) {
                    sendText(q)
                    questionInput?.setText("")
                }
            }
        }
        val close = Button(this).apply {
            text = "✕  Close"
            textSize = 14f
            setOnClickListener {
                overlayView?.let { if (it.parent != null) windowManager?.removeView(it) }
            }
        }
        actions.addView(send, LinearLayout.LayoutParams(0, -2, 1f))
        actions.addView(close, LinearLayout.LayoutParams(0, -2, 1f))
        root.addView(actions, LinearLayout.LayoutParams(-1, -2).apply {
            topMargin = (6 * dp).toInt()
        })

        overlayView = root
    }

    private fun startVoiceInput'''

s, count = panel_re.subn(panel_new, s, count=1)
if count != 1:
    raise SystemExit("buildPanel block not found")

path.write_text(s)
print("Polished Panda chat panel applied")