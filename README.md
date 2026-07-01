# Dungeon Harness

Dungeon Harness is an AI-powered illustrated Dungeon Master for tabletop RPG adventures. It turns a player-supplied adventure PDF into a responsive browser-based play session where the player can speak freely, explore scenes, talk to characters, and see the adventure illustrated as it unfolds.

The project began as an experimental AI game engine, but its direction is now more specific: a playable, text-first Dungeon Master that can run existing tabletop adventure modules while presenting them like an illustrated interactive storybook.

Live demo: [https://dungeon-harness.onrender.com/](https://dungeon-harness.onrender.com/)

## Current Capabilities

- AI-powered Dungeon Master driven by the contents of an uploaded 5e adventure PDF.
- Existing adventure PDF support through local upload or curated remote module links, with request, URL, and file-size protections.
- Beautiful AI-generated scene illustrations created during play.
- Free-form player input as the primary interface at all times.
- Contextual clickable links embedded directly in narrative text, filtered so natural player actions become shortcuts instead of accidental emphasis.
- Link, menu, upload, restart, and retry shortcuts that accelerate play while preserving unrestricted player input.
- Responsive scene-page UI with narrative, image, action, and input areas tuned for desktop and mobile.
- First-time character creation guidance with quick heroes, archetypes, free-form concepts, confirmation or revision, and illustrated portraits.
- Streamed DM responses, thematic busy states, and retry affordances for a more immediate and resilient play experience.
- Session isolation by browser session, backed by bounded in-memory state.
- Zero-schema conversational orchestration: the engine relies on text-native state and model context rather than rigid inventory, stat, or world-state tables.

Dungeon Harness is designed so the player is never trapped inside a menu. Buttons, links, and suggested actions are conveniences; the player can always type an ordinary action, question, command, or bit of dialogue.

## Engineering Philosophy

Most AI game engines rely on rigid database schemas to track inventory, character stats, locations, quests, and world state. Dungeon Harness takes a different approach: keep the live game conversational, text-native, and flexible for as long as possible.

The renderer should be deterministic: the browser turns known message, image, and action data into a stable interface. The LLM provides semantic content: narration, scene interpretation, NPC reactions, suggested actions, and image prompts.

The current prototype keeps live session state in memory for the active server process. It does not yet create durable Markdown character files, campaign journals, or database-backed saved games. Persistence, accounts, logging, deployment hardening, and release readiness are active roadmap areas.

Dungeon Harness currently uses Google's Gemini models, including multimodal image generation, to coordinate narrative play and visual scene creation inside the same overall orchestration loop.

## Running Locally

### Prerequisites

1. Google Gemini API key.

   Set GEMINI_API_KEY before starting the app, for example:

       export GEMINI_API_KEY=your-api-key-here

2. Adventure PDF.

   Choose one of the built-in starter links in the lobby, or provide your own standard 5e adventure module PDF, such as Matt Colville's *The Delian Tomb*. Start the application and use the local file selector to upload the PDF and initialize the game state.

3. Production settings, when deploying.

   For production, set a long random FLASK_SECRET_KEY, set APP_ENV=production, and serve the app over HTTPS with FLASK_COOKIE_SECURE=true.

### Start The App

    python run.py

After the backend starts, open the local web interface, upload an adventure PDF, create a character, and begin play.

### Development Checks

    pip install -r requirements-dev.txt
    python run_tests.py

Uploaded and remote PDFs are limited to 20 MiB by default. Override MAX_UPLOAD_BYTES or MAX_REMOTE_DOWNLOAD_BYTES only when the deployment has appropriate resource limits.

## Roadmap

The near-term direction is to make Dungeon Harness stable enough for trusted private feedback while preserving the fast, playful, text-first experience that makes the prototype interesting.

Current roadmap themes include:

- Continued player-facing polish for mobile layout, lobby clarity, scene readability, and the first few minutes of play.
- Durable persistence so campaigns survive refreshes, restarts, and deployment churn.
- Session management, campaign resume flows, and eventually accounts.
- Logging, observability, private feedback tooling, and release-readiness work.
- Clear privacy and licensing expectations for uploaded adventures, transcripts, and generated images.

See [ROADMAP.md](ROADMAP.md) for the full product and engineering roadmap.

## License

This repository is licensed under the **GNU General Public License v3.0 (GPLv3)**.

### Open Source Usage

Under the GPLv3, you are free to use, modify, and distribute this codebase for educational, scientific, and personal playtesting, provided that any derivative works or modifications you publish are also made 100% open-source under the exact same GPLv3 terms.

### Commercial Intent And Alternative Licensing

The author retains 100% of the original copyright and explicitly reserves the right to distribute this engine under alternative, proprietary commercial licenses for standalone applications or SaaS platforms. If you wish to use this engine framework inside a closed-source, commercial, or paid ecosystem, you must secure a commercial licensing exception from the author. For inquiries, please contact the author directly.
