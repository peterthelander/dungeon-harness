from flask import Flask, request, jsonify, Response, session
import ipaddress
import json
import logging
import os
import socket
import tempfile
import urllib.parse
import urllib.request
import uuid
from typing import Optional
from werkzeug.utils import secure_filename

from app.config import load_runtime_config
from app.engine import process_action, upload_pdf_and_init
from app.state import get_or_create_session_state


logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)
config = load_runtime_config()

ALLOWED_EXTENSIONS = {".pdf", ".txt"}
ALLOWED_UPLOAD_MIME_TYPES = {
    "application/pdf",
    "text/plain",
    "application/octet-stream",
}
ALLOWED_REMOTE_CONTENT_TYPES = {
    "application/pdf",
    "text/plain",
    "application/octet-stream",
}

app = Flask(__name__, static_folder="static", static_url_path="")
app.secret_key = config.flask_secret_key
app.config["MAX_CONTENT_LENGTH"] = config.max_upload_bytes
if not os.environ.get("FLASK_SECRET_KEY") and not config.is_production:
    logger.warning("FLASK_SECRET_KEY not set; using generated ephemeral development key.")


def _request_id() -> str:
    return request.headers.get("X-Request-ID") or str(uuid.uuid4())


def _json_error(message: str, status_code: int, code: str = "bad_request", request_id: Optional[str] = None):
    rid = request_id or _request_id()
    payload = {"error": message, "code": code, "request_id": rid}
    response = jsonify(payload)
    response.status_code = status_code
    response.headers["X-Request-ID"] = rid
    return response


def _json_ok(payload: dict, request_id: str):
    payload = {**payload, "request_id": request_id}
    response = jsonify(payload)
    response.headers["X-Request-ID"] = request_id
    return response


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


def _is_allowed_filename(filename: str) -> bool:
    ext = os.path.splitext(filename.lower())[1]
    return ext in ALLOWED_EXTENSIONS


def _is_allowed_mime_type(content_type: Optional[str]) -> bool:
    if not content_type:
        return True
    return content_type.split(";")[0].strip().lower() in ALLOWED_UPLOAD_MIME_TYPES


def _download_remote_file(validated_url: str, temp_path: str):
    req = urllib.request.Request(validated_url, headers={"User-Agent": "DungeonHarness/1.0"})
    with urllib.request.urlopen(req, timeout=config.remote_download_timeout_seconds) as response:
        content_type = response.headers.get("Content-Type", "")
        normalized_type = content_type.split(";")[0].strip().lower()
        if normalized_type and normalized_type not in ALLOWED_REMOTE_CONTENT_TYPES:
            raise ValueError("Remote file content type is not allowed.")

        content_length = response.headers.get("Content-Length")
        if content_length:
            try:
                parsed_length = int(content_length)
            except ValueError:
                raise ValueError("Remote server returned an invalid content length header.")
            if parsed_length > config.max_remote_download_bytes:
                raise ValueError("Remote file exceeds configured size limit.")

        bytes_read = 0
        with open(temp_path, "wb") as out_file:
            while True:
                chunk = response.read(64 * 1024)
                if not chunk:
                    break
                bytes_read += len(chunk)
                if bytes_read > config.max_remote_download_bytes:
                    raise ValueError("Remote file exceeds configured size limit.")
                out_file.write(chunk)


@app.route("/")
def serve_index():
    return app.send_static_file("index.html")


@app.route("/upload", methods=["POST"])
def upload():
    request_id = _request_id()
    session_state = _get_session_state()

    if "file" not in request.files:
        return _json_error("No file uploaded", 400, request_id=request_id)

    file = request.files["file"]
    if file.filename == "":
        return _json_error("No selected file", 400, request_id=request_id)

    safe_name = secure_filename(file.filename) or "module.pdf"
    if not _is_allowed_filename(safe_name):
        return _json_error("Only .pdf and .txt files are allowed.", 400, request_id=request_id)
    if not _is_allowed_mime_type(getattr(file, "mimetype", None)):
        return _json_error("Invalid upload content type.", 400, request_id=request_id)

    os.makedirs("/tmp", exist_ok=True)
    suffix = os.path.splitext(safe_name)[1] or ".pdf"
    with tempfile.NamedTemporaryFile(delete=False, dir="/tmp", suffix=suffix) as temp_file:
        temp_path = temp_file.name
    file.save(temp_path)

    try:
        logger.info("upload.start", extra={"request_id": request_id, "filename": safe_name})
        dm_text, image_data = upload_pdf_and_init(temp_path, file.filename, session_state)
        return _json_ok(
            {
                "status": "Engine Initialized Successfully",
                "dm_text": dm_text,
                "image_data": image_data,
            },
            request_id,
        )
    except Exception:
        logger.exception("upload.failed", extra={"request_id": request_id})
        return _json_error(
            "Failed to initialize engine from uploaded file.",
            500,
            code="engine_init_failed",
            request_id=request_id,
        )
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@app.route("/load_url", methods=["POST"])
def load_url():
    request_id = _request_id()
    session_state = _get_session_state()

    data = request.json or {}
    url = data.get("url")
    if not url:
        return _json_error("No url provided", 400, request_id=request_id)

    validated_url, validation_error = _validate_remote_url(url)
    if validation_error:
        return _json_error(validation_error, 400, request_id=request_id)

    filename = secure_filename(os.path.basename(urllib.parse.urlparse(validated_url).path))
    if not filename:
        filename = "module.pdf"
    if not _is_allowed_filename(filename):
        filename = "module.pdf"

    os.makedirs("/tmp", exist_ok=True)
    suffix = os.path.splitext(filename)[1] or ".pdf"
    with tempfile.NamedTemporaryFile(delete=False, dir="/tmp", suffix=suffix) as temp_file:
        temp_path = temp_file.name

    try:
        logger.info("load_url.start", extra={"request_id": request_id, "url": validated_url})
        _download_remote_file(validated_url, temp_path)
        dm_text, image_data = upload_pdf_and_init(temp_path, filename, session_state)
        return _json_ok(
            {
                "status": "Engine Initialized Successfully",
                "dm_text": dm_text,
                "image_data": image_data,
            },
            request_id,
        )
    except ValueError as e:
        logger.warning("load_url.validation_failed", extra={"request_id": request_id, "error": str(e)})
        return _json_error(
            "Remote file failed validation.",
            400,
            code="invalid_remote_file",
            request_id=request_id,
        )
    except Exception:
        logger.exception("load_url.failed", extra={"request_id": request_id})
        return _json_error(
            "Failed to load and initialize module from URL.",
            500,
            code="remote_init_failed",
            request_id=request_id,
        )
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@app.route("/action", methods=["POST"])
def action():
    request_id = _request_id()
    session_state = _get_session_state()
    chat_session = session_state.get("chat_session")
    if not chat_session:
        return _json_error(
            "Engine not initialized. Please upload a PDF first.",
            400,
            request_id=request_id,
        )

    data = request.json or {}
    player_text = data.get("text", "")
    if not player_text:
        return _json_error("No text provided", 400, request_id=request_id)

    def generate():
        for item in process_action(player_text, session_state):
            if item.get("type") == "error":
                item = {"type": "error", "error": "Action processing failed."}
            yield json.dumps(item) + "\n"
            if item.get("type") in ["done", "error"]:
                break

    response = Response(generate(), mimetype="application/x-ndjson")
    response.headers["X-Request-ID"] = request_id
    return response
