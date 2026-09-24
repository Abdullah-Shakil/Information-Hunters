"""Free hosts and credit providers the desk can show. Limits are the public free allowances as of September 2026."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FieldSpec:
    name: str
    label: str
    hint: str
    secret: bool = False
    required: bool = True
    default: str = ""
    multiline: bool = False


@dataclass(frozen=True)
class ProviderSpec:
    id: str
    name: str
    kind: str
    controllable: bool
    free_limits: str
    summary: str
    setup_hint: str
    setup_url: str
    manual_setup: str
    keeps_running: str
    fields: tuple[FieldSpec, ...] = ()
    uncontrolled_reason: str = ""


@dataclass(frozen=True)
class ExcludedSpec:
    id: str
    name: str
    reason: str


def _f(name: str, label: str, hint: str, *, secret: bool = False, required: bool = True, default: str = "", multiline: bool = False) -> FieldSpec:
    return FieldSpec(name, label, hint, secret, required, default, multiline)


CATALOG: tuple[ProviderSpec, ...] = (
    ProviderSpec(
        id="github_actions",
        name="GitHub Actions",
        kind="host",
        controllable=True,
        free_limits="2,000 minutes/month on private repositories. Minutes for public repositories are free. One job run stops after 6 hours.",
        summary="Start dispatches the hunt workflow in your repository. Stop cancels that run. The workflow file is already in this repo.",
        setup_hint="Create a personal access token that can dispatch and cancel Actions on the repository that contains this project.",
        setup_url="https://github.com/settings/tokens",
        manual_setup="Once: put this repo on GitHub, add a DATABASE_URL secret (your Supabase connection string) and the same SECRETS_MASTER_KEY the website uses. The workflow is .github/workflows/hunt.yml and only runs when you press Start.",
        keeps_running="After Start, the worker keeps polling until you press Stop, GitHub's 6-hour job limit, or the free minutes run out. It does not schedule itself the next day.",
        fields=(
            _f("GITHUB_TOKEN", "Personal access token", "Classic: repo and workflow. Fine-grained: Actions read and write.", secret=True),
            _f("GITHUB_OWNER", "Repository owner", "The user or organisation that owns the repo, not the full URL."),
            _f("GITHUB_REPO", "Repository name", "The repo name only, for example information-hunters."),
            _f("GITHUB_WORKFLOW", "Workflow file", "Shipped as hunt.yml. Change this only if you renamed the file.", default="hunt.yml"),
            _f("GITHUB_REF", "Git ref", "Branch the workflow runs on. The file must exist on that branch.", default="main"),
        ),
    ),
    ProviderSpec(
        id="gcp_cloud_run",
        name="Google Cloud Run Jobs",
        kind="host",
        controllable=True,
        free_limits="Cloud Run jobs: 240,000 vCPU-seconds and 450,000 GiB-seconds per month (US regions such as us-central1). Cloud Scheduler: 3 jobs per billing account, free regardless of how often they fire.",
        summary="Start launches the Cloud Run job and resumes a Scheduler job so hunts keep being queued. Stop pauses the scheduler and cancels the current execution.",
        setup_hint="Download a service account JSON key. An API key cannot call the Cloud Run Admin API.",
        setup_url="https://console.cloud.google.com/iam-admin/serviceaccounts",
        manual_setup="Once: create a GCP project, enable Cloud Run and Cloud Scheduler, deploy the worker image as a job named information-hunters (commands are in the README), and grant the service account Cloud Run Admin and Cloud Scheduler Admin.",
        keeps_running="With the scheduler job in place, Google keeps starting hunts while your laptop is off, until the free vCPU-seconds run out or you press Stop.",
        fields=(
            _f("GCP_SERVICE_ACCOUNT_JSON", "Service account JSON", "The whole JSON key file. It is stored encrypted and never sent back.", secret=True, multiline=True),
            _f("GCP_PROJECT_ID", "Project id", "The GCP project id, not the project number."),
            _f("GCP_REGION", "Region", "Use a US free-tier region. us-central1 is the usual choice.", default="us-central1"),
            _f("GCP_JOB_NAME", "Cloud Run job name", "Must match the job you deployed once.", default="information-hunters"),
            _f("GCP_SCHEDULER_JOB", "Scheduler job id", "Created for you if it does not exist. The free allowance is 3 scheduler jobs per billing account.", default="information-hunters-tick"),
        ),
    ),
    ProviderSpec(
        id="oracle_cloud",
        name="Oracle Cloud Always Free",
        kind="host",
        controllable=True,
        free_limits="Always Free VM: Ampere A1 up to 2 OCPUs and 12 GB RAM (cut from 4 OCPU / 24 GB in June 2026) plus AMD micro instances (1/8 OCPU, 1 GB). Capacity is often unavailable; that is reported as quota exhausted, not a crash.",
        summary="Start and Stop call the Compute InstanceAction API. The VM's systemd unit runs the worker whenever the instance is on.",
        setup_hint="Add an API key on your OCI user and paste the private key plus the OCIDs shown on that page.",
        setup_url="https://cloud.oracle.com/identity/domains/my-profile/api-keys",
        manual_setup="Once: create an Always Free VM (an AMD micro is easier to get than Ampere), clone this repo, and install deploy/oracle/information-hunters.service. Put DATABASE_URL and SECRETS_MASTER_KEY in /etc/information-hunters.env.",
        keeps_running="While the instance is RUNNING, the worker polls on its own. Stop powers the VM off. Out of host capacity does not keep retrying.",
        fields=(
            _f("OCI_TENANCY_OCID", "Tenancy OCID", "Starts with ocid1.tenancy. Shown on the tenancy details page."),
            _f("OCI_USER_OCID", "User OCID", "Starts with ocid1.user. The user that owns the API key."),
            _f("OCI_FINGERPRINT", "API key fingerprint", "Shown next to the API key you added. A colon-separated hash."),
            _f("OCI_PRIVATE_KEY", "API private key (PEM)", "The PEM you downloaded when you added the API key. Stored encrypted.", secret=True, multiline=True),
            _f("OCI_REGION", "Region", "Example: uk-london-1. Must be the region of the instance.", default="uk-london-1"),
            _f("OCI_INSTANCE_OCID", "Instance OCID", "Starts with ocid1.instance. The Always Free VM you created once."),
        ),
    ),
    ProviderSpec(
        id="apify",
        name="Apify",
        kind="host",
        controllable=True,
        free_limits="$5 of platform credits per month on the free plan. No card. Unused credit expires. When it is gone, Apify blocks runs until the next month.",
        summary="Start launches your actor and an hourly schedule. Stop aborts the run and disables the schedule. The same token can enrich contacts during a hunt.",
        setup_hint="Copy the API token from Apify integrations. Create the actor once with the Apify CLI from this repo (apify push) or point this at an actor you already built.",
        setup_url="https://console.apify.com/account/integrations",
        manual_setup="Once: on the actor, set DATABASE_URL to Supabase, SECRETS_MASTER_KEY to the same value as the website, and HOST_ID=apify. The image command is the polling worker.",
        keeps_running="The actor keeps polling until you press Stop or the $5 credit is used up. The hourly schedule starts it again if Apify ends the run.",
        fields=(
            _f("APIFY_TOKEN", "API token", "console.apify.com/account/integrations", secret=True),
            _f("APIFY_ACTOR_ID", "Actor id", "username~actor-name or the actor id from the Apify console.", secret=True),
        ),
    ),
    ProviderSpec(
        id="koyeb",
        name="Koyeb",
        kind="host",
        controllable=True,
        free_limits="One free web instance per organisation: 0.1 vCPU, 512 MB RAM, 2 GB disk, Frankfurt or Washington. It cannot be a worker service, and it scales to zero after 1 hour without inbound HTTP traffic.",
        summary="Start resumes the service. Stop pauses it. Both calls are real Koyeb API calls.",
        setup_hint="Create an API token, deploy this repo's web/worker image as a web service once, and paste that service id.",
        setup_url="https://app.koyeb.com/account/api",
        manual_setup="Once: create the free web service yourself (the API token cannot invent the free instance type reliably). Point it at docker/worker.Dockerfile only if you accept that it will sleep. A sleeping service is not searching.",
        keeps_running="It does not keep scraping while asleep. Use Oracle, GitHub Actions, or Cloud Run if the hunt must continue with your laptop off.",
        fields=(
            _f("KOYEB_API_TOKEN", "API token", "Account settings → API.", secret=True),
            _f("KOYEB_SERVICE_ID", "Service id", "The id of the free web service, from the service page URL or the API."),
        ),
    ),
    ProviderSpec(
        id="render",
        name="Render",
        kind="host",
        controllable=True,
        free_limits="Free web services: 750 instance hours per workspace per month, then Render suspends them. They spin down after 15 minutes without inbound traffic. Free background workers are not offered. Outbound bandwidth and build minutes have their own included amounts.",
        summary="Start resumes a suspended service. Stop suspends it. Render's API does both.",
        setup_hint="Create an API key, then a free web service from this repo, and paste the service id (srv-…).",
        setup_url="https://dashboard.render.com/u/settings#api-keys",
        manual_setup="Once: create the free web service in the dashboard and set DATABASE_URL plus SECRETS_MASTER_KEY. The suspend/resume buttons on this page call the API after that.",
        keeps_running="A free web service that has spun down is not scraping. 750 hours is the monthly ceiling. Prefer Oracle or Cloud Run for a hunt that should continue unattended.",
        fields=(
            _f("RENDER_API_KEY", "API key", "Account settings → API keys.", secret=True),
            _f("RENDER_SERVICE_ID", "Service id", "Starts with srv-. On the service page in the Render dashboard."),
        ),
    ),
    ProviderSpec(
        id="scrapingbee",
        name="ScrapingBee",
        kind="scraper",
        controllable=False,
        free_limits="1,000 API credits on the free plan, no card. A plain HTML request is 1 credit. JavaScript rendering costs more. This is not a host.",
        summary="The worker calls ScrapingBee while a host is running, to read a public business page. Test connection shows credits used.",
        setup_hint="Create a free account and copy the API key from the dashboard.",
        setup_url="https://app.scrapingbee.com/",
        manual_setup="No deploy step. Save the key, then choose ScrapingBee as the contact fetcher on a hunt. When the credits are gone the host card is marked quota exhausted and the hunt continues without that fetch.",
        keeps_running="There is nothing to start. Credits are spent by whichever cloud worker is already running.",
        uncontrolled_reason="ScrapingBee is a fetch API. It cannot start or stop a worker. The Test connection button checks the key and the remaining free credits.",
        fields=(_f("SCRAPINGBEE_API_KEY", "API key", "Dashboard → API key. 1,000 free credits.", secret=True),),
    ),
    ProviderSpec(
        id="libraries",
        name="BeautifulSoup and Playwright",
        kind="library",
        controllable=False,
        free_limits="No account and no meter. BeautifulSoup reads public Companies House HTML. Playwright is an optional local browser; playwright-stealth is used when that package is installed. Neither bypasses logins.",
        summary="These run inside the host you started. They are free because they are libraries, not services.",
        setup_hint="Nothing to paste. Playwright is optional: pip install -e \".[browser]\" && playwright install chromium && pip install playwright-stealth.",
        setup_url="https://github.com/beautifulsoup4/beautifulsoup",
        manual_setup="On a cloud image that should use Playwright, install the browser extra and Chromium into that image. The default worker uses HTTP and BeautifulSoup and does not need a browser.",
        keeps_running="They run only while a host process is running.",
        uncontrolled_reason="There is no provider API to start or stop a Python library. Start a host instead. The public Companies House fallback and direct page fetch already use these libraries.",
        fields=(),
    ),
)

EXCLUDED: tuple[ExcludedSpec, ...] = (
    ExcludedSpec(
        id="fly",
        name="Fly.io",
        reason="No free tier for new accounts. Fly.io is pay-as-you-go and asks for a card. Older accounts may still have a legacy allowance; that is not something a new signup can use, so there is no adapter.",
    ),
    ExcludedSpec(
        id="huggingface",
        name="Hugging Face Spaces",
        reason="CPU Basic hardware has no hourly price, but creating a Docker or Gradio Space (the only Spaces that could run this worker) requires a paid plan. Static Spaces are free and cannot run the worker. ZeroGPU is for model demos. Left out rather than pretending a free Space can host it.",
    ),
    ExcludedSpec(
        id="expandi",
        name="Expandi",
        reason="Paid LinkedIn outreach product. There is no free plan that searches Companies House or runs this worker. The name in the brief was treated as Expandi (and Apify, which is included above).",
    ),
    ExcludedSpec(
        id="brightdata",
        name="Bright Data",
        reason="No standing free tier. Trial credit is not an always-free allowance, so it is not a host. The optional paid fetcher is still on the Settings page if you already have a token.",
    ),
    ExcludedSpec(
        id="render_worker",
        name="Render background worker",
        reason="Free Render covers web services, static sites, and limited Postgres. A background worker needs a paid instance. The free web service is the Render card above, with the sleep and 750-hour limits written on it.",
    ),
    ExcludedSpec(
        id="cloudflare",
        name="Cloudflare Workers",
        reason="The free plan cannot run this Python worker (no Playwright, short CPU, no long database session). A Worker could ping a tick URL, but that would be a second hop, not a host. Not given a start button.",
    ),
)


def get_spec(provider: str) -> ProviderSpec | None:
    return next((item for item in CATALOG if item.id == provider), None)
