# Information Hunters

Control plane and remote workers for finding UK local-service businesses that may need a simple website or CRM automation. Discovery uses the official Companies House API when a key is set, a polite public-page fallback when it is not, and a synthetic catalogue when you just want the product running.

The website does not scrape. It stores keys, starts and stops cloud hosts, and reads leads, live activity, and performance. A worker process — on your laptop, or on a free host you started from the Hosts page — claims jobs from the database and keeps running if you close the browser.

## Run locally without Docker

SQLite is the default. Supabase Postgres is the hosted database. Compose is optional.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env

# Terminal 1 — control API
uvicorn information_hunters.api:create_app --factory --host 127.0.0.1 --port 8000

# Terminal 2 — worker (the same process a cloud host runs)
python -m information_hunters.worker

# Terminal 3 — website
cd web
npm install
npm run dev
```

Open http://127.0.0.1:3000 and sign in with the demo password `hunter-demo`. Create a hunt for plumbers in Manchester. The worker writes prioritised leads into SQLite (`information_hunters.db`). Demo mode needs no API keys.

One-shot mode, for a Cloud Run Job or a cron host:

```bash
python -m information_hunters.once
```

HTTP tick mode, for a platform that can only wake an HTTP service:

```bash
uvicorn information_hunters.http_worker:create_app --factory --host 0.0.0.0 --port 8080
# POST /tick with Authorization: Bearer $WORKER_TOKEN (falls back to INTERNAL_API_TOKEN)
```

## Tests

```bash
pytest
```

## Environment

See `.env.example`. Keys saved in the website are encrypted with `SECRETS_MASTER_KEY` and are never returned in full. Do not commit `.env`.

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | `sqlite:///./information_hunters.db` or a Postgres URI |
| `SUPABASE_DB_URL` | Supabase Postgres URI. When set, this is the database for the API and workers. `postgresql://` is rewritten to `postgresql+psycopg://`, and `sslmode=require` is added for Supabase hosts. |
| `SUPABASE_URL` | `https://<project>.supabase.co`. Used by the Settings “Test connection” button. Not required for workers. |
| `SUPABASE_SERVICE_ROLE_KEY` | Server-only key for that connection test. Never put it in the browser. The anon key is not used. |
| `INTERNAL_API_TOKEN` | Shared secret between the Next.js server and the Python API |
| `DEMO_PASSWORD` / `AUTH_SECRET` | Password gate for the website |
| `DEMO_MODE` | Synthetic catalogue when no live provider is selected |
| `SECRETS_MASTER_KEY` | Encrypts keys saved from the website. Every worker that should read those keys needs the same value. |
| `HOST_ID` | Optional label on activity and performance rows (`oracle_cloud`, `github_actions`, `apify`, …) |
| `COMPANIES_HOUSE_API_KEY` | Official Companies House REST API |
| `GOOGLE_PLACES_API_KEY` | Places text search for trading status, phone, website |
| `SCRAPINGBEE_API_KEY` | Optional fetch proxy. Free plan: 1,000 credits. |
| `BRIGHTDATA_API_TOKEN` / `BRIGHTDATA_ZONE` | Optional paid Bright Data fetch. Not a free tier. |
| `APIFY_TOKEN` / `APIFY_ACTOR_ID` | Free-plan actor host and optional contact enrichment |
| `CONTACT_FETCHER` | `auto`, `direct`, `scrapingbee`, `brightdata`, `playwright`, `none` |

Playwright is an optional extra (`pip install -e ".[browser]"` then `playwright install chromium`). `pip install playwright-stealth` is picked up automatically when it is installed; the fetch still works without it. Playwright is a normal headless browser for public pages, not a way past logins.

Cloud workers do not need each provider key in their environment if they share `SUPABASE_DB_URL` and `SECRETS_MASTER_KEY` with the website. Keys pasted into Hosts or Settings are decrypted from the database.

## Supabase

Free plan (confirm on [supabase.com/pricing](https://supabase.com/pricing)): 500 MB database per project, 5 GB egress and 5 GB cached egress, two active projects, and the project pauses after a week with no activity. Paused projects are restored from the dashboard. There is no downloadable backup on the free plan.

1. Create a free project.
2. Open the SQL editor and run `migrations/001_supabase.sql`. That creates leads, hunts, encrypted secrets, hosts, run metrics, errors, and activity, and enables row level security with no anon access.
3. In Project Settings → Database, copy the **session pooler** URI (port 5432). Put it in `SUPABASE_DB_URL` on the API and on every worker. Use the session pooler rather than the transaction pooler (port 6543). If you do use port 6543, the app disables prepared statements for that host.
4. Put `SUPABASE_URL` and the **service role** key in the API environment only. They are not stored in the database, because the app cannot open Supabase by reading a password from Supabase.

SQLite remains the default when `SUPABASE_DB_URL` is empty, including tests.

## How a hunt runs

1. The website inserts a `jobs` row (`queued`) and a worker claims it.
2. Discovery returns companies for each category and city. An activity row is written, for example “Searching Companies House for plumbers in Leeds”.
3. Enrichment fills address, SIC, incorporation date, phone, email, and website.
4. Verification drops businesses that are not actively trading.
5. Scoring keeps the rest. No website, a mobile or email, and recent incorporation rank highest. A “found” activity row includes the email, mobile, and whether there is a website.
6. A `run_metrics` row records companies searched, leads, email, mobile, no website, success rate, and duration. Failures go to `error_events`.
7. Pause and stop are status flags the worker checks between companies.

`auto` discovery uses Companies House when `COMPANIES_HOUSE_API_KEY` is set, otherwise the demo catalogue if `DEMO_MODE=true`, otherwise the public Companies House search pages (rate limited). `auto` verification uses Google Places when that key is set, otherwise the demo verifier in demo mode, otherwise Companies House `company_status=active` with a note that Google was not used.

## Docker Compose and Postgres

Docker is not required. When you have it:

```bash
docker compose up --build
```

That starts Postgres 16, the API, a worker, and the website on port 3000. `docker/worker.Dockerfile` is the image cloud hosts run; its command is the polling worker. Cloud Run should override the command to `python -m information_hunters.once`.

## Free hosts and providers

Only services with a real free tier (or free credits) are wired up. Start and Stop call that provider’s API. If the provider reports that the free allowance is gone, the host is marked **quota exhausted** and the API does not crash. Where a product cannot be started by an API, it is listed as left out and the UI says so. There is no fake start button.

Limits below are the public allowances as of September 2026. Check the provider’s pricing page before you depend on them; free tiers change.

| Service | Role | Free limits | Keys to paste | Where to get them | Start / Stop |
| --- | --- | --- | --- | --- | --- |
| Oracle Cloud Always Free | Always-on VM worker | Ampere A1 up to 2 OCPUs and 12 GB (reduced from 4 OCPU / 24 GB in June 2026), plus AMD micro instances (1/8 OCPU, 1 GB). Capacity errors are common. | Tenancy OCID, user OCID, fingerprint, API private key, region, instance OCID | [OCI API keys](https://cloud.oracle.com/identity/domains/my-profile/api-keys) | Yes. InstanceAction START and STOP. |
| GitHub Actions | Scheduled-style worker in a repo | 2,000 minutes/month on private repos. Public repo minutes are free. One job ends after 6 hours. | Personal access token (repo + workflow, or Actions read/write), owner, repo. Workflow file defaults to `hunt.yml`, ref `main`. | [github.com/settings/tokens](https://github.com/settings/tokens) | Yes. `workflow_dispatch` and cancel run. |
| Google Cloud Run Jobs + Cloud Scheduler | Job that Google re-launches | Jobs: 240,000 vCPU-seconds and 450,000 GiB-seconds / month in a US region such as `us-central1`. Scheduler: 3 jobs per billing account, free no matter how often they fire. | Service account JSON, project id, region, job name, scheduler id | [Service accounts](https://console.cloud.google.com/iam-admin/serviceaccounts) | Yes. Runs the job, creates/resumes the scheduler, pause + cancel on Stop. |
| Apify | Actor that polls, plus hourly restart | $5 platform credits / month. No card. Unused credit expires. The free plan is blocked when the credit is gone. | API token, actor id (`username~name`) | [Apify integrations](https://console.apify.com/account/integrations) | Yes. Starts the run, enables a schedule, abort + disable on Stop. |
| Koyeb | Pausable web service | One free instance: 0.1 vCPU, 512 MB, 2 GB disk, Frankfurt or Washington. It cannot be a worker, and it sleeps after 1 hour with no HTTP traffic. | API token, service id | [Koyeb API tokens](https://app.koyeb.com/account/api) | Yes, pause and resume. It does not keep scraping while asleep. |
| Render | Pausable web service | Free web services: 750 instance hours / month, then they are suspended. They sleep after 15 minutes with no inbound traffic. Background workers are paid. | API key, service id (`srv-…`) | [Render API keys](https://dashboard.render.com/u/settings#api-keys) | Yes, suspend and resume. A spun-down service is not scraping. |
| ScrapingBee | Page fetch credits | 1,000 API credits, no card. Not a machine. | API key | [app.scrapingbee.com](https://app.scrapingbee.com/) | No. Test connection shows credits. Exhausted credits mark the card quota exhausted and the hunt continues. |
| Companies House API | Discovery | Free. About 600 requests per 5 minutes. The client defaults to 2 requests/second. | API key | [developer.company-information.service.gov.uk](https://developer.company-information.service.gov.uk/) | Not a host. The worker calls it. |
| Companies House public pages | Discovery fallback | Free. BeautifulSoup, about one request every 2 seconds, identifying User-Agent. | None | — | Library. No start button. |
| Google Places | Trading status, phone, website | Billed against the monthly Maps Platform credit. Confirm the current credit on Google’s pricing page. Not unlimited. | API key | Google Cloud console, Places API (New) | Not a host. The test uses one small text search. |
| BeautifulSoup4 | HTML parsing | Free library. No account. | None | Installed with this package | No API to start. |
| Playwright (+ optional stealth) | Public-page browser | Free library. Does not log in or evade access controls beyond a normal browser. | None | `pip install -e ".[browser]"` and `playwright-stealth` | No API to start. |
| Supabase | Database | 500 MB, 5 GB egress, pauses after 7 idle days, 2 projects | Env vars, not the Hosts form | [supabase.com](https://supabase.com/) | Not a worker. |

### Left out

| Service | Why there is no adapter |
| --- | --- |
| Fly.io | No free tier for new accounts. Pay-as-you-go, card required. Legacy free VMs are not available to a new signup. |
| Hugging Face Spaces | CPU Basic has no hourly price, but creating a Docker or Gradio Space now requires a paid plan. Static Spaces cannot run this worker. ZeroGPU is for model demos. |
| Expandi | Paid LinkedIn outreach product. No free plan that runs this worker. “Deipify/Expandi” in the brief was treated as Apify (included) and Expandi (left out). |
| Bright Data | No standing free tier (trial credit only). The optional paid fetcher remains on Settings. |
| Render background worker | Not on the free plan. The free web service is the Render row above. |
| Cloudflare Workers | Cannot run this Python scraper (short CPU, no Playwright, poor fit for a long Postgres session). |

### One-time setup the owner still does

The repo ships the worker image, the GitHub workflow, the Apify actor file, the Oracle systemd unit, and the Supabase SQL. You still create the free accounts.

**Oracle (best always-on free option)**

1. Create an Always Free VM. An AMD micro is easier to obtain than Ampere. If START returns “out of host capacity”, the Hosts page marks quota exhausted.
2. Clone this repo to `/opt/information-hunters`, create a venv, and `pip install .`.
3. Write `/etc/information-hunters.env` with `DATABASE_URL` (Supabase URI) and `SECRETS_MASTER_KEY` (same value as the website). Do not commit that file.
4. `sudo cp deploy/oracle/information-hunters.service /etc/systemd/system/ && sudo systemctl enable --now information-hunters`.
5. On the Hosts page, paste the API key PEM and OCIDs, Test, then Start or Stop. Those buttons power the VM. systemd starts the worker when the VM is on.

**GitHub Actions**

1. Push this repo (the workflow is `.github/workflows/hunt.yml` and only runs on `workflow_dispatch`).
2. Repository secrets: `DATABASE_URL` (required), `SECRETS_MASTER_KEY` (so website-saved keys decrypt). Provider keys as secrets are optional if they already live in Supabase.
3. Paste a token, owner, and repo on the Hosts page. Start dispatches the workflow. Stop cancels it. A single run lasts at most 6 hours; press Start again the next time. Public repositories do not spend the 2,000 private minutes.

**Google Cloud Run**

1. Enable Cloud Run and Cloud Scheduler. Create a service account with Cloud Run Admin and Cloud Scheduler Admin, and download JSON.
2. Build `docker/worker.Dockerfile` once and create the job. Create an Artifact Registry repo named `hunters` first if you do not have one. Use a US region or the Cloud Run free tier does not apply. Cloud Build has its own monthly free tier; if that is exhausted, build the image on any machine and push it.

```bash
gcloud builds submit --config deploy/gcp/cloudbuild.yaml \
  --substitutions _IMAGE=us-central1-docker.pkg.dev/PROJECT/hunters/worker:latest
gcloud run jobs create information-hunters \
  --image us-central1-docker.pkg.dev/PROJECT/hunters/worker:latest \
  --region us-central1 \
  --command python \
  --args=-m,information_hunters.once \
  --set-env-vars DATABASE_URL="postgresql+psycopg://…",SECRETS_MASTER_KEY="…",HOST_ID=gcp_cloud_run,DEMO_MODE=false
```

3. Paste the JSON, project id, and region. Start runs the job and creates a scheduler called `information-hunters-tick` (every 15 minutes) if you still have a free scheduler slot. Stop pauses that scheduler and cancels the execution. Google does not expose remaining free vCPU-seconds; quota is detected when the API says the quota is exhausted.

**Apify**

1. `apify push` from this repo (`.actor/actor.json` points at the worker image), or create an actor in the console from the same Dockerfile.
2. On the actor, set `DATABASE_URL`, `SECRETS_MASTER_KEY`, and `HOST_ID=apify`.
3. Paste the token and actor id. Start launches a run and an hourly exclusive schedule. Stop aborts the run and disables the schedule. The $5 credit is checked before a start.

**Koyeb and Render**

Create the free **web** service yourself (their free tiers cannot be a background worker). Set `DATABASE_URL` and `SECRETS_MASTER_KEY` on that service. Paste the token and service id. Start and Stop call pause/resume or suspend/resume. Read the limits on the card: both sleep when idle, so they are a poor fit for a hunt that must continue with no incoming HTTP traffic. Prefer Oracle, GitHub Actions, or Cloud Run for that.

**ScrapingBee, Companies House, Places**

No deploy step. Save the key on Settings (ScrapingBee, Companies House, Places) or Hosts (ScrapingBee) and press Test connection.

## Providers

Discovery, verification, and page fetch are separate interfaces in `information_hunters/providers`. Swap them per hunt in the form.

- **Companies House API** — name, number, status, address, SIC, incorporation date. It does not provide phone, email, or website.
- **Companies House public search** — BeautifulSoup fallback for the same registry fields when you have no API key.
- **Google Places** — trading status, phone, and website URI. Official API only. The worker does not scrape Google.
- **Direct / ScrapingBee / Bright Data / Playwright** — fetch a public `http(s)` page (usually the business's own site) and read a visible email or phone. LinkedIn, other social logins, `file://`, and private IP ranges are refused.
- **Apify** — runs the actor id you configure and maps `email`, `phone`, `mobile`, and `website` from the dataset. The same token can also host the worker. No actor is hardcoded.

## Website

Next.js is a password-gated control plane. The session cookie stays on the Next.js origin. Server routes proxy to the Python API with `INTERNAL_API_TOKEN`.

- **Hosts** — paste each provider’s keys and ids, test the connection, Start, and Stop. Secrets are masked (last four characters only).
- **Live Activity** — polls every few seconds. Searching and found leads, including email and mobile, are stored in the database.
- **Performance** — per run and per host: companies searched, leads, email, mobile, no website, success rate, duration, and every error. Filters sit above the tables. Bars show leads by host.
- **Leads** — filter and export CSV. Do-not-contact is stored on the lead and omitted from the default export.
- **Settings** — Companies House, Places, ScrapingBee, and optional Bright Data, plus the Supabase connection test.

Change `DEMO_PASSWORD`, `AUTH_SECRET`, and `INTERNAL_API_TOKEN` before anyone else can reach the service. Set `NEXT_PUBLIC_DEMO_HINT=false` outside a local demo. Set `COOKIE_SECURE=true` behind HTTPS.

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
information_hunters/    Python API, worker, scoring, providers, host adapters
migrations/001_supabase.sql
web/                    Next.js control plane (hosts, activity, performance)
docker/worker.Dockerfile
.github/workflows/hunt.yml
deploy/oracle/          systemd unit for an Always Free VM
.actor/actor.json       Apify actor manifest
tests/                  Scoring, API, host adapters, Supabase URL, activity
```
