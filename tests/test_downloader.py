"""Tests for video downloading functionality."""

import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from panopto_downloader.downloader import (
    AuthenticationError,
    DownloadError,
    VideoDownloader,
)
from panopto_downloader.models import AppConfig, BrowserType, LectureInfo


class TestVideoDownloader:
    """Tests for VideoDownloader class."""

    @pytest.fixture
    def config(self, tmp_path: Path) -> AppConfig:
        """Create a test configuration."""
        return AppConfig(
            browser=BrowserType.CHROME,
            download_path=tmp_path / "downloads",
        )

    @pytest.fixture
    def downloader(self, config: AppConfig) -> VideoDownloader:
        """Create a VideoDownloader instance."""
        return VideoDownloader(config)

    @pytest.fixture
    def sample_lecture(self) -> LectureInfo:
        """Create a sample lecture."""
        return LectureInfo(
            url="https://test.panopto.com/Panopto/Pages/Viewer.aspx?id=test",
            title="Test Lecture",
            course="15.401",
            date=datetime.date(2025, 1, 15),
        )

    def test_init_creates_download_dir(self, config: AppConfig) -> None:
        """Test that downloader creates download directory."""
        downloader = VideoDownloader(config)
        assert config.download_path.exists()

    def test_get_yt_dlp_cmd(self, downloader: VideoDownloader) -> None:
        """Test yt-dlp command generation."""
        cmd = downloader._get_yt_dlp_cmd()
        assert "yt-dlp" in cmd
        assert "--cookies-from-browser" in cmd
        assert "chrome" in cmd

    @patch("panopto_downloader.downloader.subprocess.run")
    def test_get_video_info_success(
        self, mock_run: MagicMock, downloader: VideoDownloader
    ) -> None:
        """Test successful video info extraction."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"title": "Test Video", "duration": 3600}',
            stderr="",
        )

        info = downloader.get_video_info("https://panopto.com/video")
        assert info["title"] == "Test Video"
        assert info["duration"] == 3600

    @patch("panopto_downloader.downloader.subprocess.run")
    def test_get_video_info_auth_failure(
        self, mock_run: MagicMock, downloader: VideoDownloader
    ) -> None:
        """Test authentication failure during info extraction."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Please login to access this video",
        )

        with pytest.raises(AuthenticationError):
            downloader.get_video_info("https://panopto.com/video")

    @patch("panopto_downloader.downloader.subprocess.run")
    def test_get_video_info_general_failure(
        self, mock_run: MagicMock, downloader: VideoDownloader
    ) -> None:
        """Test general failure during info extraction."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Some other error",
        )

        with pytest.raises(DownloadError):
            downloader.get_video_info("https://panopto.com/video")

    @patch("panopto_downloader.downloader.subprocess.run")
    def test_detect_streams(
        self, mock_run: MagicMock, downloader: VideoDownloader
    ) -> None:
        """Test stream detection."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="""{
                "title": "Test",
                "duration": 3600,
                "formats": [
                    {"format_id": "1", "width": 1280, "height": 720, "vcodec": "h264", "acodec": "aac", "ext": "mp4"},
                    {"format_id": "2", "width": 1366, "height": 768, "vcodec": "h264", "acodec": "none", "ext": "mp4"}
                ]
            }""",
            stderr="",
        )

        streams = downloader.detect_streams("https://panopto.com/video")
        assert len(streams) == 2

        camera_stream = next((s for s in streams if s.is_camera), None)
        assert camera_stream is not None
        assert camera_stream.width == 1280
        assert camera_stream.has_audio is True

        slides_stream = next((s for s in streams if s.is_slides), None)
        assert slides_stream is not None
        assert slides_stream.width == 1366

    def test_download_lecture_dry_run(
        self,
        downloader: VideoDownloader,
        sample_lecture: LectureInfo,
    ) -> None:
        """Test dry run download."""
        result = downloader.download_lecture(sample_lecture, dry_run=True)
        assert result.success is True
        assert result.lecture == sample_lecture

    def test_download_lecture_already_exists(
        self,
        downloader: VideoDownloader,
        sample_lecture: LectureInfo,
        config: AppConfig,
    ) -> None:
        """Test skipping already downloaded file."""
        # Create the expected output file
        output_path = config.download_path / "15.401_Test_Lecture_2025-01-15.mp4"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake video content")

        result = downloader.download_lecture(sample_lecture)
        assert result.success is True
        # File should be detected as already downloaded
        assert result.file_size_bytes > 0


class TestDownloadError:
    """Tests for DownloadError exceptions."""

    def test_download_error_message(self) -> None:
        """Test DownloadError message."""
        error = DownloadError("Test error message")
        assert str(error) == "Test error message"

    def test_authentication_error_inherits(self) -> None:
        """Test AuthenticationError inherits from DownloadError."""
        error = AuthenticationError("Auth failed")
        assert isinstance(error, DownloadError)

