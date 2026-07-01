# Contributing to Dungeon Harness

## Architecture Boundaries
- `/app/main.py` owns HTTP routes, request validation, response shaping, session lookup, and action locking.
- `/app/engine.py` owns gameplay orchestration, streaming events, model tool calls, and recovery from empty model streams.
- `/app/model_client.py` owns Gemini API interaction details.
- `/app/module_loader.py` owns upload and remote PDF validation/fetching.
- `/app/prompts.py` owns reusable prompt templates and onboarding/gameplay behavior guidance.
- `/app/scenes.py` and `/app/tool_dispatch.py` own scene rendering and model tool dispatch boundaries.
- `/app/state.py` owns bounded, expiring, thread-safe session storage.
- `/app/static/script.js` owns the visible scene state, Markdown rendering, inline actions, busy/retry UI, and streamed frontend updates.

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
