# Contributing to Dungeon Harness

## Architecture Boundaries
- `/app/main.py` owns HTTP routes, request validation, and response shaping.
- `/app/engine.py` owns gameplay orchestration and tool-call execution.
- `/app/model_client.py` owns Gemini API interaction details.
- `/app/prompts.py` owns reusable prompt templates.
- `/app/state.py` owns bounded, expiring, thread-safe session storage.

## Runtime and Deployment Conventions
- Set `GEMINI_API_KEY` before running.
- In production (`APP_ENV=production`), `FLASK_SECRET_KEY` is required.
- Optional runtime limits:
  - `MAX_UPLOAD_BYTES`
  - `MAX_REMOTE_DOWNLOAD_BYTES`
  - `REMOTE_DOWNLOAD_TIMEOUT_SECONDS`
  - `SESSION_TTL_SECONDS`
  - `MAX_SESSIONS`

## Testing
- Run tests with:
  - `python run_tests.py`
- Run quick syntax checks with:
  - `python -m compileall run.py app`

## Streaming Protocol Contract
- `/action` returns NDJSON events with event `type` values expected by the frontend:
  - `text_chunk`
  - `tool_call`
  - `status`
  - `image`
  - `error`
  - `done`
