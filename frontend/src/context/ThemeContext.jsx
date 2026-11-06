import { useCallback, useEffect, useState } from "react";
import { ThemeContext } from "./theme";

const STORAGE_KEY = "fl-theme";

function readSaved() {
  try {
    const value = localStorage.getItem(STORAGE_KEY);
    return value === "light" || value === "dark" ? value : "system";
  } catch {
    return "system";
  }
}

/** Theme preference: "system" follows the OS; "light"/"dark" set <html data-theme>. */
export function ThemeProvider({ children }) {
  const [theme, setThemeState] = useState(readSaved);

  useEffect(() => {
    const root = document.documentElement;
    if (theme === "system") delete root.dataset.theme;
    else root.dataset.theme = theme;
    try {
      if (theme === "system") localStorage.removeItem(STORAGE_KEY);
      else localStorage.setItem(STORAGE_KEY, theme);
    } catch {
      // Storage can be blocked (private window); the choice still applies for this visit.
    }
  }, [theme]);

  const setTheme = useCallback((value) => setThemeState(value), []);
  return <ThemeContext.Provider value={{ theme, setTheme }}>{children}</ThemeContext.Provider>;
}
