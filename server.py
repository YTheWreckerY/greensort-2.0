import os
import base64
import requests
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise EnvironmentError("Please set GEMINI_API_KEY in .env")

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

app.config["UPLOAD_FOLDER"] = "/tmp"
app.config["MAX_CONTENT_LENGTH"] = 15 * 1024 * 1024

PROMPT = (
    "Identify the garbage in the image and classify the waste and suggest in brief a few ways to deal with the waste. "
    "Format the output as:\n"
    "Name: <name>\nDescription: <description>"
)

def identify_from_bytes(image_bytes, mime_type):
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": PROMPT},
                    {"inline_data": {"mime_type": mime_type, "data": encoded}}
                ]
            }
        ]
    }
    r = requests.post(
        f"{GEMINI_API_URL}?key={GEMINI_API_KEY}",
        headers={"Content-Type": "application/json"},
        json=payload,
        timeout=60
    )
    if r.status_code != 200:
        return {"error": r.text}

    res = r.json()
    try:
        text = res["candidates"][0]["content"]["parts"][0]["text"]
    except:
        return {"error": "Bad model response", "raw": res}

    name, description = "", ""
    for line in text.splitlines():
        l = line.lower().strip()
        if l.startswith("name:"):
            name = line.split(":", 1)[1].strip()
        if l.startswith("description:"):
            description = line.split(":", 1)[1].strip()

    if not name:
        name = "Unknown"
    if not description:
        description = text.strip()

    return {"name": name, "description": description}
    
@app.route("/")
def index():
    return render_template('index.html')
    
@app.post("/api/identify")
def identify_api():
    if "images" not in request.files:
        return jsonify({"error": "No images provided"}), 400

    files = request.files.getlist("images")
    results = []

    for idx, f in enumerate(files):
        filename = secure_filename(f.filename or f"img_{idx}.jpg")

        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpg"
        mime = "image/jpeg"
        if ext == "png": mime = "image/png"
        if ext == "webp": mime = "image/webp"

        img = f.read()
        if not img:
            results.append({"index": idx, "filename": filename, "error": "Empty file"})
            continue

        out = identify_from_bytes(img, mime)
        out.update({"index": idx, "filename": filename})
        results.append(out)

    return jsonify({"results": results})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

