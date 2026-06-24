from flask import Flask, request, jsonify, Response, session
import http.client
import ipaddress
import json
import logging
import os
import socket
import ssl
import tempfile
import threading
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

ALLOWED_EXTENSIONS = {".pdf"}
ALLOWED_UPLOAD_MIME_TYPES = {
    "application/pdf",
    "application/octet-stream",
}
ALLOWED_REMOTE_CONTENT_TYPES = {
    "application/pdf",
    "application/octet-stream",
}

app = Flask(__name__, static_folder="static", static_url_path="")
app.secret_key = config.flask_secret_key
app.config["MAX_CONTENT_LENGTH"] = config.max_upload_bytes
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("FLASK_COOKIE_SECURE", str(config.is_production)).lower() == "true",
)
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
        addresses = _resolve_public_addresses(hostname)
    except socket.gaierror:
        return True
    return not addresses


def _resolve_public_addresses(hostname: str, port: Optional[int] = None) -> tuple[str, ...]:
    addresses = {addr_info[4][0] for addr_info in socket.getaddrinfo(hostname, port)}
    public_addresses = []
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if not ip.is_global:
            return ()
        public_addresses.append(address)
    return tuple(public_addresses)


def _validate_remote_url(url: str):
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return None, "Only http/https URLs are allowed."
    if not parsed.hostname:
        return None, "URL must include a hostname."
    if parsed.username or parsed.password:
        return None, "URLs with credentials are not allowed."
    try:
        port = parsed.port
    except ValueError:
        return None, "URL contains an invalid port."
    if not _resolve_public_addresses(parsed.hostname, port):
        return None, "Private or local network addresses are not allowed."
    return parsed.geturl(), None


def _is_allowed_filename(filename: str) -> bool:
    ext = os.path.splitext(filename.lower())[1]
    return ext in ALLOWED_EXTENSIONS


def _is_allowed_mime_type(content_type: Optional[str]) -> bool:
    if not content_type:
        return True
    return content_type.split(";")[0].strip().lower() in ALLOWED_UPLOAD_MIME_TYPES


class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, host: str, port: int, address: str, timeout: int):
        super().__init__(host, port=port, timeout=timeout)
        self._address = address

    def connect(self):
        self.sock = socket.create_connection((self._address, self.port), self.timeout)


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host: str, port: int, address: str, timeout: int):
        super().__init__(host, port=port, timeout=timeout, context=ssl.create_default_context())
        self._address = address

    def connect(self):
        raw_socket = socket.create_connection((self._address, self.port), self.timeout)
        self.sock = self._context.wrap_socket(raw_socket, server_hostname=self.host)


def _looks_like_pdf(path: str) -> bool:
    with open(path, "rb") as uploaded_file:
        return uploaded_file.read(5) == b"%PDF-"


def _open_pinned_response(url: str):
    parsed = urllib.parse.urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL must include a hostname.")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    addresses = _resolve_public_addresses(hostname, port)
    if not addresses:
        raise ValueError("Private or local network addresses are not allowed.")

    target = urllib.parse.urlunparse(("", "", parsed.path or "/", "", parsed.query, ""))
    host_header = hostname if parsed.port is None else f"{hostname}:{parsed.port}"
    last_error = None
    for address in addresses:
        connection_class = _PinnedHTTPSConnection if parsed.scheme == "https" else _PinnedHTTPConnection
        connection = connection_class(hostname, port, address, config.remote_download_timeout_seconds)
        try:
            connection.request("GET", target, headers={"Host": host_header, "User-Agent": "DungeonHarness/1.0"})
            return connection, connection.getresponse()
        except OSError as error:
            connection.close()
            last_error = error
    raise ValueError("Remote server could not be reached.") from last_error


def _download_remote_file(validated_url: str, temp_path: str):
    current_url = validated_url
    for _ in range(4):
        connection = None
        try:
            connection, response = _open_pinned_response(current_url)
            if response.status in {301, 302, 303, 307, 308}:
                location = response.headers.get("Location")
                if not location:
                    raise ValueError("Remote server returned an invalid redirect.")
                candidate = urllib.parse.urljoin(current_url, location)
                current_url, validation_error = _validate_remote_url(candidate)
                if validation_error:
                    raise ValueError(validation_error)
                continue
            if not 200 <= response.status < 300:
                raise ValueError("Remote server returned an unsuccessful status.")

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
            return
        finally:
            if connection:
                connection.close()
    raise ValueError("Too many redirects.")


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
        return _json_error("Only PDF files are supported.", 400, request_id=request_id)
    if not _is_allowed_mime_type(getattr(file, "mimetype", None)):
        return _json_error("Invalid upload content type.", 400, request_id=request_id)

    os.makedirs("/tmp", exist_ok=True)
    suffix = os.path.splitext(safe_name)[1] or ".pdf"
    with tempfile.NamedTemporaryFile(delete=False, dir="/tmp", suffix=suffix) as temp_file:
        temp_path = temp_file.name
    file.save(temp_path)

    try:
        if not _looks_like_pdf(temp_path):
            return _json_error("Uploaded file is not a valid PDF.", 400, request_id=request_id)
        logger.info("upload.start", extra={"request_id": request_id, "upload_filename": safe_name})
        dm_text, image_data, suggestions = upload_pdf_and_init(temp_path, file.filename, session_state)
        return _json_ok(
            {
                "status": "Engine Initialized Successfully",
                "dm_text": dm_text,
                "image_data": image_data,
                "suggestions": suggestions,
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

    data = request.get_json(silent=True) or {}
    url = data.get("url")
    if not isinstance(url, str) or not url:
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
        if not _looks_like_pdf(temp_path):
            return _json_error("Remote file is not a valid PDF.", 400, request_id=request_id)
        dm_text, image_data, suggestions = upload_pdf_and_init(temp_path, filename, session_state)
        return _json_ok(
            {
                "status": "Engine Initialized Successfully",
                "dm_text": dm_text,
                "image_data": image_data,
                "suggestions": suggestions,
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

    data = request.get_json(silent=True) or {}
    player_text = data.get("text", "")
    if not isinstance(player_text, str) or not player_text.strip():
        return _json_error("No text provided", 400, request_id=request_id)
    if len(player_text) > 4000:
        return _json_error("Action text must be 4,000 characters or fewer.", 400, request_id=request_id)

    action_lock = session_state.setdefault("action_lock", threading.Lock())
    if not action_lock.acquire(blocking=False):
        return _json_error("A previous action is still being processed.", 409, request_id=request_id)

    def generate():
        try:
            for item in process_action(player_text, session_state):
                if item.get("type") == "error":
                    item = {"type": "error", "error": "Action processing failed."}
                yield json.dumps(item) + "\n"
                if item.get("type") in ["done", "error"]:
                    break
        finally:
            action_lock.release()

    response = Response(generate(), mimetype="application/x-ndjson")
    response.headers["X-Request-ID"] = request_id
    return response


@app.errorhandler(413)
def request_entity_too_large(_error):
    return _json_error("Upload is too large.", 413, code="upload_too_large")
