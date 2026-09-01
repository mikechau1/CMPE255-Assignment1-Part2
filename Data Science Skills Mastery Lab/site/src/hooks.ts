import { useEffect, useState } from "react";
import type { Catalog, SkillArtifact } from "./types";

const BASE = import.meta.env.BASE_URL;
const cache = new Map<string, unknown>();

async function getJson<T>(path: string): Promise<T> {
  if (cache.has(path)) return cache.get(path) as T;
  const res = await fetch(`${BASE}artifacts/${path}`);
  if (!res.ok) throw new Error(`${path}: ${res.status}`);
  const data = (await res.json()) as T;
  cache.set(path, data);
  return data;
}

export function useCatalog() {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    getJson<Catalog>("_catalog.json").then(setCatalog).catch((e) => setError(String(e)));
  }, []);
  return { catalog, error };
}

export function useArtifact(skill: string | undefined) {
  const [artifact, setArtifact] = useState<SkillArtifact | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (!skill) return;
    setArtifact(null);
    setError(null);
    getJson<SkillArtifact>(`${skill}.json`).then(setArtifact).catch((e) => setError(String(e)));
  }, [skill]);
  return { artifact, error };
}

export function useAllArtifacts(skills: string[]) {
  const [items, setItems] = useState<SkillArtifact[]>([]);
  const key = skills.join(",");
  useEffect(() => {
    if (!skills.length) return;
    Promise.all(skills.map((s) => getJson<SkillArtifact>(`${s}.json`).catch(() => null))).then((r) =>
      setItems(r.filter(Boolean) as SkillArtifact[]),
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return items;
}
