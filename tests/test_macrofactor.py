from datetime import date

import pytest
from conftest import workout_row as row

from mf2wxr.macrofactor import ExportError, available_dates, read_workout


def test_reads_the_most_recent_workout_by_default(make_export):
    path = make_export(
        [
            row("2025-03-01", "Squat (Barbell)", 100, 5, workout="Lower A"),
            row("2025-03-03", "Bench Press (Barbell)", 80, 5, workout="Upper A"),
        ]
    )

    workout = read_workout(path)

    assert workout.date == date(2025, 3, 3)
    assert workout.name == "Upper A"
    assert [e.name for e in workout.exercises] == ["Bench Press (Barbell)"]


def test_reads_the_workout_for_a_given_date(make_export):
    path = make_export(
        [
            row("2025-03-01", "Squat (Barbell)", 100, 5, workout="Lower A"),
            row("2025-03-03", "Bench Press (Barbell)", 80, 5, workout="Upper A"),
        ]
    )

    workout = read_workout(path, on=date(2025, 3, 1))

    assert workout.name == "Lower A"
    assert workout.exercises[0].sets[0].weight_kg == 100


def test_rejects_a_date_without_a_workout(make_export):
    path = make_export([row("2025-03-01", "Squat (Barbell)", 100, 5)])

    with pytest.raises(ExportError, match="2025-03-02"):
        read_workout(path, on=date(2025, 3, 2))


def test_lists_available_dates(make_export):
    path = make_export(
        [
            row("2025-03-03", "Bench Press (Barbell)", 80, 5),
            row("2025-03-01", "Squat (Barbell)", 100, 5),
            row("2025-03-01", "Squat (Barbell)", 100, 5),
        ]
    )

    assert available_dates(path) == [date(2025, 3, 1), date(2025, 3, 3)]


def test_skips_warm_up_sets(make_export):
    path = make_export(
        [
            row("2025-03-01", "Squat (Barbell)", 60, 8, set_type="Warm-Up Set"),
            row("2025-03-01", "Squat (Barbell)", 100, 5),
        ]
    )

    sets = read_workout(path).exercises[0].sets

    assert [(s.weight_kg, s.reps) for s in sets] == [(100, 5)]


def test_consolidates_superset_rows_per_exercise(make_export):
    path = make_export(
        [
            row("2025-03-01", "Curl (Dumbbell) ∈ SS1", 24, 10),
            row("2025-03-01", "Triceps Pushdown (Cable) ∈ SS1", 30, 12),
            row("2025-03-01", "Curl (Dumbbell) ∈ SS1", 24, 9),
        ]
    )

    exercises = read_workout(path).exercises

    assert [e.name for e in exercises] == ["Curl (Dumbbell)", "Triceps Pushdown (Cable)"]
    assert [s.reps for s in exercises[0].sets] == [10, 9]


@pytest.mark.parametrize(
    ("exercise", "recorded", "expected"),
    [
        ("Bench Press (Dumbbell)", 60, 30),
        ("Cable Fly", 40, 20),
        ("Single Arm Row (Dumbbell)", 30, 30),
        ("Split Squat (Offset Dumbbell)", 20, 20),
        ("Bench Press (Barbell)", 80, 80),
    ],
)
def test_halves_the_combined_load_of_bilateral_dumbbell_and_fly_exercises(make_export, exercise, recorded, expected):
    path = make_export([row("2025-03-01", exercise, recorded, 10)])

    assert read_workout(path).exercises[0].sets[0].weight_kg == expected


def test_converts_rir_to_rpe(make_export):
    path = make_export(
        [
            row("2025-03-01", "Squat (Barbell)", 100, 5, rir=2),
            row("2025-03-01", "Squat (Barbell)", 100, 5),
        ]
    )

    sets = read_workout(path).exercises[0].sets

    assert [s.rpe for s in sets] == [8, None]


def test_reads_distance_sets(make_export):
    path = make_export(
        [
            row("2025-03-01", "Farmer's Carry", 40, None, distance_m=30),
            row("2025-03-01", "Sled Push", 80, None, distance_km=0.05),
        ]
    )

    carry, sled = read_workout(path).exercises

    assert carry.is_distance and carry.sets[0].distance_m == 30
    assert sled.sets[0].distance_m == 50


def test_uses_the_last_weigh_in_on_or_before_the_workout(make_export):
    path = make_export(
        [row("2025-03-02", "Squat (Barbell)", 100, 5)],
        weigh_ins=[("2025-03-01", 80.4), ("2025-03-02", 80.1), ("2025-03-03", 79.6)],
    )

    assert read_workout(path).bodyweight_kg == 80.1


def test_bodyweight_is_optional(make_export):
    path = make_export([row("2025-03-01", "Squat (Barbell)", 100, 5)])

    assert read_workout(path).bodyweight_kg is None


def test_rejects_files_without_a_workout_log(tmp_path):
    from openpyxl import Workbook

    path = tmp_path / "nutrition.xlsx"
    Workbook().save(path)

    with pytest.raises(ExportError, match="Workout Log"):
        read_workout(path)
