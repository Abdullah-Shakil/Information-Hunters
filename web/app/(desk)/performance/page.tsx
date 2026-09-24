"use client";

import { useEffect, useState } from "react";
import { api } from "../../../lib/client";

type Totals = {
  runs: number;
  companies_searched: number;
  leads_found: number;
  leads_with_email: number;
  leads_with_mobile: number;
  leads_no_website: number;
  success_rate: number;
};

type RunRow = Totals & {
  id: string;
  job_id: string;
  job_name: string;
  host_provider: string;
  worker_id: string;
  discovery_provider: string;
  rejected_count: number;
  duration_seconds: number;
  credits_consumed: number | null;
  status: string;
  started_at: string | null;
  finished_at: string | null;
};

type HostBar = {
  host: string;
  runs: number;
  companies_searched: number;
  leads_found: number;
  success_rate: number;
};

type ErrorRow = {
  id: string;
  host_provider: string;
  worker_id: string;
  provider: string;
  error_type: string;
  message: string;
  context: Record<string, string>;
  created_at: string | null;
};

export default function PerformancePage() {
  const [totals, setTotals] = useState<Totals | null>(null);
  const [runs, setRuns] = useState<RunRow[]>([]);
  const [bars, setBars] = useState<HostBar[]>([]);
  const [errors, setErrors] = useState<ErrorRow[]>([]);
  const [host, setHost] = useState("");
  const [provider, setProvider] = useState("");
  const [errorType, setErrorType] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let stop = false;
    const load = async () => {
      try {
        const params = new URLSearchParams();
        if (host) params.set("host", host);
        const errorParams = new URLSearchParams(params);
        if (provider) errorParams.set("provider", provider);
        if (errorType) errorParams.set("error_type", errorType);
        const [performance, errorBody] = await Promise.all([
          api<{ totals: Totals; runs: RunRow[]; by_host: HostBar[] }>(`performance?${params.toString()}`),
          api<{ items: ErrorRow[] }>(`errors?${errorParams.toString()}`),
        ]);
        if (stop) return;
        setTotals(performance.totals);
        setRuns(performance.runs);
        setBars(performance.by_host);
        setErrors(errorBody.items);
        setError("");
      } catch (err) {
        if (!stop) setError(err instanceof Error ? err.message : "Could not load performance");
      }
    };
    void load();
    const timer = setInterval(() => void load(), 8000);
    return () => {
      stop = true;
      clearInterval(timer);
    };
  }, [host, provider, errorType]);

  const maxLeads = Math.max(1, ...bars.map((bar) => bar.leads_found));

  return (
    <>
      <header className="page-head">
        <div>
          <p className="eyebrow">Performance and errors</p>
          <h1>How the hunts went</h1>
          <p>Each run records what was searched, which leads had an email, a mobile, or no website, and every error.</p>
        </div>
      </header>
      <div className="filters">
        <div className="field">
          <label htmlFor="perf-host">Host</label>
          <input id="perf-host" value={host} placeholder="local or oracle_cloud" onChange={(event) => setHost(event.target.value.trim())} />
        </div>
        <div className="field">
          <label htmlFor="perf-provider">Error provider</label>
          <input id="perf-provider" value={provider} placeholder="scrapingbee" onChange={(event) => setProvider(event.target.value.trim())} />
        </div>
        <div className="field">
          <label htmlFor="perf-type">Error type</label>
          <input id="perf-type" value={errorType} placeholder="quota_exhausted" onChange={(event) => setErrorType(event.target.value.trim())} />
        </div>
      </div>
      {error ? <p className="error">{error}</p> : null}
      <section className="stats">
        <article className="stat"><span>Companies searched</span><strong>{totals?.companies_searched ?? "–"}</strong></article>
        <article className="stat"><span>Leads found</span><strong>{totals?.leads_found ?? "–"}</strong></article>
        <article className="stat"><span>With email</span><strong>{totals?.leads_with_email ?? "–"}</strong></article>
        <article className="stat"><span>Success rate</span><strong>{totals ? `${totals.success_rate}%` : "–"}</strong></article>
      </section>
      <section className="stats">
        <article className="stat"><span>With mobile</span><strong>{totals?.leads_with_mobile ?? "–"}</strong></article>
        <article className="stat"><span>No website</span><strong>{totals?.leads_no_website ?? "–"}</strong></article>
        <article className="stat"><span>Runs</span><strong>{totals?.runs ?? "–"}</strong></article>
        <article className="stat"><span>Errors</span><strong>{errors.length}</strong></article>
      </section>
      <section className="panel">
        <h2>Leads by host</h2>
        {bars.length === 0 ? <p className="muted">No runs for this filter yet.</p> : null}
        <div className="chart">
          {bars.map((bar) => (
            <div key={bar.host} className="chart-row">
              <span>{bar.host}</span>
              <div className="chart-track"><span style={{ width: `${Math.max(4, (bar.leads_found / maxLeads) * 100)}%` }} /></div>
              <b>{bar.leads_found}</b>
            </div>
          ))}
        </div>
      </section>
      <section className="panel">
        <h2>Runs</h2>
        <table>
          <thead>
            <tr>
              <th>Hunt</th>
              <th>Host</th>
              <th>Searched</th>
              <th>Leads</th>
              <th>Email</th>
              <th>Mobile</th>
              <th>No site</th>
              <th>Rate</th>
              <th>Duration</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => (
              <tr key={run.id}>
                <td>
                  <strong>{run.job_name}</strong>
                  <div className="muted">{run.worker_id || "worker"} · {run.discovery_provider}</div>
                </td>
                <td>{run.host_provider || "local"}</td>
                <td>{run.companies_searched}</td>
                <td>{run.leads_found}</td>
                <td>{run.leads_with_email}</td>
                <td>{run.leads_with_mobile}</td>
                <td>{run.leads_no_website}</td>
                <td>{run.success_rate}%</td>
                <td>{formatDuration(run.duration_seconds)}</td>
                <td><span className={`pill ${run.status === "completed" ? "good" : run.status === "failed" ? "bad" : "neutral"}`}>{run.status}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
        {runs.length === 0 ? <p className="muted">Queue a hunt and let a worker finish it. A row appears here even if you are not watching.</p> : null}
      </section>
      <section className="panel">
        <h2>Errors</h2>
        <table>
          <thead>
            <tr>
              <th>When</th>
              <th>Host</th>
              <th>Provider</th>
              <th>Type</th>
              <th>Message</th>
            </tr>
          </thead>
          <tbody>
            {errors.map((item) => (
              <tr key={item.id}>
                <td className="muted">{item.created_at ? new Date(item.created_at).toLocaleString() : ""}</td>
                <td>{item.host_provider || item.worker_id || "local"}</td>
                <td>{item.provider}</td>
                <td><span className={`pill ${item.error_type === "quota_exhausted" ? "warn" : "bad"}`}>{item.error_type}</span></td>
                <td>{item.message}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {errors.length === 0 ? <p className="muted">No errors for this filter.</p> : null}
      </section>
    </>
  );
}

function formatDuration(seconds: number) {
  if (!seconds) return "0s";
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return minutes ? `${minutes}m ${rest}s` : `${rest}s`;
}
