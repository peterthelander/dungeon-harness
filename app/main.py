from flask import Flask, request, jsonify, Response
import os
import json
import urllib.request
import urllib.parse

from app.state import engine_state
from app.engine import upload_pdf_and_init, process_action

# Initialize Flask app pointing to local static directory
app = Flask(__name__, static_folder='static', static_url_path='')

@app.route('/')
def serve_index():
    return app.send_static_file('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    """ Accepts a PDF module, uploads it to Gemini, and spins up a new DM chat session. """
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    os.makedirs('/tmp', exist_ok=True)
    temp_path = os.path.join('/tmp', file.filename)
    file.save(temp_path)

    try:
        dm_text, image_data = upload_pdf_and_init(temp_path, file.filename)
        return jsonify({
            "status": "Engine Initialized Successfully",
            "dm_text": dm_text,
            "image_data": image_data
        })
    except Exception as e:
        print(f"Upload error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

@app.route('/load_url', methods=['POST'])
def load_url():
    """ Downloads a PDF module from a URL, uploads it to Gemini, and spins up a new DM session. """
    data = request.json
    url = data.get("url")
    if not url:
        return jsonify({"error": "No url provided"}), 400

    filename = os.path.basename(urllib.parse.urlparse(url).path)
    if not (filename.endswith(".pdf") or filename.endswith(".txt")):
        filename += ".pdf"
    
    os.makedirs('/tmp', exist_ok=True)
    temp_path = os.path.join('/tmp', filename)
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response, open(temp_path, 'wb') as out_file:
            out_file.write(response.read())
            
        dm_text, image_data = upload_pdf_and_init(temp_path, filename)
        return jsonify({
            "status": "Engine Initialized Successfully",
            "dm_text": dm_text,
            "image_data": image_data
        })
    except Exception as e:
        print(f"URL load error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

@app.route('/action', methods=['POST'])
def action():
    """ Validates action and returns NDJSON streaming response """
    chat_session = engine_state.get("chat_session")
    if not chat_session:
        return jsonify({"error": "Engine not initialized. Please upload a PDF first."}), 400
    
    data = request.json
    player_text = data.get("text", "")

    if not player_text:
        return jsonify({"error": "No text provided"}), 400

    def generate():
        for item in process_action(player_text):
            yield json.dumps(item) + "\n"
            if item.get("type") in ["done", "error"]:
                break

    return Response(generate(), mimetype='application/x-ndjson')