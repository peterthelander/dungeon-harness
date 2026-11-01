#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# .env is a local, gitignored shell environment file.
if [[ -f .env ]]; then
    set -a
    source .env
    set +a
fi
if [[ -z "${GEMINI_API_KEY:-${GOOGLE_API_KEY:-}}" ]]; then
    echo 'Set GEMINI_API_KEY in .env before starting (see README.md).' >&2
    exit 1
fi

python_bin="${PYTHON_BIN:-.venv/bin/python}"
if [[ ! -x "$python_bin" ]]; then
    echo 'Create .venv and install requirements.txt first (see README.md).' >&2
    exit 1
fi

if [[ -n "${PHONE_URL:-}" ]]; then
    printf 'Phone: %s (connect Tailscale first)\n' "$PHONE_URL"
else
    echo 'Open your laptop’s Tailscale HTTPS URL on your phone (set PHONE_URL in .env to display it here).'
fi
echo 'Keep this terminal and laptop running. Ctrl+C stops the app.'
# Reload local edits, but never expose Flask’s interactive debugger.
export FLASK_COOKIE_SECURE=true
exec "$python_bin" -m flask --app app.main run --host 127.0.0.1 --port 5000 --reload --no-debugger
