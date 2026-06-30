# Dungeon Harness Roadmap

Last updated: 2026-06-30

This document tracks the direction of Dungeon Harness as it moves from a playable prototype toward an AI-powered illustrated Dungeon Master that other people can use. It is a living note: areas of work, not fixed release commitments.

## Product Vision

Dungeon Harness should feel like an illustrated interactive storybook that can run real tabletop RPG adventure PDFs while preserving the freedom of tabletop play.

Principles:

- Free-form text is always the primary interface.
- Links, buttons, menus, and suggested actions are shortcuts that submit ordinary player text.
- The player should never feel trapped by the UI or limited to visible choices.
- The experience should be visual, responsive, and readable, with generated illustrations reinforcing the current scene rather than replacing the player's imagination.
- The renderer is deterministic; the LLM provides semantic content.
- The browser should render known structures predictably: messages, images, links, loading states, errors, and session controls.
- The model should provide narrative interpretation, NPC behavior, world description, suggested actions, and visual prompts.
- Every enhancement should leave the game in a playable, releasable state.
- Engineering work should preserve the fast loop that makes the prototype compelling: upload an adventure, create a character, and start playing.

The long-term goal is not a rigid video-game adaptation of tabletop rules. It is an AI Dungeon Master that can read and run adventure material, improvise within the spirit of the module, and present the session with enough illustration and interface assistance to make solo or small-group play feel immediate.

## Current State

Dungeon Harness can load a 5e adventure PDF, initialize a Gemini-backed play session, stream DM responses, render generated scene images, and let the player continue through the browser UI. Recent work has made the browser experience feel more like a game surface than a raw chat transcript.

The current architecture is still lightweight and text-native. Flask routes handle upload, initialization, action streaming, and session lookup. The engine handles gameplay orchestration. The browser client owns Markdown rendering, inline actions, scene layout, generated image display, and streamed UI updates. Session state is isolated per browser session, but still held in bounded process memory.

Current player-facing capabilities include:

- Adventure PDF initialization.
- Character creation and customization with illustrated portraits.
- Free-form player actions, questions, and dialogue.
- Contextual inline links embedded in narrative text.
- AI-generated scene illustrations.
- Responsive scene-page layout with a persistent input footer.
- Streamed responses and visible busy states.

## Recent Progress

- Inline action links: DM output can turn actionable bold labels into clickable inline action buttons while still preserving free-form player input.
- Markdown rendering: DM, player, and system blocks render as sanitized Markdown, improving readability and supporting richer adventure text.
- Scene layout: the play view has been reworked into a responsive scene page with narrative, generated imagery, and a persistent input footer.
- Character presentation: character creation now has a stronger visual loop through generated portraits.
- Session isolation: server state is keyed by a browser session cookie and stored in a bounded, expiring in-memory session store. This is a useful first step beyond a single global game state.
- Runtime hardening: upload and remote PDF paths include content limits, file validation, request IDs, and more structured error responses.

## Playtest Observations

These are observations from use and feedback, not implementation tasks.

- Character customization is unexpectedly engaging because regenerated portraits provide immediate visual feedback.
- Players naturally spend time experimenting with character identity and appearance before beginning the adventure.
- Inline contextual links feel more natural than separate button lists because they stay inside the fiction.
- Free-form input remains essential even when good shortcuts are available.
- NPCs should be more believable and less overly agreeable; they need clearer motives, boundaries, and friction.
- Mobile screen space is valuable, especially when narrative, image, suggested actions, and input are all visible.
- Visible loading and progress feedback greatly improves perceived responsiveness during model and image generation.
- Long responses need careful pacing so the player can scan what changed, what matters, and what they can do next.
- The best UI affordances feel like accelerators for tabletop play, not replacements for player intent.

## Interaction Modes (Vision)

Dungeon Harness may eventually support different interaction modes while keeping free-form text as the primary interface. These modes should not become hard constraints; they should help the renderer, model prompts, and tool usage match the current kind of play.

Potential modes:

- Character creation and customization.
- Exploration and movement.
- Local interaction with objects, clues, rooms, traps, treasure, and environmental details.
- Dialogue with NPCs, factions, and companions.
- Combat and other turn-sensitive conflict.

These modes may eventually differ in:

- Layout.
- Image policy.
- Response length.
- Pacing.
- Suggested actions.
- Dice and tool usage.
- How much recent context is shown.
- Whether the UI emphasizes map-like orientation, portrait-like character focus, tactical state, or narrative continuity.

The renderer should remain predictable. The LLM can decide what mode the scene is in, but the client should render that mode through explicit, testable UI rules.

## Player-Facing Improvements

Near-term polish should make the current play experience smoother without blocking the larger persistence and release work.

- Tune inline action detection so stat labels, headings, and descriptive emphasis do not become accidental choices.
- Consider moving from inferred bold-text actions to explicit model-produced choice markup if the heuristic becomes fragile.
- Make inactive inline actions clear without making older narrative feel broken.
- Preserve enough visible action history for the user to understand what happened after a streamed response.
- Continue layout tuning across desktop, portrait mobile, and phone landscape.
- Refine long-message readability, image height limits, and footer behavior.
- Improve character creation pacing, customization prompts, portrait regeneration, and transition into the adventure.
- Make NPC behavior less generically agreeable and more grounded in the adventure, situation, and character motives.
- Replace generic alerts and connection failures with contextual recovery states.
- Clearly distinguish uninitialized, busy, disconnected, and failed engine states.
- Keep visible loading/progress feedback during PDF initialization, character generation, DM response streaming, and image generation.

## Private Feedback Readiness

A near-term goal is to make the hosted link safe and useful enough to share with a trusted friend for feedback. This does not require the full public-release roadmap, but it does require enough stability, identity, persistence, and observability that a test session can be recovered, understood, and debugged.

### Step 0: Review And Tidy

Before adding new release foundations, do a short review pass to reduce obvious tech debt and make the next changes easier to land safely. See [STEP0_REVIEW.md](STEP0_REVIEW.md) for the first review pass and proposed private-feedback implementation order.

- Review current route, engine, state, and frontend boundaries for any tangled responsibilities that will make persistence harder.
- Identify brittle spots in streaming, session cleanup, upload handling, and frontend recovery behavior.
- Remove dead code, stale temporary files, and confusing naming where it creates friction.
- Add or update focused tests around the behavior that private feedback depends on most.
- Document the smallest viable architecture for private feedback before choosing storage, auth, or analytics tools.

Minimum useful pieces:

- Gate access so the link is not effectively a public anonymous playground before the project is ready.
- Identify at least the tester or browser session well enough to distinguish one feedback session from another.
- Persist the visible play session so refreshes, tab closes, or short network interruptions do not destroy the adventure.
- Capture basic activity logs: session start, PDF initialization, player actions, engine responses, errors, latency, and disconnects.
- Add lightweight analytics or admin visibility for activity volume, failure points, and where a tester drops off.
- Provide a simple way for the developer to inspect a session transcript and correlate it with request IDs or logs.
- Make privacy expectations explicit before collecting transcripts, uploaded content, or behavioral analytics.

Separately releasable sub-steps:

1. Access gate.
   Add a simple private-access mechanism for trusted testers, such as a shared invite token, allowlist, or lightweight login, without building the full account system yet.

2. Tester or session identity.
   Attach a stable tester or session label to actions, errors, and saved state so feedback from different people can be separated.

3. Refresh-safe scene state.
   Persist the visible scene, current transcript blocks, and enough campaign metadata to recover from refresh or short disconnects.

4. Basic activity logging.
   Record session start, module initialization, player actions, engine response completion, errors, latency, and disconnects with request IDs.

5. Lightweight review surface.
   Provide a developer-only way to inspect recent sessions, transcripts, error events, and activity summaries.

6. Feedback and privacy notes.
   Add a short tester-facing note explaining that this is private feedback software, what data may be logged, and how the tester should report problems.

## Engineering Infrastructure

The largest missing foundation is durable state. Today, a game can survive multiple HTTP requests in the same browser session, but it does not survive browser refresh, server restart, session expiration, or deployment churn in a user-friendly way.

### Persistence

Goals:

- Persist campaign and session state outside process memory.
- Restore the visible scene after refresh.
- Recover cleanly from interrupted requests or transient network failures.
- Preserve enough model and game context to continue an adventure without forcing a full PDF re-upload.

Likely work:

- Define a durable campaign record for metadata, uploaded module metadata, current scene, message blocks, generated image references, and engine continuation state.
- Choose a storage backend for the next deployment stage, such as SQLite for local or single-instance use, and Postgres plus object storage for hosted multi-user use.
- Decide what should be source-of-truth text or Markdown versus what can be reconstructed from model state.
- Add migration and versioning strategy before public users depend on saved games.
- Add tests around restore, expiration, concurrent actions, and interrupted streams.

### Accounts And User Sessions

Session cookies are enough for the prototype, but a released product probably needs real user identity.

Goals:

- Let a user return to campaigns from another browser or device.
- Support multiple campaigns per user.
- Make ownership and access explicit before shared or hosted play.

Likely work:

- Add an account model and login flow.
- Associate campaign records with a user.
- Build a campaign list, resume flow, rename and delete actions, and possibly archive or export.
- Decide whether anonymous sessions can later be claimed by a logged-in user.
- Define privacy and data-retention expectations for uploaded PDFs and generated content.

### Multi-Session Management

The current in-memory session store is a good first step for active isolation, but release-ready multi-session support needs durable lifecycle management.

Likely work:

- Separate active engine runtime state from durable campaign records.
- Support loading, pausing, resuming, and expiring campaigns intentionally.
- Make concurrency rules explicit: one active action per campaign, clear conflict responses, and predictable recovery if a request is abandoned.
- Add operator visibility into active sessions, failures, and resource usage.

### Logging And Observability

Activity logging should support debugging and private feedback without turning play into opaque surveillance.

Likely work:

- Add structured logs around initialization, action latency, model errors, image generation, session restore, and tester drop-off points.
- Make request IDs useful for debugging user-reported failures and correlating a visible session with backend logs.
- Capture enough transcript and event information to understand failures while documenting what is collected.
- Provide a developer-only review surface for recent sessions, errors, latency, and activity summaries.

### Deployment And Operations

Likely work:

- Confirm production configuration, secret handling, HTTPS cookie behavior, upload limits, and resource limits.
- Decide how generated images and uploaded PDFs are stored, cleaned up, and served.
- Define backup, cleanup, and retention policies once durable storage exists.
- Keep local development simple even if hosted deployment gains accounts, storage, and observability.

## Later Release Readiness

- Expand backend tests for session lifecycle, upload validation, streaming errors, and persistence once introduced.
- Add frontend smoke tests for initialization, action streaming, inline actions, character creation, and refresh or resume behavior.
- Clarify what adventure content users may upload and document licensing expectations for modules, generated images, and hosted play.
- Decide whether Dungeon Harness is primarily a local tool, a hosted app, or a framework other developers can run.
- Write onboarding docs for non-developer users once persistence and resume flows exist.
- Document privacy expectations for transcripts, uploaded PDFs, generated content, and analytics.
- Prepare release notes and known-limitations docs before broader testing.

## Open Questions

- What is the minimum saved state needed to resume a game faithfully?
- Should durable state be human-readable Markdown first, database records first, or a hybrid?
- Can model sessions be resumed directly, or should the engine rebuild context from saved transcript and campaign notes?
- Should uploaded PDFs be stored long-term, re-uploaded on resume, or converted into extracted text and assets during initialization?
- What is the right first authentication path: password login, magic links, OAuth, or local-only profiles?
- How much of the generated scene image history should be retained?
- Should inline choices eventually come from structured tool output instead of inferred Markdown emphasis?
- How explicit should interaction modes be in model output versus inferred from recent scene context?
- What level of tactical combat support belongs in Dungeon Harness without undermining free-form play?

## Suggested Milestones

0. Review and tidy the prototype: reduce obvious tech debt, confirm boundaries, and add focused tests around the fragile paths.
1. Stabilize the current play UI: finish inline-action tuning, layout polish, character creation flow, loading feedback, and clearer connection or error states.
2. Prepare for trusted private feedback in small releases: access gate, tester or session identity, refresh-safe scene state, logging, review surface, and tester-facing privacy notes.
3. Add broader local persistence: persist enough campaign metadata to survive browser refresh and server restart in a local or single-user deployment.
4. Add campaign resume flows: give users a way to see, resume, rename, and delete saved adventures.
5. Add accounts and hosted multi-user isolation: introduce user identity, ownership, storage policies, and multi-campaign management.
6. Prepare public release: round out tests, deployment docs, observability, licensing notes, privacy notes, and user-facing onboarding.
