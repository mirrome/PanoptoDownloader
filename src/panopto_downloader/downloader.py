"""Video downloading functionality using yt-dlp."""

import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from rich.console import Console
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .models import (
    AppConfig,
    BrowserType,
    DownloadResult,
    LectureInfo,
    StreamInfo,
)
from .utils import (
    ensure_directory,
    format_bytes,
    format_duration,
    format_filename,
    format_speed,
    get_file_info,
    print_error,
    print_info,
    print_success,
    print_warning,
)

console = Console()


class DownloadError(Exception):
    """Download-related errors."""

    pass


class AuthenticationError(DownloadError):
    """Authentication failures."""

    pass


class VideoDownloader:
    """Downloads videos from Panopto using yt-dlp."""

    def __init__(
        self,
        config: AppConfig,
        cookies_file: Path | None = None,
        write_subs: bool = True,
        auth: "Any | None" = None,
    ) -> None:
        """Initialize downloader.

        Args:
            config:       Application configuration.
            cookies_file: Optional path to cookies.txt file.
            write_subs:   Whether to download subtitles/captions.
            auth:         Optional :class:`~.auth.PanoptoAuth` instance for
                          OAuth-based stream discovery (skips cookie requirement
                          for the DeliveryInfo API).
        """
        self.config = config
        self.download_path = ensure_directory(config.download_path)
        self.cookies_file = cookies_file
        self.write_subs = write_subs
        self.auth = auth

    @staticmethod
    def _exported_cookies_path() -> Path | None:
        """Return the exported cookies file if it exists and is not empty."""
        p = Path("~/.config/panopto-downloader/cookies.txt").expanduser()
        return p if p.exists() and p.stat().st_size > 100 else None

    @staticmethod
    def _is_complete(path: Path, min_bytes: int = 1_000_000) -> bool:
        """Return True if path exists as a complete file (no .part counterpart)."""
        return path.exists() and path.stat().st_size >= min_bytes

    @staticmethod
    def _part_path(path: Path) -> Path:
        """Return the yt-dlp .part file path for a given output path."""
        return path.with_suffix(path.suffix + ".part")

    @staticmethod
    def _yt_dlp_stream_cmd(output_path: Path, stream_url: str) -> list[str]:
        """Build a yt-dlp command for a direct CDN stream URL.

        Includes resume (--continue) and retry flags so interrupted downloads
        pick up from where they left off rather than starting over.
        """
        return [
            "yt-dlp",
            "--no-warnings",
            "--continue",              # resume .part files
            "--retries", "10",         # retry full download on error
            "--fragment-retries", "10",# retry individual HLS fragments
            "--retry-sleep", "5",      # seconds between retries
            "--socket-timeout", "60",  # socket timeout per operation
            "-o", str(output_path),
            stream_url,
        ]

    def _get_yt_dlp_cmd(self) -> list[str]:
        """Get base yt-dlp command with common options.

        Returns:
            List of command arguments.
        """
        cmd = ["yt-dlp"]

        # Used only for the viewer-URL fallback path (no OAuth + no podcast URL).
        # Priority: explicit cookies file > exported cookies file > live browser.
        cookies = self.cookies_file or self._exported_cookies_path()
        if cookies:
            cmd.extend(["--cookies", str(cookies)])
        else:
            cmd.extend(["--cookies-from-browser", self.config.browser.value])
        
        # Subtitle/caption options
        if self.write_subs:
            cmd.extend([
                "--write-subs",           # Download subtitles
                "--write-auto-subs",      # Download auto-generated subs if available
                "--sub-langs", "all",     # Download all available languages
                "--embed-subs",           # Embed subs in video if possible (mp4)
            ])
        
        cmd.append("--no-warnings")
        return cmd

    def _run_yt_dlp(
        self,
        url: str,
        extra_args: list[str] | None = None,
        capture_output: bool = True,
        retry_on_auth: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        """Run yt-dlp with given arguments.

        Args:
            url: Video URL.
            extra_args: Additional yt-dlp arguments.
            capture_output: Whether to capture stdout/stderr.
            retry_on_auth: Whether to retry once on auth failure (cookie timing issue).

        Returns:
            CompletedProcess result.

        Raises:
            DownloadError: If yt-dlp command fails.
            AuthenticationError: If authentication fails.
        """
        cmd = self._get_yt_dlp_cmd()
        if extra_args:
            cmd.extend(extra_args)
        cmd.append(url)

        max_attempts = 2 if retry_on_auth else 1

        for attempt in range(max_attempts):
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=capture_output,
                    text=True,
                    check=False,
                )

                if result.returncode != 0:
                    stderr = result.stderr or ""
                    is_auth_error = (
                        "login" in stderr.lower()
                        or "auth" in stderr.lower()
                        or "registered users" in stderr.lower()
                    )

                    if is_auth_error:
                        if attempt < max_attempts - 1:
                            # Cookie timing issue - wait and retry once
                            print_warning(
                                "Cookie access issue, retrying in 2 seconds..."
                            )
                            time.sleep(2)
                            continue
                        raise AuthenticationError(
                            f"Authentication failed. Make sure you're logged into Panopto "
                            f"in {self.config.browser.value}. Error: {stderr}"
                        )
                    raise DownloadError(f"yt-dlp failed: {stderr}")

                return result

            except FileNotFoundError:
                raise DownloadError(
                    "yt-dlp not found. Install with: pip install yt-dlp"
                ) from None

        # Should not reach here, but just in case
        raise DownloadError("yt-dlp failed after retries")

    def get_video_info(self, url: str) -> dict[str, Any]:
        """Get video metadata using yt-dlp.

        Args:
            url: Video URL.

        Returns:
            Video metadata dictionary.

        Raises:
            DownloadError: If info extraction fails.
        """
        result = self._run_yt_dlp(
            url,
            extra_args=["--dump-json", "--no-download"],
        )

        import json

        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as e:
            raise DownloadError(f"Failed to parse video info: {e}") from e

    def list_formats(self, url: str) -> list[dict[str, Any]]:
        """List available formats for a video.

        Args:
            url: Video URL.

        Returns:
            List of format dictionaries.

        Raises:
            DownloadError: If format listing fails.
        """
        info = self.get_video_info(url)
        return info.get("formats", [])

    def detect_streams(self, url: str) -> list[StreamInfo]:
        """Detect available streams in a Panopto video.

        Args:
            url: Panopto video URL.

        Returns:
            List of detected streams.

        Raises:
            DownloadError: If stream detection fails.
        """
        info = self.get_video_info(url)
        streams: list[StreamInfo] = []

        # Check if this is a multi-stream video
        formats = info.get("formats", [])
        
        # Group formats by their source (some Panopto videos have multiple sources)
        video_formats = [f for f in formats if f.get("vcodec", "none") != "none"]

        # Identify unique streams by resolution
        seen_resolutions: set[str] = set()
        for fmt in video_formats:
            width = fmt.get("width", 0)
            height = fmt.get("height", 0)
            if not width or not height:
                continue

            resolution = f"{width}x{height}"
            if resolution in seen_resolutions:
                continue
            seen_resolutions.add(resolution)

            # Determine if this is camera or slides based on resolution
            # Camera: typically 1280x720, Slides: typically 1366x768
            is_camera = width == 1280 and height == 720
            is_slides = width == 1366 and height == 768

            # If we can't determine, use heuristics
            if not is_camera and not is_slides:
                # Assume wider aspect ratio is slides
                aspect_ratio = width / height if height else 0
                is_slides = aspect_ratio > 1.7  # Slides tend to be wider
                is_camera = not is_slides

            streams.append(
                StreamInfo(
                    stream_id=fmt.get("format_id", "unknown"),
                    url=fmt.get("url", ""),
                    resolution=resolution,
                    width=width,
                    height=height,
                    duration=info.get("duration", 0),
                    format=fmt.get("ext", "mp4"),
                    codec=fmt.get("vcodec"),
                    has_audio=fmt.get("acodec", "none") != "none",
                    is_camera=is_camera,
                    is_slides=is_slides,
                )
            )

        return streams

    def _create_download_retry(self, max_attempts: int) -> Any:
        """Create a retry decorator with configured attempts.

        Args:
            max_attempts: Maximum number of retry attempts.

        Returns:
            Configured retry decorator.
        """

        @retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=1, min=2, max=30),
            retry=retry_if_exception_type(DownloadError),
            reraise=True,
        )
        def download_with_retry(
            url: str, output_path: Path, format_selector: str | None = None
        ) -> Path:
            return self._download_single(url, output_path, format_selector)

        return download_with_retry

    # Format selectors for different stream types
    FORMAT_COMPOSED = "10/8/9/11/12/best[protocol=https]"  # PODCAST pre-composed
    FORMAT_CAMERA = "best[protocol=m3u8_native][acodec!=none]/best[protocol=m3u8][acodec!=none]"  # DV with audio
    # For slides: Select best video-only stream (OBJECT). These have no audio and are typically 1366x768
    # We look for streams without audio by checking if format note contains "video only"
    FORMAT_SLIDES = "best[height>=720][acodec=none]/bestvideo[height>=720]"
    FORMAT_DEFAULT = f"{FORMAT_COMPOSED}/{FORMAT_CAMERA}/best"  # Prefer composed, fallback to camera

    def _download_single(
        self, url: str, output_path: Path, format_selector: str | None = None, quiet: bool = False
    ) -> Path:
        """Download a single video.

        Args:
            url: Video URL.
            output_path: Where to save the video.
            format_selector: yt-dlp format selector string.
            quiet: If True, suppress yt-dlp progress output.

        Returns:
            Path to downloaded file.

        Raises:
            DownloadError: If download fails.
        """
        extra_args = [
            "-o",
            str(output_path),
        ]
        
        # Show progress only if not in quiet mode
        if not quiet:
            extra_args.append("--progress")
        else:
            extra_args.extend(["--no-progress", "--quiet"])

        if format_selector:
            extra_args.extend(["-f", format_selector])
        else:
            extra_args.extend(["-f", self.FORMAT_DEFAULT])

        if not quiet:
            print_info(f"Downloading to: {output_path.name}")

        result = self._run_yt_dlp(url, extra_args=extra_args, capture_output=quiet)

        if not output_path.exists():
            # yt-dlp may add extension
            possible_paths = list(output_path.parent.glob(f"{output_path.stem}.*"))
            if possible_paths:
                return possible_paths[0]
            raise DownloadError(f"Download completed but file not found: {output_path}")

        return output_path

    def download_all_streams(
        self, url: str, base_path: Path, dry_run: bool = False, quiet: bool = False
    ) -> dict[str, Path | None]:
        """Download all available streams (composed, camera, slides).

        Args:
            url: Panopto video URL.
            base_path: Base path for output files (without extension).
                       Will create: base_composed.mp4, base_camera.mp4, base_slides.mp4
            dry_run: If True, only simulate downloads.
            quiet: If True, suppress yt-dlp progress output.

        Returns:
            Dict mapping stream type to output path (None if failed/skipped).
        """
        results: dict[str, Path | None] = {
            "composed": None,
            "camera": None,
            "slides": None,
        }

        streams = [
            ("composed", self.FORMAT_COMPOSED, "Pre-composed (slides + camera)"),
            ("camera", self.FORMAT_CAMERA, "Camera/lecture video with audio"),
            ("slides", self.FORMAT_SLIDES, "Slides only (no audio)"),
        ]

        for stream_type, format_selector, description in streams:
            # base_path is already the full path without extension
            # Just append stream type to the name
            output_path = base_path.parent / f"{base_path.name}_{stream_type}.mp4"

            # Check if already exists
            if self.config.resume.check_existing and output_path.exists():
                size, _ = get_file_info(output_path)
                if size > 0:
                    if not quiet:
                        print_success(f"Already downloaded: {output_path.name} ({format_bytes(size)})")
                    results[stream_type] = output_path
                    continue

            if dry_run:
                print_info(f"[DRY RUN] Would download {stream_type}: {output_path.name}")
                continue

            if not quiet:
                console.print(f"\n[bold cyan]Downloading {stream_type}:[/bold cyan] {description}")
            else:
                console.print(f"  → Downloading {stream_type}: {output_path.name}")

            try:
                actual_path = self._download_single(url, output_path, format_selector, quiet=quiet)
                size, _ = get_file_info(actual_path)
                if not quiet:
                    print_success(f"Downloaded: {actual_path.name} ({format_bytes(size)})")
                else:
                    console.print(f"    ✓ {stream_type}: {format_bytes(size)}")
                results[stream_type] = actual_path
            except DownloadError as e:
                # Some streams may not be available (e.g., no PODCAST format)
                if not quiet:
                    print_warning(f"Could not download {stream_type}: {e}")
                results[stream_type] = None

        return results

    def _download_lecture_all_streams(
        self, lecture: LectureInfo, dry_run: bool = False
    ) -> DownloadResult:
        """Download all stream types for a single lecture.

        Args:
            lecture: Lecture information.
            dry_run: If True, only simulate the download.

        Returns:
            DownloadResult with combined file info.
        """
        start_time = time.time()
        
        # Generate base path
        filename = format_filename(
            template=self.config.naming.format,
            course=lecture.course,
            title=lecture.title,
            lecture_date=lecture.date,
            date_format=self.config.naming.date_format,
        )
        
        # Determine base path (with or without lecture folder)
        if self.config.naming.create_lecture_folders:
            from .utils import sanitize_filename
            folder_name = sanitize_filename(lecture.title)
            lecture_folder = self.download_path / folder_name
            ensure_directory(lecture_folder)
            # Remove .mp4 extension from filename to get base name
            # Don't use Path.stem as it treats dots in filenames (like 15.724) incorrectly
            base_name = filename.rsplit('.', 1)[0] if '.' in filename else filename
            base_path = lecture_folder / base_name
        else:
            base_name = filename.rsplit('.', 1)[0] if '.' in filename else filename
            base_path = self.download_path / base_name

        if dry_run:
            print_info(f"[DRY RUN] Would download all streams for: {lecture.title}")
            print_info(f"  Composed: {base_path}_composed.mp4")
            print_info(f"  Camera: {base_path}_camera.mp4")
            print_info(f"  Slides: {base_path}_slides.mp4")
            return DownloadResult(
                success=True,
                lecture=lecture,
                output_path=base_path.with_suffix(".mp4"),
                duration_seconds=0,
                was_skipped=False,
            )

        # Check if all streams already exist
        all_exist = True
        total_existing_size = 0
        for stream_type in ["composed", "camera", "slides"]:
            stream_path = base_path.parent / f"{base_path.name}_{stream_type}.mp4"
            if self.config.resume.check_existing and stream_path.exists():
                size, _ = get_file_info(stream_path)
                if size > 0:
                    total_existing_size += size
                else:
                    all_exist = False
                    break
            else:
                all_exist = False
                break
        
        if all_exist:
            # All streams already downloaded, skip
            return DownloadResult(
                success=True,
                lecture=lecture,
                output_path=base_path.with_suffix(".mp4"),
                file_size_bytes=total_existing_size,
                duration_seconds=time.time() - start_time,
                was_skipped=True,
            )

        # Download all streams (use quiet mode if parallel downloads are configured)
        use_quiet = self.config.download.parallel_workers > 1
        results = self.download_all_streams(lecture.url, base_path, dry_run=False, quiet=use_quiet)
        
        # Calculate total size and check if anything was actually downloaded
        total_size = 0
        any_downloaded = False
        for stream_type, path in results.items():
            if path:
                size, _ = get_file_info(path)
                total_size += size
                # Check if this stream was just downloaded (file modification time is recent)
                if path.exists() and (time.time() - path.stat().st_mtime) < 10:
                    any_downloaded = True

        elapsed = time.time() - start_time
        downloaded_count = sum(1 for p in results.values() if p is not None)
        
        if not use_quiet:
            console.print(f"\n[bold]Downloaded {downloaded_count}/3 streams for: {lecture.title}[/bold]")

        return DownloadResult(
            success=downloaded_count > 0,
            lecture=lecture,
            output_path=results.get("composed") or results.get("camera"),
            file_size_bytes=total_size,
            duration_seconds=elapsed,
            was_skipped=not any_downloaded,
        )

    def download_lecture(
        self,
        lecture: LectureInfo,
        dry_run: bool = False,
        output_path: Path | None = None,
    ) -> DownloadResult:
        """Download a single lecture.

        Args:
            lecture: Lecture information.
            dry_run: If True, only simulate the download.
            output_path: Optional explicit output path. If not provided,
                generates from lecture info and config naming template.

        Returns:
            DownloadResult with success status and file info.
        """
        # Check if we should download all streams
        if self.config.download.download_all_streams and not output_path:
            return self._download_lecture_all_streams(lecture, dry_run)
        
        start_time = time.time()

        # Use explicit output path or generate from template
        if output_path:
            # Ensure the path is absolute and has .mp4 extension
            if not output_path.is_absolute():
                output_path = self.download_path / output_path
            if not output_path.suffix:
                output_path = output_path.with_suffix(".mp4")
        else:
            # Generate output filename from template
            filename = format_filename(
                template=self.config.naming.format,
                course=lecture.course,
                title=lecture.title,
                lecture_date=lecture.date,
                date_format=self.config.naming.date_format,
            )
            
            # Create subfolder per lecture if configured
            if self.config.naming.create_lecture_folders:
                from .utils import sanitize_filename
                folder_name = sanitize_filename(lecture.title)
                lecture_folder = self.download_path / folder_name
                ensure_directory(lecture_folder)
                output_path = lecture_folder / filename
            else:
                output_path = self.download_path / filename

        # Check if already downloaded
        if self.config.resume.check_existing and output_path.exists():
            size, duration = get_file_info(output_path)
            if size > 0:
                print_success(
                    f"Already downloaded: {filename} ({format_bytes(size)})"
                )
                return DownloadResult(
                    success=True,
                    lecture=lecture,
                    output_path=output_path,
                    file_size_bytes=size,
                    duration_seconds=time.time() - start_time,
                    was_skipped=True,
                )

        if dry_run:
            print_info(f"[DRY RUN] Would download: {lecture.title}")
            print_info(f"  URL: {lecture.url}")
            print_info(f"  Output: {output_path}")
            return DownloadResult(
                success=True,
                lecture=lecture,
                output_path=output_path,
                duration_seconds=0,
            )

        # Download with retry
        max_attempts = (
            self.config.retry.max_attempts if self.config.retry.enabled else 1
        )

        try:
            download_with_retry = self._create_download_retry(max_attempts)
            actual_path = download_with_retry(lecture.url, output_path)

            size, _ = get_file_info(actual_path)
            elapsed = time.time() - start_time
            speed = format_speed(size, elapsed)

            print_success(
                f"Downloaded: {actual_path.name} "
                f"({format_bytes(size)} in {format_duration(elapsed)} @ {speed})"
            )

            return DownloadResult(
                success=True,
                lecture=lecture,
                output_path=actual_path,
                file_size_bytes=size,
                duration_seconds=elapsed,
            )

        except RetryError as e:
            error_msg = f"Download failed after {max_attempts} attempts: {e}"
            print_error(error_msg)
            return DownloadResult(
                success=False,
                lecture=lecture,
                error_message=error_msg,
                duration_seconds=time.time() - start_time,
            )

        except AuthenticationError as e:
            print_error(str(e))
            return DownloadResult(
                success=False,
                lecture=lecture,
                error_message=str(e),
                duration_seconds=time.time() - start_time,
            )

        except DownloadError as e:
            print_error(f"Download failed: {e}")
            return DownloadResult(
                success=False,
                lecture=lecture,
                error_message=str(e),
                duration_seconds=time.time() - start_time,
            )

    def download_all(
        self, dry_run: bool = False, parallel: bool | None = None
    ) -> list[DownloadResult]:
        """Download all lectures from config.

        Args:
            dry_run: If True, only simulate downloads.
            parallel: Override parallel setting. If None, uses config setting.

        Returns:
            List of download results.
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        if not self.config.lectures:
            print_warning("No lectures configured to download.")
            return []

        total = len(self.config.lectures)
        
        # Determine number of workers
        if parallel is None:
            # Use config setting
            workers = self.config.download.parallel_workers
        elif parallel:
            # Parallel mode requested - use config workers
            workers = self.config.download.parallel_workers
        else:
            # Sequential mode explicitly requested
            workers = 1

        # Cap workers to number of lectures
        workers = min(workers, total)

        print_info(f"Processing {total} lecture(s) with {workers} worker(s)...")
        console.print()

        start_time = time.time()
        results: list[DownloadResult] = []
        completed = 0

        if workers == 1 or dry_run:
            # Sequential download (simpler output for dry-run)
            for i, lecture in enumerate(self.config.lectures, 1):
                console.print(f"[bold cyan]({i}/{total})[/bold cyan] {lecture.course} - {lecture.title}")
                result = self.download_lecture(lecture, dry_run=dry_run)
                results.append(result)
                completed += 1
        else:
            # Parallel download
            future_to_lecture = {}

            with ThreadPoolExecutor(max_workers=workers) as executor:
                # Submit all downloads
                for lecture in self.config.lectures:
                    future = executor.submit(self.download_lecture, lecture, dry_run)
                    future_to_lecture[future] = lecture

                # Process completed downloads as they finish
                for future in as_completed(future_to_lecture):
                    lecture = future_to_lecture[future]
                    completed += 1
                    try:
                        result = future.result()
                        results.append(result)

                        # Show progress
                        status = "[green]✓[/green]" if result.success else "[red]✗[/red]"
                        console.print(
                            f"[bold cyan]({completed}/{total})[/bold cyan] "
                            f"{status} {lecture.course} - {lecture.title}"
                        )
                    except Exception as e:
                        # Handle unexpected errors
                        console.print(
                            f"[bold cyan]({completed}/{total})[/bold cyan] "
                            f"[red]✗[/red] {lecture.title}: {e}"
                        )
                        results.append(
                            DownloadResult(
                                success=False,
                                lecture=lecture,
                                error_message=str(e),
                                duration_seconds=0,
                            )
                        )

        # Print summary
        elapsed = time.time() - start_time
        successful = sum(1 for r in results if r.success)
        # A file is "skipped" if it already existed (file_path is set but no actual download happened)
        # We detect this by checking if was_skipped flag or duration is very short with file already existing
        skipped = sum(1 for r in results if r.success and r.was_skipped)
        downloaded = successful - skipped
        failed = total - successful
        # Only count size of actually downloaded files (not skipped)
        downloaded_size = sum(r.file_size_bytes for r in results if r.success and not r.was_skipped)
        total_size = sum(r.file_size_bytes for r in results if r.success)
        avg_speed = format_speed(downloaded_size, elapsed) if downloaded_size > 0 else "0.0 Mb/s"

        console.print()
        console.print("=" * 60)
        console.print("[bold]Download Summary[/bold]")
        console.print(f"  [green]Downloaded:[/green] {downloaded}")
        if skipped > 0:
            console.print(f"  [dim]Skipped (existing):[/dim] {skipped}")
        if failed > 0:
            console.print(f"  [red]Failed:[/red] {failed}")
            for r in results:
                if not r.success:
                    console.print(f"    - {r.lecture.title}: {r.error_message}")
        console.print(f"  [bold]Total:[/bold] {successful}/{total} successful")
        console.print(f"  Total size: {format_bytes(total_size)}")
        console.print(f"  Total time: {format_duration(elapsed)} @ {avg_speed}")
        console.print("=" * 60)

        return results

    def download_all_panopto_streams(
        self,
        url: str,
        base_path: Path,
        dry_run: bool = False,
        include_composed: bool = True,
    ) -> dict[str, Path | None]:
        """Download everything Panopto has for a session.

        Discovers all raw streams (every camera angle + slides) via the
        DeliveryInfo API, also downloads the composed/stitched view via
        yt-dlp, and fetches any available captions/transcripts.

        Auth priority: OAuth Bearer token (``self.auth``) → cookies file →
        browser cookies (yt-dlp falls back automatically).

        Args:
            url:              Panopto viewer URL.
            base_path:        Base path for output files (stem, no extension).
            dry_run:          Preview only — no files written.
            include_composed: Also download the composed/stitched view.

        Returns:
            Dict mapping asset name → Path (or None on failure).
        """
        from .panopto_api import PanoptoAPI, PanoptoAPIError, PanoptoRestAPI

        results: dict[str, Path | None] = {}

        try:
            video_id, server = PanoptoAPI.extract_video_id(url)
        except PanoptoAPIError as exc:
            raise DownloadError(f"Invalid Panopto URL: {exc}") from exc

        # ---- 1 & 2. All streams via DeliveryInfo (Bearer token, no browser) ---
        # One API call gets both the composed/podcast stream and all raw camera
        # / slides streams. The CDN URLs returned are pre-signed, so yt-dlp can
        # download them without any authentication headers at all.
        # DeliveryInfo requires browser session cookies (not Bearer token).
        # Priority: explicit cookies_file > exported file > browser extraction.
        # When OAuth is configured, browser extraction is skipped to avoid
        # Chrome dependency — use `auth export-cookies` instead.
        cookies_file = self.cookies_file or self._exported_cookies_path()

        api = PanoptoAPI(
            auth=self.auth,
            cookies_file=cookies_file,
            browser=self.config.browser.value,
        )

        console.print("[bold]Fetching stream info via Panopto API…[/bold]")
        try:
            delivery_info = api.get_delivery_info(video_id, server)
        except PanoptoAPIError as exc:
            err_msg = str(exc)
            if "export-cookies" in err_msg or "session cookie" in err_msg:
                console.print(
                    "\n[bold red]✗ No session cookies available for stream discovery.[/bold red]\n"
                    "  Panopto's stream info endpoint requires browser session cookies\n"
                    "  (OAuth tokens alone are not accepted by this endpoint).\n\n"
                    "  Fix — run this once, then downloads will work without Chrome:\n"
                    "    [bold cyan]panopto-downloader auth export-cookies[/bold cyan]\n"
                )
            else:
                console.print(f"[red]✗ Stream discovery failed: {exc}[/red]")
            # Return only the composed result (already downloaded or skipped above)
            return results

        delivery = (
            delivery_info.get("Delivery")
            or delivery_info.get("d", {}).get("Delivery")
            or {}
        )

        raw_streams_data = delivery.get("Streams", [])
        podcast_data = delivery.get("PodcastStreams", [])

        from .panopto_api import PanoptoStream
        raw_streams = [PanoptoStream(s) for s in raw_streams_data]
        podcast_streams = [PanoptoStream(s) for s in podcast_data]

        total_found = len(raw_streams) + len(podcast_streams)
        console.print(
            f"[green]Found {len(raw_streams)} camera/slide stream(s) + "
            f"{len(podcast_streams)} composed stream(s)[/green]\n"
        )

        # ---- 1. Composed / stitched view (from PodcastStreams) ----------
        if include_composed:
            composed_path = Path(str(base_path) + "_composed.mp4")
            part_path = self._part_path(composed_path)
            console.print("[bold cyan]── Composed view ──[/bold cyan]")

            if self._is_complete(composed_path):
                print_info(f"Already exists ({format_bytes(composed_path.stat().st_size)}), skipping")
                results["composed"] = composed_path
            elif dry_run:
                console.print(f"  [dim]Would download: {composed_path.name}[/dim]")
                results["composed"] = composed_path
            elif podcast_streams and podcast_streams[0].stream_url:
                cdn_url = podcast_streams[0].stream_url
                if part_path.exists():
                    console.print(
                        f"  [yellow]Resuming partial download "
                        f"({format_bytes(part_path.stat().st_size)} already downloaded)…[/yellow]"
                    )
                try:
                    cmd = self._yt_dlp_stream_cmd(composed_path, cdn_url)
                    proc = subprocess.run(cmd, capture_output=False, check=False)
                    if proc.returncode == 0 and self._is_complete(composed_path):
                        results["composed"] = composed_path
                        print_success(f"Composed: {format_bytes(composed_path.stat().st_size)}")
                    else:
                        results["composed"] = None
                        print_error("Composed download failed")
                except Exception as exc:
                    print_error(f"Composed download error: {exc}")
                    results["composed"] = None
            else:
                if cookies_file:
                    if part_path.exists():
                        console.print(
                            f"  [yellow]Resuming partial download "
                            f"({format_bytes(part_path.stat().st_size)} already downloaded)…[/yellow]"
                        )
                    try:
                        cmd = self._get_yt_dlp_cmd()
                        cmd.extend([
                            "--continue",
                            "--retries", "10",
                            "--fragment-retries", "10",
                            "--retry-sleep", "5",
                            "--socket-timeout", "60",
                            "-f", "hls-2160/hls-1080/hls-720/hls-480/best",
                            "-o", str(composed_path),
                            url,
                        ])
                        proc = subprocess.run(cmd, capture_output=False, check=False)
                        if proc.returncode == 0 and self._is_complete(composed_path):
                            results["composed"] = composed_path
                            print_success(f"Composed: {format_bytes(composed_path.stat().st_size)}")
                        else:
                            results["composed"] = None
                    except Exception as exc:
                        print_error(f"Composed download error: {exc}")
                        results["composed"] = None
                else:
                    console.print(
                        "[yellow]⚠  No composed stream URL and no session cookies.\n"
                        "  Run [bold cyan]panopto-downloader auth export-cookies[/bold cyan] "
                        "to fix this.[/yellow]"
                    )
                    results["composed"] = None

            console.print()

        # ---- 2. Raw streams (all cameras + slides) ----------------------
        if not raw_streams:
            console.print(
                "[dim]ℹ  Only a composed/single-stream recording — "
                "no separate camera or slides files available.[/dim]\n"
            )

        for i, stream in enumerate(raw_streams, 1):
            stream_name = stream.clean_name
            output_path = Path(str(base_path) + f"_{stream_name}.mp4")

            console.print(
                f"[bold cyan]── Stream {i}/{len(raw_streams)}: {stream.name}[/bold cyan]  "
                f"[dim]({stream.stream_type})[/dim]"
            )

            if dry_run:
                console.print(f"  [dim]Would download: {output_path.name}[/dim]")
                results[stream_name] = output_path
                console.print()
                continue

            if self._is_complete(output_path):
                print_info(f"Already exists ({format_bytes(output_path.stat().st_size)}), skipping")
                results[stream_name] = output_path
                console.print()
                continue

            if not stream.stream_url:
                print_warning("No stream URL available, skipping")
                results[stream_name] = None
                console.print()
                continue

            part_path = self._part_path(output_path)
            if part_path.exists():
                console.print(
                    f"  [yellow]Resuming partial download "
                    f"({format_bytes(part_path.stat().st_size)} already downloaded)…[/yellow]"
                )

            try:
                # CDN URLs from DeliveryInfo are pre-signed — no auth headers needed
                cmd = self._yt_dlp_stream_cmd(output_path, stream.stream_url)
                proc = subprocess.run(cmd, capture_output=False, check=False)
                if proc.returncode == 0 and self._is_complete(output_path):
                    results[stream_name] = output_path
                    print_success(f"Saved: {format_bytes(output_path.stat().st_size)}")
                else:
                    results[stream_name] = None
                    print_error(f"Failed (exit {proc.returncode})")
            except Exception as exc:
                print_error(f"Error: {exc}")
                results[stream_name] = None

            console.print()

        # ---- 3. Captions / transcripts ----------------------------------
        console.print("[bold cyan]── Captions / transcripts ──[/bold cyan]")
        captions_saved = 0
        if self.auth:
            try:
                rest = PanoptoRestAPI(self.auth)
                transcripts = rest.get_session_transcripts(video_id)
                for t in transcripts:
                    lang = (t.get("Language") or "unknown").replace(" ", "_")
                    ttype = (t.get("TranscriptType") or "srt").lower()
                    ext = "vtt" if "vtt" in ttype else "srt"
                    dest = Path(str(base_path) + f"_captions_{lang}.{ext}")
                    turl = t.get("TranscriptFileUrl") or t.get("Url") or ""
                    if not turl or dry_run:
                        console.print(f"  [dim]Caption ({lang}): {dest.name}[/dim]")
                        captions_saved += 1
                        continue
                    if rest.download_transcript(turl, dest):
                        results[f"captions_{lang}"] = dest
                        print_success(f"Captions ({lang}): {dest.name}")
                        captions_saved += 1
                    else:
                        print_warning(f"Caption download failed ({lang})")
            except Exception as exc:
                print_warning(f"Transcript fetch failed: {exc}")

        # yt-dlp also writes embedded subs automatically when write_subs=True
        if captions_saved == 0:
            console.print("  [dim]No separate caption files found (subtitles may be embedded).[/dim]")
        console.print()

        # ---- Summary ----------------------------------------------------
        ok = sum(1 for p in results.values() if p is not None)
        total = len(results)
        console.print(f"[bold]{'Dry run — ' if dry_run else ''}Downloaded {ok}/{total} assets[/bold]")
        for name, path in results.items():
            icon = "[green]✓[/green]" if path else "[red]✗[/red]"
            label = path.name if path else "failed"
            console.print(f"  {icon} {name}: {label}")

        return results