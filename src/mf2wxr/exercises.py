"""Matches MacroFactor exercise names to the exercises in your weightxreps journal."""

import tomllib
from dataclasses import dataclass
from pathlib import Path


class AliasError(ValueError):
    pass


@dataclass(frozen=True)
class Match:
    name: str
    """The name to use on weightxreps."""
    eid: int | None
    """The weightxreps exercise id, or None if the exercise doesn't exist there yet."""


def match_exercises(names: list[str], known: dict[int, str], aliases: dict[str, str] | None = None) -> dict[str, Match]:
    """Map each MacroFactor exercise name to a weightxreps exercise.

    Names match case-insensitively, like they do in the weightxreps editor. An alias renames a MacroFactor
    exercise first, for when your journal already has it under another name.
    """
    aliases = aliases or {}
    ids = {_normalize(name): eid for eid, name in known.items()}

    matches = {}
    for name in names:
        target = aliases.get(name, name)
        matches[name] = Match(target, ids.get(_normalize(target)))
    return matches


def load_aliases(path: Path) -> dict[str, str]:
    """Read `"MacroFactor name" = "weightxreps name"` pairs from a TOML file, if it exists."""
    if not path.exists():
        return {}
    with path.open("rb") as f:
        data = tomllib.load(f)
    aliases = data.get("aliases", data)
    if not all(isinstance(k, str) and isinstance(v, str) for k, v in aliases.items()):
        raise AliasError(f"{path}: aliases must map exercise names to exercise names")
    return aliases


def _normalize(name: str) -> str:
    return name.strip().lower()
