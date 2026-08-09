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
        payload = {"contents": [{"parts": [{"inline_data": {"mime_type": mime_type, "data": video_b64}}, {"text": build_prompt(instructions)}]}]}
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


# NEW: Live Screen token endpoint. Existing /analyze flow remains unchanged.
@app.route('/live-token', methods=['POST'])
def live_token():
    if not GEMINI_API_KEY:
        return jsonify({"error": "GEMINI_API_KEY set nahi hai Render environment variables me."}), 500
    try:
        now = datetime.datetime.now(datetime.timezone.utc)
        payload = {
            "uses": 1,
            "expireTime": (now + datetime.timedelta(minutes=30)).isoformat().replace('+00:00', 'Z'),
            "newSessionExpireTime": (now + datetime.timedelta(minutes=1)).isoformat().replace('+00:00', 'Z')
        }
        resp = requests.post(
            'https://generativelanguage.googleapis.com/v1alpha/auth_tokens',
            headers={'x-goog-api-key': GEMINI_API_KEY, 'Content-Type': 'application/json'},
            json=payload,
            timeout=20
        )
        if resp.status_code != 200:
            print('Live token error:', resp.status_code, resp.text[:1000])
            return jsonify({"error": f"Gemini Live token error ({resp.status_code}): {resp.text[:500]}"}), 500
        data = resp.json()
        token = data.get('name')
        if not token:
            return jsonify({"error": "Gemini Live token response invalid hai."}), 500
        return jsonify({"token": token, "model": LIVE_MODEL_NAME})
    except Exception as e:
        print('Live token exception:', repr(e))
        return jsonify({"error": f"Live Screen start nahi ho saka: {type(e).__name__}: {e}"}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
