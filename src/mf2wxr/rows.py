"""Builds the rows that weightxreps' `saveJEditor` mutation expects.

These mirror what the weightxreps editor sends after parsing the text you type, see
https://github.com/bandinopla/weightxreps-server/blob/main/docs/JEditorSaveRow.md
"""

from mf2wxr.exercises import Match
from mf2wxr.model import Exercise, Set, Workout, is_weighted_bodyweight

# set types, from weightxreps-client src/data/set-types.js
WEIGHT_FOR_REPS = 0
WEIGHT_FOR_DISTANCE = 2


class MissingBodyweight(ValueError):
    """weightxreps needs the day's bodyweight to log a bodyweight set."""


def to_rows(workout: Workout, matches: dict[str, Match]) -> list[dict]:
    new_exercises: list[str] = []
    blocks = []

    for exercise in workout.exercises:
        match = matches[exercise.name]
        eid = match.eid
        if eid is None:
            # new exercises are referenced by 0, -1, -2, ... in the order they're declared
            key = match.name.replace(" ", "").lower()
            known = [n.replace(" ", "").lower() for n in new_exercises]
            if key not in known:
                new_exercises.append(match.name)
                known.append(key)
            eid = -known.index(key)
        blocks.append({"eid": eid, "erows": _erows(exercise, workout.bodyweight_kg)})

    rows: list[dict] = [{"newExercise": name} for name in new_exercises]
    rows.append({"on": workout.date.isoformat()})
    if workout.bodyweight_kg:
        rows.append({"bw": round(workout.bodyweight_kg, 1), "lb": 0})
    rows.append({"text": workout.name})
    rows += blocks
    return rows


def _erows(exercise: Exercise, bodyweight_kg: float | None) -> list[dict]:
    added_to_bodyweight = is_weighted_bodyweight(exercise.name)
    erows = []
    i = 0
    while i < len(exercise.sets):
        current = exercise.sets[i]
        count = 1
        while i + count < len(exercise.sets) and exercise.sets[i + count] == current:
            count += 1

        erow = _erow(current, count, added_to_bodyweight)
        if erow["w"].get("usebw") and not bodyweight_kg:
            raise MissingBodyweight(
                f"'{exercise.name}' is a bodyweight exercise, but the export has no weigh-in on or before that day"
            )
        erows.append(erow)
        i += count
    return erows


def _erow(s: Set, count: int, added_to_bodyweight: bool) -> dict:
    if s.weight_kg == 0:
        weight = {"v": 0, "usebw": 1}
    elif added_to_bodyweight:
        weight = {"v": s.weight_kg, "usebw": 1}
    else:
        weight = {"v": s.weight_kg, "lb": 0}

    erow = {"w": weight, "r": s.reps, "s": count, "t": 0, "c": "", "type": WEIGHT_FOR_REPS, "d": None}
    if s.distance_m is not None:
        # stored as centimeters * 100, see WxDoT_encodeDistance in weightxreps-client
        erow.update(r=1, type=WEIGHT_FOR_DISTANCE, d={"val": int(s.distance_m * 100 * 100), "unit": "m"})
    if s.rpe is not None:
        erow["rpe"] = s.rpe
    return erow
