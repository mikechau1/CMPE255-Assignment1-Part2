/** Display formatting. Centralised so a duration reads the same everywhere. */

/** "18 min" / "1 h 24 min" -- how a rider thinks about a trip, not raw seconds. */
export function formatDuration(seconds: number): string {
  const total = Math.max(0, Math.round(seconds));
  const h = Math.floor(total / 3600);
  const m = Math.round((total % 3600) / 60);
  if (h > 0) return m > 0 ? `${h} h ${m} min` : `${h} h`;
  if (m >= 1) return `${m} min`;
  return `${total} s`;
}

/** Compact form for axis ticks and dense tables. */
export function formatDurationShort(seconds: number): string {
  const m = Math.round(seconds / 60);
  return m >= 60 ? `${Math.floor(m / 60)}h${String(m % 60).padStart(2, "0")}` : `${m}m`;
}

export function formatCurrency(value: number): string {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
}

export function formatDistance(km: number): string {
  const miles = km / 1.609344;
  return `${km.toFixed(1)} km · ${miles.toFixed(1)} mi`;
}

export function formatClock(iso: string): string {
  return new Date(iso).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
}

export function formatHour(hour: number): string {
  if (hour === 0) return "12a";
  if (hour === 12) return "12p";
  return hour < 12 ? `${hour}a` : `${hour - 12}p`;
}

export function formatNumber(value: number): string {
  return new Intl.NumberFormat("en-US").format(Math.round(value));
}

/** datetime-local input value from a Date, in the browser's own timezone. */
export function toLocalInputValue(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
    `T${pad(date.getHours())}:${pad(date.getMinutes())}`
  );
}

/**
 * Wall-clock ISO string with NO timezone suffix.
 *
 * The API must receive the hour the user actually picked. `Date.toISOString()`
 * converts to UTC, so a 5:30 PM departure would reach the model as 9:30 PM and
 * be scored against the wrong traffic conditions entirely. The model is trained
 * on naive local NYC timestamps, so naive local is what we send.
 */
export function toNaiveLocalISO(date: Date): string {
  return `${toLocalInputValue(date)}:00`;
}

/** Titles a model id: "distance_speed_baseline" -> "Distance speed baseline". */
export function humanizeModel(name: string): string {
  const specials: Record<string, string> = {
    lightgbm: "LightGBM",
    random_forest: "Random forest",
    ridge: "Ridge regression",
    median_baseline: "Median baseline",
    distance_speed_baseline: "Distance ÷ speed",
  };
  return specials[name] ?? name.replace(/_/g, " ");
}
