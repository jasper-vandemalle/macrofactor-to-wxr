import pytest

from mf2wxr.exercises import Match, load_aliases, match_exercises


def test_matches_case_insensitively():
    matches = match_exercises(["Squat (Barbell)"], {12: "squat (barbell) "})

    assert matches == {"Squat (Barbell)": Match("Squat (Barbell)", 12)}


def test_unknown_exercises_have_no_id():
    matches = match_exercises(["Leg Curl (Machine)"], {12: "Squat (Barbell)"})

    assert matches["Leg Curl (Machine)"] == Match("Leg Curl (Machine)", None)


def test_aliases_rename_before_matching():
    matches = match_exercises(["Squat (Barbell)"], {12: "Back Squat"}, {"Squat (Barbell)": "Back Squat"})

    assert matches["Squat (Barbell)"] == Match("Back Squat", 12)


def test_loads_aliases_from_toml(tmp_path):
    path = tmp_path / "aliases.toml"
    path.write_text('[aliases]\n"Squat (Barbell)" = "Back Squat"\n')

    assert load_aliases(path) == {"Squat (Barbell)": "Back Squat"}


def test_missing_alias_file_means_no_aliases(tmp_path):
    assert load_aliases(tmp_path / "nope.toml") == {}


def test_rejects_malformed_aliases(tmp_path):
    path = tmp_path / "aliases.toml"
    path.write_text('[aliases]\n"Squat (Barbell)" = 3\n')

    with pytest.raises(ValueError, match="aliases"):
        load_aliases(path)
