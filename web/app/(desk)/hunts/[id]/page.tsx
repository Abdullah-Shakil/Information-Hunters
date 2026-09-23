"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api, type Job } from "../../../../lib/client";

type LogLine = { id: string; level: string; message: string; created_at: string };

export default function HuntDetailPage() {
  const params = useParams<{ id: string }>();
  const [job, setJob] = useState<Job | null>(null);
  const [logs, setLogs] = useState<LogLine[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    let stop = false;
    const load = async () => {
      try {
        const [nextJob, nextLogs] = await Promise.all([
          api<Job>(`jobs/${params.id}`),
          api<{ items: LogLine[] }>(`jobs/${params.id}/logs`),
        ]);
        if (stop) return;
        setJob(nextJob);
        setLogs(nextLogs.items);
      } catch (err) {
        if (!stop) setError(err instanceof Error ? err.message : "Could not load hunt");
      }
    };
    void load();
    const timer = setInterval(() => void load(), 2000);
    return () => {
      stop = true;
      clearInterval(timer);
    };
  }, [params.id]);

  async function act(action: "start" | "pause" | "stop") {
    setError("");
    try {
      const next = await api<Job>(`jobs/${params.id}/${action}`, { method: "POST" });
      setJob(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Control failed");
    }
  }

  if (!job) return <p className="muted">{error || "Loading hunt…"}</p>;

  return (
    <>
      <header className="page-head">
        <div>
          <p className="eyebrow">Hunt</p>
          <h1>{job.name}</h1>
          <p>{job.stage}{job.worker_id ? ` · worker ${job.worker_id}` : ""}</p>
        </div>
        <div className="btn-row">
          <button className="btn primary" type="button" onClick={() => void act("start")}>Start</button>
          <button className="btn" type="button" onClick={() => void act("pause")}>Pause</button>
          <button className="btn danger" type="button" onClick={() => void act("stop")}>Stop</button>
        </div>
      </header>
      {error ? <p className="error">{error}</p> : null}
      {job.error ? <div className="notice">{job.error}</div> : null}
      <section className="stats">
        <article className="stat"><span>Status</span><strong style={{ fontSize: 28 }}>{job.status}</strong></article>
        <article className="stat"><span>Discovered</span><strong>{job.discovered_count}</strong></article>
        <article className="stat"><span>Qualified</span><strong>{job.qualified_count}</strong></article>
        <article className="stat"><span>Rejected</span><strong>{job.rejected_count}</strong></article>
      </section>
      <div className="progress" style={{ marginBottom: 16 }}><span style={{ width: `${job.progress}%` }} /></div>
      <p className="muted">{job.categories.join(", ")} in {job.regions.join(", ")} · {job.discovery_provider} / {job.verification_provider}</p>
      <section className="panel">
        <h2>Worker log</h2>
        <div className="log" aria-live="polite">
          {logs.map((line) => (
            <div key={line.id}>[{line.level}] {line.message}</div>
          ))}
          {logs.length === 0 ? <div>Waiting for the worker…</div> : null}
        </div>
      </section>
    </>
  );
}
