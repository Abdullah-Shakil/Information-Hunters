"use client";

import { useEffect, useState, type Dispatch, type SetStateAction } from "react";
import { api } from "../../../lib/client";

type Field = {
  name: string;
  label: string;
  hint: string;
  secret: boolean;
  required: boolean;
  multiline: boolean;
  value: string;
  configured: boolean;
  last4: string | null;
  source: string | null;
};

type HostCard = {
  provider: string;
  name: string;
  kind: string;
  controllable: boolean;
  status: string;
  status_detail: string;
  free_limits: string;
  summary: string;
  setup_hint: string;
  setup_url: string;
  manual_setup: string;
  keeps_running: string;
  uncontrolled_reason: string;
  remote_id: string | null;
  usage: { summary?: string; used?: number | null; limit?: number | null; unit?: string } | null;
  last_error: string | null;
  fields: Field[];
};

type Excluded = { id: string; name: string; reason: string };

const PILL: Record<string, string> = {
  running: "good",
  stopped: "neutral",
  unconfigured: "warn",
  starting: "warn",
  stopping: "warn",
  quota_exhausted: "bad",
  error: "bad",
};

export default function HostsPage() {
  const [hosts, setHosts] = useState<HostCard[]>([]);
  const [excluded, setExcluded] = useState<Excluded[]>([]);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");

  async function load() {
    const body = await api<{ hosts: HostCard[]; excluded: Excluded[] }>("hosts");
    setHosts(body.hosts);
    setExcluded(body.excluded);
    setDrafts((current) => {
      const next = { ...current };
      for (const host of body.hosts) {
        for (const field of host.fields) {
          const key = `${host.provider}:${field.name}`;
          if (!field.secret && next[key] === undefined) next[key] = field.value || "";
        }
      }
      return next;
    });
  }

  useEffect(() => {
    void load().catch((err: Error) => setError(err.message));
  }, []);

  useEffect(() => {
    const timer = setInterval(() => {
      const running = hosts.filter((host) => host.controllable && (host.status === "running" || host.status === "starting"));
      for (const host of running) {
        void api<HostCard>(`hosts/${host.provider}/refresh`, { method: "POST" })
          .then((updated) => setHosts((current) => current.map((item) => (item.provider === updated.provider ? updated : item))))
          .catch(() => undefined);
      }
    }, 20000);
    return () => clearInterval(timer);
  }, [hosts]);

  function replace(updated: HostCard) {
    setHosts((current) => current.map((item) => (item.provider === updated.provider ? updated : item)));
  }

  async function save(host: HostCard) {
    const values: Record<string, string> = {};
    for (const field of host.fields) {
      const draft = drafts[`${host.provider}:${field.name}`];
      if (field.secret) {
        if (draft && draft.trim()) values[field.name] = draft.trim();
      } else if (draft !== undefined) {
        values[field.name] = draft;
      }
    }
    setBusy(host.provider);
    setError("");
    try {
      const updated = await api<HostCard>(`hosts/${host.provider}`, { method: "POST", body: JSON.stringify({ values }) });
      replace(updated);
      setDrafts((current) => {
        const next = { ...current };
        for (const field of host.fields) {
          if (field.secret) next[`${host.provider}:${field.name}`] = "";
        }
        return next;
      });
      setMessage(`${host.name} saved. The full key stays on the server.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save");
    } finally {
      setBusy("");
    }
  }

  async function act(host: HostCard, action: "test" | "start" | "stop") {
    setBusy(`${host.provider}:${action}`);
    setError("");
    setMessage("");
    try {
      const body = await api<HostCard | { host: HostCard; detail: string }>(`hosts/${host.provider}/${action}`, { method: "POST" });
      const updated = "host" in body ? body.host : body;
      replace(updated);
      const detail = "detail" in body ? body.detail : updated.status_detail;
      setMessage(detail || `${host.name} is ${updated.status.replaceAll("_", " ")}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setBusy("");
    }
  }

  const controllable = hosts.filter((host) => host.kind === "host");
  const others = hosts.filter((host) => host.kind !== "host");

  return (
    <>
      <header className="page-head">
        <div>
          <p className="eyebrow">Hosts</p>
          <h1>Cloud workers</h1>
          <p>Paste the free-tier keys, then press Start. The website does not scrape. A started host keeps working after this browser closes, until you stop it or its free allowance runs out.</p>
        </div>
      </header>
      <div className="notice">
        Demo hunts still run with no keys. Supabase credentials belong in the server environment (SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_DB_URL), not in this form — the database cannot store the password it needs in order to open.
      </div>
      {message ? <p className="hint">{message}</p> : null}
      {error ? <p className="error">{error}</p> : null}
      {controllable.map((host) => (
        <HostPanel key={host.provider} host={host} drafts={drafts} setDrafts={setDrafts} busy={busy} onSave={save} onAct={act} />
      ))}
      <h2 style={{ margin: "28px 0 12px" }}>Scrapers and libraries</h2>
      <p className="muted">These do not have a start button. They run inside a host that is already on.</p>
      {others.map((host) => (
        <HostPanel key={host.provider} host={host} drafts={drafts} setDrafts={setDrafts} busy={busy} onSave={save} onAct={act} />
      ))}
      <section className="panel">
        <h2>Evaluated and left out</h2>
        <p className="muted">No adapter was added, because there is no genuine free tier that can run this worker.</p>
        {excluded.map((item) => (
          <div key={item.id} className="activity-line">
            <strong>{item.name}</strong>
            <span className="muted">{item.reason}</span>
          </div>
        ))}
      </section>
    </>
  );
}

function HostPanel({
  host,
  drafts,
  setDrafts,
  busy,
  onSave,
  onAct,
}: {
  host: HostCard;
  drafts: Record<string, string>;
  setDrafts: Dispatch<SetStateAction<Record<string, string>>>;
  busy: string;
  onSave: (host: HostCard) => void;
  onAct: (host: HostCard, action: "test" | "start" | "stop") => void;
}) {
  return (
    <section className="panel host-card">
      <div className="split" style={{ alignItems: "start" }}>
        <div>
          <h2>{host.name}</h2>
          <p className="muted" style={{ marginTop: 0 }}>{host.summary}</p>
        </div>
        <div>
          <span className={`pill ${PILL[host.status] || "neutral"}`}>{host.status.replaceAll("_", " ")}</span>
        </div>
      </div>
      <p className="limits"><strong>Free limits. </strong>{host.free_limits}</p>
      <p className="limits">{host.keeps_running}</p>
      {host.uncontrolled_reason ? <p className="limits">{host.uncontrolled_reason}</p> : null}
      <p className="hint">
        {host.setup_hint}{" "}
        <a href={host.setup_url} target="_blank" rel="noreferrer">{host.setup_url.replace("https://", "")}</a>
      </p>
      <p className="hint">{host.manual_setup}</p>
      {host.usage?.summary ? <p className="hint">{host.usage.summary}</p> : null}
      {host.last_error ? <p className="error">{host.last_error}</p> : null}
      {host.status_detail && host.status_detail !== host.last_error ? <p className="hint">{host.status_detail}</p> : null}
      {host.fields.map((field) => {
        const key = `${host.provider}:${field.name}`;
        const shown = drafts[key] ?? (field.secret ? "" : field.value);
        return (
          <div key={field.name} className="field-block">
            <label htmlFor={key}>{field.label}</label>
            {field.multiline ? (
              <textarea id={key} value={shown} aria-label={field.label} placeholder={field.secret ? "Paste a new value" : ""} onChange={(event) => setDrafts((current) => ({ ...current, [key]: event.target.value }))} />
            ) : (
              <input id={key} type={field.secret ? "password" : "text"} value={shown} aria-label={field.label} placeholder={field.secret ? "Paste a new value" : ""} autoComplete="off" onChange={(event) => setDrafts((current) => ({ ...current, [key]: event.target.value }))} />
            )}
            <div className="muted">
              {field.hint}
              {field.configured ? ` · saved${field.source ? ` via ${field.source}` : ""}${field.last4 ? ` · ···${field.last4}` : ""}` : ""}
            </div>
          </div>
        );
      })}
      <div className="btn-row" style={{ marginTop: 14 }}>
        {host.fields.length ? (
          <button className="btn" type="button" disabled={busy.startsWith(host.provider)} onClick={() => onSave(host)}>Save</button>
        ) : null}
        <button className="btn" type="button" disabled={Boolean(busy)} onClick={() => onAct(host, "test")}>Test connection</button>
        {host.controllable ? (
          <>
            <button className="btn primary" type="button" disabled={Boolean(busy)} onClick={() => onAct(host, "start")}>Start</button>
            <button className="btn danger" type="button" disabled={Boolean(busy) || host.status === "stopped" || host.status === "unconfigured"} onClick={() => onAct(host, "stop")}>Stop</button>
          </>
        ) : null}
      </div>
    </section>
  );
}
