"use client";

import { useEffect, useState } from "react";
import { applyTheme, resolveTheme, THEME_KEY, type Theme } from "../lib/theme";

export default function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>("day");

  useEffect(() => {
    const next = resolveTheme(localStorage.getItem(THEME_KEY));
    setTheme(next);
    applyTheme(next);
  }, []);

  function toggle() {
    const next: Theme = theme === "night" ? "day" : "night";
    setTheme(next);
    localStorage.setItem(THEME_KEY, next);
    applyTheme(next);
  }

  const toNight = theme === "day";

  return (
    <button
      type="button"
      className="theme-btn"
      onClick={toggle}
      aria-label={toNight ? "Switch to night theme" : "Switch to day theme"}
      title="Day / night"
    >
      <span className="theme-icon" aria-hidden />
      <span className="theme-label">{toNight ? "Night" : "Day"}</span>
    </button>
  );
}
