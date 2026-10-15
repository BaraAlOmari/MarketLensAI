"use client";

import { useEffect, useRef, useSyncExternalStore } from "react";

import { getTheme, setTheme, subscribeTheme, syncThemeColor, type Theme } from "@/lib/theme";

import { AutoIcon, MoonIcon, SunIcon } from "./icons";

const OPTIONS: { value: Theme; label: string; Icon: typeof SunIcon }[] = [
  { value: "system", label: "Match system", Icon: AutoIcon },
  { value: "light", label: "Light", Icon: SunIcon },
  { value: "dark", label: "Dark", Icon: MoonIcon },
];

/**
 * Appearance as an iOS segmented control (segmented-controls.md): a gray track with the
 * selected segment raised. A radio group for assistive tech, with arrow-key movement.
 */
export function ThemeSwitch() {
  const theme = useSyncExternalStore(subscribeTheme, getTheme, () => "system" as Theme);
  const refs = useRef<(HTMLButtonElement | null)[]>([]);

  useEffect(() => syncThemeColor(getTheme()), []);

  function move(from: number, step: number) {
    const next = (from + step + OPTIONS.length) % OPTIONS.length;
    setTheme(OPTIONS[next].value);
    refs.current[next]?.focus();
  }

  return (
    <div
      role="radiogroup"
      aria-label="Appearance"
      className="flex h-8 items-center rounded-full bg-fill p-0.5"
    >
      {OPTIONS.map(({ value, label, Icon }, i) => {
        const selected = theme === value;
        return (
          <button
            key={value}
            ref={(el) => {
              refs.current[i] = el;
            }}
            type="button"
            role="radio"
            aria-checked={selected}
            aria-label={label}
            title={label}
            tabIndex={selected ? 0 : -1}
            onClick={() => setTheme(value)}
            onKeyDown={(e) => {
              if (e.key === "ArrowRight" || e.key === "ArrowDown") {
                e.preventDefault();
                move(i, 1);
              } else if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
                e.preventDefault();
                move(i, -1);
              }
            }}
            className={`flex h-7 w-9 items-center justify-center rounded-full transition-colors duration-200 motion-reduce:transition-none ${
              selected
                ? "bg-thumb text-content shadow-[0_1px_3px_rgb(0_0_0/0.12),0_1px_1px_rgb(0_0_0/0.06)]"
                : "text-secondary hover:text-content"
            }`}
          >
            <Icon size={16} />
          </button>
        );
      })}
    </div>
  );
}
