// Build gate. The site must not build unless every registered skill has an artifact
// AND every chart in it matches the shape its renderer expects.
import { readFileSync, existsSync, readdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const dir = join(root, "public", "artifacts");
const catalog = JSON.parse(readFileSync(join(dir, "_catalog.json"), "utf8"));

const problems = [];

for (const s of catalog.skills) {
  const file = join(dir, `${s.skill}.json`);
  if (!existsSync(file)) {
    problems.push(`${s.skill}: artifact missing`);
    continue;
  }
  const a = JSON.parse(readFileSync(file, "utf8"));

  for (const field of ["title", "prescribes", "applied", "takeaway", "code_excerpt"]) {
    if (!a[field]) problems.push(`${s.skill}: empty ${field}`);
  }
  if (!Array.isArray(a.narrative) || a.narrative.length < 2)
    problems.push(`${s.skill}: narrative needs at least two paragraphs`);

  for (const c of a.charts ?? []) {
    const where = `${s.skill}/${c.id}`;
    if (!c.data?.length) {
      problems.push(`${where}: no data`);
      continue;
    }
    const keys = new Set(Object.keys(c.data[0]));

    if (c.kind === "heatmap") {
      // Heatmap renders row x col cells; the value key must exist.
      if (!keys.has("row")) problems.push(`${where}: heatmap rows need a "row" key`);
      if (!keys.has(c.x)) problems.push(`${where}: heatmap rows need the x key "${c.x}"`);
      if (!keys.has(c.series[0]?.key)) problems.push(`${where}: heatmap missing value key`);
    } else if (c.kind === "scatter") {
      if (!keys.has("x") || !keys.has("y")) problems.push(`${where}: scatter rows need x and y`);
    } else {
      if (!keys.has(c.x)) problems.push(`${where}: rows are missing the x key "${c.x}"`);
      for (const ser of c.series) {
        const present = c.data.some((row) => row[ser.key] !== undefined);
        if (!present) problems.push(`${where}: series key "${ser.key}" is in no row`);
      }
    }
    if (!c.series?.length) problems.push(`${where}: no series defined`);
  }

  for (const t of a.tables ?? []) {
    const bad = (t.rows ?? []).filter((r) => r.length !== t.columns.length);
    if (bad.length) problems.push(`${s.skill}/${t.id}: ${bad.length} row(s) do not match the column count`);
  }
}

const files = readdirSync(dir).filter((f) => f.endsWith(".json") && !f.startsWith("_"));

if (problems.length) {
  console.error(`check-artifacts: ${problems.length} problem(s):`);
  problems.forEach((p) => console.error(`  - ${p}`));
  process.exit(1);
}
console.log(
  `check-artifacts: ${files.length} skill artifacts present and well-formed, ${catalog.skills.length} registered.`,
);
