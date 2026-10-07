import os
from argparse import Namespace
from datetime import date

import pytest
from conftest import workout_row as row

from mf2wxr.api import JournalDay
from mf2wxr.cli import UsageError, find_export, push
from mf2wxr.config import Config


class FakeApi:
    def __init__(self, exercises=None, has_log=False):
        self.day = JournalDay(exercises or {}, has_log)
        self.saved = None

    def journal_day(self, day):
        return self.day

    def save(self, rows, day):
        self.saved = (rows, day)


def push_args(path, **overrides):
    return Namespace(**{"path": path, "date": None, "dry_run": False, "replace": False, **overrides})


@pytest.fixture
def export(make_export):
    return make_export(
        [
            row("2025-03-01", "Squat (Barbell)", 100, 5, rir=2),
            row("2025-03-01", "Leg Curl (Machine)", 50, 12),
        ],
        weigh_ins=[("2025-03-01", 80)],
    )


def test_push_saves_the_workout(export, tmp_path, capsys):
    api = FakeApi({4: "Squat (Barbell)"})

    assert push(push_args(export), Config(), api, aliases_path=tmp_path / "none.toml") == 0

    rows, day = api.saved
    assert day == date(2025, 3, 1)
    assert rows[0] == {"newExercise": "Leg Curl (Machine)"}
    assert [r["eid"] for r in rows if "eid" in r] == [4, 0]
    output = capsys.readouterr().out
    assert "New on weightxreps: Leg Curl (Machine)" in output
    assert "Logged Upper A on 2025-03-01: 2 exercises, 2 sets." in output


def test_dry_run_saves_nothing(export, tmp_path, capsys):
    api = FakeApi()

    assert push(push_args(export, dry_run=True), Config(), api, aliases_path=tmp_path / "none.toml") == 0

    assert api.saved is None
    assert "Dry run" in capsys.readouterr().out


def test_refuses_to_overwrite_an_existing_log(export, tmp_path):
    api = FakeApi(has_log=True)

    with pytest.raises(UsageError, match="--replace"):
        push(push_args(export), Config(), api, aliases_path=tmp_path / "none.toml")
    assert api.saved is None


def test_replace_overwrites_an_existing_log(export, tmp_path):
    api = FakeApi(has_log=True)

    push(push_args(export, replace=True), Config(), api, aliases_path=tmp_path / "none.toml")

    assert api.saved is not None


def test_uses_aliases(export, tmp_path):
    aliases = tmp_path / "aliases.toml"
    aliases.write_text('"Squat (Barbell)" = "Back Squat"\n')
    api = FakeApi({9: "Back Squat"})

    push(push_args(export), Config(), api, aliases_path=aliases)

    rows, _ = api.saved
    assert [r["eid"] for r in rows if "eid" in r][0] == 9


def test_finds_the_newest_workout_export_in_a_directory(make_export, tmp_path):
    older = make_export([row("2025-03-01", "Squat (Barbell)", 100, 5)], name="MacroFactor-20250301.xlsx")
    newer = make_export([row("2025-03-02", "Squat (Barbell)", 100, 5)], name="MacroFactor-20250302.xlsx")
    os.utime(older, (1_000, 1_000))
    os.utime(newer, (2_000, 2_000))

    assert find_export(tmp_path, Config()) == newer


def test_skips_exports_without_workouts(make_export, tmp_path):
    from openpyxl import Workbook

    workouts = make_export([row("2025-03-01", "Squat (Barbell)", 100, 5)], name="MacroFactor-1.xlsx")
    nutrition = tmp_path / "MacroFactor-2.xlsx"
    Workbook().save(nutrition)
    os.utime(workouts, (1_000, 1_000))
    os.utime(nutrition, (2_000, 2_000))

    assert find_export(tmp_path, Config()) == workouts


def test_falls_back_to_the_configured_exports_directory(make_export, tmp_path):
    export = make_export([row("2025-03-01", "Squat (Barbell)", 100, 5)])

    assert find_export(None, Config(exports=tmp_path)) == export


def test_complains_when_there_is_no_export(tmp_path):
    with pytest.raises(UsageError, match="No MacroFactor workout export"):
        find_export(tmp_path, Config())
