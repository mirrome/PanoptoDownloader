"""OAuth2 PKCE authentication for the Panopto REST API.

Credentials are read from a .env file (project root or CWD) or from
environment variables (PANOPTO_SERVER, PANOPTO_CLIENT_ID,
PANOPTO_CLIENT_SECRET).  Tokens are persisted at
~/.config/panopto-downloader/tokens-<profile>.json and refreshed automatically.

Profiles let you stay logged in to multiple Panopto instances simultaneously:
    panopto-downloader --profile sloan auth login
    panopto-downloader --profile eecs  auth login --server mit.hosted.panopto.com ...
    panopto-downloader --profile eecs  discover
"""

import base64
import hashlib
import http.server
import json
import os
import secrets
import time
import urllib.parse
import webbrowser
from pathlib import Path
from typing import Any

import requests

REDIRECT_PORT = 9127
REDIRECT_URI = f"http://localhost:{REDIRECT_PORT}/redirect"
SCOPES = "openid api offline_access"
TOKEN_DIR = Path("~/.config/panopto-downloader").expanduser()
DEFAULT_PROFILE = "default"


def token_file_for_profile(profile: str) -> Path:
    """Return the token file path for the given profile name."""
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in profile)
    return TOKEN_DIR / f"tokens-{safe}.json"


# Keep the old default path as an alias so existing tokens aren't lost
TOKEN_FILE = token_file_for_profile(DEFAULT_PROFILE)

# ---------------------------------------------------------------------------
# .env loader — no third-party dependency required
# ---------------------------------------------------------------------------

_ENV_SEARCH_PATHS = [
    Path.cwd() / ".env",
    Path(__file__).parents[4] / ".env",   # repo root when installed -e
]


def load_env_file(path: Path | None = None) -> dict[str, str]:
    """Parse a .env file and return its key/value pairs.

    Does **not** mutate ``os.environ``; call :func:`apply_env_file` for that.
    Lines starting with ``#`` and blank lines are ignored.
    Values may be optionally quoted with ``"`` or ``'``.
    """
    candidates = [path] if path else _ENV_SEARCH_PATHS
    for candidate in candidates:
        if candidate and candidate.exists():
            result: dict[str, str] = {}
            for line in candidate.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, _, raw_value = line.partition("=")
                key = key.strip()
                value = raw_value.strip().strip("'\"")
                result[key] = value
            return result
    return {}


def get_env(key: str, default: str = "") -> str:
    """Return *key* from ``os.environ``, falling back to the .env file."""
    if key in os.environ:
        return os.environ[key]
    return load_env_file().get(key, default)

# Refresh access token when fewer than this many seconds remain
_REFRESH_MARGIN_SECONDS = 120


class AuthError(Exception):
    """Authentication and token errors."""

    pass


class TokenStorage:
    """Reads and writes OAuth tokens to disk, one file per profile."""

    def __init__(self, profile: str = DEFAULT_PROFILE) -> None:
        self.profile = profile
        self.path = token_file_for_profile(profile)

    def save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2))

    def load(self) -> dict[str, Any] | None:
        if not self.path.exists():
            return None
        try:
            return json.loads(self.path.read_text())  # type: ignore[no-any-return]
        except (json.JSONDecodeError, OSError):
            return None

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()

    @staticmethod
    def list_profiles() -> list[str]:
        """Return all profile names that have a saved token file."""
        if not TOKEN_DIR.exists():
            return []
        profiles = []
        for f in sorted(TOKEN_DIR.glob("tokens-*.json")):
            name = f.stem[len("tokens-"):]  # strip "tokens-" prefix
            profiles.append(name)
        return profiles


class PanoptoAuth:
    """OAuth2 PKCE authentication client for Panopto.

    Typical usage:
        auth = PanoptoAuth()                        # default profile
        auth = PanoptoAuth(profile="eecs")          # named profile
        auth.login("mit.hosted.panopto.com", "id")
        token = auth.get_access_token()             # auto-refreshes
    """

    def __init__(
        self,
        storage: TokenStorage | None = None,
        profile: str = DEFAULT_PROFILE,
    ) -> None:
        self.storage = storage or TokenStorage(profile=profile)
        self.profile = self.storage.profile
        self._token_data: dict[str, Any] | None = None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def login_headless(
        self,
        server: str,
        client_id: str,
        client_secret: str,
    ) -> None:
        """Authenticate using the OAuth2 client_credentials grant (no browser needed).

        Requires a client secret — this only works when the API client was
        registered as a "Server-Side Web Application" in Panopto System Settings.
        Tries both form-body and HTTP Basic Auth credential encoding since
        different Panopto instances require different approaches.

        Args:
            server:        Panopto hostname, e.g. ``mitsloan.hosted.panopto.com``.
            client_id:     The API client ID from Panopto System Settings.
            client_secret: The client secret (required for this grant type).
        """
        if not client_secret:
            raise AuthError(
                "client_credentials grant requires a client secret. "
                "Use 'auth login' (browser) if you only have a client ID."
            )

        token_url = f"https://{server}/Panopto/oauth2/connect/token"

        # Panopto instances vary: some want credentials in the POST body,
        # others expect HTTP Basic Auth. Try both before giving up.
        attempts = [
            # 1) credentials in form body (most common)
            {
                "data": {
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "scope": "api",
                },
                "auth": None,
            },
            # 2) HTTP Basic Auth + minimal body
            {
                "data": {
                    "grant_type": "client_credentials",
                    "scope": "api",
                },
                "auth": (client_id, client_secret),
            },
            # 3) no scope (some servers reject unknown scopes for CC grant)
            {
                "data": {
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
                "auth": None,
            },
        ]

        last_error = ""
        for attempt in attempts:
            try:
                resp = requests.post(
                    token_url,
                    data=attempt["data"],
                    auth=attempt["auth"],
                    timeout=30,
                )
                if resp.ok:
                    token_data = resp.json()
                    if "access_token" in token_data:
                        token_data["server"] = server
                        token_data["client_id"] = client_id
                        token_data["client_secret"] = client_secret
                        token_data["issued_at"] = time.time()
                        self.storage.save(token_data)
                        self._token_data = token_data
                        return
                # Capture the body for the error message
                try:
                    body = resp.json()
                except Exception:
                    body = resp.text
                last_error = f"HTTP {resp.status_code}: {body}"
            except requests.RequestException as exc:
                last_error = str(exc)

        raise AuthError(
            f"Headless login failed — all attempts returned errors.\n"
            f"Last response: {last_error}\n\n"
            "Possible causes:\n"
            "  • API client type must be 'Server-Side Web Application' in Panopto\n"
            "  • Your Panopto instance may not support client_credentials grant at all\n"
            "  • Ask your Panopto admin to enable API access for this client"
        )

    def login_manual(
        self,
        server: str,
        client_id: str,
        client_secret: str = "",
    ) -> None:
        """Run the copy-paste auth flow for headless / SSH environments.

        Prints the authorization URL so the user can open it on any browser.
        After login Panopto redirects to localhost:9127 which fails — the user
        copies that full redirect URL from the browser address bar and pastes
        it here. We extract the code and exchange it for tokens.

        Uses PKCE when no client_secret is provided (Mobile/Desktop app type).
        Uses plain authorization_code + secret when client_secret is given
        (Server-Side Web Application type — PKCE not supported for those).

        Args:
            server:        Panopto hostname.
            client_id:     The API client ID.
            client_secret: Client secret if using a server-side app client.
        """
        state = secrets.token_urlsafe(16)
        use_pkce = not client_secret

        if use_pkce:
            code_verifier, code_challenge = self._generate_pkce()
            auth_url = (
                f"https://{server}/Panopto/oauth2/connect/authorize"
                f"?client_id={urllib.parse.quote(client_id)}"
                f"&response_type=code"
                f"&redirect_uri={urllib.parse.quote(REDIRECT_URI)}"
                f"&scope={urllib.parse.quote(SCOPES)}"
                f"&state={state}"
                f"&code_challenge={code_challenge}"
                f"&code_challenge_method=S256"
            )
        else:
            # Server-Side Web Application: plain auth code flow, no PKCE
            code_verifier = ""
            auth_url = (
                f"https://{server}/Panopto/oauth2/connect/authorize"
                f"?client_id={urllib.parse.quote(client_id)}"
                f"&response_type=code"
                f"&redirect_uri={urllib.parse.quote(REDIRECT_URI)}"
                f"&scope={urllib.parse.quote(SCOPES)}"
                f"&state={state}"
            )

        print("\n" + "─" * 60)
        print("STEP 1 — Send this URL to the person whose account this is:")
        print("─" * 60)
        print(f"\n{auth_url}\n")
        print("─" * 60)
        print("STEP 2 — They open it in any browser and log in with their")
        print("         Panopto username and password.")
        print()
        print("STEP 3 — After login their browser will try to redirect to")
        print("         http://localhost:9127/redirect?code=...")
        print("         and show 'connection refused' or a blank page.")
        print("         They should copy the FULL URL from the address bar")
        print("         (it starts with http://localhost:9127/redirect?code=)")
        print("         and send it back to you.")
        print("─" * 60)

        while True:
            try:
                pasted = input("\nPaste the full redirect URL here: ").strip()
            except (EOFError, KeyboardInterrupt):
                raise AuthError("Login cancelled.")

            if not pasted:
                continue

            parsed = urllib.parse.urlparse(pasted)
            params = urllib.parse.parse_qs(parsed.query)

            if "error" in params:
                raise AuthError(f"Login failed: {params['error'][0]}")

            if "code" not in params:
                print("  ✗ Could not find 'code=' in that URL. Please try again.")
                continue

            code = params["code"][0]
            break

        self._exchange_code(server, client_id, code, code_verifier, client_secret)

    def login(
        self,
        server: str,
        client_id: str,
        client_secret: str = "",
    ) -> None:
        """Run the browser-based OAuth2 PKCE login flow.

        Opens the user's default browser at the Panopto authorization page,
        starts a temporary HTTP server on localhost to catch the redirect, then
        exchanges the authorization code for access + refresh tokens.

        Args:
            server:        Panopto hostname, e.g. ``mitsloan.hosted.panopto.com``.
            client_id:     The API client ID from Panopto System Settings.
            client_secret: Optional client secret (included in token requests
                           when provided; not required for PKCE public clients).
        """
        code_verifier, code_challenge = self._generate_pkce()
        state = secrets.token_urlsafe(16)

        received_code: list[str] = []
        received_error: list[str] = []

        # Inline callback handler — captures the auth code from the redirect
        class _CallbackHandler(http.server.BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                parsed = urllib.parse.urlparse(self.path)
                params = urllib.parse.parse_qs(parsed.query)

                if "code" in params:
                    received_code.append(params["code"][0])
                    body = (
                        b"<html><body>"
                        b"<h2>Login successful &#8212; you can close this tab.</h2>"
                        b"</body></html>"
                    )
                    self.send_response(200)
                else:
                    desc = params.get("error_description", params.get("error", ["Unknown error"]))
                    received_error.append(desc[0])
                    body = b"<html><body><h2>Login failed. Check the terminal.</h2></body></html>"
                    self.send_response(400)

                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
                pass  # suppress request logging

        auth_url = (
            f"https://{server}/Panopto/oauth2/connect/authorize"
            f"?client_id={urllib.parse.quote(client_id)}"
            f"&response_type=code"
            f"&redirect_uri={urllib.parse.quote(REDIRECT_URI)}"
            f"&scope={urllib.parse.quote(SCOPES)}"
            f"&state={state}"
            f"&code_challenge={code_challenge}"
            f"&code_challenge_method=S256"
        )

        httpd = http.server.HTTPServer(("localhost", REDIRECT_PORT), _CallbackHandler)
        httpd.timeout = 1  # non-blocking poll interval

        webbrowser.open(auth_url)

        deadline = time.time() + 120  # 2-minute window
        while not received_code and not received_error and time.time() < deadline:
            httpd.handle_request()

        httpd.server_close()

        if received_error:
            raise AuthError(f"Authorization failed: {received_error[0]}")
        if not received_code:
            raise AuthError("Authorization timed out after 2 minutes. Please try again.")

        self._exchange_code(server, client_id, received_code[0], code_verifier, client_secret)

    def get_access_token(self) -> str:
        """Return a valid access token, refreshing if it is near expiry."""
        return self._get_token_data()["access_token"]

    def get_server(self) -> str:
        """Return the Panopto server hostname stored with the tokens."""
        return self._get_token_data()["server"]  # type: ignore[no-any-return]

    def get_client_id(self) -> str:
        """Return the client ID stored with the tokens."""
        return self._get_token_data()["client_id"]  # type: ignore[no-any-return]

    def is_logged_in(self) -> bool:
        """Return True if tokens exist on disk."""
        data = self.storage.load()
        return data is not None and "access_token" in data

    def get_session_cookies(self) -> dict[str, str]:
        """Exchange the OAuth access token for Panopto session cookies.

        Hits several Panopto web pages with the Bearer token so the server
        can establish a full forms-auth session (ASPXAUTH + ASP.NET_SessionId).
        The resulting cookies are what DeliveryInfo.aspx requires.
        """
        server = self.get_server()
        token = self.get_access_token()
        sess = requests.Session()
        headers = {"Authorization": f"Bearer {token}"}

        # Hit multiple pages in sequence — some Panopto versions set the
        # full ASPXAUTH cookie only after a second authenticated request.
        pages = [
            f"https://{server}/Panopto/Pages/Home.aspx",
            f"https://{server}/Panopto/Pages/Sessions/List.aspx",
        ]
        for url in pages:
            try:
                sess.get(url, headers=headers, timeout=30, allow_redirects=True)
            except requests.RequestException:
                pass

        return {c.name: c.value for c in sess.cookies}

    def write_cookies_file(self, path: Path) -> Path:
        """Write Panopto session cookies to a Netscape-format cookies.txt file.

        The file can be passed directly to yt-dlp via ``--cookies``.

        Returns the path that was written.
        """
        cookies = self.get_session_cookies()
        server = self.get_server()

        path.parent.mkdir(parents=True, exist_ok=True)
        lines = ["# Netscape HTTP Cookie File\n"]
        for name, value in cookies.items():
            # domain  flag  path  secure  expiry  name  value
            lines.append(f".{server}\tTRUE\t/\tFALSE\t0\t{name}\t{value}\n")
        path.write_text("".join(lines))
        return path

    def logout(self) -> None:
        """Delete stored tokens."""
        self.storage.clear()
        self._token_data = None

    def status(self) -> dict[str, Any]:
        """Return a dict describing the current auth state."""
        data = self.storage.load()
        if not data or "access_token" not in data:
            return {"logged_in": False}

        issued_at = data.get("issued_at", 0.0)
        expires_in = data.get("expires_in", 3600)
        seconds_left = max(0, int(issued_at + expires_in - time.time()))

        return {
            "logged_in": True,
            "server": data.get("server"),
            "client_id": data.get("client_id"),
            "token_expires_in_seconds": seconds_left,
            "has_refresh_token": "refresh_token" in data,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_pkce() -> tuple[str, str]:
        """Return (code_verifier, code_challenge) for the PKCE flow."""
        # 32 random bytes → 43-char base64url string (within 43-128 range)
        raw = secrets.token_bytes(32)
        code_verifier = base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
        digest = hashlib.sha256(code_verifier.encode()).digest()
        code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
        return code_verifier, code_challenge

    def _exchange_code(
        self,
        server: str,
        client_id: str,
        code: str,
        code_verifier: str,
        client_secret: str = "",
    ) -> None:
        """Exchange an authorization code for access + refresh tokens."""
        token_url = f"https://{server}/Panopto/oauth2/connect/token"
        payload: dict[str, str] = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": client_id,
        }
        # PKCE: include code_verifier only when we used a code_challenge
        if code_verifier:
            payload["code_verifier"] = code_verifier
        # Server-side app: authenticate with client_secret instead of PKCE
        if client_secret:
            payload["client_secret"] = client_secret

        try:
            resp = requests.post(token_url, data=payload, timeout=30)
            if not resp.ok:
                try:
                    body = resp.json()
                except Exception:
                    body = resp.text
                raise AuthError(f"Token exchange failed: HTTP {resp.status_code}: {body}")
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise AuthError(f"Token exchange failed: {exc}") from exc

        token_data = resp.json()
        token_data["server"] = server
        token_data["client_id"] = client_id
        if client_secret:
            token_data["client_secret"] = client_secret
        token_data["issued_at"] = time.time()
        self.storage.save(token_data)
        self._token_data = token_data

    def _refresh(self) -> None:
        """Use the refresh token (or re-run client_credentials) to obtain a new access token."""
        data = self._token_data
        if not data:
            profile_flag = f" --profile {self.profile}" if self.profile != DEFAULT_PROFILE else ""
            raise AuthError(f"Session expired. Run: panopto-downloader{profile_flag} auth login")

        # client_credentials tokens have no refresh token — just re-authenticate silently
        if "refresh_token" not in data and data.get("client_secret"):
            self.login_headless(data["server"], data["client_id"], data["client_secret"])
            return

        if "refresh_token" not in data:
            profile_flag = f" --profile {self.profile}" if self.profile != DEFAULT_PROFILE else ""
            raise AuthError(f"Session expired. Run: panopto-downloader{profile_flag} auth login")

        server = data["server"]
        client_id = data["client_id"]
        client_secret = data.get("client_secret", "")
        token_url = f"https://{server}/Panopto/oauth2/connect/token"

        payload: dict[str, str] = {
            "grant_type": "refresh_token",
            "refresh_token": data["refresh_token"],
            "client_id": client_id,
        }
        if client_secret:
            payload["client_secret"] = client_secret

        try:
            resp = requests.post(token_url, data=payload, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise AuthError(f"Token refresh failed: {exc}") from exc

        new_data = resp.json()
        new_data["server"] = server
        new_data["client_id"] = client_id
        if client_secret:
            new_data["client_secret"] = client_secret
        new_data["issued_at"] = time.time()
        # Keep the old refresh token if the server didn't issue a new one
        if "refresh_token" not in new_data:
            new_data["refresh_token"] = data["refresh_token"]

        self.storage.save(new_data)
        self._token_data = new_data

    def _get_token_data(self) -> dict[str, Any]:
        """Return token data, loading from disk and refreshing if needed."""
        if self._token_data is None:
            self._token_data = self.storage.load()

        if not self._token_data or "access_token" not in self._token_data:
            profile_flag = f" --profile {self.profile}" if self.profile != DEFAULT_PROFILE else ""
            raise AuthError(f"Not logged in. Run: panopto-downloader{profile_flag} auth login")

        issued_at = self._token_data.get("issued_at", 0.0)
        expires_in = self._token_data.get("expires_in", 3600)
        if time.time() > issued_at + expires_in - _REFRESH_MARGIN_SECONDS:
            self._refresh()

        return self._token_data
