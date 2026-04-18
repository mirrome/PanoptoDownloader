"""Command-line interface for Panopto Downloader."""

from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from . import __version__
from .auth import AuthError, PanoptoAuth
from .config import ConfigError, ConfigLoader, create_default_config, load_config
from .downloader import DownloadError, VideoDownloader
from .models import BrowserType

console = Console()

# Custom help settings: -h for short help, --help for detailed
CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


def print_banner() -> None:
    """Print the application banner."""
    console.print(
        Panel.fit(
            "[bold blue]Panopto Lecture Downloader[/bold blue]\n"
            f"[dim]Version {__version__}[/dim]",
            border_style="blue",
        )
    )


DEFAULT_SERVER = "mitsloan.hosted.panopto.com"


def print_quick_usage() -> None:
    """Print quick usage summary."""
    console.print(
        """
[bold]Quick Usage:[/bold]

  [cyan]panopto-downloader download -u URL -o file.mp4[/cyan]   Download single video
  [cyan]panopto-downloader download -u URL -o name -a[/cyan]    Download all streams
  [cyan]panopto-downloader download[/cyan]                      Batch download from config
  [cyan]panopto-downloader list[/cyan]                          List configured lectures
  [cyan]panopto-downloader --help[/cyan]                        Detailed help

[bold]Options:[/bold]
  -c, --config PATH    Config file (default: config.yaml)
  -b, --browser TYPE   Browser for cookies: chrome, safari
  -n, --dry-run        Preview without downloading
  -v, --verbose        Verbose output
  -h, --help           Show help
  --version            Show version

[dim]Close Chrome before running for reliable cookie access.[/dim]
"""
    )


@click.group(invoke_without_command=True, context_settings=CONTEXT_SETTINGS)
@click.option(
    "--config",
    "-c",
    "config_path",
    type=click.Path(exists=False, path_type=Path),
    help="Path to configuration file (default: config.yaml)",
)
@click.option(
    "--browser",
    "-b",
    type=click.Choice(["chrome", "safari"]),
    help="Browser to extract cookies from",
)
@click.option(
    "--dry-run",
    "-n",
    is_flag=True,
    help="Show what would be downloaded without actually downloading",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose output",
)
@click.version_option(version=__version__, prog_name="panopto-downloader")
@click.pass_context
def main(
    ctx: click.Context,
    config_path: Path | None,
    browser: str | None,
    dry_run: bool,
    verbose: bool,
) -> None:
    """Panopto Lecture Downloader - Download MIT Sloan lecture recordings.

    \b
    QUICK START:
      panopto-downloader download -u URL -o "Lecture.mp4"
      panopto-downloader download                          (batch from config)

    \b
    COMMANDS:
      download   Download lectures (single or batch)
      info       Show video information and streams
      list       List configured lectures with status
      validate   Validate configuration file
      init       Create new config file

    \b
    EXAMPLES:
      # Single video
      panopto-downloader download -u "https://..." -o "Lecture1.mp4"

      # All streams (composed + camera + slides)
      panopto-downloader download -u "https://..." -o "Lecture1" -a

      # Batch with parallel downloads
      panopto-downloader download -p -w 3

    \b
    NOTE: Close Chrome before running for reliable cookie access.
    """
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["dry_run"] = dry_run
    ctx.obj["config_path"] = config_path
    ctx.obj["browser_override"] = browser

    # If no subcommand, run the default download
    if ctx.invoked_subcommand is None:
        ctx.invoke(download)


@main.command(context_settings=CONTEXT_SETTINGS)
@click.option(
    "--url", "-u",
    help="Panopto video URL to download",
)
@click.option(
    "--output", "-o",
    type=click.Path(path_type=Path),
    help="Output filename (e.g., Lecture1.mp4)",
)
@click.option(
    "--all-streams", "-a",
    is_flag=True,
    help="Download all streams: composed, camera, slides",
)
@click.option(
    "--all-cameras",
    is_flag=True,
    help="Download ALL camera angles (PC1, PC2, Wideshot, etc.) using Panopto API",
)
@click.option(
    "--cookies",
    type=click.Path(exists=True, path_type=Path),
    help="Path to cookies.txt file (alternative to --cookies-from-browser)",
)
@click.option(
    "--write-subs/--no-write-subs",
    default=True,
    help="Download subtitles/captions if available (default: True)",
)
@click.option(
    "--parallel/--sequential", "-p/-s",
    default=None,
    help="Parallel or sequential batch downloads",
)
@click.option(
    "--workers", "-w",
    type=int,
    help="Number of parallel workers (1-10)",
)
@click.pass_context
def download(
    ctx: click.Context,
    url: str | None,
    output: Path | None,
    all_streams: bool,
    all_cameras: bool,
    cookies: Path | None,
    write_subs: bool,
    parallel: bool | None,
    workers: int | None,
) -> None:
    """Download lectures from Panopto.

    \b
    MODES:
      Single:  panopto-downloader download -u URL -o file.mp4
      Batch:   panopto-downloader download  (uses config.yaml)

    \b
    EXAMPLES:
      # Download single video
      panopto-downloader download -u "https://..." -o "Lecture1.mp4"

      # Download all streams (composed + camera + slides)
      panopto-downloader download -u "https://..." -o "Lecture1" -a

      # Batch download with 3 parallel workers
      panopto-downloader download -p -w 3

      # Dry run (preview only)
      panopto-downloader download -n
    """
    from .models import AppConfig

    print_banner()

    config_path = ctx.obj.get("config_path")
    browser_override = ctx.obj.get("browser_override")
    dry_run = ctx.obj.get("dry_run", False)
    verbose = ctx.obj.get("verbose", False)

    try:
        # Try to load config, but use defaults if URL is provided and no config found
        try:
            config = load_config(config_path)
        except ConfigError:
            if url:
                # No config file - use defaults for single URL download
                config = AppConfig()
            else:
                # Config required for batch download
                raise

        # Apply browser override if specified
        if browser_override:
            config.browser = BrowserType(browser_override)

        # Use cookies from: 1) CLI option, 2) config file, 3) None (use browser)
        cookies_to_use = cookies or config.cookies_file
        if cookies_to_use:
            cookies_to_use = Path(cookies_to_use)

        downloader = VideoDownloader(config, cookies_file=cookies_to_use, write_subs=write_subs)

        if url:
            # Single video download
            import datetime

            from .models import LectureInfo

            # If output path is provided, use it directly
            if output:
                # Use the filename as-is, extracting just title from stem
                title = output.stem
                course = "download"
            else:
                title = "lecture"
                course = "single_download"

            if all_cameras:
                # Download ALL camera angles using Panopto API
                if output:
                    base_path = config.download_path / output.stem
                else:
                    base_path = config.download_path / f"{course}_{title}_{datetime.date.today()}"

                console.print(f"[bold]Downloading ALL Panopto camera angles to:[/bold] {base_path.parent}")
                results = downloader.download_all_panopto_streams(url, base_path, dry_run=dry_run)

                # Summary already printed by the method
            elif all_streams:
                # Download all streams (composed, camera, slides)
                if output:
                    base_path = config.download_path / output.stem
                else:
                    base_path = config.download_path / f"{course}_{title}_{datetime.date.today()}"

                console.print(f"[bold]Downloading all streams to:[/bold] {base_path.parent}")
                results = downloader.download_all_streams(url, base_path, dry_run=dry_run)

                # Summary
                downloaded = sum(1 for p in results.values() if p is not None)
                console.print(f"\n[bold]Downloaded {downloaded}/3 streams[/bold]")
                for stream_type, path in results.items():
                    if path:
                        console.print(f"  [green]✓[/green] {stream_type}: {path.name}")
                    else:
                        console.print(f"  [yellow]✗[/yellow] {stream_type}: not available")
            else:
                # Single stream download (default: composed/best)
                lecture = LectureInfo(
                    url=url,
                    title=title,
                    course=course,
                    date=datetime.date.today(),
                )

                # Pass the explicit output path if provided
                result = downloader.download_lecture(
                    lecture, dry_run=dry_run, output_path=output
                )
                if not result.success:
                    raise click.ClickException(result.error_message or "Download failed")
        else:
            # Download all from config (batch mode)
            # Apply workers override if specified
            if workers is not None:
                config.download.parallel_workers = workers

            # Determine parallel mode
            use_parallel = parallel if parallel is not None else (config.download.parallel_workers > 1)

            results = downloader.download_all(dry_run=dry_run, parallel=use_parallel)
            failed = [r for r in results if not r.success]
            if failed:
                # Summary already printed by download_all
                pass

    except ConfigError as e:
        raise click.ClickException(str(e)) from e
    except DownloadError as e:
        raise click.ClickException(str(e)) from e


@main.command(context_settings=CONTEXT_SETTINGS)
@click.option("--url", "-u", required=True, help="Panopto video URL to analyze")
@click.pass_context
def info(ctx: click.Context, url: str) -> None:
    """Show information about a Panopto video.

    \b
    EXAMPLE:
      panopto-downloader info -u "https://mitsloan.hosted.panopto.com/..."
    """
    from .models import AppConfig

    print_banner()

    config_path = ctx.obj.get("config_path")
    browser_override = ctx.obj.get("browser_override")

    try:
        # Try to load config, but use defaults if not found
        try:
            config = load_config(config_path)
        except ConfigError:
            # No config file - use defaults for info command
            config = AppConfig()

        if browser_override:
            config.browser = BrowserType(browser_override)

        downloader = VideoDownloader(config)

        console.print(f"\n[bold]Fetching info for:[/bold] {url}\n")

        video_info = downloader.get_video_info(url)

        console.print(f"[bold]Title:[/bold] {video_info.get('title', 'Unknown')}")
        console.print(f"[bold]Duration:[/bold] {video_info.get('duration', 0):.0f}s")
        console.print(f"[bold]Uploader:[/bold] {video_info.get('uploader', 'Unknown')}")

        streams = downloader.detect_streams(url)
        if streams:
            console.print(f"\n[bold]Detected Streams ({len(streams)}):[/bold]")
            for stream in streams:
                stream_type = (
                    "Camera" if stream.is_camera else "Slides" if stream.is_slides else "Unknown"
                )
                audio = "✓ audio" if stream.has_audio else "no audio"
                console.print(
                    f"  - {stream.resolution} ({stream_type}) - {stream.codec} - {audio}"
                )
        else:
            console.print("\n[yellow]No separate streams detected (single stream video)[/yellow]")

    except ConfigError as e:
        raise click.ClickException(str(e)) from e
    except DownloadError as e:
        raise click.ClickException(str(e)) from e


@main.command(context_settings=CONTEXT_SETTINGS)
@click.option("--output", "-o", type=click.Path(path_type=Path), default=Path("config.yaml"),
              help="Output path (default: config.yaml)")
def init(output: Path) -> None:
    """Create a new configuration file.

    \b
    EXAMPLE:
      panopto-downloader init
      panopto-downloader init -o finance_course.yaml
    """
    print_banner()

    try:
        create_default_config(output)
        console.print(
            f"\n[green]Created:[/green] {output}\n"
            f"Edit this file to add your Panopto lecture URLs."
        )
    except ConfigError as e:
        raise click.ClickException(str(e)) from e


@main.command(context_settings=CONTEXT_SETTINGS)
@click.pass_context
def validate(ctx: click.Context) -> None:
    """Validate the configuration file.

    \b
    EXAMPLE:
      panopto-downloader validate
      panopto-downloader -c finance.yaml validate
    """
    print_banner()

    config_path = ctx.obj.get("config_path")

    try:
        config = load_config(config_path)
        console.print("[green]✓[/green] Configuration is valid")
        console.print(f"  Browser: {config.browser.value}")
        console.print(f"  Download path: {config.download_path}")
        console.print(f"  Lectures: {len(config.lectures)}")

        if config.lectures:
            console.print("\n[bold]Configured lectures:[/bold]")
            for i, lecture in enumerate(config.lectures, 1):
                console.print(f"  {i}. {lecture.course} - {lecture.title} ({lecture.date})")

    except ConfigError as e:
        raise click.ClickException(str(e)) from e


@main.command("list", context_settings=CONTEXT_SETTINGS)
@click.pass_context
def list_lectures(ctx: click.Context) -> None:
    """List configured lectures with download status.

    \b
    EXAMPLE:
      panopto-downloader list
      panopto-downloader -c finance.yaml list
    """
    from .utils import format_bytes, get_file_info

    print_banner()

    config_path = ctx.obj.get("config_path")

    try:
        config = load_config(config_path)

        if not config.lectures:
            console.print("[yellow]No lectures configured.[/yellow]")
            console.print("Run 'panopto-downloader init' to create a config file.")
            return

        console.print(f"[bold]Configured Lectures ({len(config.lectures)}):[/bold]\n")

        from .utils import format_filename

        for i, lecture in enumerate(config.lectures, 1):
            # Generate expected filename
            filename = format_filename(
                template=config.naming.format,
                course=lecture.course,
                title=lecture.title,
                lecture_date=lecture.date,
                date_format=config.naming.date_format,
            )
            expected_path = config.download_path / filename

            # Check if already downloaded
            if expected_path.exists():
                size, _ = get_file_info(expected_path)
                status = f"[green]✓ Downloaded[/green] ({format_bytes(size)})"
            else:
                status = "[dim]Pending[/dim]"

            console.print(f"  {i}. [bold]{lecture.course}[/bold] - {lecture.title}")
            console.print(f"     Date: {lecture.date}")
            if lecture.instructor:
                console.print(f"     Instructor: {lecture.instructor}")
            console.print(f"     Status: {status}")
            console.print()

    except ConfigError as e:
        raise click.ClickException(str(e)) from e


# ---------------------------------------------------------------------------
# auth commands
# ---------------------------------------------------------------------------


@main.group(context_settings=CONTEXT_SETTINGS)
def auth() -> None:
    """Manage Panopto API authentication.

    \b
    COMMANDS:
      login    Authenticate via browser (OAuth2 PKCE)
      status   Show current auth state
      logout   Delete stored tokens
    """


@auth.command("login", context_settings=CONTEXT_SETTINGS)
@click.option(
    "--server", "-s",
    default=None,
    help=f"Panopto server hostname (default: $PANOPTO_SERVER or {DEFAULT_SERVER})",
)
@click.option(
    "--client-id", "-i",
    default=None,
    help="API client ID (default: $PANOPTO_CLIENT_ID from .env)",
)
@click.option(
    "--client-secret",
    default=None,
    help="API client secret (default: $PANOPTO_CLIENT_SECRET from .env)",
)
def auth_login(server: str | None, client_id: str | None, client_secret: str | None) -> None:
    """Authenticate with Panopto via your browser.

    \b
    Credentials are read automatically from a .env file in the current
    directory (PANOPTO_SERVER, PANOPTO_CLIENT_ID, PANOPTO_CLIENT_SECRET).
    You only need to pass flags when overriding those values.

    \b
    EXAMPLES:
      panopto-downloader auth login                      (uses .env)
      panopto-downloader auth login --client-id "id"    (explicit)

    \b
    HOW IT WORKS:
      1. Your browser opens the Panopto login page.
      2. Sign in with your institutional account.
      3. Tokens are saved to ~/.config/panopto-downloader/tokens.json.
      You will not need to log in again until the refresh token expires.
    """
    from .auth import get_env

    print_banner()

    # Resolve values: flag → env var / .env → hardcoded default
    resolved_server = server or get_env("PANOPTO_SERVER") or DEFAULT_SERVER
    resolved_client_id = client_id or get_env("PANOPTO_CLIENT_ID")
    resolved_secret = client_secret or get_env("PANOPTO_CLIENT_SECRET")

    if not resolved_client_id:
        raise click.ClickException(
            "No client ID found. Pass --client-id or set PANOPTO_CLIENT_ID in .env"
        )

    pa = PanoptoAuth()

    if pa.is_logged_in():
        st = pa.status()
        if not click.confirm(
            f"Already logged in to {st['server']}. Re-authenticate?",
            default=False,
        ):
            return

    console.print(f"\n[bold]Opening browser for[/bold] {resolved_server} …")
    console.print("[dim]Waiting up to 2 minutes for you to complete login in the browser.[/dim]\n")

    try:
        pa.login(resolved_server, resolved_client_id, resolved_secret)
    except AuthError as exc:
        raise click.ClickException(str(exc)) from exc

    console.print(f"[green]✓[/green] Logged in to [bold]{resolved_server}[/bold]")
    console.print("[dim]Tokens saved. Run 'panopto-downloader browse' to explore content.[/dim]")


@auth.command("status", context_settings=CONTEXT_SETTINGS)
def auth_status() -> None:
    """Show current authentication status."""
    print_banner()
    pa = PanoptoAuth()
    st = pa.status()

    if not st["logged_in"]:
        console.print("[yellow]Not logged in.[/yellow]")
        console.print("Run: [cyan]panopto-downloader auth login --client-id YOUR_ID[/cyan]")
        return

    secs: int = st["token_expires_in_seconds"]  # type: ignore[assignment]
    if secs > 3600:
        expiry = f"{secs // 3600}h {(secs % 3600) // 60}m"
    elif secs > 60:
        expiry = f"{secs // 60}m {secs % 60}s"
    else:
        expiry = f"{secs}s (expiring soon)"

    console.print(f"[green]✓[/green] Logged in to [bold]{st['server']}[/bold]")
    console.print(f"  Client ID:      {st['client_id']}")
    console.print(f"  Access token:   expires in {expiry}")
    console.print(
        f"  Refresh token:  {'yes' if st['has_refresh_token'] else '[yellow]no[/yellow]'}"
    )


@auth.command("export-cookies", context_settings=CONTEXT_SETTINGS)
@click.option(
    "--browser", "-b",
    default="chrome",
    show_default=True,
    help="Browser to export cookies from",
)
@click.option(
    "--output", "-o",
    type=click.Path(path_type=Path),
    default=None,
    help="Output path (default: ~/.config/panopto-downloader/cookies.txt)",
)
def auth_export_cookies(browser: str, output: Path | None) -> None:
    """Export browser cookies to a file for reliable offline use.

    \b
    Closes the dependency on Chrome being shut before every download.
    Run this once after logging into Panopto in your browser, then all
    subsequent downloads will use the exported file automatically.

    \b
    EXAMPLE:
      panopto-downloader auth export-cookies
      panopto-downloader auth export-cookies --browser safari
    """
    import subprocess as _sp

    print_banner()

    dest = output or Path("~/.config/panopto-downloader/cookies.txt").expanduser()
    dest.parent.mkdir(parents=True, exist_ok=True)

    pa = PanoptoAuth()
    server = pa.get_server() if pa.is_logged_in() else DEFAULT_SERVER

    console.print(f"\n[bold]Exporting cookies from {browser}…[/bold]")
    console.print(
        f"[dim]Using yt-dlp to read {browser}'s cookie store "
        f"(Chrome must be closed for best results)[/dim]\n"
    )

    # Use yt-dlp's battle-tested browser cookie extraction; --skip-download
    # means we only export the jar without actually downloading anything.
    probe_url = f"https://{server}/Panopto/Pages/Home.aspx"
    cmd = [
        "yt-dlp",
        "--cookies-from-browser", browser,
        "--cookies", str(dest),
        "--skip-download",
        probe_url,
    ]

    result = _sp.run(cmd, capture_output=True, text=True)

    if dest.exists() and dest.stat().st_size > 100:
        line_count = dest.read_text().count("\n")
        console.print(f"[green]✓[/green] Cookies exported to [bold]{dest}[/bold]")
        console.print(f"  [dim]{line_count} cookie entries[/dim]")
        console.print(
            "\n[dim]This file will be used automatically for all future downloads.[/dim]"
        )
    else:
        err = result.stderr.strip().splitlines()[-3:] if result.stderr else ["unknown error"]
        raise click.ClickException(
            f"Cookie export failed.\n" + "\n".join(err)
        )


@auth.command("logout", context_settings=CONTEXT_SETTINGS)
def auth_logout() -> None:
    """Delete stored tokens."""
    print_banner()
    pa = PanoptoAuth()
    if not pa.is_logged_in():
        console.print("[yellow]Not logged in — nothing to clear.[/yellow]")
        return
    pa.logout()
    console.print("[green]✓[/green] Logged out. Tokens deleted.")


# ---------------------------------------------------------------------------
# browse command
# ---------------------------------------------------------------------------


@main.command(context_settings=CONTEXT_SETTINGS)
@click.option(
    "--folder", "-f",
    "folder_id",
    help="Folder ID to open directly (skip interactive navigation)",
)
@click.option(
    "--search", "-q",
    "search_query",
    help="Search sessions by name (client-side filtered for precision)",
)
@click.option(
    "--folder-search", "-F",
    "folder_search",
    help="Find a course folder by name then list ALL its sessions",
)
@click.option(
    "--output-dir", "-o",
    type=click.Path(path_type=Path),
    help="Download directory (overrides config)",
)
@click.option(
    "--all-streams", "-a",
    is_flag=True,
    help="Download everything: composed view + every camera angle + slides + captions",
)
@click.option(
    "--limit", "-l",
    default=250,
    show_default=True,
    help="Max results fetched from the API before client-side filtering",
)
@click.option(
    "--dry-run", "-n",
    is_flag=True,
    help="Show what would be downloaded without downloading",
)
def browse(
    folder_id: str | None,
    search_query: str | None,
    folder_search: str | None,
    output_dir: Path | None,
    all_streams: bool,
    limit: int,
    dry_run: bool,
) -> None:
    """Browse Panopto folders and download sessions via the REST API.

    \b
    SEARCH MODES:
      --search QUERY        Session title search with client-side filtering
      --folder-search NAME  Find course folder by name, list ALL its sessions
      --folder UUID         Jump straight into a known folder ID

    \b
    EXAMPLES:
      panopto-downloader browse
      panopto-downloader browse --search "15.707"
      panopto-downloader browse --folder-search "15.707"
      panopto-downloader browse --folder-search "Global Strategy" --all-streams

    \b
    REQUIREMENTS:
      Run 'panopto-downloader auth login' first.
    """
    from .models import AppConfig
    from .panopto_api import PanoptoAPIError, PanoptoRestAPI, PanoptoSession

    print_banner()

    pa = PanoptoAuth()
    if not pa.is_logged_in():
        raise click.ClickException(
            "Not logged in. Run: panopto-downloader auth login --client-id YOUR_ID"
        )

    try:
        api = PanoptoRestAPI(pa)

        # ---- Folder-search mode -----------------------------------------
        if folder_search:
            console.print(f"\n[bold]Searching for folder:[/bold] {folder_search}\n")
            folders = api.search_folders(folder_search, max_results=20)
            term = folder_search.lower()
            matched = [f for f in folders if term in f.name.lower()] or folders

            if not matched:
                console.print("[yellow]No folders found.[/yellow]")
                return

            console.print(f"[dim]Found {len(matched)} folder(s) — fetching sessions from all…[/dim]\n")

            all_sessions: list[Any] = []
            for f in matched:
                batch = api.get_all_sessions(f.id)
                for s in batch:
                    # Tag each session with its source folder name for display
                    s._source_folder = f.name
                all_sessions.extend(batch)

            if not all_sessions:
                console.print("[yellow]No sessions found in any of these folders.[/yellow]")
                return

            # Sort by date then title so the combined list is coherent
            all_sessions.sort(key=lambda s: (s.start_time or "", s.name))

            console.print(f"[dim]Total: {len(all_sessions)} session(s) across {len(matched)} folder(s)[/dim]\n")
            _display_sessions(all_sessions, show_folder=True)
            selected = _prompt_session_selection(all_sessions)

        # ---- Session search mode ----------------------------------------
        elif search_query:
            console.print(f"\n[bold]Searching for:[/bold] {search_query}\n")
            raw_sessions = api.search_sessions(search_query, max_results=limit)
            # Client-side filter: only keep sessions whose title contains the query
            term = search_query.lower()
            sessions = [s for s in raw_sessions if term in s.name.lower()]
            if not sessions:
                # Fall back to unfiltered results with a note
                sessions = raw_sessions
                console.print(
                    f"[yellow]No exact title matches — showing {len(sessions)} "
                    f"API results (Panopto full-text search).[/yellow]\n"
                )
            if not sessions:
                console.print("[yellow]No sessions found.[/yellow]")
                return
            _display_sessions(sessions)
            selected = _prompt_session_selection(sessions)

        # ---- Folder mode ------------------------------------------------
        elif folder_id:
            folder = api.get_folder(folder_id)
            console.print(f"\n[bold]Folder:[/bold] {folder.name}\n")
            sessions, total = api.list_sessions(folder_id, page_size=200)
            if not sessions:
                console.print("[yellow]No sessions in this folder.[/yellow]")
                return
            if total > len(sessions):
                console.print(f"[dim]Showing first {len(sessions)} of {total} sessions.[/dim]\n")
            _display_sessions(sessions)
            selected = _prompt_session_selection(sessions)

        # ---- Interactive navigation ------------------------------------
        else:
            selected = _interactive_browse(api, search_limit=limit)
            if not selected:
                return

        if not selected:
            console.print("[yellow]No sessions selected.[/yellow]")
            return

        # ---- Download --------------------------------------------------
        try:
            config = load_config(None)
        except ConfigError:
            config = AppConfig()

        if output_dir:
            config.download_path = output_dir

        downloader = VideoDownloader(config, write_subs=True, auth=pa)

        console.print(
            f"\n[bold]Downloading {len(selected)} session(s) to:[/bold] {config.download_path}\n"
        )

        for session in selected:
            url = session.viewer_url
            if not url:
                console.print(f"[yellow]⚠[/yellow]  No URL for {session.name!r} — skipping")
                continue

            safe_name = _safe_filename(session.name)
            console.print(
                f"\n[bold bright_white]{'─' * 60}[/bold bright_white]\n"
                f"[bold]→ {session.name}[/bold]\n"
                f"[dim]{url}[/dim]\n"
            )

            if all_streams:
                # Full download: composed + all camera angles + slides + captions
                base = config.download_path / safe_name
                base.parent.mkdir(parents=True, exist_ok=True)
                downloader.download_all_panopto_streams(url, base, dry_run=dry_run)
            else:
                import datetime
                from .models import LectureInfo

                if dry_run:
                    console.print(f"  [dim]Would download: {safe_name}.mp4[/dim]")
                    continue

                lecture = LectureInfo(
                    url=url,
                    title=session.name,
                    course=session.folder_name or "panopto",
                    date=datetime.date.today(),
                )
                output_path = config.download_path / f"{safe_name}.mp4"
                result = downloader.download_lecture(lecture, output_path=output_path)
                if result.success:
                    console.print(f"  [green]✓[/green] Saved: {output_path.name}")
                else:
                    console.print(f"  [red]✗[/red] Failed: {result.error_message}")

    except (AuthError, PanoptoAPIError) as exc:
        raise click.ClickException(str(exc)) from exc


# ---------------------------------------------------------------------------
# browse helpers (not click commands)
# ---------------------------------------------------------------------------


def _display_sessions(sessions: list[Any], show_folder: bool = False) -> None:
    """Render a numbered table of sessions."""
    table = Table(show_header=True, header_style="bold blue", box=None, padding=(0, 1))
    table.add_column("#", style="dim", width=4, justify="right")
    table.add_column("Title", min_width=30)
    if show_folder:
        table.add_column("Folder", style="dim", min_width=12)
    table.add_column("Duration", justify="right")
    table.add_column("Date")

    for i, s in enumerate(sessions, 1):
        date_str = s.start_time[:10] if s.start_time else "—"
        folder_name = getattr(s, "_source_folder", s.folder_name or "")
        if show_folder:
            table.add_row(str(i), s.name, folder_name, s.duration_str, date_str)
        else:
            table.add_row(str(i), s.name, s.duration_str, date_str)

    console.print(table)


def _prompt_session_selection(sessions: list[Any]) -> list[Any]:
    """Ask the user which sessions to download. Accepts '1,3,5-7' or 'all'."""
    console.print(
        "\n[bold]Select sessions to download[/bold] "
        "(e.g. [cyan]1,3,5-7[/cyan] or [cyan]all[/cyan] or [cyan]q[/cyan] to quit):"
    )
    raw = click.prompt("Selection", default="q").strip().lower()

    if raw in ("q", "quit", ""):
        return []
    if raw == "all":
        return list(sessions)

    selected: list[Any] = []
    for part in raw.split(","):
        part = part.strip()
        if "-" in part:
            try:
                lo, hi = part.split("-", 1)
                selected.extend(sessions[int(lo) - 1 : int(hi)])
            except (ValueError, IndexError):
                console.print(f"[yellow]Skipping invalid range: {part}[/yellow]")
        else:
            try:
                selected.append(sessions[int(part) - 1])
            except (ValueError, IndexError):
                console.print(f"[yellow]Skipping invalid number: {part}[/yellow]")

    return selected


def _interactive_browse(api: Any, search_limit: int = 250) -> list[Any]:
    """Navigate the folder hierarchy interactively and return selected sessions."""
    from .panopto_api import PanoptoAPIError

    # Resolve the user's personal folder once at startup
    personal_folder_id: str | None = None
    try:
        personal_folder_id = api.get_personal_folder_id()
    except Exception:
        pass

    breadcrumb: list[tuple[str, str]] = []  # [(folder_id, folder_name), ...]
    current_id: str | None = None

    while True:
        try:
            if current_id is None:
                root_folders = api.list_root_folders(max_results=100)
                location = "Root"
            else:
                root_folders = api.list_child_folders(current_id)
                location = " > ".join(name for _, name in breadcrumb)

            sessions: list[Any] = []
            total_sessions = 0
            if current_id:
                sessions, total_sessions = api.list_sessions(
                    current_id, page_size=100, sort_field="StartTime", sort_order="Asc"
                )

        except (PanoptoAPIError, Exception) as exc:
            console.print(f"[red]Error fetching content:[/red] {exc}")
            return []

        console.print(f"\n[bold]📁 {location}[/bold]")

        options: list[tuple[str, str, Any]] = []  # (label, kind, object)

        if breadcrumb:
            options.append(("↑  Go up", "up", None))

        # Inject "My Folder" shortcut at root when we have a personal folder
        if current_id is None and personal_folder_id:
            options.append(("🏠  My Folder", "folder_id", personal_folder_id))

        for f in root_folders:
            label = f"📁  {f.name}"
            if f.num_sessions:
                label += f"  [dim]({f.num_sessions} sessions)[/dim]"
            options.append((label, "folder", f))

        if sessions:
            options.append(
                (f"── {total_sessions} session(s) ──", "header", None)
            )
            for s in sessions:
                date_str = s.start_time[:10] if s.start_time else ""
                label = f"🎬  {s.name}"
                if date_str:
                    label += f"  [dim]{date_str}[/dim]"
                options.append((label, "session", s))

        if not root_folders and not sessions and not (current_id is None and personal_folder_id):
            console.print("[dim]Empty folder.[/dim]")
            if not breadcrumb:
                return []
            breadcrumb.pop()
            current_id = breadcrumb[-1][0] if breadcrumb else None
            continue

        for i, (label, kind, _) in enumerate(options, 1):
            if kind == "header":
                console.print(f"\n  [dim]{label}[/dim]")
            else:
                console.print(f"  [cyan]{i:2}[/cyan]  {label}")

        console.print(
            "\n  [dim]Commands:[/dim] "
            "[cyan]NUMBER[/cyan] navigate  "
            "[cyan]d NUMBER[/cyan] download  "
            "[cyan]s QUERY[/cyan] search sessions  "
            "[cyan]fs QUERY[/cyan] search folders  "
            "[cyan]q[/cyan] quit"
        )
        raw = click.prompt("", default="q", prompt_suffix="").strip()

        if raw.lower() in ("q", "quit"):
            return []

        # 'fs QUERY' → find folder by name then list its sessions
        if raw.lower().startswith("fs "):
            query = raw[3:].strip()
            if not query:
                console.print("[yellow]Enter a search term after 'fs'.[/yellow]")
                continue
            console.print(f"\n[bold]Searching folders for:[/bold] {query}\n")
            try:
                folders = api.search_folders(query, max_results=20)
                term = query.lower()
                matched = [f for f in folders if term in f.name.lower()] or folders
            except PanoptoAPIError as exc:
                console.print(f"[red]Folder search failed:[/red] {exc}")
                continue
            if not matched:
                console.print("[yellow]No folders found.[/yellow]")
                continue
            for i, f in enumerate(matched, 1):
                count = f"  [dim]({f.num_sessions} sessions)[/dim]" if f.num_sessions else ""
                console.print(f"  [cyan]{i:2}[/cyan]  📁  {f.name}{count}")
            raw2 = click.prompt("\nSelect folder number (or q)", default="1")
            if raw2.lower() == "q":
                continue
            try:
                chosen = matched[int(raw2) - 1]
            except (ValueError, IndexError):
                console.print("[yellow]Invalid selection.[/yellow]")
                continue
            console.print(f"\n[bold]Fetching all sessions in:[/bold] {chosen.name}")
            try:
                all_sess = api.get_all_sessions(chosen.id)
            except PanoptoAPIError as exc:
                console.print(f"[red]Failed:[/red] {exc}")
                continue
            if not all_sess:
                console.print("[yellow]No sessions found.[/yellow]")
                continue
            _display_sessions(all_sess)
            return _prompt_session_selection(all_sess)

        # 's QUERY' → search sessions by name with client-side filtering
        if raw.lower().startswith("s "):
            query = raw[2:].strip()
            if not query:
                console.print("[yellow]Enter a search term after 's'.[/yellow]")
                continue
            console.print(f"\n[bold]Searching sessions for:[/bold] {query}\n")
            try:
                raw_results = api.search_sessions(query, max_results=search_limit)
                term = query.lower()
                results = [s for s in raw_results if term in s.name.lower()] or raw_results
            except PanoptoAPIError as exc:
                console.print(f"[red]Search failed:[/red] {exc}")
                continue
            if not results:
                console.print("[yellow]No sessions found.[/yellow]")
                continue
            _display_sessions(results)
            return _prompt_session_selection(results)

        # 'd N' → download session #N directly
        if raw.lower().startswith("d "):
            try:
                idx = int(raw[2:].strip()) - 1
                kind = options[idx][1]
                obj = options[idx][2]
                if kind == "session":
                    return [obj]
                console.print("[yellow]That item is not a session.[/yellow]")
            except (ValueError, IndexError):
                console.print("[yellow]Invalid number.[/yellow]")
            continue

        try:
            idx = int(raw) - 1
            label, kind, obj = options[idx]
        except (ValueError, IndexError):
            console.print("[yellow]Invalid selection.[/yellow]")
            continue

        if kind == "up":
            breadcrumb.pop()
            current_id = breadcrumb[-1][0] if breadcrumb else None
        elif kind == "folder":
            breadcrumb.append((obj.id, obj.name))
            current_id = obj.id
        elif kind == "folder_id":
            # Direct folder ID shortcut (e.g. My Folder)
            try:
                folder = api.get_folder(obj)
                breadcrumb.append((folder.id, folder.name))
                current_id = folder.id
            except PanoptoAPIError as exc:
                console.print(f"[red]Could not open folder:[/red] {exc}")
        elif kind == "session":
            if current_id and sessions:
                _display_sessions(sessions)
                return _prompt_session_selection(sessions)
            return [obj]


@main.command("batch", context_settings=CONTEXT_SETTINGS)
@click.option(
    "--courses-file", "-c",
    type=click.Path(exists=True, path_type=Path),
    default=Path("courses.yaml"),
    show_default=True,
    help="YAML file listing courses to download",
)
@click.option(
    "--output-dir", "-o",
    type=click.Path(path_type=Path),
    default=None,
    help="Root download directory (overrides output_path in courses.yaml)",
)
@click.option(
    "--all-streams", "-a",
    is_flag=True,
    help="Download composed view + every camera angle + slides + captions",
)
@click.option(
    "--dry-run", "-n",
    is_flag=True,
    help="Show what would be downloaded without downloading anything",
)
@click.option(
    "--only",
    default=None,
    help="Comma-separated list of search terms to process (e.g. '15.720,15.707')",
)
def batch(
    courses_file: Path,
    output_dir: Path | None,
    all_streams: bool,
    dry_run: bool,
    only: str | None,
) -> None:
    """Download all courses listed in a YAML file.

    \b
    Each course is searched by its course number, and all sessions are saved
    to a subfolder named after the course under the root output directory.

    \b
    EXAMPLES:
      # Download everything to the NAS (dry-run first to preview):
      panopto-downloader batch --dry-run
      panopto-downloader batch --output-dir "/Volumes/NAS/MIT EMBA/MIT_Lectures" --all-streams

      # Re-run for specific courses only:
      panopto-downloader batch --all-streams --only "15.720,15.707"

    \b
    REQUIREMENTS:
      Run 'panopto-downloader auth login' and 'panopto-downloader auth export-cookies' first.
    """
    import yaml  # type: ignore[import]
    from .models import AppConfig
    from .panopto_api import PanoptoAPIError, PanoptoRestAPI

    print_banner()

    pa = PanoptoAuth()
    if not pa.is_logged_in():
        raise click.ClickException(
            "Not logged in. Run: panopto-downloader auth login"
        )

    # Load courses YAML
    try:
        with open(courses_file) as f:
            data = yaml.safe_load(f)
    except Exception as exc:
        raise click.ClickException(f"Could not read {courses_file}: {exc}") from exc

    courses: list[dict[str, str]] = data.get("courses", [])
    if not courses:
        raise click.ClickException(f"No courses found in {courses_file}")

    # Resolve output path: CLI flag > YAML field > default
    yaml_output = data.get("output_path")
    root_dir = output_dir or (Path(yaml_output) if yaml_output else Path("~/Videos/MIT_Lectures").expanduser())
    root_dir = root_dir.expanduser()

    # Filter to specific courses if --only given
    if only:
        wanted = {t.strip().lower() for t in only.split(",")}
        courses = [c for c in courses if c.get("search", "").lower() in wanted]
        if not courses:
            raise click.ClickException(f"No courses matched --only filter: {only}")

    mode = "[DRY RUN] " if dry_run else ""
    streams_label = "all streams" if all_streams else "composed view"
    console.print(
        f"\n[bold]{mode}Batch download — {len(courses)} course(s)[/bold]\n"
        f"  Output:  [cyan]{root_dir}[/cyan]\n"
        f"  Mode:    {streams_label}\n"
    )

    api = PanoptoRestAPI(pa)

    # Validate the token is actually usable — is_logged_in() only checks disk.
    # Use folder search rather than users/self (some instances don't support it).
    try:
        api.list_root_folders(max_results=1)
    except (AuthError, PanoptoAPIError) as exc:
        raise click.ClickException(
            f"Authentication failed — your session has likely expired.\n"
            f"  Error: {exc}\n"
            f"  Fix:   panopto-downloader auth login"
        ) from exc

    try:
        config = load_config(None)
    except ConfigError:
        config = AppConfig()

    config.download_path = root_dir
    downloader = VideoDownloader(config, write_subs=True, auth=pa)

    total_courses = len(courses)
    total_sessions_downloaded = 0
    total_sessions_failed = 0
    skipped_courses: list[str] = []

    for ci, course in enumerate(courses, 1):
        search_term: str = course.get("search", "")
        folder_name: str = course.get("folder", search_term)
        course_dir = root_dir / _safe_filename(folder_name)

        console.print(
            f"\n[bold bright_white]{'═' * 60}[/bold bright_white]\n"
            f"[bold cyan]({ci}/{total_courses})[/bold cyan] "
            f"[bold]{folder_name}[/bold]  [dim](search: {search_term!r})[/dim]"
        )

        # Find Panopto folders matching the search term
        try:
            folders = api.search_folders(search_term, max_results=20)
            term_lower = search_term.lower()
            matched = [f for f in folders if term_lower in f.name.lower()] or folders
        except PanoptoAPIError as exc:
            console.print(f"  [red]✗ Folder search failed:[/red] {exc}")
            skipped_courses.append(folder_name)
            continue

        if not matched:
            console.print(f"  [yellow]⚠  No Panopto folders found for {search_term!r}[/yellow]")
            skipped_courses.append(folder_name)
            continue

        console.print(f"  [dim]Found {len(matched)} folder(s): {', '.join(f.name for f in matched)}[/dim]")

        # Collect all sessions across matching folders
        sessions: list[Any] = []
        for f in matched:
            try:
                batch_sessions = api.get_all_sessions(f.id)
                sessions.extend(batch_sessions)
            except PanoptoAPIError as exc:
                console.print(f"  [yellow]⚠  Could not list sessions in {f.name!r}: {exc}[/yellow]")

        if not sessions:
            console.print(f"  [yellow]⚠  No sessions found[/yellow]")
            skipped_courses.append(folder_name)
            continue

        sessions.sort(key=lambda s: s.start_time or "")
        console.print(f"  [green]{len(sessions)} session(s) found[/green]")

        if dry_run:
            console.print(f"  [dim]Would create: {course_dir}[/dim]")
            for s in sessions:
                console.print(f"    [dim]• {s.name}[/dim]")
            continue

        course_dir.mkdir(parents=True, exist_ok=True)

        for si, session in enumerate(sessions, 1):
            url = session.viewer_url
            if not url:
                console.print(f"  [yellow]⚠  No URL for {session.name!r} — skipping[/yellow]")
                continue

            safe_name = _safe_filename(session.name)
            console.print(
                f"\n  [bold]({si}/{len(sessions)})[/bold] {session.name}"
            )

            if all_streams:
                base = course_dir / safe_name
                try:
                    downloader.download_all_panopto_streams(url, base, dry_run=False)
                    total_sessions_downloaded += 1
                except DownloadError as exc:
                    console.print(f"    [red]✗ Failed:[/red] {exc}")
                    total_sessions_failed += 1
            else:
                import datetime
                from .models import LectureInfo

                lecture = LectureInfo(
                    url=url,
                    title=session.name,
                    course=folder_name,
                    date=datetime.date.today(),
                )
                output_path = course_dir / f"{safe_name}.mp4"
                result = downloader.download_lecture(lecture, output_path=output_path)
                if result.success:
                    total_sessions_downloaded += 1
                else:
                    console.print(f"    [red]✗ Failed:[/red] {result.error_message}")
                    total_sessions_failed += 1

    # Final summary
    console.print(
        f"\n[bold]{'═' * 60}[/bold]\n"
        f"[bold]Batch complete[/bold]\n"
        f"  [green]Sessions downloaded:[/green] {total_sessions_downloaded}\n"
        f"  [red]Sessions failed:[/red]     {total_sessions_failed}"
    )
    if skipped_courses:
        console.print(f"  [yellow]Courses skipped (no folder found):[/yellow]")
        for name in skipped_courses:
            console.print(f"    • {name}")


def _safe_filename(name: str) -> str:
    """Strip characters that are unsafe in file/directory names."""
    import re
    name = re.sub(r'[<>:"/\\|?*]', "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name[:200] or "session"


# ---------------------------------------------------------------------------
# discover command — exhaustive folder scan
# ---------------------------------------------------------------------------


@main.command("discover", context_settings=CONTEXT_SETTINGS)
@click.option(
    "--courses-file", "-c",
    type=click.Path(path_type=Path),
    default=Path("courses.yaml"),
    show_default=True,
    help="Existing courses.yaml to compare against (shows NEW folders only)",
)
@click.option(
    "--all/--new-only", "-a/-n",
    "show_all",
    default=False,
    show_default=True,
    help="Show all discovered folders (default: only folders not in courses.yaml)",
)
@click.option(
    "--queries", "-q",
    default="EMBA,15.,6.,18.,Spring Term,Fall Term,IAP",
    show_default=True,
    help="Comma-separated search queries to run against Panopto folders",
)
def discover(
    courses_file: Path,
    show_all: bool,
    queries: str,
) -> None:
    """Discover all Panopto course folders accessible to your account.

    \b
    Panopto's folder tree is not navigable for viewer-role accounts, so this
    command runs broad keyword searches instead and deduplicates the results.
    Any folder not already covered by courses.yaml is flagged as NEW.

    \b
    EXAMPLES:
      panopto-downloader discover
      panopto-downloader discover --all                    # show known + new
      panopto-downloader discover --queries "EMBA,6.,18."  # custom queries

    \b
    REQUIREMENTS:
      Run 'panopto-downloader auth login' first.
    """
    import yaml  # type: ignore[import]
    from .panopto_api import PanoptoAPIError, PanoptoFolder, PanoptoRestAPI

    print_banner()

    pa = PanoptoAuth()
    if not pa.is_logged_in():
        raise click.ClickException(
            "Not logged in. Run: panopto-downloader auth login"
        )

    # Load known search terms from courses.yaml for comparison
    known_terms: set[str] = set()
    known_folders_in_yaml: set[str] = set()
    if courses_file.exists():
        try:
            with open(courses_file) as f:
                yaml_data = yaml.safe_load(f) or {}
            for course in yaml_data.get("courses", []):
                term = course.get("search", "").strip().lower()
                folder = course.get("folder", "").strip().lower()
                if term:
                    known_terms.add(term)
                if folder:
                    known_folders_in_yaml.add(folder)
            console.print(
                f"[dim]Loaded {len(known_terms)} known course search terms from {courses_file}[/dim]"
            )
        except Exception as exc:
            console.print(f"[yellow]Could not load {courses_file}: {exc}[/yellow]")
    else:
        console.print(f"[dim]{courses_file} not found — will show all discovered folders[/dim]")

    api = PanoptoRestAPI(pa)

    # Validate token is actually usable (is_logged_in only checks disk).
    # users/self is unsupported on some instances; use folders/search instead.
    try:
        api.search_folders("test", max_results=1)
    except (AuthError, PanoptoAPIError) as exc:
        raise click.ClickException(
            f"Authentication failed — your session has likely expired.\n"
            f"  Error: {exc}\n"
            f"  Fix:   panopto-downloader auth login"
        ) from exc

    search_queries = [q.strip() for q in queries.split(",") if q.strip()]
    console.print(
        f"\n[bold]Searching Panopto for accessible course folders[/bold]\n"
        f"[dim]Queries: {', '.join(repr(q) for q in search_queries)}[/dim]\n"
    )

    # Run each search query and collect unique folders by ID
    discovered: dict[str, PanoptoFolder] = {}  # id -> folder

    try:
        for q in search_queries:
            with console.status(f"[bold green]Searching '{q}'…[/bold green]"):
                try:
                    folders = api.search_folders(q, max_results=200)
                    new_count = 0
                    for f in folders:
                        if f.id not in discovered:
                            discovered[f.id] = f
                            new_count += 1
                    console.print(
                        f"  [dim]'{q}': {len(folders)} result(s), {new_count} new unique folders[/dim]"
                    )
                except (AuthError, PanoptoAPIError) as exc:
                    console.print(f"  [yellow]⚠ Search '{q}' failed: {exc}[/yellow]")
    except (AuthError, PanoptoAPIError) as exc:
        raise click.ClickException(
            f"Session expired during search.\n"
            f"  Error: {exc}\n"
            f"  Fix:   panopto-downloader auth login"
        ) from exc

    if not discovered:
        console.print("\n[yellow]No folders found.[/yellow]")
        return

    console.print(f"\n[dim]Total unique folders found: {len(discovered)}[/dim]\n")

    def _is_known(folder: PanoptoFolder) -> bool:
        name_lower = folder.name.lower()
        return any(term in name_lower for term in known_terms)

    all_folders = sorted(discovered.values(), key=lambda f: f.name)
    new_folders = [f for f in all_folders if not _is_known(f)]
    known_folder_list = [f for f in all_folders if _is_known(f)]

    folders_to_show = all_folders if show_all else new_folders

    if not folders_to_show:
        console.print(
            f"[green]✓ All {len(all_folders)} discovered folder(s) are already covered by {courses_file}[/green]"
        )
        return

    table = Table(
        show_header=True,
        header_style="bold blue",
        box=None,
        padding=(0, 1),
    )
    table.add_column("Folder Name", min_width=50)
    table.add_column("Status", justify="left")

    for folder in folders_to_show:
        status = (
            "[dim]already covered[/dim]"
            if _is_known(folder)
            else "[green bold]NEW[/green bold]"
        )
        table.add_row(folder.name, status)

    console.print(table)
    console.print()

    if not show_all:
        console.print(
            f"[bold]{len(new_folders)} new folder(s)[/bold] not covered by {courses_file}  "
            f"[dim]({len(known_folder_list)} already known)[/dim]"
        )
    else:
        console.print(
            f"[bold]{len(all_folders)} total folder(s)[/bold]  "
            f"[dim]({len(new_folders)} new, {len(known_folder_list)} already covered)[/dim]"
        )

    if new_folders:
        console.print(
            "\n[dim]To add a new course, append an entry to courses.yaml:[/dim]\n"
            "[dim]  - search: \"<folder name or course number>\"[/dim]\n"
            "[dim]    folder: \"<human-readable name>\"[/dim]"
        )


if __name__ == "__main__":
    main()

