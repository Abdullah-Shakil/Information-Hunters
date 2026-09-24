"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import ThemeToggle from "./ThemeToggle";

const LINKS = [
  ["/", "Overview"],
  ["/leads", "Leads"],
  ["/hunts", "Hunts"],
  ["/scrapers", "Scrapers"],
  ["/bots", "Bots"],
  ["/hosts", "Hosts"],
  ["/activity", "Activity"],
  ["/performance", "Performance"],
  ["/settings", "Settings"],
];

export default function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="shell">
      <div className="atmosphere" aria-hidden>
        <div className="atmosphere-grid" />
        <div className="atmosphere-glow" />
      </div>

      <header className="top">
        <Link className="brand" href="/" aria-label="Information Hunters home">
          <span className="brand-mark">Hunters</span>
          <span className="brand-sub">Desk</span>
        </Link>
        <nav className="nav" aria-label="Primary">
          {LINKS.map(([href, label]) => {
            const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
            return (
              <Link key={href} href={href} className={active ? "nav-btn is-active" : "nav-btn"}>
                {label}
              </Link>
            );
          })}
        </nav>
        <div className="top-actions">
          <ThemeToggle />
          <Link className="run-btn cloud-header" href="/hunts">
            New hunt
          </Link>
        </div>
      </header>

      <main className="main">{children}</main>
    </div>
  );
}
