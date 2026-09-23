"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api, type Lead } from "../../../../lib/client";

export default function LeadDetailPage() {
  const params = useParams<{ id: string }>();
  const [lead, setLead] = useState<Lead | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    void api<Lead>(`leads/${params.id}`).then(setLead).catch((err: Error) => setError(err.message));
  }, [params.id]);

  async function toggle() {
    if (!lead) return;
    setBusy(true);
    try {
      const next = await api<Lead>(`leads/${lead.id}`, {
        method: "PATCH",
        body: JSON.stringify({ do_not_contact: !lead.do_not_contact }),
      });
      setLead(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update");
    } finally {
      setBusy(false);
    }
  }

  if (!lead) return <p className="muted">{error || "Loading lead…"}</p>;

  return (
    <>
      <header className="page-head">
        <div>
          <p className="eyebrow">{lead.category} · {lead.location}</p>
          <h1>{lead.name}</h1>
          <p>{lead.company_number}{lead.synthetic ? " · synthetic demo record" : ""}</p>
        </div>
        <div className="score">
          <b style={{ fontSize: 48 }}>{lead.priority_score}</b>
          <span className="band">Band {lead.priority_band}</span>
        </div>
      </header>
      {lead.synthetic ? <div className="notice">Demo data only. The phone numbers are Ofcom drama ranges and the domain is .example.</div> : null}
      {lead.do_not_contact ? <div className="notice">Marked do not contact. CSV export skips this lead unless you include suppressed rows.</div> : null}
      <div className="detail">
        <section className="panel">
          <h2>Record</h2>
          <div className="kv">
            <span>Address</span><div>{lead.address || "—"} {lead.postcode}</div>
            <span>Phone</span><div>{lead.phone || "—"}</div>
            <span>Mobile</span><div>{lead.mobile || "—"}</div>
            <span>Email</span><div>{lead.email || "—"}</div>
            <span>Website</span><div>{lead.has_website ? lead.website : "No website"}</div>
            <span>Incorporated</span><div>{lead.incorporation_date || "—"}</div>
            <span>Registry</span><div>{lead.company_status}</div>
            <span>Trading</span><div>{lead.trading_status}</div>
            <span>SIC</span><div>{(lead.sic_labels || []).join(", ") || (lead.sic_codes || []).join(", ") || "—"}</div>
          </div>
          <div className="btn-row" style={{ marginTop: 18 }}>
            <button className="btn" type="button" disabled={busy} onClick={() => void toggle()}>
              {lead.do_not_contact ? "Clear do not contact" : "Do not contact"}
            </button>
            {lead.job_id ? <Link className="btn" href={`/hunts/${lead.job_id}`}>Open hunt</Link> : null}
          </div>
        </section>
        <div className="stack">
          <section className="panel">
            <h2>Why this score</h2>
            <ul className="reasons">
              {lead.priority_reasons.map((reason) => <li key={reason}>{reason}</li>)}
            </ul>
          </section>
          <section className="panel">
            <h2>Verification</h2>
            <p>{lead.verification_notes}</p>
            <ul className="reasons">
              {(lead.sources || []).map((source, index) => (
                <li key={`${source.provider}-${index}`}>{source.provider}{source.reference ? ` · ${source.reference}` : ""}</li>
              ))}
            </ul>
          </section>
        </div>
      </div>
      {error ? <p className="error">{error}</p> : null}
    </>
  );
}
