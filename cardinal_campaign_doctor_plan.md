# Cardinal Campaign Doctor — v1 Proof-of-Work Plan

## Purpose
Build a small, independent demonstration of a debugging need documented in Cardinal's publicly available YC job descriptions: troubleshooting unexpected outbound campaign behavior, replaying events, and improving health checks. This is **not** a claim that a specific bug exists in Cardinal's production service.

## Evidence (checked October 27, 2026)
- Founding Customer Engineer: requests fixing campaign issues and building internal admin, replay/debugging, and health-check tools: https://www.ycombinator.com/companies/trycardinal-ai/jobs/Po0pWFA-founding-customer-engineer
- Founding Product Engineer: describes sequence/enrollment systems, observability, and why reply detection and enrichment timeouts matter: https://www.ycombinator.com/companies/trycardinal-ai/jobs/HwZIbQl-founding-product-engineer
- Founding Engineer: mentions TypeScript, React, Next.js, Python, distributed systems, and multi-channel orchestration: https://www.ycombinator.com/companies/trycardinal-ai/jobs/vLd6N4I-founding-engineer

## Specific scenario: delayed reply notification
A sales sequence automatically follows up with a prospect if the system believes the prospect has not replied.

Synthetic timeline (all times same timezone, ISO-8601 UTC in data):
1. 09:00 — Initial email sent.
2. 09:58 — Prospect replies at the external mail provider.
3. 10:00 — Follow-up is sent; the automation's state is still `ACTIVE` because the reply has not been observed.
4. 10:02 — Reply webhook reaches/is processed by the automation and changes state to `STOPPED`.

**Why this happens in the demo:** a notification can arrive later than the real-world action. The demo must distinguish the event's `occurred_at` from its `observed_at`. The 10:00 send is **retrospectively suspicious**, not proof that the system could have known the reply at send time.

## Objective
Given an event log, replay how the system's known state changed and explain which operations occurred after a prospect had replied. Demonstrate an optional protective policy in a controlled synthetic simulation: before sending, query a simulated authoritative provider for replies; block the send if a reply is already visible; otherwise record limits and uncertainty.

## MVP user story
As a customer engineer investigating a campaign, I can choose a sample incident and see:
- A timeline in occurrence order and a timeline in processing/observation order.
- What the automation believed at the time of each decision.
- A clear diagnosis: "The follow-up was sent after a prospect had replied, but before the reply notification was processed. This is consistent with delayed event delivery."
- What checks might reduce repeats, and their limitations.
- A baseline vs guarded simulation of the same incident.

## Model (minimal)
Event: `event_id`, `campaign_id`, `lead_id`, `type`, `occurred_at`, `observed_at`, `metadata`.
Event types for v1: `INITIAL_EMAIL_SENT`, `PROSPECT_REPLIED`, `FOLLOWUP_SENT`.
Sequence state: `ACTIVE` or `STOPPED`. A reply only stops the sequence when observed/processed. Send events are recorded as outcomes, not silently assumed successful.

## Architecture by phase
**Milestone 1 — Python engine, no web app**
- Fixture: `scenarios/delayed_reply.json` with the four timeline facts above (3 recorded events: initial send, reply, follow-up send).
- Pure Python replay function producing processed order, resulting state, and an incident diagnosis.
- Pytest tests: chronological difference, no false positive when reply occurs after follow-up, stable handling of out-of-order events, no change of diagnosis upon file-order reordering, reject invalid/missing timestamps.
- README explaining occurred vs observed timestamps and how to run tests.

**Milestone 2 — API**
- Small FastAPI service exposing `GET /scenarios`, `GET /scenarios/{id}`, `POST /analyze` for arbitrary validated synthetic logs. No real email integrations.

**Milestone 3 — Demo UI**
- Next.js/React/TypeScript interface with scenario selector, two timelines, state-at-send explanation, diagnosis, and baseline/guarded comparison. Show synthetic-data notice.

**Milestone 4 — Engineering credibility**
- Add idempotency/duplicate-delivery scenario and enrichment-timeout scenario only if Milestones 1–3 are solid.
- Demo recording (60–90 seconds), documentation, tests, and tradeoffs.

## Important technical caveats
- Simply replaying an incident does not prevent the original incident; prevention requires additional safeguards.
- Checking the automation database at 10:00 would not detect a reply that has not arrived yet.
- A provider-side check may help but can also be delayed, inaccessible, or subject to rate limits; cannot guarantee exactly-once/zero-unwanted-send behavior.
- Synthetic events are not evidence of Cardinal's actual architecture or incidents.
- No live outreach, no scraping of private systems, no customer data.

## Cursor prompt — Milestone 1
You are helping me implement Milestone 1 of an independent engineering case study called Cardinal Campaign Doctor. Do not build the frontend, API, database, Redis queue, LLM component, integrations, or send actual messages yet.

Set up a minimal Python 3.11+ project with:
1. `src/campaign_doctor/models.py` defining validated event records with event_id, campaign_id, lead_id, event type (INITIAL_EMAIL_SENT, PROSPECT_REPLIED, FOLLOWUP_SENT), occurred_at, observed_at, metadata.
2. `src/campaign_doctor/replay.py` implementing deterministic event replay ordered by observed_at (tie break event_id). A PROSPECT_REPLIED event switches known state ACTIVE -> STOPPED only when observed. A FOLLOWUP_SENT event is an observed send outcome, not a command to execute.
3. `src/campaign_doctor/analysis.py` comparing occurred_at times to flag follow-ups sent after a real reply but before that reply was observed. Distinguish "suspicious after reply" from "confirmed root cause"; avoid causal certainty.
4. `scenarios/delayed_reply.json` with ISO-8601 UTC timestamps: initial email 09:00, reply occurred 09:58 observed 10:02, follow-up sent/observed 10:00.
5. `tests/` with pytest coverage for delayed reply detection, reply after follow-up (not a match), shuffled input order, and malformed timestamps.
6. A CLI command to print both occurrence-order and observation-order timelines plus the diagnosis. Document setup and running the CLI/tests in README.

Keep the code readable with concise comments explaining the business problem. Use standard library where practical and a minimal dependency set. After coding, run tests, show their output, and explain which files you created and why. Do not claim the prototype integrates with Cardinal's actual systems.

## How to explain to a CTO
"I noticed Cardinal's jobs mention debugging campaign behavior and replay tools. I built a small independent simulator of one tricky case: a prospect replied before a follow-up, but the reply notification was processed later. It shows the difference between when an event happened and when the automation knew about it, reconstructs the state at send time, and flags a potentially unwanted follow-up. It's synthetic, but I used it to explore concrete reliability safeguards and their tradeoffs."
