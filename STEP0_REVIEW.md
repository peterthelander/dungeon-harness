# Step 0 Review: Private Feedback Readiness

Last updated: 2026-06-30

This note is the first pass of Step 0 from the roadmap. Its purpose is to reduce uncertainty before adding private-feedback features such as access gating, tester identity, persistence, logging, and a review surface.

## Validation Baseline

- python run_tests.py passes: 44 tests green.
- Existing tests cover engine streaming/tool behavior, route validation, remote URL safety, session-store eviction/TTL behavior, dice tools, prompts, and static frontend expectations.
- Route tests use faked Flask and engine modules, which keeps them fast but means they do not exercise full Flask session/cookie behavior or real response parsing.

## Current Ownership Boundaries

- app/main.py owns HTTP routes, request validation, Flask cookie session lookup, temporary upload files, response shaping, and action locking.
- app/engine.py owns model-backed gameplay orchestration, model tool calls, scene generation events, and recovery from empty model streams.
- app/state.py owns active in-memory runtime sessions keyed by Flask session ID. It currently stores chat_session, latest_pdf, and an action_lock.
- app/static/script.js owns the visible scene state, transcript blocks, hero image URL, inline action conversion, busy state, and streaming response rendering.
- app/module_loader.py owns upload/remote PDF validation and SSRF-resistant remote fetching.

The main boundary issue for private feedback is that the server owns model runtime state while the browser owns visible scene state. A refresh loses the user's visible game even if the server-side model session still exists.

## Fragile Paths To Review Before Feature Work

- Refresh or tab close after initialization: browser scene state is lost; server runtime state may still exist but has no restore route.
- Refresh during /action: client loses the stream; server may continue until the generator exits and releases the action lock, but the user has no clear recovery path.
- Session expiry or process restart: SessionStore is in memory, so initialized games disappear without a resumable record.
- Network failure during action: frontend now offers a contextual retry action for failed player turns; initialization and some restart/upload failures still use generic alerts or system messages.
- Duplicate or concurrent actions: server action locking exists, but the UX for a 409 conflict is still a retry-oriented scene message rather than a richer conflict state.
- Scene image handling: generated images are data URLs in browser memory, not durable assets with metadata or cleanup policy.
- Logs and observability: request IDs exist, but there is no durable activity log, tester/session label, transcript inspection, or summary view.
- Privacy and expectations: there is no tester-facing note explaining what may be logged or how feedback data is handled.

## Low-Risk Tidy Candidates

- Add a small server-side representation for visible scene blocks before choosing a durable database. This can start as a dataclass or plain dict structure in SessionState.
- Separate session identity helpers from route logic once access gating or tester labels are introduced.
- Define typed event names/constants for streamed UI events to reduce drift between backend and frontend.
- Add route tests for uninitialized action, action conflict, oversized/invalid action text, and request ID propagation using the current fake setup or a real Flask test client.
- Add frontend static tests for JSON parse failure handling, inactive inline action behavior, mobile layout expectations, and refresh/resume hooks once those hooks exist.
- Decide whether tmp/, __pycache__/, and generated screenshots are acceptable local-only artifacts or whether a cleanup script would help contributors.

## Suggested Step 0 Deliverables

1. Boundary note: confirm which state lives in browser memory, active server memory, durable storage, and logs.
2. Failure matrix: document current behavior and desired behavior for refresh, disconnect, duplicate action, expired session, and backend restart.
3. Test patch: add focused route/session tests around the fragile paths that already have clear expected behavior.
4. Minimal private-feedback design: choose the first implementation slice for access gate, tester/session identity, visible scene persistence, and activity logs.

## Proposed First Implementation Slice After Step 0

Start with tester/session identity plus activity logging before full persistence. That gives private feedback immediate diagnostic value and creates stable identifiers that persistence can attach to later.

A practical order:

1. Add a tester/session label accepted from a private link or simple access token.
2. Log structured activity events with request ID, session ID, tester label, event type, and timestamp.
3. Add a developer-only recent activity view or export.
4. Persist visible scene state after that, using the same session identifiers.

This keeps the first release small while making every later feedback session easier to understand.
