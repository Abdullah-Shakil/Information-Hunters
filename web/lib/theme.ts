export type Theme = "day" | "night";

export const THEME_KEY = "ih-theme";

export function resolveTheme(stored: string | null): Theme {
  if (stored === "day" || stored === "night") return stored;
  // Migrate older values
  if (stored === "light") return "day";
  if (stored === "dark") return "night";
  if (typeof window !== "undefined" && window.matchMedia("(prefers-color-scheme: dark)").matches) {
    return "night";
  }
  return "day";
}

export function applyTheme(theme: Theme) {
  document.documentElement.setAttribute("data-theme", theme);
  document.documentElement.style.colorScheme = theme === "night" ? "dark" : "light";
}
