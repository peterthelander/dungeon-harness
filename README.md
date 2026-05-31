# Dungeon Harness
**A Zero-Schema, Lightweight AI Game Engine for Autonomous TTRPGs**

Dungeon Harness is an experimental architectural exploration into building autonomous Tabletop RPG orchestration using lightweight, text-native state tracking and advanced multimodal models. 

## Engineering Philosophy

Most AI game engines rely on rigid database schemas to track inventory, character stats, and world state. Dungeon Harness takes a radically different approach: **Zero-Schema State Tracking**.

*   **Markdown State Tracking**: All game state (e.g., `character.md`, `gamestate.md`) is maintained as free-form Markdown. This allows the LLM to read and natively update the state without brittle JSON serialization, heavy ORMs, or complex relational databases.
*   **Native Multimodal Processing**: Powered natively by `gemini-2.5-flash-image`, the engine leverages fast, low-cost multimodal iteration. This enables precise prompt adherence for both complex narrative generation and visual asset generation dynamically inside the orchestration loop.

## Prerequisites & Setup

To run Dungeon Harness locally, you will need to configure your environment and supply your own adventure content.

1. **Google Gemini API Key**: The engine requires a valid API key for Google's Gemini models. Set this as an environment variable before starting:
   ```bash
   export GEMINI_API_KEY="your-api-key-here"
   ```
2. **Adventure PDF**: To play, you must provide your own standard 5e adventure module PDF (such as Matt Colville's '*The Delian Tomb*'). Start the application and use the local file selector to upload the PDF and initialize the game state.

## Running the Engine
```bash
# Install dependencies and start the local engine
python run.py
```
After starting the backend, navigate to the local web interface to upload your PDF and begin.

## Licensing & Dual-License Notice

This repository is licensed under the **GNU General Public License v3.0 (GPLv3)**. 

### Open Source Usage
Under the GPLv3, you are free to use, modify, and distribute this codebase for educational, scientific, and personal playtesting, provided that any derivative works or modifications you publish are also made 100% open-source under the exact same GPLv3 terms.

### Commercial Intent & Alternative Licensing
The author retains 100% of the original copyright and explicitly reserves the right to distribute this engine under alternative, proprietary commercial licenses for standalone applications or SaaS platforms. If you wish to use this engine framework inside a closed-source, commercial, or paid ecosystem, you must secure a commercial licensing exception from the author. For inquiries, please contact the author directly.

