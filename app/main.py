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
if os.environ.get("FLASK_ENV") == "production" and not os.environ.get("FLASK_SECRET_KEY"):
    raise RuntimeError("FLASK_SECRET_KEY must be set in production")
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dungeon-harness-local-secret')
app.config.update(
    MAX_CONTENT_LENGTH=int(os.environ.get("MAX_UPLOAD_BYTES", 20 * 1024 * 1024)),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("FLASK_COOKIE_SECURE", "false").lower() == "true",
)

MAX_REMOTE_DOWNLOAD_BYTES = int(os.environ.get("MAX_REMOTE_DOWNLOAD_BYTES", 20 * 1024 * 1024))
REMOTE_DOWNLOAD_TIMEOUT_SECONDS = float(os.environ.get("REMOTE_DOWNLOAD_TIMEOUT_SECONDS", 15))

class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Force every redirect through the same SSRF validation as the original URL."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

_NO_REDIRECT_OPENER = urllib.request.build_opener(_NoRedirectHandler)

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

def _download_remote_file(url: str, destination: str):
    """Download a bounded public file while revalidating every redirect."""
    current_url = url
    for _ in range(4):
        req = urllib.request.Request(current_url, headers={'User-Agent': 'DungeonHarness/1.0'})
        try:
            response = _NO_REDIRECT_OPENER.open(req, timeout=REMOTE_DOWNLOAD_TIMEOUT_SECONDS)
        except urllib.error.HTTPError as error:
            if error.code not in {301, 302, 303, 307, 308}:
                raise
            location = error.headers.get("Location")
            if not location:
                raise ValueError("Remote server returned an invalid redirect")
            candidate = urllib.parse.urljoin(current_url, location)
            current_url, validation_error = _validate_remote_url(candidate)
            if validation_error:
                raise ValueError(validation_error)
            continue

        with response:
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > MAX_REMOTE_DOWNLOAD_BYTES:
                raise ValueError("Remote file is too large")
            total = 0
            with open(destination, 'wb') as out_file:
                while chunk := response.read(64 * 1024):
                    total += len(chunk)
                    if total > MAX_REMOTE_DOWNLOAD_BYTES:
                        raise ValueError("Remote file is too large")
                    out_file.write(chunk)
            return current_url
    raise ValueError("Too many redirects")

def _looks_like_pdf(path: str) -> bool:
    with open(path, "rb") as uploaded_file:
        return uploaded_file.read(5) == b"%PDF-"

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
    if not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Only PDF files are supported"}), 400

    os.makedirs('/tmp', exist_ok=True)
    safe_name = secure_filename(file.filename) or "module.pdf"
    suffix = os.path.splitext(safe_name)[1] or ".pdf"
    with tempfile.NamedTemporaryFile(delete=False, dir='/tmp', suffix=suffix) as temp_file:
        temp_path = temp_file.name
    file.save(temp_path)

    try:
        if not _looks_like_pdf(temp_path):
            return jsonify({"error": "Uploaded file is not a valid PDF"}), 400
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

    data = request.get_json(silent=True) or {}
    url = data.get("url")
    if not isinstance(url, str) or not url:
        return jsonify({"error": "No url provided"}), 400

    validated_url, validation_error = _validate_remote_url(url)
    if validation_error:
        return jsonify({"error": validation_error}), 400

    filename = secure_filename(os.path.basename(urllib.parse.urlparse(validated_url).path))
    if not filename:
        filename = "module.pdf"
    if not filename.lower().endswith(".pdf"):
        filename += ".pdf"
    
    os.makedirs('/tmp', exist_ok=True)
    with tempfile.NamedTemporaryFile(delete=False, dir='/tmp', suffix=os.path.splitext(filename)[1]) as temp_file:
        temp_path = temp_file.name
    
    try:
        _download_remote_file(validated_url, temp_path)
        if not _looks_like_pdf(temp_path):
            return jsonify({"error": "Remote file is not a valid PDF"}), 400
            
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
    
    data = request.get_json(silent=True) or {}
    player_text = data.get("text", "")

    if not isinstance(player_text, str) or not player_text.strip():
        return jsonify({"error": "No text provided"}), 400
    if len(player_text) > 4000:
        return jsonify({"error": "Action text must be 4,000 characters or fewer"}), 400

    action_lock = session_state["action_lock"]
    if not action_lock.acquire(blocking=False):
        return jsonify({"error": "A previous action is still being processed."}), 409

    def generate():
        try:
            for item in process_action(player_text, session_state):
                yield json.dumps(item) + "\n"
                if item.get("type") in ["done", "error"]:
                    break
        finally:
            action_lock.release()

    return Response(generate(), mimetype='application/x-ndjson')

@app.errorhandler(413)
def request_entity_too_large(_error):
    return jsonify({"error": "Upload is too large"}), 413
