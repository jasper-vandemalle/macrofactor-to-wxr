from datetime import datetime

import pytest
from openpyxl import Workbook

WORKOUT_HEADER = [
    "Date",
    "Workout",
    "Exercise",
    "Set Type",
    "Weight (kg)",
    "Reps",
    "RIR",
    "Distance Short (m)",
    "Distance Long (km)",
]


def workout_row(day, exercise, weight=None, reps=None, rir=None, set_type="Standard Set", workout="Upper A", **extra):
    return {
        "Date": datetime.fromisoformat(day),
        "Workout": workout,
        "Exercise": exercise,
        "Set Type": set_type,
        "Weight (kg)": weight,
        "Reps": reps,
        "RIR": rir,
        "Distance Short (m)": extra.get("distance_m"),
        "Distance Long (km)": extra.get("distance_km"),
    }


@pytest.fixture
def make_export(tmp_path):
    """Build a minimal MacroFactor export: a Workout Log sheet and, optionally, weigh-ins."""

    def make(rows, weigh_ins=None, name="MacroFactor-20250101000000.xlsx"):
        wb = Workbook()
        log = wb.active
        log.title = "Workout Log"
        log.append(WORKOUT_HEADER)
        for row in rows:
            log.append([row[column] for column in WORKOUT_HEADER])

        if weigh_ins is not None:
            quick = wb.create_sheet("Quick Export")
            quick.append(["Date", "Weight (kg)"])
            for day, weight in weigh_ins:
                quick.append([datetime.fromisoformat(day), weight])

        path = tmp_path / name
        wb.save(path)
        return path

    return make
