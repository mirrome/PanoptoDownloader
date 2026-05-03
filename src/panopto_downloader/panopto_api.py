"""Panopto API access: unofficial DeliveryInfo endpoint + official REST API v1."""

import json
import urllib.parse
from pathlib import Path
from typing import Any

import requests

from .auth import AuthError, PanoptoAuth


class PanoptoAPIError(Exception):
    """Panopto API related errors."""

    pass


class PanoptoStream:
    """Represents a single Panopto video stream."""

    def __init__(self, data: dict[str, Any]) -> None:
        """Initialize stream from API data.

        Args:
            data: Stream data from Panopto API.
        """
        self.name = data.get("Name") or f"Stream_{data.get('Tag', 'unknown')}"
        self.tag = data.get("Tag", "unknown")
        self.stream_type = data.get("StreamTypeName", "Unknown")
        self.stream_url = data.get("StreamHttpUrl", "")
        self.stream_id = data.get("StreamFileId", "")
        self.public_id = data.get("PublicID", "")
        self.duration = data.get("RelativeEnd", 0) - data.get("RelativeStart", 0)

    @property
    def clean_name(self) -> str:
        """Get a clean filename-safe name for this stream.

        Returns:
            Cleaned stream name.
        """
        # Handle None or empty names - use tag
        if not self.name or self.name == "Unknown":
            tag = self.tag.upper()
            if tag == "DV":
                # DV is the main camera/delivery stream (with audio)
                return "camera"
            elif tag == "OBJECT":
                # OBJECT streams are typically slides or secondary views
                return "slides"
            else:
                return f"stream_{self.tag.lower()}"
        
        # Remove file extension and clean up the name
        name = self.name.replace(".mp4", "").replace(".m4v", "")
        
        # Use tag if name is generic or starts with "Stream_"
        if name.startswith("Stream_"):
            tag = self.tag.upper()
            if tag == "DV":
                return "camera"
            elif tag == "OBJECT":
                return "slides"
            else:
                return name.lower().replace(" ", "_")
        elif name.lower().startswith("tracking"):
            return "tracking_camera"
        elif name.lower().startswith("pc1"):
            return "pc1_camera"
        elif name.lower().startswith("pc2"):
            return "pc2_camera"
        elif name.lower().startswith("wideshot"):
            return "wideshot_camera"
        elif "middle" in name.lower():
            return "middle_chalkboard"
        elif "left" in name.lower():
            return "left_chalkboard"
        elif "right" in name.lower():
            return "right_chalkboard"
        else:
            # Fallback: sanitize the name
            return name.replace(" ", "_").replace("-", "_").lower()

    def __repr__(self) -> str:
        """String representation."""
        return f"PanoptoStream({self.clean_name}, {self.stream_type})"


class PanoptoAPI:
    """Direct Panopto API client (DeliveryInfo / unofficial endpoint).

    Auth priority:
    1. OAuth2 Bearer token via ``auth`` — preferred; no browser needed.
    2. Explicit ``cookies_file`` (Netscape format).
    3. ``cookies_dict`` (name→value mapping).
    4. Browser cookies extracted via ``browser_cookie3`` — last resort fallback
       only when neither OAuth nor an explicit cookies file is available.
    """

    def __init__(
        self,
        cookies_file: Path | None = None,
        cookies_dict: dict[str, str] | None = None,
        auth: "PanoptoAuth | None" = None,
        browser: str = "chrome",
    ) -> None:
        self.session = requests.Session()
        self._auth = auth
        self._browser = browser

        # DeliveryInfo only accepts browser session cookies — Bearer tokens are
        # rejected by the server. Always load whatever cookies are available so
        # the cookie-based fallback in get_delivery_info actually has something
        # to work with. Only fall back to live browser extraction when there is
        # no OAuth token and no explicit cookies source.
        if cookies_file:
            self._load_cookies_from_file(cookies_file)
        elif cookies_dict:
            for name, value in cookies_dict.items():
                self.session.cookies.set(name, value)
        elif not auth:
            # Live browser extraction only when no OAuth is configured — avoids
            # the Chrome-open / stale-cookie problem for API-authenticated users.
            self._load_browser_cookies(browser)

    def _load_cookies_from_file(self, cookies_file: Path) -> None:
        """Load cookies from Netscape format cookies.txt file.

        Args:
            cookies_file: Path to cookies.txt file.
        """
        with open(cookies_file, "r") as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if not line or line.startswith("#"):
                    continue
                
                try:
                    # Netscape format: domain, flag, path, secure, expiration, name, value
                    parts = line.split("\t")
                    if len(parts) == 7:
                        domain, _, path, secure, expiration, name, value = parts
                        self.session.cookies.set(
                            name=name,
                            value=value,
                            domain=domain,
                            path=path,
                        )
                except Exception:
                    continue

    def _load_browser_cookies(self, browser: str = "chrome") -> None:
        """Load cookies from the specified browser using browser_cookie3."""
        try:
            import browser_cookie3  # type: ignore[import]
            loader = getattr(browser_cookie3, browser, None)
            if loader is None:
                return
            jar = loader(domain_name=".panopto.com")
            for cookie in jar:
                self.session.cookies.set(cookie.name, cookie.value, domain=cookie.domain)
        except Exception:
            pass  # browser_cookie3 may fail if browser is open or not installed

    def get_delivery_info(self, video_id: str, server: str = "mit.hosted.panopto.com") -> dict[str, Any]:
        """Get delivery information for a Panopto video.

        Tries OAuth2 Bearer token first (no browser required), then falls back
        to session cookies if the Bearer attempt is rejected.

        Args:
            video_id: Panopto video ID.
            server: Panopto server hostname.

        Returns:
            Delivery info dictionary.

        Raises:
            PanoptoAPIError: If API request fails.
        """
        url = f"https://{server}/Panopto/Pages/Viewer/DeliveryInfo.aspx"
        params = {"deliveryId": video_id, "responseType": "json"}

        # Strategy 1: try Bearer token directly — some Panopto versions accept it.
        if self._auth:
            try:
                token = self._auth.get_access_token()
                r = requests.get(
                    url,
                    params=params,
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=30,
                )
                if r.ok:
                    d = r.json()
                    if "ErrorCode" not in d and "LoginRedirect" not in d:
                        return d
            except Exception:
                pass  # fall through to cookie-based attempt

        # Strategy 2: session cookies loaded at init time (browser export or
        # from-token).  Some Panopto instances set enough cookies when you hit
        # the home page with a Bearer token; others need the full browser flow.
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            raise PanoptoAPIError(f"Failed to fetch delivery info: {e}") from e
        except json.JSONDecodeError as e:
            raise PanoptoAPIError(f"Failed to parse API response: {e}") from e

        # Server returns HTTP 200 with an error body when no valid session exists.
        if "ErrorCode" in data or "LoginRedirect" in data:
            err = data.get("ErrorMessage") or "session cookie required"
            raise PanoptoAPIError(
                f"DeliveryInfo authentication failed ({err}). "
                "Run: panopto-downloader auth export-cookies"
            )

        return data

    def get_podcast_streams(self, video_id: str, server: str = "mit.hosted.panopto.com") -> list["PanoptoStream"]:
        """Return the composed/podcast streams from DeliveryInfo.

        Panopto stores the pre-composed (stitched) video under the
        ``PodcastStreams`` key in the DeliveryInfo response. These are the
        download-ready MP4/HLS URLs that do not require the browser-based viewer.

        Args:
            video_id: Panopto video ID.
            server:   Panopto server hostname.

        Returns:
            List of :class:`PanoptoStream` objects (often just one).
        """
        delivery_info = self.get_delivery_info(video_id, server)
        delivery = (
            delivery_info.get("Delivery")
            or delivery_info.get("d", {}).get("Delivery")
            or {}
        )
        podcast_data = delivery.get("PodcastStreams", [])
        return [PanoptoStream(s) for s in podcast_data]

    def get_all_streams(self, video_id: str, server: str = "mit.hosted.panopto.com") -> list[PanoptoStream]:
        """Get all available streams for a Panopto video.

        Args:
            video_id: Panopto video ID.
            server: Panopto server hostname.

        Returns:
            List of PanoptoStream objects.

        Raises:
            PanoptoAPIError: If API request fails or no streams are found.
        """
        delivery_info = self.get_delivery_info(video_id, server)

        # Newer Panopto versions wrap the delivery under a "d" key (JSON hijacking
        # protection); handle both layouts transparently.
        delivery = (
            delivery_info.get("Delivery")
            or delivery_info.get("d", {}).get("Delivery")
            or {}
        )

        streams_data = delivery.get("Streams", [])

        if not streams_data:
            # Build a helpful message listing what top-level keys were present
            # so it's easy to diagnose unexpected response shapes.
            keys = list(delivery_info.keys())
            delivery_keys = list(delivery.keys()) if delivery else []
            raise PanoptoAPIError(
                f"No streams found in delivery info. "
                f"Response keys: {keys}. "
                f"Delivery keys: {delivery_keys}. "
                f"This video may only have a composed/single-stream recording."
            )

        return [PanoptoStream(stream_data) for stream_data in streams_data]

    @staticmethod
    def extract_video_id(url: str) -> tuple[str, str]:
        """Extract video ID and server from Panopto URL.

        Args:
            url: Panopto video URL.

        Returns:
            Tuple of (video_id, server).

        Raises:
            PanoptoAPIError: If URL is invalid.
        """
        parsed = urllib.parse.urlparse(url)
        
        # Extract server
        server = parsed.netloc
        if not server:
            raise PanoptoAPIError(f"Invalid Panopto URL: {url}")

        # Extract video ID from query parameters
        query_params = urllib.parse.parse_qs(parsed.query)
        video_id = query_params.get("id", [None])[0]
        
        if not video_id:
            raise PanoptoAPIError(f"No video ID found in URL: {url}")

        return video_id, server


# ---------------------------------------------------------------------------
# Panopto REST API v1 — requires OAuth2 (see auth.py)
# ---------------------------------------------------------------------------


class PanoptoFolder:
    """A Panopto folder returned by the REST API."""

    def __init__(self, data: dict[str, Any]) -> None:
        self.id: str = data.get("Id", "")
        self.name: str = data.get("Name", "Unknown")
        self.parent_folder_id: str = data.get("ParentFolder", "") or ""
        self.num_sessions: int = data.get("NumSessions", 0)
        self.num_children: int = data.get("NumChildren", 0)

    def __repr__(self) -> str:
        return f"PanoptoFolder({self.name!r}, sessions={self.num_sessions})"


class PanoptoSession:
    """A Panopto session (video/recording) returned by the REST API."""

    def __init__(self, data: dict[str, Any], server: str = "") -> None:
        self.id: str = data.get("Id", "")
        self.name: str = data.get("Name", "Unknown")
        self.description: str = data.get("Description", "") or ""
        self.duration: float = data.get("Duration", 0.0) or 0.0
        self.start_time: str = data.get("StartTime", "") or ""
        self.folder_id: str = data.get("FolderId", "") or ""
        folder_details = data.get("FolderDetails") or {}
        self.folder_name: str = folder_details.get("Name", "") or ""
        # ViewerUrl may come from API; fall back to constructing it
        self._viewer_url: str = data.get("ViewerUrl", "") or ""
        self._server = server

    @property
    def viewer_url(self) -> str:
        if self._viewer_url:
            return self._viewer_url
        if self.id and self._server:
            return f"https://{self._server}/Panopto/Pages/Viewer.aspx?id={self.id}"
        return ""

    @property
    def duration_str(self) -> str:
        if not self.duration:
            return "Unknown"
        total = int(self.duration)
        hours, remainder = divmod(total, 3600)
        mins, secs = divmod(remainder, 60)
        if hours:
            return f"{hours}h {mins:02d}m"
        return f"{mins}m {secs:02d}s"

    def __repr__(self) -> str:
        return f"PanoptoSession({self.name!r}, {self.duration_str})"


class PanoptoRestAPI:
    """Panopto REST API v1 client.

    Authenticates using OAuth2 access tokens from :class:`~.auth.PanoptoAuth`.
    All methods raise :class:`PanoptoAPIError` on request failures and
    :class:`~.auth.AuthError` if the auth state is invalid.
    """

    def __init__(self, auth: PanoptoAuth) -> None:
        self.auth = auth
        self._session = requests.Session()

    # ------------------------------------------------------------------
    # Folders
    # ------------------------------------------------------------------

    def get_folder(self, folder_id: str) -> PanoptoFolder:
        """Fetch a single folder by ID."""
        data = self._get(f"folders/{folder_id}")
        return PanoptoFolder(data)

    def list_child_folders(self, folder_id: str, max_results: int = 200) -> list[PanoptoFolder]:
        """Return all child folders inside *folder_id*."""
        data = self._get(
            f"folders/{folder_id}/children",
            {"sortField": "Name", "sortOrder": "Asc", "maxResults": max_results},
        )
        return [PanoptoFolder(f) for f in data.get("Results", [])]

    # Panopto uses this sentinel GUID to represent the root of the folder tree
    ROOT_FOLDER_ID = "00000000-0000-0000-0000-000000000000"

    def list_root_folders(self, max_results: int = 100) -> list[PanoptoFolder]:
        """Return the top-level folders accessible to the authenticated user."""
        return self.list_child_folders(self.ROOT_FOLDER_ID, max_results=max_results)

    def search_folders(self, query: str, max_results: int = 50) -> list[PanoptoFolder]:
        """Full-text search for folders by name. Query must be non-empty."""
        if not query.strip():
            return self.list_root_folders(max_results)
        data = self._get(
            "folders/search",
            {"searchQuery": query, "sortField": "Name", "sortOrder": "Asc", "maxResults": max_results},
        )
        return [PanoptoFolder(f) for f in data.get("Results", [])]

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------

    def list_sessions(
        self,
        folder_id: str,
        page: int = 0,
        page_size: int = 50,
        sort_field: str = "StartTime",
        sort_order: str = "Desc",
    ) -> tuple[list[PanoptoSession], int]:
        """Return sessions in *folder_id* plus the total count.

        Args:
            folder_id:  Folder to list.
            page:       Zero-based page number.
            page_size:  Results per page (max 200).
            sort_field: ``StartTime``, ``Name``, or ``Duration``.
            sort_order: ``Asc`` or ``Desc``.

        Returns:
            ``(sessions, total_count)``
        """
        data = self._get(
            f"folders/{folder_id}/sessions",
            {
                "sortField": sort_field,
                "sortOrder": sort_order,
                "pageNumber": page,
                "maxResults": page_size,
            },
        )
        server = self.auth.get_server()
        sessions = [PanoptoSession(s, server) for s in data.get("Results", [])]
        total = data.get("TotalNumberOfResults", len(sessions))
        return sessions, int(total)

    def get_all_sessions(
        self,
        folder_id: str,
        recurse: bool = True,
        _depth: int = 0,
    ) -> list[PanoptoSession]:
        """Fetch every session in *folder_id*, paging automatically.

        When *recurse* is True (default) and the folder contains no direct
        sessions, child folders are searched one level deep so that course
        folders whose sessions live in section sub-folders are handled
        transparently.
        """
        page_size = 200
        page = 0
        results: list[PanoptoSession] = []
        while True:
            batch, total = self.list_sessions(
                folder_id, page=page, page_size=page_size,
                sort_field="StartTime", sort_order="Asc",
            )
            results.extend(batch)
            if len(results) >= total or not batch:
                break
            page += 1

        # If this folder is empty and we haven't gone too deep, check children
        if not results and recurse and _depth < 3:
            try:
                children = self.list_child_folders(folder_id)
                for child in children:
                    results.extend(
                        self.get_all_sessions(child.id, recurse=True, _depth=_depth + 1)
                    )
            except PanoptoAPIError:
                pass

        return results

    def search_sessions(self, query: str, max_results: int = 250) -> list[PanoptoSession]:
        """Full-text search for sessions across all accessible content."""
        data = self._get(
            "sessions/search",
            {"searchQuery": query, "maxResults": max_results},
        )
        server = self.auth.get_server()
        return [PanoptoSession(s, server) for s in data.get("Results", [])]

    def get_session(self, session_id: str) -> PanoptoSession:
        """Fetch a single session by ID."""
        data = self._get(f"sessions/{session_id}")
        server = self.auth.get_server()
        return PanoptoSession(data, server)

    # ------------------------------------------------------------------
    # Users
    # ------------------------------------------------------------------

    def get_user_info(self) -> dict[str, Any]:
        """Return the current authenticated user's profile."""
        return self._get("users/self")  # type: ignore[no-any-return]

    def get_session_transcripts(self, session_id: str) -> list[dict[str, Any]]:
        """Return available transcripts for a session.

        Each entry is a dict with at least ``Language``, ``TranscriptFileUrl``,
        and ``TranscriptType`` keys as returned by the Panopto API.
        """
        try:
            data = self._get(f"sessions/{session_id}/transcripts")
            return data if isinstance(data, list) else data.get("Results", [])  # type: ignore[no-any-return]
        except PanoptoAPIError:
            return []

    def download_transcript(self, transcript_url: str, dest: Path) -> bool:
        """Download a transcript file (SRT/VTT) to *dest*.

        Returns True on success.
        """
        headers = {"Authorization": f"Bearer {self.auth.get_access_token()}"}
        try:
            resp = self._session.get(transcript_url, headers=headers, timeout=60)
            resp.raise_for_status()
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(resp.content)
            return True
        except requests.RequestException:
            return False

    def get_personal_folder_id(self) -> str | None:
        """Return the ID of the current user's personal ('My Folder') folder.

        Returns ``None`` if the API does not expose a personal folder for this
        account (e.g. service accounts).
        """
        try:
            user = self.get_user_info()
            details = user.get("PersonalFolderDetails") or {}
            return details.get("Id") or None
        except PanoptoAPIError:
            return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        server = self.auth.get_server()
        url = f"https://{server}/Panopto/api/v1/{path}"
        headers = {"Authorization": f"Bearer {self.auth.get_access_token()}"}
        try:
            resp = self._session.get(url, headers=headers, params=params, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise PanoptoAPIError(f"REST API request failed [{path}]: {exc}") from exc
        try:
            return resp.json()
        except json.JSONDecodeError as exc:
            raise PanoptoAPIError(f"Invalid JSON from REST API [{path}]") from exc
