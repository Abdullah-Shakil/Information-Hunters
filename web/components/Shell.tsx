"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "../lib/client";

const LINKS = [
  ["/", "Overview"],
  ["/leads", "Leads"],
  ["/hunts", "Hunts"],
  ["/hosts", "Hosts"],
  ["/activity", "Live Activity"],
  ["/performance", "Performance"],
  ["/settings", "Settings"],
];

export default function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [live, setLive] = useState(false);
  const [workerLabel, setWorkerLabel] = useState("No worker seen");

  useEffect(() => {
    let stop = false;
    const load = async () => {
      try {
        const stats = await api<{ workers: { id: string; last_seen: string | null }[] }>("stats");
        if (stop) return;
        const recent = stats.workers.find((worker) => {
          if (!worker.last_seen) return false;
          return Date.now() - new Date(worker.last_seen).getTime() < 15000;
        });
        setLive(Boolean(recent));
        setWorkerLabel(recent ? `Worker ${recent.id.split("-").slice(-1)}` : "No worker seen");
      } catch {
        if (!stop) setLive(false);
      }
    };
    void load();
    const timer = setInterval(() => void load(), 5000);
    return () => {
      stop = true;
      clearInterval(timer);
    };
  }, []);

  async function logout() {
    await fetch("/api/logout", { method: "POST" });
    router.push("/login");
    router.refresh();
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="mark" aria-hidden>
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
              <circle cx="8" cy="8" r="4.5" stroke="#e2b657" strokeWidth="1.4" />
              <path d="M11.2 11.2 L15 15" stroke="#e2b657" strokeWidth="1.4" strokeLinecap="round" />
            </svg>
          </div>
          <div>
            <strong>Information Hunters</strong>
            <span>Lead desk</span>
          </div>
        </div>
        <nav className="nav">
          {LINKS.map(([href, label]) => {
            const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
            return (
              <Link key={href} href={href} className={active ? "active" : ""}>
                {label}
              </Link>
            );
          })}
        </nav>
        <footer>
          <div className={live ? "worker-dot live" : "worker-dot"}>
            <i />
            {workerLabel}
          </div>
          <button className="btn ghost" type="button" onClick={() => void logout()}>
            Sign out
          </button>
        </footer>
      </aside>
      <div className="main">{children}</div>
    </div>
  );
}
