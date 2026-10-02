from datetime import date

import pytest

from mf2wxr.exercises import Match
from mf2wxr.model import Exercise, Set, Workout
from mf2wxr.rows import WEIGHT_FOR_DISTANCE, WEIGHT_FOR_REPS, MissingBodyweight, to_rows


def workout(*exercises, bodyweight=80.04):
    return Workout(date(2025, 3, 1), "Upper A", list(exercises), bodyweight_kg=bodyweight)


def known(*names, eid=1):
    return {name: Match(name, eid + i) for i, name in enumerate(names)}


def test_day_bodyweight_and_name_come_before_the_exercises():
    rows = to_rows(workout(Exercise("Squat (Barbell)", [Set(100, 5)])), known("Squat (Barbell)", eid=7))

    assert rows[:3] == [{"on": "2025-03-01"}, {"bw": 80.0, "lb": 0}, {"text": "Upper A"}]
    assert rows[3]["eid"] == 7


def test_bodyweight_row_is_left_out_when_unknown():
    rows = to_rows(workout(bodyweight=None), {})

    assert rows == [{"on": "2025-03-01"}, {"text": "Upper A"}]


def test_identical_consecutive_sets_are_counted():
    squat = Exercise("Squat (Barbell)", [Set(100, 5, rpe=8), Set(100, 5, rpe=8), Set(100, 5, rpe=9), Set(90, 8)])

    erows = to_rows(workout(squat), known("Squat (Barbell)"))[-1]["erows"]

    assert [(e["w"]["v"], e["r"], e["s"], e.get("rpe")) for e in erows] == [
        (100, 5, 2, 8),
        (100, 5, 1, 9),
        (90, 8, 1, None),
    ]
    assert all(e["w"]["lb"] == 0 and e["type"] == WEIGHT_FOR_REPS for e in erows)


def test_new_exercises_are_declared_first_and_referenced_by_non_positive_ids():
    rows = to_rows(
        workout(
            Exercise("Squat (Barbell)", [Set(100, 5)]),
            Exercise("Hip Thrust (Barbell)", [Set(120, 10)]),
            Exercise("Leg Curl (Machine)", [Set(50, 12)]),
        ),
        {
            "Squat (Barbell)": Match("Squat (Barbell)", 3),
            "Hip Thrust (Barbell)": Match("Hip Thrust (Barbell)", None),
            "Leg Curl (Machine)": Match("Leg Curl (Machine)", None),
        },
    )

    assert rows[:2] == [{"newExercise": "Hip Thrust (Barbell)"}, {"newExercise": "Leg Curl (Machine)"}]
    assert [r["eid"] for r in rows if "eid" in r] == [3, 0, -1]


def test_new_exercises_use_their_alias():
    rows = to_rows(workout(Exercise("Squat (Barbell)", [Set(100, 5)])), {"Squat (Barbell)": Match("Back Squat", None)})

    assert rows[0] == {"newExercise": "Back Squat"}


def test_weight_added_to_bodyweight():
    pull_up = Exercise("Pull Up", [Set(10, 8), Set(0, 8)])

    erows = to_rows(workout(pull_up), known("Pull Up"))[-1]["erows"]

    assert [e["w"] for e in erows] == [{"v": 10, "usebw": 1}, {"v": 0, "usebw": 1}]


def test_bodyweight_sets_need_a_weigh_in():
    with pytest.raises(MissingBodyweight, match="Push Up"):
        to_rows(workout(Exercise("Push Up", [Set(0, 20)]), bodyweight=None), known("Push Up"))


def test_distance_sets():
    carry = Exercise("Farmer's Carry", [Set(40, 0, distance_m=30), Set(40, 0, distance_m=30)])

    (erow,) = to_rows(workout(carry), known("Farmer's Carry"))[-1]["erows"]

    assert erow["type"] == WEIGHT_FOR_DISTANCE
    assert erow["d"] == {"val": 300_000, "unit": "m"}
    assert (erow["r"], erow["s"]) == (1, 2)
