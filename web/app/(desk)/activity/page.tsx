"use client";

import { useEffect, useState } from "react";
import { api } from "../../../lib/client";

type EventRow = {
  id: string;
  host_provider: string;
  worker_id: string;
  kind: string;
  message: string;
  detail: { email?: string | null; mobile?: string | null; name?: string };
  created_at: string | null;
};

const KINDS = ["", "searching", "found", "rejected", "status"];

export default function ActivityPage() {
  const [items, setItems] = useState<EventRow[]>([]);
  const [kind, setKind] = useState("");
  const [host, setHost] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let stop = false;
    const load = async () => {
      try {
        const params = new URLSearchParams();
        if (kind) params.set("kind", kind);
        if (host) params.set("host", host);
        const body = await api<{ items: EventRow[] }>(`activity?${params.toString()}`);
        if (!stop) {
          setItems(body.items);
          setError("");
        }
      } catch (err) {
        if (!stop) setError(err instanceof Error ? err.message : "Could not load activity");
      }
    };
    void load();
    const timer = setInterval(() => void load(), 3000);
    return () => {
      stop = true;
      clearInterval(timer);
    };
  }, [kind, host]);

  return (
    <>
      <header className="page-head">
        <div>
          <p className="eyebrow">Live activity</p>
          <h1>What the workers just did</h1>
          <p>Events are stored in the database and this page refreshes every few seconds. A host keeps writing them while this laptop is off.</p>
        </div>
        <span className="pill good"><i className="live-dot" /> Live</span>
      </header>
      <div className="filters">
        <div className="field">
          <label htmlFor="kind">Kind</label>
          <select id="kind" value={kind} onChange={(event) => setKind(event.target.value)}>
            {KINDS.map((value) => (
              <option key={value || "all"} value={value}>{value || "All"}</option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="host">Host</label>
          <input id="host" value={host} placeholder="local, apify, oracle_cloud" onChange={(event) => setHost(event.target.value.trim())} />
        </div>
      </div>
      {error ? <p className="error">{error}</p> : null}
      <section className="panel">
        {items.length === 0 ? <p className="muted">Nothing yet. Start a host, or run a local worker, then queue a hunt.</p> : null}
        {items.map((item) => (
          <div key={item.id} className="activity-line">
            <div className="btn-row">
              <span className={`pill ${item.kind === "found" ? "good" : item.kind === "rejected" ? "warn" : "neutral"}`}>{item.kind}</span>
              <span className="muted">{item.host_provider || "local"}{item.worker_id ? ` · ${item.worker_id}` : ""}</span>
              <span className="muted">{item.created_at ? new Date(item.created_at).toLocaleString() : ""}</span>
            </div>
            <strong>{item.message}</strong>
          </div>
        ))}
      </section>
    </>
  );
}
