"use client";

import { useEffect, useState } from "react";
import { api } from "../../../lib/client";

type SecretRow = {
  name: string;
  configured: boolean;
  source: string | null;
  last4: string | null;
  label: string;
  hint: string;
  group: string;
  placement: string;
};

type Settings = {
  demo_mode: boolean;
  database: string;
  supabase_url_set: boolean;
  supabase_key_set: boolean;
  can_edit_secrets: boolean;
  secrets: SecretRow[];
};

const GROUP_LABELS: Record<string, string> = {
  companies_house: "Companies House",
  google_places: "Google Places",
  scrapingbee: "ScrapingBee",
  brightdata: "Bright Data",
};

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function load() {
    setSettings(await api<Settings>("settings"));
  }

  useEffect(() => {
    void load().catch((err: Error) => setError(err.message));
  }, []);

  async function save(name: string) {
    const value = (drafts[name] || "").trim();
    if (!value) return;
    setError("");
    setMessage("");
    try {
      await api("settings/secrets", { method: "POST", body: JSON.stringify({ name, value }) });
      setDrafts((current) => ({ ...current, [name]: "" }));
      setMessage("Stored on the server. The full value is not sent back.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save");
    }
  }

  async function test(provider: string) {
    setError("");
    setMessage("");
    try {
      const result = await api<{ ok: boolean; detail?: string; status?: string }>("settings/test", {
        method: "POST",
        body: JSON.stringify({ provider }),
      });
      setMessage(result.detail || (result.ok ? "Connection succeeded." : "Connection failed."));
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Test failed");
    }
  }

  async function purge() {
    if (!window.confirm("Delete synthetic demo leads?")) return;
    const result = await api<{ deleted: number }>("leads/purge-synthetic", { method: "POST" });
    setMessage(`Removed ${result.deleted} synthetic leads.`);
  }

  const visible = (settings?.secrets || []).filter((row) => row.placement !== "host");
  const groups = [...new Set(visible.map((row) => row.group))];

  return (
    <>
      <header className="page-head">
        <div>
          <p className="eyebrow">Settings</p>
          <h1>Data provider keys</h1>
          <p>Keys stay on the API. This page never receives the full value back. Cloud host keys are on the Hosts page.</p>
        </div>
      </header>
      <div className="notice">
        Database: {settings?.database || "…"}. Demo mode: {settings?.demo_mode ? "on" : "off"}.
        Supabase URL: {settings?.supabase_url_set ? "set" : "not set"}. Service role key: {settings?.supabase_key_set ? "set" : "not set"}.
        Workers read the same database, so a key saved here is available to the next hunt.
      </div>
      {message ? <p className="hint">{message}</p> : null}
      {error ? <p className="error">{error}</p> : null}
      <section className="panel">
        <h2>Supabase</h2>
        <p className="muted">
          Set SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, and SUPABASE_DB_URL in the server environment, then run migrations/001_supabase.sql in the Supabase SQL editor.
          Free plan: 500 MB database, 5 GB egress, project pauses after a week with no activity, two active projects. The anon key is not used.
        </p>
        <button className="btn" type="button" onClick={() => void test("supabase")}>Test connection</button>
      </section>
      {groups.map((group) => (
        <section className="panel" key={group}>
          <div className="split" style={{ alignItems: "center" }}>
            <h2>{GROUP_LABELS[group] || group}</h2>
            <button className="btn" type="button" onClick={() => void test(group)}>Test connection</button>
          </div>
          {visible.filter((row) => row.group === group).map((row) => (
            <div key={row.name} className="field-block">
              <label htmlFor={row.name}>{row.label || row.name}</label>
              <div className="muted">
                {row.hint} {row.configured ? `Configured via ${row.source}${row.last4 ? ` · ···${row.last4}` : ""}.` : "Not set."}
              </div>
              <div className="btn-row" style={{ marginTop: 8 }}>
                <input
                  id={row.name}
                  type="password"
                  aria-label={row.label || row.name}
                  placeholder={settings?.can_edit_secrets ? "Paste a new value" : "Set SECRETS_MASTER_KEY to edit"}
                  value={drafts[row.name] || ""}
                  disabled={!settings?.can_edit_secrets}
                  onChange={(event) => setDrafts((current) => ({ ...current, [row.name]: event.target.value }))}
                />
                <button className="btn" type="button" disabled={!settings?.can_edit_secrets} onClick={() => void save(row.name)}>Save</button>
              </div>
            </div>
          ))}
        </section>
      ))}
      <section className="panel">
        <h2>Demo data</h2>
        <p className="muted">Synthetic leads are labelled and safe to delete before you connect a live provider.</p>
        <button className="btn danger" type="button" onClick={() => void purge()}>Purge synthetic leads</button>
      </section>
    </>
  );
}
