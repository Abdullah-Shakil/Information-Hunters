"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { api, downloadLeads, type Catalogue, type Lead } from "../../../lib/client";

export default function LeadsPage() {
  const router = useRouter();
  const [catalogue, setCatalogue] = useState<Catalogue | null>(null);
  const [items, setItems] = useState<Lead[]>([]);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState("");
  const [filters, setFilters] = useState({
    q: "",
    category: "",
    location: "",
    has_email: false,
    has_mobile: false,
    no_website: false,
    incorporated_after: "",
    min_priority: "",
  });

  const query = useMemo(() => {
    const params = new URLSearchParams();
    if (filters.q) params.set("q", filters.q);
    if (filters.category) params.set("category", filters.category);
    if (filters.location) params.set("location", filters.location);
    if (filters.has_email) params.set("has_email", "true");
    if (filters.has_mobile) params.set("has_mobile", "true");
    if (filters.no_website) params.set("no_website", "true");
    if (filters.incorporated_after) params.set("incorporated_after", filters.incorporated_after);
    if (filters.min_priority) params.set("min_priority", filters.min_priority);
    const text = params.toString();
    return text ? `?${text}` : "";
  }, [filters]);

  useEffect(() => {
    void api<Catalogue>("categories").then(setCatalogue).catch((err: Error) => setError(err.message));
  }, []);

  useEffect(() => {
    let stop = false;
    const load = async () => {
      try {
        const data = await api<{ items: Lead[]; total: number }>(`leads${query}`);
        if (stop) return;
        setItems(data.items);
        setTotal(data.total);
        setError("");
      } catch (err) {
        if (!stop) setError(err instanceof Error ? err.message : "Could not load leads");
      }
    };
    void load();
    const timer = setInterval(() => void load(), 4000);
    return () => {
      stop = true;
      clearInterval(timer);
    };
  }, [query]);

  function set<K extends keyof typeof filters>(key: K, value: (typeof filters)[K]) {
    setFilters((current) => ({ ...current, [key]: value }));
  }

  return (
    <>
      <header className="page-head">
        <div>
          <p className="eyebrow">Leads</p>
          <h1>Qualified companies</h1>
          <p>{total} matching. Sorted by priority.</p>
        </div>
        <button className="btn" type="button" onClick={() => void downloadLeads(query).catch((err: Error) => setError(err.message))}>
          Export CSV
        </button>
      </header>
      {items.some((lead) => lead.synthetic) ? (
        <div className="notice">These rows include synthetic demo records. They use reserved .example domains and Ofcom drama numbers. Do not contact them.</div>
      ) : null}
      <div className="filters">
        <div className="field">
          <label htmlFor="q">Name</label>
          <input id="q" value={filters.q} onChange={(event) => set("q", event.target.value)} placeholder="Harbour" />
        </div>
        <div className="field">
          <label htmlFor="category">Category</label>
          <select id="category" value={filters.category} onChange={(event) => set("category", event.target.value)}>
            <option value="">Any</option>
            {catalogue?.categories.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
          </select>
        </div>
        <div className="field">
          <label htmlFor="location">Location</label>
          <select id="location" value={filters.location} onChange={(event) => set("location", event.target.value)}>
            <option value="">Any</option>
            {catalogue?.regions.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
          </select>
        </div>
        <div className="field">
          <label htmlFor="after">Incorporated after</label>
          <input id="after" type="date" value={filters.incorporated_after} onChange={(event) => set("incorporated_after", event.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="priority">Minimum priority</label>
          <input id="priority" type="number" min={0} max={100} value={filters.min_priority} onChange={(event) => set("min_priority", event.target.value)} />
        </div>
        <label className="field check"><input type="checkbox" checked={filters.has_email} onChange={(event) => set("has_email", event.target.checked)} /> Has email</label>
        <label className="field check"><input type="checkbox" checked={filters.has_mobile} onChange={(event) => set("has_mobile", event.target.checked)} /> Has mobile</label>
        <label className="field check"><input type="checkbox" checked={filters.no_website} onChange={(event) => set("no_website", event.target.checked)} /> No website</label>
      </div>
      {error ? <p className="error">{error}</p> : null}
      <div className="panel">
        <table>
          <thead>
            <tr>
              <th>Company</th>
              <th>Category</th>
              <th>Phone</th>
              <th>Email</th>
              <th>Website</th>
              <th>Priority</th>
            </tr>
          </thead>
          <tbody>
            {items.map((lead) => (
              <tr key={lead.id} className="clickable" onClick={() => router.push(`/leads/${lead.id}`)}>
                <td>
                  <strong>{lead.name}</strong>
                  <div className="muted">{lead.location}{lead.do_not_contact ? " · do not contact" : ""}</div>
                </td>
                <td>{lead.category}</td>
                <td>{lead.mobile || lead.phone || "—"}</td>
                <td>{lead.email || "—"}</td>
                <td>{lead.has_website ? "Yes" : "No"}</td>
                <td>
                  <div className="score">
                    <b>{lead.priority_score}</b>
                    <span className="bar" aria-hidden><span style={{ width: `${lead.priority_score}%` }} /></span>
                    <span className="band">{lead.priority_band}</span>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {items.length === 0 ? <p className="muted">No leads match these filters.</p> : null}
      </div>
    </>
  );
}
