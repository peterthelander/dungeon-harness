from flask import Flask, request, jsonify, Response
import os
import queue
import threading
import json

from app.state import engine_state, set_active_queue
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

    os.makedirs('tmp', exist_ok=True)
    temp_path = os.path.join('tmp', file.filename)
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

@app.route('/action', methods=['POST'])
def action():
    """ Validates action, queues task, and returns NDJSON streaming response """
    chat_session = engine_state.get("chat_session")
    if not chat_session:
        return jsonify({"error": "Engine not initialized. Please upload a PDF first."}), 400
    
    data = request.json
    player_text = data.get("text", "")

    if not player_text:
        return jsonify({"error": "No text provided"}), 400

    q = queue.Queue()
    set_active_queue(q)

    # Dispatch to background process so we can stream instantly over HTTP
    threading.Thread(target=process_action, args=(player_text,)).start()

    def generate():
        while True:
            item = q.get()
            yield json.dumps(item) + "\n"
            if item.get("type") in ["done", "error"]:
                break

    return Response(generate(), mimetype='application/x-ndjson')