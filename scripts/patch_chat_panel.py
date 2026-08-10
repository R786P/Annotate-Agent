from pathlib import Path
import re

path = Path("android/app/src/main/java/com/r786p/annotateagent/live/LiveScreenService.kt")
s = path.read_text()
s = s.replace('import android.view.WindowManager\n', 'import android.view.WindowManager\nimport android.webkit.JavascriptInterface\nimport android.webkit.WebView\nimport android.webkit.WebViewClient\n')
s = s.replace('    private var questionInput: EditText? = null\n', '    private var questionInput: EditText? = null\n    private var chatWebView: WebView? = null\n', 1)
panel_re = re.compile(r'    private fun buildPanel\(\) \{.*?\n    \}\n\n    private fun startVoiceInput', re.S)
panel_new = '''    private fun buildPanel() {
        val dp = resources.displayMetrics.density
        val web = WebView(this).apply {
            setBackgroundColor(Color.TRANSPARENT)
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            settings.allowFileAccess = false
            webViewClient = WebViewClient()
            addJavascriptInterface(PandaWebBridge(), "NativeBridge")
            loadUrl("$backendUrl/static/mobile_panel.html")
        }
        chatWebView = web
        overlayView = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding((4 * dp).toInt(), (4 * dp).toInt(), (4 * dp).toInt(), (4 * dp).toInt())
            setBackgroundColor(Color.TRANSPARENT)
            addView(web, LinearLayout.LayoutParams(-1, -1))
        }
    }

    private inner class PandaWebBridge {
        @JavascriptInterface fun send(text: String) { val q = text.trim(); if (q.isNotBlank()) sendText(q) }
        @JavascriptInterface fun voice() { startVoiceInput() }
        @JavascriptInterface fun closePanel() { Handler(mainLooper).post { overlayView?.let { if (it.parent != null) windowManager?.removeView(it) } } }
        @JavascriptInterface fun copy(text: String) {
            val cm = getSystemService(CLIPBOARD_SERVICE) as android.content.ClipboardManager
            cm.setPrimaryClip(android.content.ClipData.newPlainText("Panda reply", text))
            pushReply("✅ Reply copied")
        }
        @JavascriptInterface fun paste(): String {
            val cm = getSystemService(CLIPBOARD_SERVICE) as android.content.ClipboardManager
            return cm.primaryClip?.getItemAt(0)?.coerceToText(this@LiveScreenService)?.toString().orEmpty()
        }
        @JavascriptInterface fun openFilePicker() {
            try {
                val intent = Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
                    addCategory(Intent.CATEGORY_OPENABLE)
                    type = "*/*"
                    addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                }
                startActivity(intent)
            } catch (_: Exception) { pushReply("📎 File picker open nahi hua.") }
        }
    }

    private fun pushReply(text: String) {
        Handler(mainLooper).post { chatWebView?.evaluateJavascript("window.setReply(${JSONObject.quote(text)})", null) }
    }

    private fun startVoiceInput'''
s, count = panel_re.subn(panel_new, s, count=1)
if count != 1: raise SystemExit("buildPanel block not found")
show_re = re.compile(r'    private fun showAnswer\(text: String\) \{.*?\n    \}\n', re.S)
show_new = '''    private fun showAnswer(text: String) {
        Handler(mainLooper).post {
            chatWebView?.evaluateJavascript("window.setReply(${JSONObject.quote(text)})", null)
            answerView?.text = text
        }
    }
'''
s, count = show_re.subn(show_new, s, count=1)
if count != 1: raise SystemExit("showAnswer block not found")
path.write_text(s)
print("Panda panel now uses Render-hosted mobile UI")
