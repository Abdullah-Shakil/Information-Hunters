"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "../lib/client";

export type Model = {
  id: string;
  display_name?: string;
  provider?: string;
  connected?: boolean;
  has_limit?: boolean;
  used_units?: number;
  limit_units?: number | null;
  remaining?: number | null;
  pct_used?: number;
  unit_label?: string;
  reset_label?: string;
  reset_in_human?: string;
  needs_manual_reset?: boolean;
  manual_reset_url?: string;
  manual_reset_note?: string;
  profile_summary?: string;
  source_url?: string;
  console_url?: string;
  docs_url?: string;
  activation?: { state: string; label: string; detail: string; key_hint?: string | null };
};

export type Module = { name: string; path: string; purpose: string };

export type Agent = {
  id: string;
  name: string;
  role: string;
  kind: string;
  description: string;
  importance: number;
  importance_label?: string;
  is_engine?: boolean;
  status: string;
  source_name?: string;
  source_url?: string;
  docs_url?: string;
  origin?: string;
  profile_summary?: string;
  modules: Module[];
  model?: Model | null;
  activation?: Model["activation"];
  cloud_run?: { id?: number; status?: string; conclusion?: string | null; html_url?: string } | null;
};

export type Fleet = {
  scrapers: Agent[];
  bots: Agent[];
  workers: { id: string; hostname: string; last_seen: string | null; live: boolean }[];
  active_jobs: number;
  database: string;
  cloud_run?: Agent["cloud_run"];
  can_start_cloud?: boolean;
};

function statusMeta(status: string) {
  const key = (status || "idle").toLowerCase();
  if (key === "live" || key === "running") return { key: "live", label: "Live" };
  if (key === "ready") return { key: "ready", label: "Ready" };
  if (key === "paused") return { key: "paused", label: "Paused · needs key" };
  if (key === "error") return { key: "error", label: "Error" };
  return { key: "idle", label: "Idle" };
}

function importanceCell(agent: Agent, kind: "scrapers" | "bots") {
  const pill = kind === "scrapers" ? "engine" : "scraper";
  const label = kind === "scrapers" ? "Scraper" : "Bot";
  return (
    <div className="importance-cell">
      <span className={`rank-pill ${pill}`}>{label}</span>
      <span className="importance-label">{agent.importance_label || agent.role}</span>
    </div>
  );
}

function usageCompact(model?: Model | null) {
  if (!model) return <span className="muted">—</span>;
  if (!model.has_limit) {
    return (
      <div className="usage-cell">
        <strong>Unlimited</strong>
        <div className="muted">{model.reset_label || "No usage cap"}</div>
      </div>
    );
  }
  const used = model.used_units ?? 0;
  const limit = model.limit_units ?? 0;
  const pct = Math.min(100, Math.max(0, model.pct_used ?? 0));
  return (
    <div className="usage-cell">
      <div className="usage-meta">
        <span>
          {used}/{limit} {model.unit_label}
        </span>
        <span>{model.remaining ?? "—"} left</span>
      </div>
      <div className="bar">
        <span style={{ width: `${pct}%` }} />
      </div>
      <div className="usage-reset">
        {model.needs_manual_reset ? (
          model.manual_reset_url ? (
            <a href={model.manual_reset_url} target="_blank" rel="noreferrer" className="source-link" onClick={(e) => e.stopPropagation()}>
              Manual — visit portal
            </a>
          ) : (
            <span>Manual — visit portal</span>
          )
        ) : (
          <span>{model.reset_in_human || model.reset_label || "Auto reset"}</span>
        )}
      </div>
    </div>
  );
}

function activationBadge(act?: Model["activation"]) {
  if (!act) return <span className="badge off">Unknown</span>;
  const cls = act.state === "connected" ? "on" : act.state === "needs_activate" ? "need" : act.state === "skip" ? "skip" : "off";
  return <span className={`badge ${cls}`}>{act.label || act.state}</span>;
}

function AgentTable({
  rows,
  kind,
  onOpen,
  loading,
}: {
  rows: Agent[];
  kind: "scrapers" | "bots";
  onOpen: (index: number) => void;
  loading?: boolean;
}) {
  if (loading) return <p className="muted">Loading {kind}…</p>;
  if (!rows.length) return <p className="empty">None yet.</p>;
  return (
    <div className="table-wrap bots-table-wrap">
      <table className="bots-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Description</th>
            <th>Status</th>
            <th>{kind === "scrapers" ? "Activation" : "Usage & reset"}</th>
            <th>Source</th>
            <th>Importance</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((agent, idx) => {
            const st = statusMeta(agent.status);
            return (
              <tr
                key={agent.id}
                className="bot-row"
                tabIndex={0}
                role="button"
                aria-label={`Open profile for ${agent.name}`}
                onClick={() => onOpen(idx)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onOpen(idx);
                  }
                }}
              >
                <td>
                  <strong className="bot-name">{agent.name}</strong>
                  <div className="bot-role">{agent.role}</div>
                </td>
                <td className="bot-desc">{agent.description}</td>
                <td>
                  <span className={`status ${st.key}`}>{st.label}</span>
                </td>
                <td>
                  {kind === "scrapers" ? (
                    <div className="usage-cell">
                      {activationBadge(agent.activation || agent.model?.activation)}
                      <div className="muted" style={{ marginTop: 6 }}>
                        {agent.status === "live"
                          ? "Cloud run in progress"
                          : agent.status === "ready"
                            ? "Start to hunt · device can sleep"
                            : agent.status === "paused"
                              ? "Needs cloud DB / token"
                              : "Idle"}
                      </div>
                    </div>
                  ) : (
                    usageCompact(agent.model)
                  )}
                </td>
                <td>
                  <div className="source-cell">
                    <strong>{agent.source_name || "—"}</strong>
                    {agent.source_url ? (
                      <a
                        href={agent.source_url}
                        target="_blank"
                        rel="noreferrer"
                        className="source-link"
                        onClick={(e) => e.stopPropagation()}
                      >
                        Open source
                      </a>
                    ) : null}
                  </div>
                </td>
                <td>{importanceCell(agent, kind)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

type Props = {
  kind: "scrapers" | "bots";
};

export default function FleetAgents({ kind }: Props) {
  const [fleet, setFleet] = useState<Fleet | null>(null);
  const [error, setError] = useState("");
  const [actionMsg, setActionMsg] = useState("");
  const [busy, setBusy] = useState<"start" | "stop" | null>(null);
  const [profileIndex, setProfileIndex] = useState<number | null>(null);

  async function load() {
    try {
      const data = await api<Fleet>("fleet");
      setFleet(data);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load fleet");
    }
  }

  useEffect(() => {
    void load();
    const timer = setInterval(() => void load(), 8000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    return () => document.body.classList.remove("profile-open");
  }, []);

  const rows = kind === "scrapers" ? fleet?.scrapers ?? [] : fleet?.bots ?? [];
  const profile = profileIndex != null ? rows[profileIndex] : null;
  const dbCloud = fleet?.database === "postgres";
  const loading = !fleet && !error;
  const cloudLive = rows.some((r) => r.status === "live") || fleet?.cloud_run?.status === "in_progress" || fleet?.cloud_run?.status === "queued";
  const canStart = Boolean(fleet?.can_start_cloud);

  async function startCloud() {
    setBusy("start");
    setActionMsg("");
    try {
      await api("fleet/cloud/start", { method: "POST" });
      setActionMsg("Cloud worker started — hunts will run in GitHub Actions even if this PC sleeps.");
      await load();
    } catch (err) {
      setActionMsg(err instanceof Error ? err.message : "Could not start cloud worker");
    } finally {
      setBusy(null);
    }
  }

  async function stopCloud() {
    setBusy("stop");
    setActionMsg("");
    try {
      await api("fleet/cloud/stop", { method: "POST" });
      setActionMsg("Cancelled in-progress cloud worker runs.");
      await load();
    } catch (err) {
      setActionMsg(err instanceof Error ? err.message : "Could not stop cloud worker");
    } finally {
      setBusy(null);
    }
  }

  function openProfile(index: number) {
    setProfileIndex(index);
    document.body.classList.add("profile-open");
  }

  function closeProfile() {
    setProfileIndex(null);
    document.body.classList.remove("profile-open");
  }

  function step(delta: number) {
    if (profileIndex == null || !rows.length) return;
    setProfileIndex((profileIndex + delta + rows.length) % rows.length);
  }

  const isScrapers = kind === "scrapers";

  return (
    <>
      <header className="page-head">
        <div>
          <p className="eyebrow">{isScrapers ? "Start · stop · device can sleep" : "Auto-run · no approval needed"}</p>
          <h1>{isScrapers ? "Scrapers" : "Bots"}</h1>
          <p>
            {isScrapers
              ? "One cloud worker. Start it to process queued hunts on GitHub Actions with your API keys — turn this device off and hunting continues."
              : "Discover, Verify, Extract, and Score run automatically when the cloud worker claims a hunt. You do not start or approve bots."}
          </p>
        </div>
        {isScrapers ? (
          <div style={{ display: "flex", gap: "0.65rem", flexWrap: "wrap", alignItems: "center" }}>
            <button type="button" className="run-btn cloud" disabled={!canStart || busy === "start"} onClick={() => void startCloud()}>
              {busy === "start" ? "Starting…" : cloudLive ? "Start again" : "Start cloud worker"}
            </button>
            <button type="button" className="ghost-btn" disabled={!canStart || busy === "stop"} onClick={() => void stopCloud()}>
              {busy === "stop" ? "Stopping…" : "Stop"}
            </button>
          </div>
        ) : (
          <Link className="ghost-btn" href="/scrapers">
            Start cloud worker
          </Link>
        )}
      </header>

      {error ? <p className="error">{error}</p> : null}
      {actionMsg ? <p className={actionMsg.toLowerCase().includes("could not") ? "error" : "muted"}>{actionMsg}</p> : null}

      <div className="stat-row" style={{ marginBottom: "1.5rem" }}>
        {isScrapers ? (
          <>
            <article className="stat">
              <span className="label">Cloud worker</span>
              <strong className="value" style={{ fontSize: "1.35rem" }}>
                {fleet ? (cloudLive ? "Live" : canStart ? "Ready" : "Setup") : "–"}
              </strong>
            </article>
            <article className="stat">
              <span className="label">Database</span>
              <strong className="value" style={{ fontSize: "1.35rem" }}>
                {fleet ? (dbCloud ? "Cloud" : "Local") : "–"}
              </strong>
            </article>
            <article className="stat">
              <span className="label">Active hunts</span>
              <strong className="value">{fleet?.active_jobs ?? "–"}</strong>
            </article>
            <article className="stat">
              <span className="label">Schedule</span>
              <strong className="value" style={{ fontSize: "1.35rem" }}>
                15 min
              </strong>
            </article>
          </>
        ) : (
          <>
            <article className="stat">
              <span className="label">Bots</span>
              <strong className="value">{fleet?.bots?.length ?? "–"}</strong>
            </article>
            <article className="stat">
              <span className="label">Ready</span>
              <strong className="value">{(fleet?.bots ?? []).filter((b) => b.status === "ready" || b.status === "live").length || (fleet ? 0 : "–")}</strong>
            </article>
            <article className="stat">
              <span className="label">Need key</span>
              <strong className="value">{(fleet?.bots ?? []).filter((b) => b.status === "paused").length || (fleet ? 0 : "–")}</strong>
            </article>
            <article className="stat">
              <span className="label">Active hunts</span>
              <strong className="value">{fleet?.active_jobs ?? "–"}</strong>
            </article>
          </>
        )}
      </div>

      {isScrapers && fleet && !dbCloud ? (
        <div className="notice">
          Scrapers need Supabase so hunts survive when this PC is off. Set <code>DATABASE_URL</code> in .env and the same value as a GitHub Action secret.
        </div>
      ) : null}

      {isScrapers && fleet && dbCloud && !canStart ? (
        <div className="notice">
          Add <code>GITHUB_TOKEN</code> to .env (PAT with Actions write on Information-Hunters) to enable Start / Stop. Keys for hunting must also be Action secrets so the worker has them offline.
        </div>
      ) : null}

      <p className="muted" style={{ marginBottom: "0.85rem" }}>
        {isScrapers
          ? "Only the cloud worker appears here. Bots (Discover → Score) live on the Bots tab and need no start button."
          : "Informational only — bots run when the cloud worker processes a hunt. Start hunting from Scrapers or Hunts."}
      </p>

      <AgentTable rows={rows} kind={kind} onOpen={openProfile} loading={loading} />

      {profile ? (
        <div className="profile-overlay" role="dialog" aria-modal="true" aria-label={`${isScrapers ? "Scraper" : "Bot"} profile`}>
          <button type="button" className="profile-backdrop" aria-label="Close profile" onClick={closeProfile} />
          <div className="profile-sheet">
            <div className="profile-chrome">
              <div className="profile-nav">
                <button type="button" className="chrome-btn" onClick={() => step(-1)}>
                  Prev
                </button>
                <button type="button" className="chrome-btn" onClick={() => step(1)}>
                  Next
                </button>
                <span className="profile-index">
                  {(profileIndex ?? 0) + 1} / {rows.length}
                </span>
              </div>
              <button type="button" className="chrome-btn close" onClick={closeProfile} aria-label="Close">
                ×
              </button>
            </div>
            <div className="profile-body">
              <div className="profile-hero">
                <p className="kind-tag">{isScrapers ? "Scraper" : "Bot"}</p>
                <h2>{profile.name}</h2>
                <p className="role">{profile.role}</p>
                <span className={`status ${statusMeta(profile.status).key}`}>{statusMeta(profile.status).label}</span>
              </div>
              <p className="profile-summary">{profile.profile_summary || profile.description}</p>

              {profile.activation || profile.model?.activation ? (
                <div className={`activation-report state-${(profile.activation || profile.model?.activation)?.state}`}>
                  {activationBadge(profile.activation || profile.model?.activation)}
                  <p className="activation-detail">{(profile.activation || profile.model?.activation)?.detail}</p>
                  {(profile.activation || profile.model?.activation)?.key_hint ? (
                    <div className="env key-hint">Key · {(profile.activation || profile.model?.activation)?.key_hint}</div>
                  ) : null}
                </div>
              ) : null}

              <h3 className="profile-section-title">Source</h3>
              <dl className="profile-dl">
                <div>
                  <dt>Origin</dt>
                  <dd>{profile.origin || "—"}</dd>
                </div>
                <div>
                  <dt>Provider</dt>
                  <dd>{profile.model?.display_name || profile.source_name || "—"}</dd>
                </div>
              </dl>
              <div className="link-row">
                {profile.source_url ? (
                  <a className="link-pill primary" href={profile.source_url} target="_blank" rel="noreferrer">
                    Source
                  </a>
                ) : null}
                {profile.docs_url ? (
                  <a className="link-pill" href={profile.docs_url} target="_blank" rel="noreferrer">
                    Docs
                  </a>
                ) : null}
                {profile.model?.console_url ? (
                  <a className="link-pill" href={profile.model.console_url} target="_blank" rel="noreferrer">
                    Console
                  </a>
                ) : null}
                {isScrapers ? (
                  <Link className="link-pill" href="/bots" onClick={closeProfile}>
                    View bots
                  </Link>
                ) : (
                  <Link className="link-pill" href="/scrapers" onClick={closeProfile}>
                    View scrapers
                  </Link>
                )}
              </div>

              <h3 className="profile-section-title">{isScrapers ? "Start / stop" : "Usage & reset"}</h3>
              {isScrapers ? (
                <div className="activation-report">
                  <p className="activation-detail">
                    Use Start cloud worker on this page (needs GITHUB_TOKEN). The same workflow also runs every 15 minutes. Put DATABASE_URL and provider keys in GitHub Action secrets so hunting continues when this PC is off.
                  </p>
                  <div className="link-row" style={{ marginTop: "0.75rem" }}>
                    <button type="button" className="link-pill primary" disabled={!canStart || busy === "start"} onClick={() => void startCloud()}>
                      Start cloud worker
                    </button>
                    <button type="button" className="link-pill" disabled={!canStart || busy === "stop"} onClick={() => void stopCloud()}>
                      Stop
                    </button>
                  </div>
                </div>
              ) : (
                <>
                  {usageCompact(profile.model)}
                  {profile.model?.manual_reset_note ? <p className="muted">{profile.model.manual_reset_note}</p> : null}
                  {profile.model?.profile_summary ? <p className="muted">{profile.model.profile_summary}</p> : null}
                </>
              )}

              <h3 className="profile-section-title">Modules</h3>
              <ul className="mod-list">
                {(profile.modules || []).map((mod) => (
                  <li key={`${mod.path}-${mod.name}`}>
                    <strong>{mod.name}</strong>
                    <span>{mod.purpose}</span>
                    <span className="path">{mod.path}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
