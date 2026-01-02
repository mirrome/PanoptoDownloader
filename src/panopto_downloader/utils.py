"""Utility functions for Panopto Downloader."""

import datetime
import re
import unicodedata
from pathlib import Path

from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

console = Console()


def sanitize_filename(name: str, max_length: int = 200) -> str:
    """Sanitize a string for use as a filename.

    Args:
        name: The string to sanitize.
        max_length: Maximum length of the filename.

    Returns:
        Sanitized filename string.
    """
    # Normalize unicode characters
    name = unicodedata.normalize("NFKD", name)
    name = name.encode("ascii", "ignore").decode("ascii")

    # Replace problematic characters (but keep dots for course numbers like 15.724)
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    name = re.sub(r"\s+", "_", name)
    name = re.sub(r"_+", "_", name)
    name = name.strip("_ ")  # Only strip underscores and spaces, NOT dots

    # Truncate if too long
    if len(name) > max_length:
        name = name[:max_length].rstrip("_")

    return name


def format_filename(
    template: str,
    course: str,
    title: str,
    lecture_date: datetime.date,
    date_format: str = "%Y-%m-%d",
    extension: str = "mp4",
) -> str:
    """Format a filename using the template and lecture info.

    Args:
        template: Format string with {course}, {title}, {date} placeholders.
        course: Course name/code.
        title: Lecture title.
        lecture_date: Lecture date.
        date_format: strftime format for date.
        extension: File extension (without dot).

    Returns:
        Formatted filename.
    """
    formatted_date = lecture_date.strftime(date_format)

    filename = template.format(
        course=sanitize_filename(course),
        title=sanitize_filename(title),
        date=formatted_date,
    )

    return f"{filename}.{extension}"


def ensure_directory(path: Path) -> Path:
    """Ensure a directory exists, creating it if necessary.

    Args:
        path: Directory path.

    Returns:
        The same path.
    """
    path.mkdir(parents=True, exist_ok=True)
    return path


def format_bytes(size: int) -> str:
    """Format bytes as human-readable string.

    Args:
        size: Size in bytes.

    Returns:
        Formatted string (e.g., "1.5 GB").
    """
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


def format_speed(bytes_downloaded: int, seconds: float) -> str:
    """Format download speed in Mb/s (megabits per second).

    Args:
        bytes_downloaded: Total bytes downloaded.
        seconds: Time taken in seconds.

    Returns:
        Formatted string (e.g., "45.2 Mb/s").
    """
    if seconds <= 0:
        return "N/A"

    # Convert bytes to bits, then to megabits
    bits = bytes_downloaded * 8
    megabits = bits / 1_000_000  # Use SI units (1 Mb = 1,000,000 bits)
    speed_mbps = megabits / seconds

    if speed_mbps >= 1000:
        return f"{speed_mbps / 1000:.1f} Gb/s"
    elif speed_mbps >= 1:
        return f"{speed_mbps:.1f} Mb/s"
    else:
        return f"{speed_mbps * 1000:.1f} Kb/s"


def format_duration(seconds: float) -> str:
    """Format seconds as human-readable duration.

    Args:
        seconds: Duration in seconds.

    Returns:
        Formatted string (e.g., "1h 23m 45s").
    """
    if seconds < 0:
        return "0s"

    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0 or hours > 0:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")

    return " ".join(parts)


def create_download_progress() -> Progress:
    """Create a Rich progress bar for downloads.

    Returns:
        Configured Progress object.
    """
    return Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=console,
    )


def create_processing_progress() -> Progress:
    """Create a Rich progress bar for processing tasks.

    Returns:
        Configured Progress object.
    """
    return Progress(
        SpinnerColumn(),
        TextColumn("[bold green]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
    )


def print_success(message: str) -> None:
    """Print a success message.

    Args:
        message: Message to print.
    """
    console.print(f"[bold green]✓[/bold green] {message}")


def print_error(message: str) -> None:
    """Print an error message.

    Args:
        message: Message to print.
    """
    console.print(f"[bold red]✗[/bold red] {message}")


def print_warning(message: str) -> None:
    """Print a warning message.

    Args:
        message: Message to print.
    """
    console.print(f"[bold yellow]![/bold yellow] {message}")


def print_info(message: str) -> None:
    """Print an info message.

    Args:
        message: Message to print.
    """
    console.print(f"[bold blue]ℹ[/bold blue] {message}")


def get_file_info(path: Path) -> tuple[int, float]:
    """Get file size and duration (if video).

    Args:
        path: Path to file.

    Returns:
        Tuple of (size_bytes, duration_seconds). Duration is 0 if not a video.
    """
    if not path.exists():
        return 0, 0

    size = path.stat().st_size

    # Try to get duration using ffprobe
    try:
        import subprocess

        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "quiet",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
        )
        duration = float(result.stdout.strip()) if result.stdout.strip() else 0
    except (subprocess.SubprocessError, ValueError, FileNotFoundError):
        duration = 0

    return size, duration

