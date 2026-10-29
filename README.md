# Cardinal Campaign Doctor

Independent engineering case study. It replays one synthetic campaign incident, explains a follow-up that went out before a reply notification was processed, and compares that recorded send with a hypothetical pre-send check.

It was built as a small, inspectable proof of work: a deterministic replay engine, a local HTTP API, and an investigation UI. This is not a Cardinal product. It does not connect to Cardinal, a mailbox, or a CRM, and it does not send email.

## Synthetic data

The log is made up. The sample day is 2026-10-27 UTC so the clock times can be real timestamps. Nothing here is a customer incident. The diagnosis is a suspicion about that made-up log. It is not a confirmed production bug.

## Two clocks

Each event has two timestamps.

- `occurred_at` is when the thing happened. The prospect's reply gets this time from the mail provider.
- `observed_at` is when the automation processed the event. A webhook can land later than the reply itself.

| What | Occurred | Observed |
| --- | --- | --- |
| Initial email | 09:00 | 09:00 |
| Prospect reply | 09:58 | 10:02 |
| Follow-up | 10:00 | 10:00 |

In the world, the reply is already there at 10:00. In the automation, the sequence is still `ACTIVE`, because the reply has not been processed. Replay walks observation order and stops the sequence only when the reply is processed. The follow-up row is a send that already happened. Replaying it does not send another one.

The diagnosis calls that follow-up suspicious when the known state at send time is still `ACTIVE`. The timing fits delayed delivery. The log does not name a root cause, and it does not show that the sender could have known about the reply at 10:00.

If an earlier reply was already processed, the known state at send time is `STOPPED`. That send is reported on its own. A later reply can still overlap the send time, and that overlap stays in the report, but it is not used as the explanation for the send.

## Architecture

The Python package owns the rules. The UI renders the JSON those rules already produced.

- `src/campaign_doctor/models.py` validates events and loads a scenario file.
- `src/campaign_doctor/replay.py` rebuilds known state in observation order.
- `src/campaign_doctor/analysis.py` flags a follow-up sent inside the gap between a reply happening and that reply being processed.
- `src/campaign_doctor/safeguards.py` decides a simulated follow-up from known state and a provider check.
- `src/campaign_doctor/api/` serves the engine over HTTP. It does not reimplement replay or safeguards.
- `src/campaign_doctor/cli.py` prints the report and the guarded versus unguarded comparison.
- `scenarios/delayed_reply.json` is the sample log.
- `web/` is the Next.js investigation UI. It calls the API and does not reimplement the diagnosis.
- `tests/` holds the pytest suite.

Ordering is deterministic. Occurrence order sorts by `occurred_at`, then `event_id`. Observation order sorts by `observed_at`, then `event_id`. A follow-up matches the delayed-reply pattern only when `reply.occurred_at < followup.occurred_at < reply.observed_at` for the same campaign and lead, and the known state at send time is still `ACTIVE`.

## Backend

Python 3.11 or newer.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m campaign_doctor scenarios/delayed_reply.json
uvicorn campaign_doctor.api.app:app --reload --port 8000
```

After install, `campaign-doctor scenarios/delayed_reply.json` does the same thing as the module command.

| Method | Path | What it calls |
| --- | --- | --- |
| GET | `/api/health` | A status check. It does not load a scenario. |
| GET | `/api/scenarios` | The allow-list of synthetic files. |
| GET | `/api/scenarios/delayed_reply/report` | Occurrence order, observation order, known state, findings, and sends after a known stop. |
| POST | `/api/scenarios/delayed_reply/compare` | One safeguard comparison. |

The compare body is `{"provider_condition": "reply_visible"}`. The other conditions are `reply_not_yet_visible` and `provider_unavailable`. An unknown scenario id returns 404. A bad body returns 422.

Interactive API docs are at `http://localhost:8000/docs`.

```bash
pytest
```

`tests/cardinal_review_tests.py` and `tests/cardinal_m2_review_tests.py` are part of that run.

## Frontend

The UI is a Next.js app in `web/`. Open it at `http://localhost:3000` while the API is running. With `CORS_ORIGINS` unset, the API allows browser calls from `http://localhost:3000` and `http://127.0.0.1:3000`.

```bash
cd web
npm install
npm run dev
```

`NEXT_PUBLIC_API_BASE_URL` defaults to `http://localhost:8000` during local development and tests. Copy `web/.env.example` to `web/.env.local` if the API lives somewhere else. A production build does not use that default. Set the public API origin before `npm run build`, or the page will say the address is missing instead of calling localhost.

```bash
npm test
npm run build
```

## Run both locally

In one terminal, from the repository root:

```bash
source .venv/bin/activate
uvicorn campaign_doctor.api.app:app --reload --port 8000
```

In another:

```bash
cd web
npm run dev
```

Then open `http://localhost:3000`. The page loads the registered incident, lets you switch the timeline between occurrence order and observation order, and runs the three provider conditions against the compare endpoint.

## Tests

From the repository root, with the dev extra installed:

```bash
pytest
```

That run includes `tests/cardinal_review_tests.py` and `tests/cardinal_m2_review_tests.py`.

From `web/`:

```bash
npm test
npm run build
```

`npm test` checks the API client, the timeline clocks, and the three safeguard conditions, including a late response that must not overwrite a newer choice. `npm run build` is the production frontend compile. It succeeds without `NEXT_PUBLIC_API_BASE_URL`; the resulting bundle will not call localhost until that variable is set and the app is built again.

## Deployment

Nothing in this repository is already deployed. There is no database and no authentication. A public copy is two processes: this API, and the Next.js app. They can sit on different origins. The browser talks to the API directly, so the API's allowed origins must include the site the browser is on.

Install the API without the test extra. `uvicorn` is a runtime dependency.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install .
```

Start it from the repository root so the allow-listed files in `scenarios/` can be found. Do not use `--reload` in production.

```bash
CORS_ORIGINS=https://campaign-doctor.example.com \
  uvicorn campaign_doctor.api.app:app --host 0.0.0.0 --port 8000
```

`CORS_ORIGINS` is a comma-separated list, read when the process starts. Leave it unset on a laptop. The local origins are then `http://localhost:3000` and `http://127.0.0.1:3000`. If you set the variable, those local origins are not added for you, so include `http://localhost:3000` when you still want the local UI. Credentials are not allowed, and an unknown origin is refused. See `.env.example`.

If the process working directory is not the repository, set `SCENARIO_DIR` to the `scenarios` directory. The URL still selects an id from the allow-list. It is never used as a filesystem path. A missing file is the same public 404 as an unknown id: `{"detail":"Unknown scenario."}`.

Unexpected server errors return `{"detail":"The request could not be completed."}`. The response does not include a stack trace or a local path. Validation errors stay 422 and unknown scenarios stay 404.

Build the frontend with the public API origin. Next.js inlines `NEXT_PUBLIC_*` at build time, so changing the variable later does not change an already built bundle.

```bash
cd web
npm ci
NEXT_PUBLIC_API_BASE_URL=https://api.example.com \
  NEXT_PUBLIC_GITHUB_REPO_URL=https://github.com/YOUR_USER/YOUR_REPO \
  npm run build
npm start
```

`npm start` listens on `0.0.0.0` and port `3000`, or the `PORT` environment variable when the host sets one. The footer reads "Built by Dhruv Nakum". The GitHub link appears only when `NEXT_PUBLIC_GITHUB_REPO_URL` is an `https://github.com` URL. That line is a personal attribution. It is not a Cardinal affiliation.

## Known limitations

- The records are synthetic. They are not evidence of Cardinal's architecture or of a real customer incident.
- The safeguard does not guarantee that an unwanted follow-up can never go out.
- A provider index can lag, so a check can allow a follow-up the prospect has already answered. A reply can also arrive after an allow decision and before a real handoff. The simulator does not close that gap.
- `DEFER` postpones one hypothetical send. It is not a permanent block. `ALLOW` and `CANCEL` are hypothetical too. `SENT` is the follow-up already in the log.
- Each compare request builds a new in-memory ledger and drops it with the response. Idempotency is not durable across HTTP requests.
- The in-process lock does not cover another process.
- There is no database and no authentication. This repository does not host the app. A public copy is the two processes described above, and it still only serves the synthetic log.
- `SENT` is the follow-up already in that log. `ALLOW`, `CANCEL`, and `DEFER` are hypothetical decisions about a simulated send. None of them delivers email.
