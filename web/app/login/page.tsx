"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export default function LoginPage() {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const showHint = process.env.NEXT_PUBLIC_DEMO_HINT === "true";

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const response = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    });
    setBusy(false);
    if (!response.ok) {
      setError("That password was not accepted.");
      return;
    }
    router.push("/");
    router.refresh();
  }

  return (
    <div className="login">
      <section className="login-copy">
        <div>
          <p className="eyebrow">Information Hunters</p>
          <h1>Find the trades that still need a website.</h1>
        </div>
        <p className="lede">
          A control plane for UK company discovery. Hunts run on a worker, so the search continues when this browser is closed.
        </p>
      </section>
      <section className="login-panel">
        <form className="card" onSubmit={submit}>
          <p className="eyebrow">Desk access</p>
          <h2 style={{ fontFamily: "var(--serif)", fontWeight: 560, fontSize: 32, margin: "0 0 8px" }}>Sign in</h2>
          <p className="hint">Local password gate. Replace it before anyone else can reach this service.</p>
          <div style={{ height: 16 }} />
          <label htmlFor="password">Password</label>
          <input id="password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoFocus required />
          {showHint ? <p className="hint">Demo password: hunter-demo</p> : null}
          {error ? <p className="error">{error}</p> : null}
          <div style={{ height: 16 }} />
          <button className="btn primary" type="submit" disabled={busy}>
            {busy ? "Checking…" : "Enter the desk"}
          </button>
        </form>
      </section>
    </div>
  );
}
