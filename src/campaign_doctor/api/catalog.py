"""Allow-list of synthetic scenario files.

The id in the URL is never used as a path. Display name and problem category
live here. The event description is read from the scenario file.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from campaign_doctor.models import Scenario, load_scenario


@dataclass(frozen=True)
class ScenarioEntry:
    scenario_id: str
    name: str
    problem_category: str
    filename: str


# One row per file we are willing to serve. Add a row when a new synthetic
# file is checked in. Do not accept a filename from the request.
_ENTRIES: tuple[ScenarioEntry, ...] = (
    ScenarioEntry(
        scenario_id="delayed_reply",
        name="Delayed reply notification",
        problem_category="delayed_reply",
        filename="delayed_reply.json",
    ),
)


class ScenarioNotFound(Exception):
    """The id is not in the allow-list."""


@dataclass(frozen=True)
class LoadedScenario:
    entry: ScenarioEntry
    scenario: Scenario


def list_entries() -> tuple[ScenarioEntry, ...]:
    return _ENTRIES


def load_entry(scenario_id: str) -> LoadedScenario:
    entry = _find(scenario_id)
    if entry is None:
        raise ScenarioNotFound()
    scenario = load_scenario(_scenario_file(entry.filename))
    return LoadedScenario(entry=entry, scenario=scenario)


def _find(scenario_id: str) -> ScenarioEntry | None:
    for entry in _ENTRIES:
        if entry.scenario_id == scenario_id:
            return entry
    return None


def _scenario_file(filename: str) -> Path:
    """Find an allow-listed file. The URL id is never joined onto a path."""
    if not filename or Path(filename).name != filename:
        raise ScenarioNotFound()
    override = os.environ.get("SCENARIO_DIR", "").strip()
    if override:
        path = Path(override) / filename
        if path.is_file():
            return path
        raise ScenarioNotFound()
    for directory in _scenario_directories():
        path = directory / filename
        if path.is_file():
            return path
    raise ScenarioNotFound()


def _scenario_directories() -> tuple[Path, ...]:
    here = Path(__file__).resolve()
    # Checkout layout: <repo>/src/campaign_doctor/api/catalog.py
    checkout = here.parents[3] / "scenarios" if len(here.parents) > 3 else None
    packaged = here.parents[1] / "scenarios"
    return tuple(
        directory
        for directory in (checkout, Path.cwd() / "scenarios", packaged)
        if directory is not None
    )
