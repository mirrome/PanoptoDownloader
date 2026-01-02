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

    def __init__(self, config: AppConfig) -> None:
        """Initialize downloader.

        Args:
            config: Application configuration.
        """
        self.config = config
        self.download_path = ensure_directory(config.download_path)

    def _get_yt_dlp_cmd(self) -> list[str]:
        """Get base yt-dlp command with common options.

        Returns:
            List of command arguments.
        """
        cmd = [
            "yt-dlp",
            "--cookies-from-browser",
            self.config.browser.value,
            "--no-warnings",
        ]
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

