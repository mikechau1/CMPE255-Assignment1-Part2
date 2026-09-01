"""One serializer for every skill demo.

Each demo returns a `SkillResult`; `emit()` validates it and writes
`site/public/artifacts/<skill>.json`. The React site has exactly one renderer
because every skill produces exactly this shape.
"""
from __future__ import annotations
import dataclasses, json, math, datetime as _dt
from dataclasses import dataclass, field
from typing import Any

from .paths import SITE_ARTIFACTS

CHART_KINDS = {"line", "bar", "hbar", "stacked-bar", "area", "scatter", "heatmap", "funnel", "pie"}


@dataclass
class Chart:
    id: str
    kind: str
    title: str
    data: list[dict]
    x: str = "x"
    series: list[dict] = field(default_factory=list)   # [{"key": "...", "label": "..."}]
    subtitle: str = ""
    xLabel: str = ""
    yLabel: str = ""
    note: str = ""
    valueFormat: str = "number"                        # number | percent | currency | compact
    domain: list[float] | None = None


@dataclass
class Table:
    id: str
    title: str
    columns: list[str]
    rows: list[list]
    note: str = ""


@dataclass
class Kpi:
    label: str
    value: str
    caption: str = ""
    tone: str = "neutral"                              # neutral | good | warn | bad


@dataclass
class SkillResult:
    skill: str
    source: str                                        # agent-ml-skills | data-analytics-skills
    category: str
    phase: int                                         # 1..6 CRISP-DM
    track: str                                         # dataset track label
    title: str
    prescribes: str                                    # what the SKILL.md asks for
    applied: str                                       # what this lab actually ran
    narrative: list[str] = field(default_factory=list)
    kpis: list[Kpi] = field(default_factory=list)
    charts: list[Chart] = field(default_factory=list)
    tables: list[Table] = field(default_factory=list)
    code_excerpt: str = ""
    code_language: str = "python"
    takeaway: str = ""
    used_skill_scripts: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)


def _clean(o: Any):
    """JSON-safe: numpy scalars -> python, NaN/inf -> None."""
    if isinstance(o, float):
        return None if (math.isnan(o) or math.isinf(o)) else round(o, 6)
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if hasattr(o, "item") and not isinstance(o, (str, bytes)):
        try:
            return _clean(o.item())
        except Exception:
            pass
    if isinstance(o, (_dt.date, _dt.datetime)):
        return o.isoformat()
    if o is None or isinstance(o, (str, int, bool)):
        return o
    return str(o)


def emit(result: SkillResult) -> str:
    for c in result.charts:
        if c.kind not in CHART_KINDS:
            raise ValueError(f"{result.skill}: unknown chart kind {c.kind!r}")
        if not c.data:
            raise ValueError(f"{result.skill}: chart {c.id} has no data")
    if not result.narrative:
        raise ValueError(f"{result.skill}: narrative is required")
    if not result.takeaway:
        raise ValueError(f"{result.skill}: takeaway is required")

    payload = _clean(dataclasses.asdict(result))
    payload["generated_at"] = _dt.datetime.now().isoformat(timespec="seconds")
    out = SITE_ARTIFACTS / f"{result.skill}.json"
    out.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print(f"  [emit] {result.skill:38s} -> {out.relative_to(SITE_ARTIFACTS.parents[2])}")
    return str(out)
