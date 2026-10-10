"""Signs in to weightxreps with OAuth2 (authorization code + PKCE) and keeps the tokens fresh.

See https://github.com/bandinopla/weightxreps-server/blob/main/docs/OAUTH.md
"""

import base64
import hashlib
import json
import os
import secrets
import sys
import threading
import time
import webbrowser
from dataclasses import asdict, dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

AUTH_URL = "https://weightxreps.net/api/auth"
TOKEN_URL = "https://weightxreps.net/api/auth/token"
REDIRECT_HOST, REDIRECT_PORT = "127.0.0.1", 8765
REDIRECT_URI = f"http://{REDIRECT_HOST}:{REDIRECT_PORT}/callback"
SCOPE = "jwrite"
LOGIN_TIMEOUT_S = 300
NAVIGATION_GRACE_S = 5
ALLOWED_ORIGINS = {"https://weightxreps.net", "https://www.weightxreps.net"}
# refresh a bit before the access token actually expires
EXPIRY_MARGIN_S = 60


class AuthError(RuntimeError):
    pass


@dataclass
class Tokens:
    client_id: str
    access_token: str
    refresh_token: str | None
    expires_at: float

    @classmethod
    def from_response(cls, client_id: str, body: dict) -> "Tokens":
        if "access_token" not in body:
            raise AuthError(f"weightxreps didn't return a token: {body}")
        return cls(
            client_id=client_id,
            access_token=body["access_token"],
            refresh_token=body.get("refresh_token"),
            expires_at=time.time() + float(body.get("expires_in", 3600)),
        )

    @property
    def expired(self) -> bool:
        return time.time() >= self.expires_at - EXPIRY_MARGIN_S


class TokenStore:
    def __init__(self, path: Path):
        self.path = path

    def load(self) -> Tokens | None:
        if not self.path.exists():
            return None
        return Tokens(**json.loads(self.path.read_text()))

    def save(self, tokens: Tokens) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # create the file with owner-only permissions before writing the secret into it
        self.path.touch(mode=0o600, exist_ok=True)
        self.path.chmod(0o600)
        self.path.write_text(json.dumps(asdict(tokens)))

    def clear(self) -> None:
        self.path.unlink(missing_ok=True)


def pkce_pair() -> tuple[str, str]:
    """A code verifier and its S256 challenge. weightxreps stores verifiers in a VARCHAR(64)."""
    verifier = secrets.token_urlsafe(48)  # 64 characters
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def authorization_url(client_id: str, state: str, challenge: str) -> str:
    query = {
        "grant_type": "authorization_code",
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPE,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return f"{AUTH_URL}?{urlencode(query)}"


def login(client_id: str, http: httpx.Client, open_browser=webbrowser.open) -> Tokens:
    """Have the user approve access in the browser and exchange the code for tokens."""
    verifier, challenge = pkce_pair()
    state = secrets.token_urlsafe(16)
    url = authorization_url(client_id, state, challenge)

    with _CallbackServer() as server:
        print(f"Opening weightxreps to approve access. If nothing opens, visit:\n{url}")
        open_browser(url)
        code = server.wait_for_code(state)

    response = http.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": client_id,
            "code_verifier": verifier,
        },
    )
    return Tokens.from_response(client_id, _json(response))


def refresh(tokens: Tokens, http: httpx.Client) -> Tokens:
    if not tokens.refresh_token:
        raise AuthError("The session expired; run `mf2wxr login` again")
    response = http.post(
        TOKEN_URL,
        data={"grant_type": "refresh_token", "refresh_token": tokens.refresh_token, "client_id": tokens.client_id},
    )
    if response.status_code in (400, 401):
        raise AuthError("The session expired; run `mf2wxr login` again")
    return Tokens.from_response(tokens.client_id, _json(response))


def access_token(store: TokenStore, http: httpx.Client) -> str:
    """A valid access token, refreshing and saving it if needed."""
    tokens = store.load()
    if tokens is None:
        raise AuthError("Not signed in; run `mf2wxr login` first")
    if tokens.expired:
        tokens = refresh(tokens, http)
        store.save(tokens)
    return tokens.access_token


def _json(response: httpx.Response) -> dict:
    try:
        body = response.json()
    except ValueError:
        body = {"error": response.text}
    if response.is_error:
        raise AuthError(f"weightxreps refused the token request ({response.status_code}): {body}")
    return body


class _CallbackServer:
    """Catches the redirect back from weightxreps on the loopback address.

    The weightxreps consent page doesn't simply redirect the browser here: it first `fetch`es the authorize
    endpoint, follows the redirect to this callback cross-origin and reads the code from the final URL, and only
    then navigates here. So the callback has to answer CORS (and private network access) preflights, and stay up
    for that second, navigating request.
    """

    def __enter__(self):
        result = self.result = {}
        received = self.received = threading.Event()
        navigated = self.navigated = threading.Event()

        class Handler(BaseHTTPRequestHandler):
            def do_OPTIONS(self):
                self.send_response(204)
                self._cors()
                self.send_header("Access-Control-Allow-Methods", "GET")
                requested = self.headers.get("Access-Control-Request-Headers")
                if requested:
                    self.send_header("Access-Control-Allow-Headers", requested)
                self.send_header("Access-Control-Allow-Private-Network", "true")
                self.end_headers()

            def do_GET(self):
                url = urlparse(self.path)
                if url.path != "/callback":
                    self.send_error(404)
                    return

                query = {k: v[0] for k, v in parse_qs(url.query).items()}
                if not received.is_set() and ("code" in query or "error" in query):
                    result.update(query)
                    received.set()
                if self.headers.get("Sec-Fetch-Mode") == "navigate":
                    navigated.set()

                ok = "code" in result
                self.send_response(200 if ok else 400)
                self._cors()
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                message = "Signed in to mf2wxr, you can close this tab." if ok else "Sign-in failed, see the terminal."
                self.wfile.write(message.encode())

            def _cors(self):
                origin = self.headers.get("Origin")
                if origin in ALLOWED_ORIGINS:
                    self.send_header("Access-Control-Allow-Origin", origin)
                    self.send_header("Vary", "Origin")

            def log_message(self, format, *args):
                if os.environ.get("MF2WXR_DEBUG"):
                    super().log_message(format, *args)
                    print(f"  headers: {dict(self.headers)}", file=sys.stderr)

        try:
            self.server = ThreadingHTTPServer((REDIRECT_HOST, REDIRECT_PORT), Handler)
        except OSError as e:
            raise AuthError(f"Can't listen on {REDIRECT_URI} for the sign-in redirect: {e}") from e
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self

    def wait_for_code(self, state: str) -> str:
        if not self.received.wait(LOGIN_TIMEOUT_S):
            raise AuthError("Timed out waiting for the weightxreps sign-in")
        if "error" in self.result:
            raise AuthError(f"weightxreps denied access: {self.result['error']}")
        if self.result.get("state") != state:
            raise AuthError("The sign-in response didn't match this request; try again")
        return self.result["code"]

    def __exit__(self, *exc):
        # give the browser a moment to land on the callback page instead of a connection error
        if self.received.is_set():
            self.navigated.wait(NAVIGATION_GRACE_S)
        self.server.shutdown()
        self.server.server_close()
