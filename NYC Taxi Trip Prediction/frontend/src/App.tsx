import { useEffect, useState } from "react";
import { useTheme } from "./hooks/useTheme";
import { api } from "./lib/api";
import type { HealthResponse } from "./lib/types";
import { Estimator } from "./pages/Estimator";
import { Insights } from "./pages/Insights";
import { ModelPage } from "./pages/ModelPage";

type Tab = "estimator" | "insights" | "model";

const TABS: { id: Tab; label: string }[] = [
  { id: "estimator", label: "Estimator" },
  { id: "insights", label: "Insights" },
  { id: "model", label: "Model" },
];

export default function App() {
  const { theme, toggle } = useTheme();
  const [tab, setTab] = useState<Tab>("estimator");
  const [health, setHealth] = useState<HealthResponse | null>(null);

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null));
  }, []);

  return (
    <div className="relative h-full overflow-hidden bg-bg">
      <header className="glass absolute inset-x-0 top-0 z-30 flex h-[52px] items-center justify-between px-4">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span
              aria-hidden
              className="grid h-6 w-6 place-items-center rounded-md bg-accent text-[13px] font-bold text-black"
            >
              N
            </span>
            <span className="text-[13.5px] font-semibold tracking-tight text-ink">
              NYC Taxi Trip Prediction
            </span>
          </div>
          <span className="hidden text-[11px] text-faint sm:inline">
            duration · uncertainty · metered fare
          </span>
        </div>

        <nav className="flex items-center gap-1">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              aria-current={tab === t.id ? "page" : undefined}
              className={`rounded-lg px-3 py-1.5 text-[12.5px] transition ${
                tab === t.id
                  ? "bg-accent/15 text-accent-ink"
                  : "text-dim hover:bg-line/60 hover:text-ink"
              }`}
            >
              {t.label}
            </button>
          ))}

          <span className="mx-2 hidden h-4 w-px bg-line sm:block" />

          {health && (
            <span
              className="hidden items-center gap-1.5 text-[11px] text-faint sm:flex"
              title={
                health.model_loaded
                  ? `Model ${health.model_version} · source ${health.data_source}`
                  : (health.detail ?? "No model loaded")
              }
            >
              <span
                className={`h-1.5 w-1.5 rounded-full ${
                  health.model_loaded ? "bg-good" : "bg-warn"
                }`}
              />
              {health.model_loaded ? health.data_source : "no model"}
            </span>
          )}

          <button
            onClick={toggle}
            aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
            className="ml-1 rounded-lg border border-line px-2 py-1.5 text-[12px] text-dim transition hover:border-accent/50 hover:text-ink"
          >
            {theme === "dark" ? "☀" : "☾"}
          </button>
        </nav>
      </header>

      {/* Each tab owns a full-bleed map, so they are mounted exclusively
          rather than hidden -- two live GL contexts is a real cost. */}
      {tab === "estimator" && <Estimator theme={theme} />}
      {tab === "insights" && <Insights theme={theme} />}
      {tab === "model" && (
        <div className="absolute inset-0 top-[52px] overflow-y-auto">
          <ModelPage />
        </div>
      )}
    </div>
  );
}
