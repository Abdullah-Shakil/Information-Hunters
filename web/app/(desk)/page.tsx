"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, type Job, type Lead } from "../../lib/client";

type Stats = {
  leads: number;
  new_leads_7d: number;
  with_email: number;
  with_mobile: number;
  no_website: number;
  high_priority: number;
  active_jobs: number;
};

export default function OverviewPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    let stop = false;
    const load = async () => {
      try {
        const [nextStats, nextLeads, nextJobs] = await Promise.all([
          api<Stats>("stats"),
          api<{ items: Lead[] }>("leads?page_size=6"),
          api<{ items: Job[] }>("jobs"),
        ]);
        if (stop) return;
        setStats(nextStats);
        setLeads(nextLeads.items);
        setJobs(nextJobs.items.slice(0, 4));
        setError("");
      } catch (err) {
        if (!stop) setError(err instanceof Error ? err.message : "Could not load the desk");
      }
    };
    void load();
    const timer = setInterval(() => void load(), 4000);
    return () => {
      stop = true;
      clearInterval(timer);
    };
  }, []);

  return (
    <>
      <header className="page-head">
        <div>
          <p className="eyebrow">Cloud workers · UK trades · shared desk</p>
          <h1>Today’s desk</h1>
          <p>Qualified leads from hunts the worker has already finished or is still running.</p>
        </div>
        <Link className="run-btn cloud" href="/hunts">
          New hunt
        </Link>
      </header>
      {error ? <p className="error">{error}</p> : null}
      <section className="stat-row">
        <article className="stat"><span className="label">Qualified leads</span><strong className="value">{stats?.leads ?? "–"}</strong></article>
        <article className="stat"><span className="label">New this week</span><strong className="value">{stats?.new_leads_7d ?? "–"}</strong></article>
        <article className="stat"><span className="label">No website</span><strong className="value">{stats?.no_website ?? "–"}</strong></article>
        <article className="stat"><span className="label">Active hunts</span><strong className="value">{stats?.active_jobs ?? "–"}</strong></article>
      </section>
      <div className="split">
        <section className="panel-block">
          <h2 className="section-title">Highest priority</h2>
          {leads.length === 0 ? <p className="muted">No leads yet. Start a hunt for a trade and a city.</p> : null}
          {leads.length > 0 ? (
            <table>
              <tbody>
                {leads.map((lead) => (
                  <tr key={lead.id} className="clickable" onClick={() => (window.location.href = `/leads/${lead.id}`)}>
                    <td>
                      <strong>{lead.name}</strong>
                      <div className="muted">{lead.location} · {lead.category}</div>
                    </td>
                    <td className="score"><b>{lead.priority_score}</b><span className="band">{lead.priority_band}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : null}
        </section>
        <section className="panel-block">
          <h2 className="section-title">Hunts</h2>
          {jobs.length === 0 ? <p className="muted">Nothing queued.</p> : null}
          {jobs.map((job) => (
            <div key={job.id} style={{ padding: "0.75rem 0", borderTop: "1px solid var(--line)" }}>
              <Link href={`/hunts/${job.id}`}><strong>{job.name}</strong></Link>
              <div className="muted">{job.status} · {job.qualified_count} qualified</div>
              <div className="progress" style={{ marginTop: 8 }}><span style={{ width: `${job.progress}%` }} /></div>
            </div>
          ))}
          <p className="hint">High priority {stats?.high_priority ?? 0} · with mobile {stats?.with_mobile ?? 0} · with email {stats?.with_email ?? 0}</p>
        </section>
      </div>
    </>
  );
}
