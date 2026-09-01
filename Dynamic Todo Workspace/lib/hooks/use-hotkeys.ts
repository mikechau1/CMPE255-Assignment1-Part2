"use client";

import * as React from "react";

/**
 * Global keyboard shortcuts.
 *
 * Keys are written as "n", "/", "?", "mod+k", "shift+d" — `mod` is Cmd on
 * macOS and Ctrl elsewhere. Plain single-key shortcuts are suppressed while the
 * user is typing; combinations and Escape still fire, so Cmd+K opens the
 * palette from anywhere.
 */
export type HotkeyMap = Record<string, (event: KeyboardEvent) => void>;

function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (target.isContentEditable) return true;
  const tag = target.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";
}

function normalizeEvent(event: KeyboardEvent): string[] {
  const parts: string[] = [];
  if (event.metaKey || event.ctrlKey) parts.push("mod");
  if (event.altKey) parts.push("alt");
  if (event.shiftKey) parts.push("shift");

  const key = event.key.length === 1 ? event.key.toLowerCase() : event.key;
  parts.push(key);

  const combos = [parts.join("+")];
  // "?" arrives as shift+/ on most layouts; accept it written either way.
  if (event.shiftKey && key !== "Shift") {
    combos.push(parts.filter((part) => part !== "shift").join("+"));
  }
  return combos;
}

export function useHotkeys(map: HotkeyMap, enabled = true): void {
  const mapRef = React.useRef(map);
  mapRef.current = map;

  React.useEffect(() => {
    if (!enabled) return;

    function onKeyDown(event: KeyboardEvent) {
      if (event.repeat) return;

      const combos = normalizeEvent(event);
      const typing = isTypingTarget(event.target);

      for (const combo of combos) {
        const handler = mapRef.current[combo];
        if (!handler) continue;

        const isCombination = combo.includes("+");
        if (typing && !isCombination && combo !== "Escape") continue;

        event.preventDefault();
        handler(event);
        return;
      }
    }

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [enabled]);
}

/** True on Apple platforms, so shortcut hints can show ⌘ instead of Ctrl. */
export function useIsMac(): boolean {
  const [isMac, setIsMac] = React.useState(false);
  React.useEffect(() => {
    setIsMac(/Mac|iPhone|iPad/.test(navigator.platform ?? navigator.userAgent));
  }, []);
  return isMac;
}
