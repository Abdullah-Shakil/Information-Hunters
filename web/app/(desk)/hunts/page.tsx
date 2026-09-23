"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, type Catalogue, type Job } from "../../../lib/client";

const pill = (status: string) => {
  if (status === "completed") return "pill good";
  if (status === "running" || status === "queued") return "pill warn";
  if (status === "failed") return "pill bad";
  return "pill neutral";
};

export default function HuntsPage() {
  const [catalogue, setCatalogue] = useState<Catalogue | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    name: "Plumbers in Manchester",
    categories: ["plumbers"] as string[],
    regions: ["Manchester"] as string[],
    limit_per_search: 8,
    discovery_provider: "auto",
    verification_provider: "auto",
    contact_fetcher: "auto",
  });

  async function load() {
    const data = await api<{ items: Job[] }>("jobs");
    setJobs(data.items);
  }

  useEffect(() => {
    void api<Catalogue>("categories").then(setCatalogue).catch((err: Error) => setError(err.message));
    void load().catch((err: Error) => setError(err.message));
    const timer = setInterval(() => void load().catch(() => undefined), 4000);
    return () => clearInterval(timer);
  }, []);

  function toggle(list: "categories" | "regions", id: string) {
    setForm((current) => {
      const has = current[list].includes(id);
      return { ...current, [list]: has ? current[list].filter((item) => item !== id) : [...current[list], id] };
    });
  }

  async function createHunt(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const job = await api<Job>("jobs", { method: "POST", body: JSON.stringify(form) });
      window.location.href = `/hunts/${job.id}`;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not queue the hunt");
      setBusy(false);
    }
  }

  return (
    <>
      <header className="page-head">
        <div>
          <p className="eyebrow">Hunts</p>
          <h1>Send the worker out</h1>
          <p>The website only queues the job. A worker process claims it and keeps going if you close this tab.</p>
        </div>
      </header>
      <form className="panel" onSubmit={createHunt}>
        <div className="form-grid">
          <div className="field">
            <label htmlFor="name">Name</label>
            <input id="name" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} required />
          </div>
          <div className="field">
            <label htmlFor="limit">Companies per search</label>
            <input id="limit" type="number" min={1} max={100} value={form.limit_per_search} onChange={(event) => setForm({ ...form, limit_per_search: Number(event.target.value) })} />
          </div>
          <div className="field">
            <label htmlFor="discovery">Discovery</label>
            <select id="discovery" value={form.discovery_provider} onChange={(event) => setForm({ ...form, discovery_provider: event.target.value })}>
              <option value="auto">Auto</option>
              <option value="demo">Demo catalogue</option>
              <option value="companies_house">Companies House API</option>
              <option value="companies_house_public">Public registry search</option>
            </select>
          </div>
        </div>
        <div className="form-grid" style={{ marginTop: 12 }}>
          <div className="field">
            <label htmlFor="verify">Verification</label>
            <select id="verify" value={form.verification_provider} onChange={(event) => setForm({ ...form, verification_provider: event.target.value })}>
              <option value="auto">Auto</option>
              <option value="demo">Demo</option>
              <option value="google_places">Google Places</option>
              <option value="registry">Registry status only</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="fetch">Contact fetch</label>
            <select id="fetch" value={form.contact_fetcher} onChange={(event) => setForm({ ...form, contact_fetcher: event.target.value })}>
              <option value="auto">Auto</option>
              <option value="direct">Direct public page</option>
              <option value="scrapingbee">ScrapingBee</option>
              <option value="brightdata">Bright Data</option>
              <option value="playwright">Playwright</option>
              <option value="none">None</option>
            </select>
          </div>
        </div>
        <p className="eyebrow" style={{ marginTop: 18 }}>Categories</p>
        <div className="choices">
          {catalogue?.categories.map((item) => (
            <label key={item.id}>
              <input type="checkbox" checked={form.categories.includes(item.id)} onChange={() => toggle("categories", item.id)} />
              {item.label}
            </label>
          ))}
        </div>
        <p className="eyebrow" style={{ marginTop: 18 }}>Regions</p>
        <div className="choices">
          {catalogue?.regions.map((item) => (
            <label key={item.id}>
              <input type="checkbox" checked={form.regions.includes(item.id)} onChange={() => toggle("regions", item.id)} />
              {item.label}
            </label>
          ))}
        </div>
        {error ? <p className="error">{error}</p> : null}
        <div style={{ marginTop: 16 }}>
          <button className="btn primary" type="submit" disabled={busy}>Queue hunt</button>
        </div>
      </form>
      <section className="panel">
        <h2>Recent hunts</h2>
        <table>
          <thead>
            <tr><th>Name</th><th>Status</th><th>Progress</th><th>Qualified</th><th>Rejected</th></tr>
          </thead>
          <tbody>
            {jobs.map((job) => (
              <tr key={job.id}>
                <td><Link href={`/hunts/${job.id}`}><strong>{job.name}</strong></Link><div className="muted">{job.categories.join(", ")} · {job.regions.join(", ")}</div></td>
                <td><span className={pill(job.status)}>{job.status}</span></td>
                <td>{job.progress}%</td>
                <td>{job.qualified_count}</td>
                <td>{job.rejected_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {jobs.length === 0 ? <p className="muted">No hunts yet.</p> : null}
      </section>
    </>
  );
}
