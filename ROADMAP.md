# Dungeon Harness Roadmap

Last updated: 2026-06-28

This document tracks the direction of Dungeon Harness as it moves from an experimental playable prototype toward something stable enough for other people to use. It is a living note: areas of work, not fixed release commitments.

## Current State

Dungeon Harness can load a 5e adventure PDF, initialize a Gemini-backed play session, stream DM responses, render generated scene images, and let the player continue through the browser UI. Recent work has made the browser experience feel more like a game surface than a raw chat transcript.

The current architecture is still lightweight and text-native. Flask routes handle upload, initialization, action streaming, and session lookup. The engine handles gameplay orchestration. The browser client owns Markdown rendering, inline actions, scene layout, and streamed UI updates. Session state is isolated per browser session, but still held in bounded process memory.

## Recent Progress

- Inline action links: DM output can turn actionable bold labels into clickable inline action buttons while still preserving free-form player input.
- Markdown rendering: DM, player, and system blocks render as sanitized Markdown, improving readability and supporting richer adventure text.
- Scene layout: the play view has been reworked into a responsive scene page with narrative, generated imagery, and a persistent input footer.
- Session isolation: server state is keyed by a browser session cookie and stored in a bounded, expiring in-memory session store. This is a useful first step beyond a single global game state.
- Runtime hardening: upload and remote PDF paths include content limits, file validation, request IDs, and more structured error responses.

## Near-Term Polish

- Tune inline action detection so stat labels, headings, and descriptive emphasis do not become accidental choices.
- Consider moving from inferred bold-text actions to explicit model-produced choice markup if the heuristic becomes fragile.
- Make inactive inline actions clear without making older narrative feel broken.
- Preserve enough visible action history for the user to understand what happened after a streamed response.
- Continue layout tuning across desktop, portrait mobile, and phone landscape.
- Refine long-message readability, image height limits, and footer behavior.
- Replace generic alerts and connection failures with contextual recovery states.
- Clearly distinguish uninitialized, busy, disconnected, and failed engine states.

## Private Feedback Readiness

A near-term goal is to make the hosted link safe and useful enough to share with a trusted friend for feedback. This does not require the full public-release roadmap, but it does require enough stability, identity, persistence, and observability that a test session can be recovered, understood, and debugged.

### Step 0: Review and Tidy

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

## Release Foundations

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

### Accounts and User Sessions

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

## Later Release Readiness

- Confirm production configuration, secret handling, HTTPS cookie behavior, upload limits, and resource limits.
- Decide how generated images and uploaded PDFs are stored, cleaned up, and served.
- Add structured logs and lightweight analytics around initialization, action latency, model errors, image generation, session restore, and tester drop-off points.
- Make request IDs useful for debugging user-reported failures and correlating a visible session with backend logs.
- Expand backend tests for session lifecycle, upload validation, streaming errors, and persistence once introduced.
- Add frontend smoke tests for initialization, action streaming, inline actions, and refresh or resume behavior.
- Clarify what adventure content users may upload and document licensing expectations for modules, generated images, and hosted play.
- Decide whether Dungeon Harness is primarily a local tool, a hosted app, or a framework other developers can run.
- Write onboarding docs for non-developer users once persistence and resume flows exist.

## Open Questions

- What is the minimum saved state needed to resume a game faithfully?
- Should durable state be human-readable Markdown first, database records first, or a hybrid?
- Can model sessions be resumed directly, or should the engine rebuild context from saved transcript and campaign notes?
- Should uploaded PDFs be stored long-term, re-uploaded on resume, or converted into extracted text and assets during initialization?
- What is the right first authentication path: password login, magic links, OAuth, or local-only profiles?
- How much of the generated scene image history should be retained?
- Should inline choices eventually come from structured tool output instead of inferred Markdown emphasis?

## Suggested Milestones

0. Review and tidy the prototype: reduce obvious tech debt, confirm boundaries, and add focused tests around the fragile paths.
1. Stabilize the current play UI: finish inline-action tuning, layout polish, and clearer connection or error states.
2. Prepare for trusted private feedback in small releases: access gate, tester or session identity, refresh-safe scene state, logging, review surface, and tester-facing privacy notes.
3. Add broader local persistence: persist enough campaign metadata to survive browser refresh and server restart in a local or single-user deployment.
4. Add campaign resume flows: give users a way to see, resume, rename, and delete saved adventures.
5. Add accounts and hosted multi-user isolation: introduce user identity, ownership, storage policies, and multi-campaign management.
6. Prepare public release: round out tests, deployment docs, observability, licensing notes, and user-facing onboarding.
