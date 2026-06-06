from flask import Flask, request, jsonify, Response, session
import os
import json
import urllib.request
import urllib.parse
import uuid
import tempfile
import ipaddress
import socket
from werkzeug.utils import secure_filename

from app.state import get_or_create_session_state
from app.engine import upload_pdf_and_init, process_action

# Initialize Flask app pointing to local static directory
app = Flask(__name__, static_folder='static', static_url_path='')
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dungeon-harness-local-secret')

def _get_session_state():
    session_id = session.get("session_id")
    if not session_id:
        session_id = str(uuid.uuid4())
        session["session_id"] = session_id
    return get_or_create_session_state(session_id)

def _is_private_host(hostname: str) -> bool:
    try:
        addresses = {addr_info[4][0] for addr_info in socket.getaddrinfo(hostname, None)}
    except socket.gaierror:
        return True

    for address in addresses:
        ip = ipaddress.ip_address(address)
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            return True
    return False

def _validate_remote_url(url: str):
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return None, "Only http/https URLs are allowed."
    if not parsed.hostname:
        return None, "URL must include a hostname."
    if _is_private_host(parsed.hostname):
        return None, "Private or local network addresses are not allowed."
    return parsed.geturl(), None

@app.route('/')
def serve_index():
    return app.send_static_file('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    """ Accepts a PDF module, uploads it to Gemini, and spins up a new DM chat session. """
    session_state = _get_session_state()

    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    os.makedirs('/tmp', exist_ok=True)
    safe_name = secure_filename(file.filename) or "module.pdf"
    suffix = os.path.splitext(safe_name)[1] or ".pdf"
    with tempfile.NamedTemporaryFile(delete=False, dir='/tmp', suffix=suffix) as temp_file:
        temp_path = temp_file.name
    file.save(temp_path)

    try:
        dm_text, image_data = upload_pdf_and_init(temp_path, file.filename, session_state)
        return jsonify({
            "status": "Engine Initialized Successfully",
            "dm_text": dm_text,
            "image_data": image_data
        })
    except Exception as e:
        print(f"Upload error: {e}")
        return jsonify({"error": "Failed to initialize engine from uploaded file."}), 500
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

@app.route('/load_url', methods=['POST'])
def load_url():
    """ Downloads a PDF module from a URL, uploads it to Gemini, and spins up a new DM session. """
    session_state = _get_session_state()

    data = request.json
    url = data.get("url")
    if not url:
        return jsonify({"error": "No url provided"}), 400

    validated_url, validation_error = _validate_remote_url(url)
    if validation_error:
        return jsonify({"error": validation_error}), 400

    filename = secure_filename(os.path.basename(urllib.parse.urlparse(validated_url).path))
    if not filename:
        filename = "module.pdf"
    if not (filename.endswith(".pdf") or filename.endswith(".txt")):
        filename += ".pdf"
    
    os.makedirs('/tmp', exist_ok=True)
    with tempfile.NamedTemporaryFile(delete=False, dir='/tmp', suffix=os.path.splitext(filename)[1]) as temp_file:
        temp_path = temp_file.name
    
    try:
        req = urllib.request.Request(validated_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response, open(temp_path, 'wb') as out_file:
            out_file.write(response.read())
            
        dm_text, image_data = upload_pdf_and_init(temp_path, filename, session_state)
        return jsonify({
            "status": "Engine Initialized Successfully",
            "dm_text": dm_text,
            "image_data": image_data
        })
    except Exception as e:
        print(f"URL load error: {e}")
        return jsonify({"error": "Failed to load and initialize module from URL."}), 500
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

@app.route('/action', methods=['POST'])
def action():
    """ Validates action and returns NDJSON streaming response """
    session_state = _get_session_state()
    chat_session = session_state.get("chat_session")
    if not chat_session:
        return jsonify({"error": "Engine not initialized. Please upload a PDF first."}), 400
    
    data = request.json
    player_text = data.get("text", "")

    if not player_text:
        return jsonify({"error": "No text provided"}), 400

    def generate():
        for item in process_action(player_text, session_state):
            yield json.dumps(item) + "\n"
            if item.get("type") in ["done", "error"]:
                break

    return Response(generate(), mimetype='application/x-ndjson')