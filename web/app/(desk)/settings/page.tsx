"use client";

import { useEffect, useState } from "react";
import { api } from "../../../lib/client";

type SecretRow = { name: string; configured: boolean; source: string | null; last4: string | null };
type Settings = { demo_mode: boolean; database: string; can_edit_secrets: boolean; secrets: SecretRow[] };

const LABELS: Record<string, string> = {
  COMPANIES_HOUSE_API_KEY: "Companies House",
  GOOGLE_PLACES_API_KEY: "Google Places",
  SCRAPINGBEE_API_KEY: "ScrapingBee",
  BRIGHTDATA_API_TOKEN: "Bright Data token",
  BRIGHTDATA_ZONE: "Bright Data zone",
  APIFY_TOKEN: "Apify token",
  APIFY_ACTOR_ID: "Apify actor id",
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
      await api(`settings/secrets`, { method: "POST", body: JSON.stringify({ name, value }) });
      setDrafts((current) => ({ ...current, [name]: "" }));
      setMessage(`${LABELS[name] || name} stored on the server.`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save");
    }
  }

  async function purge() {
    if (!window.confirm("Delete synthetic demo leads?")) return;
    const result = await api<{ deleted: number }>("leads/purge-synthetic", { method: "POST" });
    setMessage(`Removed ${result.deleted} synthetic leads.`);
  }

  return (
    <>
      <header className="page-head">
        <div>
          <p className="eyebrow">Settings</p>
          <h1>Server secrets</h1>
          <p>Keys stay on the API. This page never receives the full value back.</p>
        </div>
      </header>
      <div className="notice">
        Database: {settings?.database || "…"}. Demo mode: {settings?.demo_mode ? "on" : "off"}.
        Workers read the same database, so a key saved here is available to the next hunt without putting it in the browser bundle.
      </div>
      {message ? <p className="hint">{message}</p> : null}
      {error ? <p className="error">{error}</p> : null}
      <section className="panel">
        {(settings?.secrets || []).map((row) => (
          <div key={row.name} className="split" style={{ alignItems: "end", marginBottom: 14 }}>
            <div>
              <strong>{LABELS[row.name] || row.name}</strong>
              <div className="muted">
                {row.configured ? `Configured via ${row.source}${row.last4 ? ` · ···${row.last4}` : ""}` : "Not set"}
              </div>
            </div>
            <div className="btn-row">
              <input
                type="password"
                aria-label={LABELS[row.name] || row.name}
                placeholder={settings?.can_edit_secrets ? "Paste a new value" : "Set SECRETS_MASTER_KEY to edit"}
                value={drafts[row.name] || ""}
                disabled={!settings?.can_edit_secrets}
                onChange={(event) => setDrafts((current) => ({ ...current, [row.name]: event.target.value }))}
              />
              <button className="btn" type="button" disabled={!settings?.can_edit_secrets} onClick={() => void save(row.name)}>
                Save
              </button>
            </div>
          </div>
        ))}
      </section>
      <section className="panel">
        <h2>Demo data</h2>
        <p className="muted">Synthetic leads are labelled and safe to delete before you connect a live provider.</p>
        <button className="btn danger" type="button" onClick={() => void purge()}>Purge synthetic leads</button>
      </section>
    </>
  );
}
