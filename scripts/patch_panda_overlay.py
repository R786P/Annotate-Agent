from pathlib import Path
import re

path = Path("android/app/src/main/java/com/r786p/annotateagent/live/LiveScreenService.kt")
s = path.read_text()

# Panda overlay: draggable + edge hide/restore.
if "bubbleParams: WindowManager.LayoutParams" not in s:
    s = s.replace("private var bubble: PandaBubbleView? = null", "private var bubble: PandaBubbleView? = null\n    private var bubbleParams: WindowManager.LayoutParams? = null", 1)

show_re = re.compile(r"    private fun showOverlay\(\) \