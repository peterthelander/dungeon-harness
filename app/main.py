from flask import Flask, request, jsonify, Response, session
import json
import logging
import os
import tempfile
import urllib.parse
import uuid
from typing import Optional
from werkzeug.utils import secure_filename

from app.config import load_runtime_config
from app.engine import process_action, upload_pdf_and_init
from app.module_loader import (
    ALLOWED_EXTENSIONS,
    ALLOWED_UPLOAD_MIME_TYPES,
    download_remote_file,
    is_allowed_filename,
    is_allowed_mime_type,
    is_private_host,
    looks_like_pdf,
    open_pinned_response,
    validate_remote_url,
)
from app.state import SessionStore


logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)
config = load_runtime_config()
session_store = SessionStore(config.session_ttl_seconds, config.max_sessions)

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
    return session_store.get_or_create(session_id)


_is_private_host = is_private_host
_validate_remote_url = validate_remote_url
_is_allowed_filename = is_allowed_filename
_is_allowed_mime_type = is_allowed_mime_type
_looks_like_pdf = looks_like_pdf


def _open_pinned_response(url: str):
    return open_pinned_response(url, config.remote_download_timeout_seconds)


def _download_remote_file(validated_url: str, temp_path: str):
    return download_remote_file(
        validated_url,
        temp_path,
        config.remote_download_timeout_seconds,
        config.max_remote_download_bytes,
    )


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
    chat_session = session_state.chat_session
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

    action_lock = session_state.action_lock
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


@app.route("/session", methods=["GET"])
def get_session():
    request_id = _request_id()
    session_state = _get_session_state()
    initialized = session_state.chat_session is not None
    logger.info("session.get", extra={"request_id": request_id, "initialized": initialized})
    return _json_ok(
        {
            "initialized": initialized,
            "blocks": session_state.history if initialized else [],
            "hero_image_url": session_state.hero_image_url if initialized else None,
        },
        request_id,
    )


@app.errorhandler(413)
def request_entity_too_large(_error):
    return _json_error("Upload is too large.", 413, code="upload_too_large")

