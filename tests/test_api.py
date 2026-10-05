import json
from datetime import date

import httpx
import pytest

from mf2wxr.api import ApiError, WxrApi


def api_answering(body: dict, status: int = 200, seen: list | None = None) -> WxrApi:
    def handle(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        return httpx.Response(status, json=body)

    return WxrApi(httpx.Client(transport=httpx.MockTransport(handle)), token=lambda: "the-token")


def test_journal_day_lists_exercises_and_whether_the_day_has_a_log():
    api = api_answering(
        {
            "data": {
                "jeditor": {
                    "exercises": [{"e": {"id": "12", "name": "Squat (Barbell)"}}],
                    "did": [{"__typename": "JEditorDayTag"}, {"__typename": "JEditorText"}],
                }
            }
        }
    )

    day = api.journal_day(date(2025, 3, 1))

    assert day.exercises == {12: "Squat (Barbell)"}
    assert day.has_log


def test_an_empty_day_has_no_log():
    api = api_answering({"data": {"jeditor": {"exercises": [], "did": []}}})

    assert not api.journal_day(date(2025, 3, 1)).has_log


def test_save_sends_rows_with_the_bearer_token():
    seen = []
    api = api_answering({"data": {"saveJEditor": True}}, seen=seen)

    api.save([{"on": "2025-03-01"}], date(2025, 3, 1))

    request = seen[0]
    assert request.headers["Authorization"] == "Bearer the-token"
    assert json.loads(request.content)["variables"] == {"rows": [{"on": "2025-03-01"}], "defaultDate": "2025-03-01"}


def test_graphql_errors_are_raised():
    api = api_answering(
        {"data": None, "errors": [{"message": "Unauthorized, client lacks the required scope: jwrite"}]}
    )

    with pytest.raises(ApiError, match="jwrite"):
        api.save([], date(2025, 3, 1))


def test_unconfirmed_save_is_an_error():
    api = api_answering({"data": {"saveJEditor": False}})

    with pytest.raises(ApiError, match="confirm"):
        api.save([], date(2025, 3, 1))
