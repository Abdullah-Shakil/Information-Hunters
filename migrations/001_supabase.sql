-- Information Hunters schema for Supabase Postgres.
-- Run this once in the Supabase SQL editor (Dashboard → SQL).
-- The API also calls create_all on startup, which creates any missing tables.
-- This file is the one that turns on row level security.
--
-- Workers connect with the Postgres URI (session pooler, port 5432), not the anon key.
-- The service role bypasses RLS. The anon and authenticated roles have no policies, so they cannot read leads.

create table if not exists public.leads (
  id varchar(36) primary key,
  company_number varchar(32) not null unique,
  name varchar(300) not null,
  location varchar(120) not null default '',
  address text not null default '',
  postcode varchar(16) not null default '',
  category varchar(64) not null default '',
  sic_codes jsonb not null default '[]'::jsonb,
  sic_labels jsonb not null default '[]'::jsonb,
  phone varchar(40),
  mobile varchar(40),
  email varchar(200),
  website varchar(400),
  has_website boolean not null default false,
  incorporation_date date,
  company_status varchar(32) not null default 'active',
  trading_status varchar(32) not null default 'verified_active',
  priority_score integer not null default 0,
  priority_band varchar(2) not null default 'D',
  priority_reasons jsonb not null default '[]'::jsonb,
  sources jsonb not null default '[]'::jsonb,
  verification_notes text not null default '',
  do_not_contact boolean not null default false,
  synthetic boolean not null default false,
  job_id varchar(36),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.jobs (
  id varchar(36) primary key,
  name varchar(200) not null,
  categories jsonb not null default '[]'::jsonb,
  regions jsonb not null default '[]'::jsonb,
  status varchar(24) not null default 'queued',
  stage varchar(200) not null default 'Queued',
  progress integer not null default 0,
  limit_per_search integer not null default 8,
  discovery_provider varchar(40) not null default 'auto',
  verification_provider varchar(40) not null default 'auto',
  contact_fetcher varchar(40) not null default 'auto',
  incorporated_after date,
  discovered_count integer not null default 0,
  qualified_count integer not null default 0,
  rejected_count integer not null default 0,
  checkpoint jsonb,
  error text,
  worker_id varchar(120),
  created_at timestamptz not null default now(),
  started_at timestamptz,
  finished_at timestamptz,
  heartbeat_at timestamptz
);

create table if not exists public.job_logs (
  id varchar(36) primary key,
  job_id varchar(36) not null,
  level varchar(16) not null default 'info',
  message text not null,
  created_at timestamptz not null default now()
);

create table if not exists public.workers (
  id varchar(120) primary key,
  hostname varchar(200) not null default '',
  last_seen timestamptz not null default now(),
  current_job_id varchar(36)
);

create table if not exists public.secrets (
  name varchar(80) primary key,
  ciphertext text not null,
  updated_at timestamptz not null default now()
);

create table if not exists public.hosts (
  id varchar(36) primary key,
  provider varchar(40) not null unique,
  name varchar(120) not null default '',
  status varchar(32) not null default 'stopped',
  remote_id varchar(400),
  config jsonb not null default '{}'::jsonb,
  status_detail text not null default '',
  usage jsonb,
  last_error text,
  controllable boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  started_at timestamptz,
  stopped_at timestamptz,
  checked_at timestamptz
);

create table if not exists public.run_metrics (
  id varchar(36) primary key,
  job_id varchar(36) not null,
  host_provider varchar(40) not null default '',
  worker_id varchar(120) not null default '',
  discovery_provider varchar(40) not null default '',
  companies_searched integer not null default 0,
  leads_found integer not null default 0,
  leads_with_email integer not null default 0,
  leads_with_mobile integer not null default 0,
  leads_no_website integer not null default 0,
  rejected_count integer not null default 0,
  success_rate integer not null default 0,
  duration_seconds integer not null default 0,
  credits_consumed double precision,
  status varchar(24) not null default 'running',
  started_at timestamptz,
  finished_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.error_events (
  id varchar(36) primary key,
  host_provider varchar(40) not null default '',
  worker_id varchar(120) not null default '',
  job_id varchar(36) not null default '',
  provider varchar(40) not null default '',
  error_type varchar(80) not null default 'error',
  message text not null default '',
  context jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.activity_events (
  id varchar(36) primary key,
  host_provider varchar(40) not null default '',
  worker_id varchar(120) not null default '',
  job_id varchar(36) not null default '',
  kind varchar(24) not null default 'status',
  message text not null default '',
  detail jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists ix_leads_company_number on public.leads (company_number);
create index if not exists ix_leads_name on public.leads (name);
create index if not exists ix_leads_location on public.leads (location);
create index if not exists ix_leads_category on public.leads (category);
create index if not exists ix_leads_priority_score on public.leads (priority_score);
create index if not exists ix_leads_job_id on public.leads (job_id);
create index if not exists ix_jobs_status on public.jobs (status);
create index if not exists ix_job_logs_job_id on public.job_logs (job_id);
create index if not exists ix_hosts_provider on public.hosts (provider);
create index if not exists ix_hosts_status on public.hosts (status);
create index if not exists ix_run_metrics_job_id on public.run_metrics (job_id);
create index if not exists ix_run_metrics_host on public.run_metrics (host_provider);
create index if not exists ix_run_metrics_worker on public.run_metrics (worker_id);
create index if not exists ix_error_events_host on public.error_events (host_provider);
create index if not exists ix_error_events_job on public.error_events (job_id);
create index if not exists ix_error_events_provider on public.error_events (provider);
create index if not exists ix_error_events_type on public.error_events (error_type);
create index if not exists ix_error_events_created on public.error_events (created_at);
create index if not exists ix_activity_host on public.activity_events (host_provider);
create index if not exists ix_activity_job on public.activity_events (job_id);
create index if not exists ix_activity_kind on public.activity_events (kind);
create index if not exists ix_activity_created on public.activity_events (created_at);

alter table public.leads enable row level security;
alter table public.jobs enable row level security;
alter table public.job_logs enable row level security;
alter table public.workers enable row level security;
alter table public.secrets enable row level security;
alter table public.hosts enable row level security;
alter table public.run_metrics enable row level security;
alter table public.error_events enable row level security;
alter table public.activity_events enable row level security;
