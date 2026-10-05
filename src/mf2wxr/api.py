"""The two weightxreps GraphQL operations this tool needs."""

from dataclasses import dataclass
from datetime import date

import httpx

GRAPHQL_URL = "https://weightxreps.net/api/graphql"

JOURNAL_DAY = """
query JournalDay($ymd: YMD) {
  jeditor(ymd: $ymd) {
    exercises { e { id name } }
    did { __typename }
  }
}
"""

SAVE = """
mutation SaveJEditor($rows: [JEditorSaveRow], $defaultDate: YMD!) {
  saveJEditor(rows: $rows, defaultDate: $defaultDate)
}
"""


class ApiError(RuntimeError):
    pass


@dataclass
class JournalDay:
    exercises: dict[int, str]
    """All of your exercises, by id."""
    has_log: bool
    """Whether something is already logged that day. Saving replaces it."""


class WxrApi:
    def __init__(self, http: httpx.Client, token):
        """`token` is a callable returning a valid access token."""
        self.http = http
        self.token = token

    def journal_day(self, day: date) -> JournalDay:
        data = self._call(JOURNAL_DAY, {"ymd": day.isoformat()})["jeditor"]
        return JournalDay(
            exercises={int(e["e"]["id"]): e["e"]["name"] for e in data["exercises"]},
            has_log=any(row["__typename"] == "JEditorDayTag" for row in data["did"]),
        )

    def save(self, rows: list[dict], day: date) -> None:
        if not self._call(SAVE, {"rows": rows, "defaultDate": day.isoformat()})["saveJEditor"]:
            raise ApiError("weightxreps didn't confirm the save")

    def _call(self, query: str, variables: dict) -> dict:
        response = self.http.post(
            GRAPHQL_URL,
            json={"query": query, "variables": variables},
            headers={"Authorization": f"Bearer {self.token()}"},
        )
        try:
            body = response.json()
        except ValueError:
            raise ApiError(f"weightxreps returned {response.status_code}: {response.text[:200]}") from None

        if body.get("errors"):
            raise ApiError("; ".join(e.get("message", str(e)) for e in body["errors"]))
        if response.is_error or body.get("data") is None:
            raise ApiError(f"weightxreps returned {response.status_code}: {body}")
        return body["data"]
