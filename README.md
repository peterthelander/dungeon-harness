# Dungeon Harness
**A Zero-Schema, Lightweight AI Game Engine for Autonomous TTRPGs**

Dungeon Harness is an experimental architectural exploration into building autonomous Tabletop RPG orchestration using lightweight, text-native state tracking and advanced multimodal models. 

🎮 **Live Demo:** You can try out the deployed version of the game online here: [https://dungeon-harness.onrender.com/](https://dungeon-harness.onrender.com/)

## Engineering Philosophy

Most AI game engines rely on rigid database schemas to track inventory, character stats, and world state. Dungeon Harness takes a radically different approach: **Zero-Schema State Tracking**.

*   **Text-native orchestration**: The model receives the adventure PDF as source context and maintains the live conversational state. The current prototype keeps that state in memory for the active server process; it does not yet create durable Markdown character or campaign files.
*   **Native Multimodal Processing**: Powered natively by `gemini-2.5-flash-image`, the engine leverages fast, low-cost multimodal iteration. This enables precise prompt adherence for both complex narrative generation and visual asset generation dynamically inside the orchestration loop.

## Prerequisites & Setup

To run Dungeon Harness locally, you will need to configure your environment and supply your own adventure content.

1. **Google Gemini API Key**: The engine requires a valid API key for Google's Gemini models. Set this as an environment variable before starting:
   ```bash
   export GEMINI_API_KEY="your-api-key-here"
   ```
   For a production deployment, also set a long, random `FLASK_SECRET_KEY`, set `APP_ENV=production`, and serve the app over HTTPS with `FLASK_COOKIE_SECURE=true`.
2. **Adventure PDF**: To play, you must provide your own standard 5e adventure module PDF (such as Matt Colville's '*The Delian Tomb*'). Start the application and use the local file selector to upload the PDF and initialize the game state.

## Running the Engine
```bash
# Install dependencies and start the local engine
python run.py
```
After starting the backend, navigate to the local web interface to upload your PDF and begin.

## Development checks

```bash
pip install -r requirements-dev.txt
pytest
```

Uploaded and remote PDFs are limited to 20 MiB by default. Override `MAX_UPLOAD_BYTES` or `MAX_REMOTE_DOWNLOAD_BYTES` only when the deployment has appropriate resource limits.

## Licensing & Dual-License Notice

This repository is licensed under the **GNU General Public License v3.0 (GPLv3)**. 

### Open Source Usage
Under the GPLv3, you are free to use, modify, and distribute this codebase for educational, scientific, and personal playtesting, provided that any derivative works or modifications you publish are also made 100% open-source under the exact same GPLv3 terms.

### Commercial Intent & Alternative Licensing
The author retains 100% of the original copyright and explicitly reserves the right to distribute this engine under alternative, proprietary commercial licenses for standalone applications or SaaS platforms. If you wish to use this engine framework inside a closed-source, commercial, or paid ecosystem, you must secure a commercial licensing exception from the author. For inquiries, please contact the author directly.
