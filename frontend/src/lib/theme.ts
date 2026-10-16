// Appearance choice: "system" (the default) follows the device; "light" or "dark" is the
// person's override, stored in <html data-theme> and remembered in this browser only.
// The inline script in layout.tsx applies a saved choice before the first paint.

export type Theme = "system" | "light" | "dark";

export const THEME_KEY = "marketlens-theme";

const SURFACE = { light: "#f2f2f7", dark: "#000000" } as const;

const listeners = new Set<() => void>();

export function getTheme(): Theme {
  const t = document.documentElement.dataset.theme;
  return t === "light" || t === "dark" ? t : "system";
}

/** The browser chrome color (theme-color metas) follows the page, forced or not. */
export function syncThemeColor(theme: Theme) {
  document.querySelectorAll<HTMLMetaElement>('meta[name="theme-color"]').forEach((meta) => {
    const media = meta.media.includes("dark") ? "dark" : "light";
    meta.content = SURFACE[theme === "system" ? media : theme];
  });
}

export function setTheme(theme: Theme) {
  // Cross-fade the change where View Transitions exist and motion is welcome.
  const fade =
    "startViewTransition" in document &&
    !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (fade) document.startViewTransition(() => apply(theme));
  else apply(theme);
}

function apply(theme: Theme) {
  const root = document.documentElement;
  if (theme === "system") delete root.dataset.theme;
  else root.dataset.theme = theme;
  try {
    if (theme === "system") localStorage.removeItem(THEME_KEY);
    else localStorage.setItem(THEME_KEY, theme);
  } catch {
    // storage blocked (private mode): the choice lasts for this page only
  }
  syncThemeColor(theme);
  listeners.forEach((listener) => listener());
}

export function subscribeTheme(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** Runs before React, in <body>: apply a saved choice so the page never flashes. */
export const THEME_SCRIPT = `try{var t=localStorage.getItem("${THEME_KEY}");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t}catch(e){}`;
