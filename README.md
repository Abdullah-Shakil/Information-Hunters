# Information Hunters

Control plane and remote workers for finding UK local-service businesses that may need a simple website or CRM automation. Discovery uses the official Companies House API when a key is set, a polite public-page fallback when it is not, and a synthetic catalogue when you just want the product running.

The website does not scrape. It starts, pauses, stops, and reads hunts. A separate worker process claims jobs from the database and keeps running if you close the browser.

## Run locally without Docker

SQLite is the default. Postgres and Compose are optional and documented below.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env

# Terminal 1 — control API
uvicorn information_hunters.api:create_app --factory --host 127.0.0.1 --port 8000

# Terminal 2 — worker (this is the process you would move to a cheap host)
python -m information_hunters.worker

# Terminal 3 — website
cd web
npm install
npm run dev
```

Open http://127.0.0.1:3000. Create a hunt for plumbers in Manchester. The worker writes prioritised leads into SQLite (`information_hunters.db`).

One-shot mode, for a Cloud Run Job or a cron host:

```bash
python -m information_hunters.once
```

HTTP tick mode, for Cloud Scheduler or a function-style host:

```bash
uvicorn information_hunters.http_worker:create_app --factory --host 0.0.0.0 --port 8080
# POST /tick with Authorization: Bearer $WORKER_TOKEN when WORKER_TOKEN is set
```

## Tests

```bash
pytest
```

## Environment

See `.env.example`. Keys stay on the server. The Settings page can store them encrypted with `SECRETS_MASTER_KEY`; the browser only receives whether a key is set and its last four characters.

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | `sqlite:///./information_hunters.db` or `postgresql+psycopg://...` |
| `WORKER_TOKEN` | Optional bearer for a public HTTP `/tick` worker URL |
| `SECRETS_MASTER_KEY` | Encrypts provider keys saved from Settings |
| `DEMO_MODE` | Use the synthetic catalogue when no live provider is selected |
| `COMPANIES_HOUSE_API_KEY` | Official Companies House REST API |
| `GOOGLE_PLACES_API_KEY` | Places text search for trading status, phone, website |
| `SCRAPINGBEE_API_KEY` | Optional fetch proxy for a public business page |
| `APIFY_TOKEN` / `APIFY_ACTOR_ID` | Optional actor for contact enrichment |
| `CONTACT_FETCHER` | `auto`, `direct`, `scrapingbee`, `playwright`, `none` |

Playwright is an optional extra (`pip install -e ".[browser]"` then `playwright install chromium`). The default worker uses HTTP fetching. Playwright is a normal headless browser for public pages, not a way past logins.

## How a hunt runs

1. The website inserts a `jobs` row (`queued`) and the worker claims it.
2. Discovery returns companies for each category and city.
3. Enrichment fills address, SIC, incorporation date, phone, email, and website.
4. Verification drops businesses that are not actively trading.
5. Scoring keeps the rest. No website, a mobile or email, and recent incorporation rank highest.
6. Leads and logs are written to the database. Pause and stop are status flags the worker checks between companies.

`auto` discovery uses Companies House when `COMPANIES_HOUSE_API_KEY` is set, otherwise the demo catalogue if `DEMO_MODE=true`, otherwise the public Companies House search pages (rate limited). `auto` verification uses Google Places when that key is set, otherwise the demo verifier in demo mode, otherwise Companies House `company_status=active` with a note that Google was not used.

## Docker Compose and Postgres

Docker is not required. When you have it:

```bash
docker compose up --build
```

That starts Postgres 16, the API, a worker, and the website on port 3000. The same Python image runs the API and the worker so you can deploy the worker alone.

To point a laptop install at Postgres instead of SQLite:

```bash
export DATABASE_URL=postgresql+psycopg://hunter:hunter@localhost:5432/information_hunters
```

Tables are created on startup (`create_all`). Move to migrations before you treat the database as production.

## Run hunts with your PC off

The desk can stay local. Hunts keep running only when **both** the database and a worker live in the cloud.

1. **Hosted Postgres** — create a free [Neon](https://neon.tech) or [Supabase](https://supabase.com) project. Copy the connection string and use the SQLAlchemy form:
   `postgresql+psycopg://USER:PASS@HOST/DB?sslmode=require`
2. **Point the desk at that DB** — set `DATABASE_URL` in `.env` to the Neon/Supabase URL (not SQLite). Restart the local API. New hunts are written there.
3. **Pick a cloud worker** (one is enough):

| Option | Cost shape | How |
| --- | --- | --- |
| **GitHub Actions** (easiest free) | Free minutes | Push the repo, add Action secrets (`DATABASE_URL`, keys). Workflow `.github/workflows/cloud-worker.yml` runs `python -m information_hunters.once` every 15 minutes. |
| **Fly.io worker** | Small always-on VM | `fly deploy -c deploy/fly.worker.toml` after `fly secrets set DATABASE_URL=...` |
| **Oracle Always Free VM** | Free VM | Install Python, set env, run `python -m information_hunters.worker` under systemd |
| **Cloud Run Job** | Per run | `python -m information_hunters.once` on a schedule |

Optional: deploy the API with `deploy/fly.api.toml` and set `web/.env.development` `API_INTERNAL_URL` to that URL so the desk does not need local uvicorn.

While SQLite stays on your laptop, a cloud worker cannot see your jobs — shared Postgres is required.

## Free and cheap hosts for workers

Workers only need outbound HTTPS and `DATABASE_URL`. Put Postgres on Neon or Supabase free tiers if you want the database off your machine. Run one worker; `SKIP LOCKED` on Postgres lets you add more later.

| Host | Pattern that fits | Always-on | Cold start | Outbound scraping | Notes |
| --- | --- | --- | --- | --- | --- |
| GitHub Actions | `python -m information_hunters.once` | Scheduled | Per run | Full | Free path in `.github/workflows/cloud-worker.yml`. Needs Neon/Supabase `DATABASE_URL`. |
| Oracle Cloud Always Free Ampere VM | `python -m information_hunters.worker` | Yes | None | Full | Best free place for a long-polling worker. |
| Google Cloud Run Jobs | `python -m information_hunters.once` | No | Per job | Full | Runs a queued hunt then exits. Free tier is request/job based, not a 24/7 VM. |
| Google Cloud Run service | `http_worker` `POST /tick` | Only if min instances > 0 (paid) | Yes, if scaled to zero | Full | Pair with Cloud Scheduler. Request timeouts mean one tick should stay under the limit; the job checkpoint resumes. |
| Google Cloud Functions | Same `/tick` idea, one batch | No | Yes | Full, short timeout | Split large hunts. Checkpointing is already in the job row. |
| Cloudflare Workers | Thin ping only | Edge | Very fast | Poor fit | No Playwright, tight CPU, awkward long Postgres sessions. Do not run scraping here. A Worker can call your tick URL. |
| Fly.io | Polling worker (`deploy/fly.worker.toml`) | Paid/allowance | None if always-on | Full | Free machines often sleep; use a paid always-on machine or the GitHub Actions schedule. |
| Neon or Supabase | Database only | Hosted | Connection cold starts | n/a | Required shared store so a cloud worker can claim jobs your desk queued. |

Rate limits: Companies House public data API is commonly 600 requests per 5 minutes. The client defaults to 2 requests per second. Public HTML search is slower on purpose (about one request every 2 seconds) and sends an identifying User-Agent. Prefer the API.

## Providers

Discovery, verification, and page fetch are separate interfaces in `information_hunters/providers`. Swap them per hunt in the form.

- **Companies House API** — name, number, status, address, SIC, incorporation date. It does not provide phone, email, or website.
- **Companies House public search** — BeautifulSoup fallback for the same registry fields when you have no API key.
- **Google Places** — trading status, phone, and website URI. Official API only. The worker does not scrape Google.
- **Direct / ScrapingBee / Playwright** — fetch a public `http(s)` page (usually the business's own site) and read a visible email or phone. LinkedIn, other social logins, `file://`, and private IP ranges are refused.
- **Apify** — runs the actor id you configure and maps `email`, `phone`, `mobile`, and `website` from the dataset. No actor is hardcoded.

## Website

Next.js is a local control plane for starting, pausing, and reading hunts, and for directing cloud workers. There is no login — the desk is meant to stay on your machine. Server routes proxy to the Python API with no token. Leads can be filtered and exported to CSV. Do-not-contact is stored on the lead and omitted from the default export.

Keep the API on localhost (or behind your own network) — it is open by design for the local desk.

## Compliance notes (UK GDPR and PECR)

This is operational hygiene, not legal advice.

- Companies House data is public, but a sole trader, partner, or director identified in a lead is still a person. Limited companies are a different case from individuals.
- PECR is stricter for individuals (including many sole traders and some partnerships) than for corporate bodies. Unsolicited marketing email to an individual generally needs consent. A `gmail.com` address on a plumbing lead is often a person, even when the company is limited.
- Do not call numbers from this tool until they have been screened against the TPS and CTPS. This product does not do that screening.
- Before any outreach, decide the lawful basis, identify who you are, and include a working opt-out. Use the in-app **Do not contact** flag and honour it. The CSV export skips those leads unless you explicitly include them.
- Keep the lead database access-controlled, collect only what you need, and delete records you no longer use.
- The demo catalogue uses reserved `.example` domains and Ofcom drama telephone ranges. Those records are synthetic and labelled. Do not treat them as real businesses.

## Layout

```
information_hunters/    Python API, worker, scoring, providers
web/                    Next.js control plane
docker-compose.yml      Postgres + api + worker + web
tests/                  Priority scoring and API routes
```
