"""Command-line interface for Panopto Downloader."""

from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel

from . import __version__
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

        downloader = VideoDownloader(config)

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

            if all_streams:
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


if __name__ == "__main__":
    main()

