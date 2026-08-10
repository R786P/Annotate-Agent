package com.r786p.annotateagent.live

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.media.projection.MediaProjectionManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.view.Gravity
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.core.content.getSystemService

class MainActivity : AppCompatActivity() {
    companion object {
        private const val REQUEST_CAPTURE = 4101
        private const val REQUEST_NOTIFICATION = 4102
        private const val REQUEST_AUDIO = 4103
        private const val PREFS = "annotate_live"
        private const val URL_KEY = "backend_url"
        private const val DEFAULT_BACKEND = "https://annotate-agent.onrender.com"
    }

    private var waitingForOverlay = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(buildUi())
        if (Build.VERSION.SDK_INT >= 33 && ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), REQUEST_NOTIFICATION)
        }
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(Manifest.permission.RECORD_AUDIO), REQUEST_AUDIO)
        }
    }

    private fun buildUi(): LinearLayout {
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_HORIZONTAL
            setPadding(40, 50, 40, 40)
        }
        root.addView(TextView(this).apply { text = "🐼 Annotate Agent Live"; textSize = 28f }, LinearLayout.LayoutParams(-1, -2))
        root.addView(TextView(this).apply {
            text = "Phone ki screen live dikhao aur kisi bhi app/website ke baare mein poochho. Panda bubble me chat aur voice dono milenge.\n\n☁️ Backend: Annotate Agent (Render)\n🧠 AI: Gemini"
            textSize = 16f
            setPadding(0, 20, 0, 20)
        }, LinearLayout.LayoutParams(-1, -2))
        root.addView(TextView(this).apply {
            text = "Connected to:\n$DEFAULT_BACKEND"
            textSize = 12f
            setPadding(0, 0, 0, 8)
        }, LinearLayout.LayoutParams(-1, -2))
        val start = Button(this).apply { text = "🔴 Start Live Screen"; setOnClickListener { startLiveFlow() } }
        root.addView(start, LinearLayout.LayoutParams(-1, -2).apply { topMargin = 30 })
        root.addView(TextView(this).apply {
            text = "Pehli baar screen-capture, microphone aur floating-bubble permission maangega. Start hone ke baad app ko background mein rakhkar Instagram, Chrome, YouTube ya koi bhi app khol sakte ho. Panda bubble par tap = chat, bubble ke 🎙️ icon par tap = voice."
            textSize = 14f
            setPadding(0, 25, 0, 0)
        }, LinearLayout.LayoutParams(-1, -2))
        return root
    }

    private fun startLiveFlow() {
        val backend = DEFAULT_BACKEND
        getSharedPreferences(PREFS, MODE_PRIVATE).edit().putString(URL_KEY, backend).apply()
        if (!Settings.canDrawOverlays(this)) {
            waitingForOverlay = true
            startActivity(Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:$packageName")))
            return
        }
        requestScreenCapture(backend)
    }

    override fun onResume() {
        super.onResume()
        if (waitingForOverlay && Settings.canDrawOverlays(this)) {
            waitingForOverlay = false
            requestScreenCapture(DEFAULT_BACKEND)
        }
    }

    private fun requestScreenCapture(backend: String) {
        val manager = getSystemService<MediaProjectionManager>() ?: return
        val intent = manager.createScreenCaptureIntent()
        intent.putExtra(LiveScreenService.EXTRA_BACKEND_URL, backend)
        startActivityForResult(intent, REQUEST_CAPTURE)
    }

    @Deprecated("Activity result API kept simple for the MediaProjection consent flow")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode != REQUEST_CAPTURE || resultCode != Activity.RESULT_OK || data == null) return
        val serviceIntent = Intent(this, LiveScreenService::class.java).apply {
            putExtra(LiveScreenService.EXTRA_RESULT_CODE, resultCode)
            putExtra(LiveScreenService.EXTRA_RESULT_DATA, data)
            putExtra(LiveScreenService.EXTRA_BACKEND_URL, DEFAULT_BACKEND)
        }
        ContextCompat.startForegroundService(this, serviceIntent)
        finish()
    }
}
