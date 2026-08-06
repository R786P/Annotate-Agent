import os
import json
import time
import google.generativeai as genai
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # 200MB max upload
UPLOAD_FOLDER = '/tmp/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

MODEL_NAME = os.environ.get('GEMINI_MODEL', 'gemini-3.5-flash-lite')


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


def upload_and_wait(video_path):
    uploaded = genai.upload_file(path=video_path)
    while uploaded.state.name == "PROCESSING":
        time.sleep(2)
        uploaded = genai.get_file(uploaded.name)
    if uploaded.state.name == "FAILED":
        raise RuntimeError("Gemini par video process nahi ho paayi.")
    return uploaded


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

    filename = secure_filename(video.filename)
    video_path = os.path.join(UPLOAD_FOLDER, filename)
    video.save(video_path)
    uploaded_file = None

    try:
        uploaded_file = upload_and_wait(video_path)

        model = genai.GenerativeModel(MODEL_NAME)
        prompt = build_prompt(instructions)
        response = model.generate_content([uploaded_file, prompt])

        raw_text = (response.text or "").strip()
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
        raw_text = raw_text.strip()

        try:
            segments = json.loads(raw_text)
        except json.JSONDecodeError:
            return jsonify({"error": "AI response parse nahi hua.", "raw": raw_text}), 500

        for seg in segments:
            seg["start_fmt"] = format_ts(seg.get("start", 0))
            seg["end_fmt"] = format_ts(seg.get("end", 0))

        return jsonify({"segments": segments})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if os.path.exists(video_path):
            os.remove(video_path)
        if uploaded_file is not None:
            try:
                genai.delete_file(uploaded_file.name)
            except Exception:
                pass


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
