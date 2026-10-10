import base64
import hashlib
import socket
import stat
import threading
import time
import urllib.request
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from mf2wxr import auth


def test_pkce_challenge_is_the_s256_of_the_verifier():
    verifier, challenge = auth.pkce_pair()

    assert len(verifier) <= 64
    expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    assert challenge == expected


def test_authorization_url_asks_for_the_journal_write_scope():
    query = parse_qs(urlparse(auth.authorization_url("mf2wxr", "s1", "c1")).query)

    assert query["client_id"] == ["mf2wxr"]
    assert query["scope"] == ["jwrite"]
    assert query["redirect_uri"] == [auth.REDIRECT_URI]
    assert query["code_challenge_method"] == ["S256"]


def test_token_store_is_private_to_the_user(tmp_path):
    store = auth.TokenStore(tmp_path / "mf2wxr" / "token.json")
    tokens = auth.Tokens("mf2wxr", "access", "refresh", time.time() + 3600)

    store.save(tokens)

    assert store.load() == tokens
    assert stat.S_IMODE(store.path.stat().st_mode) == 0o600


def token_endpoint(requests: list, body: dict, status: int = 200) -> httpx.Client:
    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(dict(parse_qs(request.content.decode())))
        return httpx.Response(status, json=body)

    return httpx.Client(transport=httpx.MockTransport(handle))


def test_access_token_refreshes_an_expired_token(tmp_path):
    store = auth.TokenStore(tmp_path / "token.json")
    store.save(auth.Tokens("mf2wxr", "old", "refresh-1", expires_at=time.time() - 1))
    requests = []
    http = token_endpoint(requests, {"access_token": "new", "refresh_token": "refresh-2", "expires_in": 3600})

    assert auth.access_token(store, http) == "new"
    assert requests == [{"grant_type": ["refresh_token"], "refresh_token": ["refresh-1"], "client_id": ["mf2wxr"]}]
    assert store.load().refresh_token == "refresh-2"


def test_access_token_keeps_a_valid_token(tmp_path):
    store = auth.TokenStore(tmp_path / "token.json")
    store.save(auth.Tokens("mf2wxr", "current", "refresh", expires_at=time.time() + 3600))
    requests = []

    assert auth.access_token(store, token_endpoint(requests, {})) == "current"
    assert requests == []


def test_access_token_needs_a_login(tmp_path):
    with pytest.raises(auth.AuthError, match="login"):
        auth.access_token(auth.TokenStore(tmp_path / "token.json"), httpx.Client())


def test_rejected_refresh_asks_to_log_in_again(tmp_path):
    store = auth.TokenStore(tmp_path / "token.json")
    store.save(auth.Tokens("mf2wxr", "old", "refresh", expires_at=0))

    with pytest.raises(auth.AuthError, match="login"):
        auth.access_token(store, token_endpoint([], {"error": "invalid_grant"}, status=400))


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_login_exchanges_the_redirected_code_for_tokens(monkeypatch):
    port = free_port()
    monkeypatch.setattr(auth, "REDIRECT_PORT", port)
    monkeypatch.setattr(auth, "NAVIGATION_GRACE_S", 0)
    requests = []
    http = token_endpoint(requests, {"access_token": "a", "refresh_token": "r", "expires_in": 60})

    def browser(url):
        # play the part of weightxreps: redirect back with a code and the state we were given
        state = parse_qs(urlparse(url).query)["state"][0]
        callback = f"http://127.0.0.1:{port}/callback?code=the-code&state={state}"
        threading.Thread(target=urllib.request.urlopen, args=(callback,), daemon=True).start()

    tokens = auth.login("mf2wxr", http, open_browser=browser)

    assert tokens.access_token == "a"
    assert requests[0]["code"] == ["the-code"]
    assert requests[0]["grant_type"] == ["authorization_code"]
    assert len(requests[0]["code_verifier"][0]) <= 64


def test_callback_answers_the_consent_pages_cross_origin_fetch(monkeypatch):
    # the weightxreps consent page fetch()es its way to the callback before navigating there
    port = free_port()
    monkeypatch.setattr(auth, "REDIRECT_PORT", port)
    monkeypatch.setattr(auth, "NAVIGATION_GRACE_S", 0)
    origin = {"Origin": "https://weightxreps.net"}
    callback = f"http://127.0.0.1:{port}/callback?code=c&state=s"

    with auth._CallbackServer() as server:
        preflight = httpx.options(
            callback,
            headers={
                **origin,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization",
                "Access-Control-Request-Private-Network": "true",
            },
        )
        fetched = httpx.get(callback, headers=origin)
        code = server.wait_for_code("s")

    assert preflight.status_code == 204
    assert preflight.headers["Access-Control-Allow-Origin"] == "https://weightxreps.net"
    assert preflight.headers["Access-Control-Allow-Headers"] == "authorization"
    assert preflight.headers["Access-Control-Allow-Private-Network"] == "true"
    assert fetched.headers["Access-Control-Allow-Origin"] == "https://weightxreps.net"
    assert code == "c"


def test_callback_doesnt_grant_cors_to_other_sites(monkeypatch):
    port = free_port()
    monkeypatch.setattr(auth, "REDIRECT_PORT", port)
    monkeypatch.setattr(auth, "NAVIGATION_GRACE_S", 0)

    with auth._CallbackServer():
        response = httpx.get(f"http://127.0.0.1:{port}/callback", headers={"Origin": "https://evil.example"})

    assert "Access-Control-Allow-Origin" not in response.headers
