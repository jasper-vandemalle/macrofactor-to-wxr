from dataclasses import dataclass, field
from datetime import date


@dataclass
class Set:
    weight_kg: float
    reps: int
    distance_m: float | None = None
    rpe: float | None = None


@dataclass
class Exercise:
    name: str
    sets: list[Set] = field(default_factory=list)

    @property
    def is_distance(self) -> bool:
        return bool(self.sets) and self.sets[0].distance_m is not None


@dataclass
class Workout:
    date: date
    name: str
    exercises: list[Exercise]
    bodyweight_kg: float | None = None


WEIGHTED_BODYWEIGHT_KEYWORDS = (
    "pull-up",
    "pull up",
    "pullup",
    "chin-up",
    "chin up",
    "chinup",
    "muscle-up",
    "muscle up",
    "dip",
)


def is_weighted_bodyweight(exercise_name: str) -> bool:
    """Pull-ups, dips and the like, where MacroFactor records only the weight added to your bodyweight."""
    name = exercise_name.lower()
    return any(keyword in name for keyword in WEIGHTED_BODYWEIGHT_KEYWORDS)
