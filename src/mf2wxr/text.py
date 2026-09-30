"""Formats a workout the way you'd type it in the weightxreps editor."""

from mf2wxr.model import Exercise, Set, Workout, is_weighted_bodyweight


def to_text(workout: Workout) -> str:
    lines = [workout.date.strftime("%Y-%m-%d")]
    if workout.bodyweight_kg:
        lines.append(f"@ {round(workout.bodyweight_kg, 1)} bw")
    lines += ["", workout.name, ""]

    for exercise in workout.exercises:
        lines.append(f"#{exercise.name}")
        lines += _exercise_lines(exercise)
        lines.append("")

    return "\n".join(lines)


def _exercise_lines(exercise: Exercise) -> list[str]:
    if exercise.is_distance:
        return _distance_lines(exercise.sets)
    return _set_lines(exercise.sets, is_weighted_bodyweight(exercise.name))


def _number(value: float) -> str:
    """12.0 -> '12', 12.5 -> '12.5'"""
    return str(int(value)) if value == int(value) else str(value)


def _weight(weight: float, added_to_bodyweight: bool = False) -> str:
    if weight == 0:
        return "BW"
    return f"BW+{_number(weight)}" if added_to_bodyweight else _number(weight)


def _rpe_suffix(run: list[Set], collapse: bool = True) -> str:
    """' @9' or ' @8, 8.5, 9'; empty if any set in the run has no RPE.

    Only collapse identical RPEs when the line is a single value repeated with `x N`.
    A comma-separated list of reps or weights needs one RPE per entry, even if they're all the same,
    so you can tell which set each belongs to.
    """
    rpes = [s.rpe for s in run]
    if any(r is None for r in rpes):
        return ""
    if collapse and len(set(rpes)) == 1:
        return f" @{_number(rpes[0])}"
    return " @" + ", ".join(_number(r) for r in rpes)


def _distance_lines(sets: list[Set]) -> list[str]:
    """`100x60m x 3` for identical consecutive sets."""
    lines = []
    i = 0
    while i < len(sets):
        current = sets[i]
        count = 1
        while (
            i + count < len(sets)
            and sets[i + count].weight_kg == current.weight_kg
            and sets[i + count].distance_m == current.distance_m
        ):
            count += 1

        line = f"{_weight(current.weight_kg)}x{_number(current.distance_m)}m"
        if count > 1:
            line += f" x {count}"
        lines.append(line + _rpe_suffix(sets[i : i + count]))
        i += count
    return lines


def _set_lines(sets: list[Set], added_to_bodyweight: bool) -> list[str]:
    """Group sets into the editor's compact notation.

    - identical sets: `40 x 15 x 2`
    - same weight, different reps: `40 x 10, 9, 8`
    - different weights, same reps: `16, 20, 24 x 12`
    - anything else: one line per set
    """

    def weight(s: Set) -> str:
        return _weight(s.weight_kg, added_to_bodyweight)

    lines = []
    i = 0
    while i < len(sets):
        current = sets[i]

        identical = _run(sets, i, lambda s: (s.weight_kg, s.reps))
        if len(identical) > 1:
            lines.append(f"{weight(current)} x {current.reps} x {len(identical)}" + _rpe_suffix(identical))
            i += len(identical)
            continue

        same_weight = _run(sets, i, lambda s: s.weight_kg)
        if len(same_weight) > 1:
            reps = ", ".join(str(s.reps) for s in same_weight)
            lines.append(f"{weight(current)} x {reps}" + _rpe_suffix(same_weight, collapse=False))
            i += len(same_weight)
            continue

        same_reps = _run(sets, i, lambda s: s.reps)
        if len(same_reps) > 1:
            weights = ", ".join(weight(s) for s in same_reps)
            lines.append(f"{weights} x {current.reps}" + _rpe_suffix(same_reps, collapse=False))
            i += len(same_reps)
            continue

        lines.append(f"{weight(current)} x {current.reps}" + _rpe_suffix([current]))
        i += 1
    return lines


def _run(sets: list[Set], start: int, key) -> list[Set]:
    """The longest stretch of sets from `start` onwards with the same key as the first."""
    end = start
    while end < len(sets) and key(sets[end]) == key(sets[start]):
        end += 1
    return sets[start:end]
