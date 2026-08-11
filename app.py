import os
import json
import base64
import mimetypes
import requests
import datetime
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024
UPLOAD_FOLDER = '/tmp/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
MODEL_NAME = os.environ.get('GEMINI_MODEL', 'gemini-3.6-flash')
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent"
LIVE_MODEL_NAME = os.environ.get('GEMINI_LIVE_MODEL', 'gemini-3.1-flash-live-preview')


def format_ts(sec):
    sec = float(sec or 0)
    m = int(sec // 60)
    s = int(sec % 60)
    return f"{m:02d}:{s:02d}"


def build_prompt(instructions):
    return (
        "Tum ek video annotation assistant ho. Diya gaya video dekho aur neeche diye "
        "client instructions ke hisaab se, video ko logical segments me todo.\n\n"
        f"CLIENT INSTRUCTIONS:\n{instructions}\n\n"
        "Ab ek JSON array do, SIRF JSON, koi extra text/markdown nahi, is format me:\n"
        '[{"start": 12.0, "end": 45.0, "label": "...", "reason": "..."}]\n'
        "start aur end seconds me (number) hone chahiye, video ke actual duration ke andar."
    )


@app.errorhandler(Exception)
def handle_any_error(e):
    return jsonify({"error": f"{type(e).__name__}: {str(e)}"}), 500


@app.route('/')
def index():
    return render_template('index.html', configured=bool(GEMINI_API_KEY))


@app.route('/analyze', methods=['POST'])
def analyze():
    if not GEMINI_API_KEY:
        return jsonify({"error": "GEMINI_API_KEY set nahi hai Render environment variables me."}), 500

    video = request.files.get('video')
    instructions = request.form.get('instructions', '').strip()
    if not video or video.filename == '':
        return jsonify({"error": "Video file zaroori hai."}), 400
    if not instructions:
        return jsonify({"error": "Instructions likhna zaroori hai."}), 400

    video_path = None
    try:
        filename = secure_filename(video.filename)
        video_path = os.path.join(UPLOAD_FOLDER, filename)
        video.save(video_path)
        mime_type = mimetypes.guess_type(video_path)[0] or "video/mp4"
        with open(video_path, "rb") as f:
            video_b64 = base64.b64encode(f.read()).decode("utf-8")
        payload = {"contents": [{"parts": [
            {"inline_data": {"mime_type": mime_type, "data": video_b64}},
            {"text": build_prompt(instructions)}
        ]}]}
        resp = requests.post(GEMINI_URL, params={"key": GEMINI_API_KEY}, json=payload, timeout=120)
        if resp.status_code != 200:
            return jsonify({"error": f"Gemini API error ({resp.status_code}): {resp.text[:300]}"}), 500
        data = resp.json()
        raw_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
        segments = json.loads(raw_text.strip())
        for seg in segments:
            seg["start_fmt"] = format_ts(seg.get("start", 0))
            seg["end_fmt"] = format_ts(seg.get("end", 0))
        return jsonify({"segments": segments})
    finally:
        if video_path and os.path.exists(video_path):
            os.remove(video_path)


@app.route('/live-chat', methods=['POST'])
def live_chat():
    """HTTP fallback for the Android Panda overlay.

    The Android client can send the latest screen frame plus a Hindi/Hinglish
    question here. This avoids making chat depend on the Gemini Live socket.
    """
    if not GEMINI_API_KEY:
        return jsonify({"error": "GEMINI_API_KEY set nahi hai Render environment variables me."}), 500

    body = request.get_json(silent=True) or {}
    question = str(body.get('question', '')).strip()
    image_b64 = str(body.get('image', '')).strip()
    image_mime = str(body.get('mime_type', 'image/jpeg')).strip() or 'image/jpeg'
    if not question:
        return jsonify({"error": "Question zaroori hai."}), 400

    parts = []
    if image_b64:
        try:
            base64.b64decode(image_b64, validate=True)
            parts.append({"inline_data": {"mime_type": image_mime, "data": image_b64}})
        except Exception:
            pass

    parts.append({"text": (
        "Tum Panda Assistant ho. User ke phone screen ka latest screenshot diya gaya hai. "
        "User Hindi ya Hinglish me baat kare to Hindi/Hinglish me natural jawab do. "
        "Screen par app, button, error, text ya UI dikh rahi ho to usko dhyan se samjho. "
        "Jawab concise rakho aur bina zarurat English me switch mat karo. "
        "Passwords, OTPs, API keys aur private secrets ko repeat mat karo.\n\n"
        f"USER QUESTION:\n{question}"
    )})

    try:
        resp = requests.post(
            GEMINI_URL,
            params={"key": GEMINI_API_KEY},
            json={"contents": [{"parts": parts}]},
            timeout=60,
        )
        if resp.status_code != 200:
            return jsonify({"error": f"Gemini API error ({resp.status_code}): {resp.text[:400]}"}), 502
        data = resp.json()
        candidates = data.get('candidates') or []
        if not candidates:
            return jsonify({"error": "Gemini ne koi reply nahi diya."}), 502
        reply = "\n".join(
            str(p.get('text', '')).strip()
            for p in candidates[0].get('content', {}).get('parts', [])
            if isinstance(p, dict) and str(p.get('text', '')).strip()
        ).strip()
        if not reply:
            return jsonify({"error": "Gemini ka text reply empty hai."}), 502
        return jsonify({"reply": reply})
    except requests.RequestException as e:
        return jsonify({"error": f"Backend network error: {str(e)}"}), 502
    except Exception as e:
        return jsonify({"error": f"Live chat error: {type(e).__name__}: {str(e)}"}), 500


@app.route('/live-token', methods=['POST'])
def live_token():
    if not GEMINI_API_KEY:
        return jsonify({"error": "GEMINI_API_KEY set nahi hai Render environment variables me."}), 500
    try:
        now = datetime.datetime.now(datetime.timezone.utc)
        expire_time = (now + datetime.timedelta(minutes=30)).isoformat().replace('+00:00', 'Z')
        new_session_expire_time = (now + datetime.timedelta(minutes=1)).isoformat().replace('+00:00', 'Z')
        payload = {
            "uses": 1,
            "expireTime": expire_time,
            "newSessionExpireTime": new_session_expire_time,
            "liveConnectConstraints": {
                "model": f"models/{LIVE_MODEL_NAME}",
                "config": {
                    "responseModalities": ["AUDIO"],
                    "outputAudioTranscription": {}
                }
            }
        }
        resp = requests.post(
            'https://generativelanguage.googleapis.com/v1beta/auth_tokens',
            headers={'x-goog-api-key': GEMINI_API_KEY, 'Content-Type': 'application/json'},
            json=payload,
            timeout=20
        )
        if resp.status_code != 200:
            print('Live token error:', resp.text[:500])
            return jsonify({"error": "Gemini Live token create nahi ho saka."}), 500
        data = resp.json()
        token = data.get('name')
        if not token:
            return jsonify({"error": "Gemini Live token response invalid hai."}), 500
        return jsonify({"token": token, "model": LIVE_MODEL_NAME})
    except Exception as e:
        print('Live token exception:', repr(e))
        return jsonify({"error": "Live Screen start nahi ho saka."}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
