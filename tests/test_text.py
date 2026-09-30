from datetime import date

from mf2wxr.model import Exercise, Set, Workout
from mf2wxr.text import to_text


def sets(*specs):
    """(weight, reps) or (weight, reps, rpe) tuples."""
    return [Set(spec[0], spec[1], rpe=spec[2] if len(spec) > 2 else None) for spec in specs]


def lines_for(name, exercise_sets):
    workout = Workout(date(2025, 3, 1), "Upper A", [Exercise(name, exercise_sets)])
    lines = to_text(workout).split("\n")
    return lines[lines.index(f"#{name}") + 1 : -1]


def test_header_has_date_bodyweight_and_workout_name():
    workout = Workout(date(2025, 3, 1), "Upper A", [], bodyweight_kg=80.14)

    assert to_text(workout).split("\n") == ["2025-03-01", "@ 80.1 bw", "", "Upper A", ""]


def test_bodyweight_line_is_left_out_when_unknown():
    workout = Workout(date(2025, 3, 1), "Upper A", [])

    assert "bw" not in to_text(workout)


def test_identical_sets_are_counted():
    assert lines_for("Squat (Barbell)", sets((100, 5), (100, 5), (100, 5))) == ["100 x 5 x 3"]


def test_same_weight_lists_reps():
    assert lines_for("Squat (Barbell)", sets((100, 5), (100, 4), (100, 3))) == ["100 x 5, 4, 3"]


def test_same_reps_lists_weights():
    assert lines_for("Squat (Barbell)", sets((90, 5), (95, 5), (100, 5))) == ["90, 95, 100 x 5"]


def test_mixed_sets_get_a_line_each():
    assert lines_for("Squat (Barbell)", sets((100, 5), (90, 8))) == ["100 x 5", "90 x 8"]


def test_fractional_weights_keep_their_decimals():
    assert lines_for("Lateral Raise (Dumbbell)", sets((7.5, 15))) == ["7.5 x 15"]


def test_identical_rpes_collapse_on_counted_sets():
    assert lines_for("Squat (Barbell)", sets((100, 5, 8), (100, 5, 8))) == ["100 x 5 x 2 @8"]


def test_listed_sets_keep_one_rpe_each():
    assert lines_for("Squat (Barbell)", sets((100, 5, 8), (100, 4, 8))) == ["100 x 5, 4 @8, 8"]


def test_rpe_is_dropped_when_a_set_lacks_one():
    assert lines_for("Squat (Barbell)", sets((100, 5, 8), (100, 5))) == ["100 x 5 x 2"]


def test_weight_added_to_bodyweight_exercises():
    assert lines_for("Pull Up", sets((10, 8), (0, 6))) == ["BW+10 x 8", "BW x 6"]
    assert lines_for("Pull Up", sets((10, 8), (0, 8))) == ["BW+10, BW x 8"]


def test_bodyweight_only_sets():
    assert lines_for("Push Up", sets((0, 20), (0, 20))) == ["BW x 20 x 2"]


def test_distance_sets():
    carry = [Set(40, 0, distance_m=30), Set(40, 0, distance_m=30), Set(50, 0, distance_m=20.5)]

    assert lines_for("Farmer's Carry", carry) == ["40x30m x 2", "50x20.5m"]
