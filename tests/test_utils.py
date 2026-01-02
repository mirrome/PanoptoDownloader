"""Tests for utility functions."""

import datetime
from pathlib import Path

import pytest

from panopto_downloader.utils import (
    format_bytes,
    format_duration,
    format_filename,
    sanitize_filename,
)


class TestSanitizeFilename:
    """Tests for sanitize_filename function."""

    def test_basic_string(self) -> None:
        """Test sanitizing a basic string."""
        result = sanitize_filename("Hello World")
        assert result == "Hello_World"

    def test_special_characters(self) -> None:
        """Test removing special characters."""
        result = sanitize_filename('File<>:"/\\|?*Name')
        assert result == "File_Name"

    def test_unicode_characters(self) -> None:
        """Test handling unicode characters."""
        result = sanitize_filename("Café résumé")
        assert "Cafe" in result
        assert "resume" in result

    def test_multiple_spaces(self) -> None:
        """Test handling multiple spaces."""
        result = sanitize_filename("Hello   World")
        assert result == "Hello_World"

    def test_leading_trailing_chars(self) -> None:
        """Test stripping leading/trailing characters."""
        result = sanitize_filename("___Hello World___")
        assert result == "Hello_World"

    def test_max_length(self) -> None:
        """Test maximum length truncation."""
        long_name = "A" * 300
        result = sanitize_filename(long_name, max_length=50)
        assert len(result) == 50


class TestFormatFilename:
    """Tests for format_filename function."""

    def test_basic_format(self) -> None:
        """Test basic filename formatting."""
        result = format_filename(
            template="{course}_{title}_{date}",
            course="15.401",
            title="Capital Budgeting",
            lecture_date=datetime.date(2025, 1, 15),
        )
        assert result == "15.401_Capital_Budgeting_2025-01-15.mp4"

    def test_custom_date_format(self) -> None:
        """Test custom date format."""
        result = format_filename(
            template="{course}_{title}_{date}",
            course="15.401",
            title="Test",
            lecture_date=datetime.date(2025, 1, 15),
            date_format="%d-%m-%Y",
        )
        assert "15-01-2025" in result

    def test_custom_extension(self) -> None:
        """Test custom file extension."""
        result = format_filename(
            template="{course}_{title}",
            course="15.401",
            title="Test",
            lecture_date=datetime.date(2025, 1, 15),
            extension="mkv",
        )
        assert result.endswith(".mkv")

    def test_special_chars_in_course(self) -> None:
        """Test handling special characters in course name."""
        result = format_filename(
            template="{course}_{title}",
            course="15.401: Finance Theory",
            title="Test",
            lecture_date=datetime.date(2025, 1, 15),
        )
        assert ":" not in result


class TestFormatBytes:
    """Tests for format_bytes function."""

    def test_bytes(self) -> None:
        """Test formatting bytes."""
        assert format_bytes(500) == "500.0 B"

    def test_kilobytes(self) -> None:
        """Test formatting kilobytes."""
        assert format_bytes(1024) == "1.0 KB"

    def test_megabytes(self) -> None:
        """Test formatting megabytes."""
        assert format_bytes(1024 * 1024) == "1.0 MB"

    def test_gigabytes(self) -> None:
        """Test formatting gigabytes."""
        assert format_bytes(1024 * 1024 * 1024) == "1.0 GB"

    def test_large_size(self) -> None:
        """Test formatting large sizes."""
        result = format_bytes(1024 * 1024 * 1024 * 1024)
        assert "TB" in result


class TestFormatDuration:
    """Tests for format_duration function."""

    def test_seconds_only(self) -> None:
        """Test formatting seconds only."""
        assert format_duration(45) == "45s"

    def test_minutes_and_seconds(self) -> None:
        """Test formatting minutes and seconds."""
        assert format_duration(125) == "2m 5s"

    def test_hours_minutes_seconds(self) -> None:
        """Test formatting hours, minutes, and seconds."""
        result = format_duration(3725)
        assert "1h" in result
        assert "2m" in result
        assert "5s" in result

    def test_negative_duration(self) -> None:
        """Test handling negative duration."""
        assert format_duration(-10) == "0s"

    def test_zero_duration(self) -> None:
        """Test handling zero duration."""
        assert format_duration(0) == "0s"

