"""Load and run the helper scripts that ship inside the installed skills.

21 of the 46 skills bundle real Python (`cohort_builder.py`, `ab_test_analyzer.py`,
`saas_metrics.py`, ...). Where a skill ships code, the demo calls *that* code on
Kaggle data instead of reimplementing it -- that is the strongest possible
demonstration that the skill works.
"""
from __future__ import annotations
import importlib.util, sys, types

from .paths import SKILLS


def load(skill: str, script: str) -> types.ModuleType:
    """Import `<skill>/**/scripts/<script>.py` as a module.

    Two upstream skills nest their folder twice (metric-reconciliation,
    schema-mapper), so the script is located by glob rather than a fixed path.
    """
    stem = script[:-3] if script.endswith(".py") else script
    matches = sorted((SKILLS / skill).rglob(f"{stem}.py"))
    if not matches:
        raise FileNotFoundError(f"{skill}: no bundled script named {stem}.py")
    path = matches[0]
    mod_name = f"skillscript_{skill.replace('-', '_')}_{stem}"
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    mod.__skill_path__ = path.relative_to(SKILLS).as_posix()
    return mod


def ref(skill: str, script: str) -> str:
    """Repo-relative path of a bundled script, for the `used_skill_scripts` field."""
    stem = script[:-3] if script.endswith(".py") else script
    matches = sorted((SKILLS / skill).rglob(f"{stem}.py"))
    if not matches:
        raise FileNotFoundError(f"{skill}: no bundled script named {stem}.py")
    return f".claude/skills/{matches[0].relative_to(SKILLS).as_posix()}"


def read_doc(skill: str, filename: str, max_chars: int = 4000) -> str:
    """Read a bundled markdown reference (templates, guides) from a skill."""
    matches = sorted((SKILLS / skill).rglob(filename))
    if not matches:
        raise FileNotFoundError(f"{skill}: no bundled doc named {filename}")
    return matches[0].read_text(encoding="utf-8", errors="replace")[:max_chars]
