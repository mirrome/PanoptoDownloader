"""Tests for configuration management."""

import datetime
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from panopto_downloader.config import (
    ConfigError,
    ConfigLoader,
    load_config,
    validate_lecture_entry,
)
from panopto_downloader.models import (
    AppConfig,
    BrowserType,
    LectureInfo,
    QualitySetting,
)


class TestLectureInfo:
    """Tests for LectureInfo model validation."""

    def test_valid_lecture(self) -> None:
        """Test valid lecture info creation."""
        lecture = LectureInfo(
            url="https://mitsloan.hosted.panopto.com/Panopto/Pages/Viewer.aspx?id=test",
            title="Test Lecture",
            course="15.401",
            date=datetime.date(2025, 1, 15),
            instructor="Prof. Smith",
        )
        assert lecture.title == "Test Lecture"
        assert lecture.course == "15.401"

    def test_empty_url_raises_error(self) -> None:
        """Test that empty URL raises validation error."""
        with pytest.raises(ValueError, match="URL cannot be empty"):
            LectureInfo(
                url="",
                title="Test",
                course="15.401",
                date=datetime.date(2025, 1, 15),
            )

    def test_non_panopto_url_raises_error(self) -> None:
        """Test that non-Panopto URL raises validation error."""
        with pytest.raises(ValueError, match="does not appear to be a Panopto URL"):
            LectureInfo(
                url="https://youtube.com/watch?v=123",
                title="Test",
                course="15.401",
                date=datetime.date(2025, 1, 15),
            )

    def test_empty_title_raises_error(self) -> None:
        """Test that empty title raises validation error."""
        with pytest.raises(ValueError, match="Title cannot be empty"):
            LectureInfo(
                url="https://panopto.com/video",
                title="   ",
                course="15.401",
                date=datetime.date(2025, 1, 15),
            )

    def test_empty_course_raises_error(self) -> None:
        """Test that empty course raises validation error."""
        with pytest.raises(ValueError, match="Course cannot be empty"):
            LectureInfo(
                url="https://panopto.com/video",
                title="Test",
                course="",
                date=datetime.date(2025, 1, 15),
            )

    def test_title_whitespace_trimmed(self) -> None:
        """Test that title whitespace is trimmed."""
        lecture = LectureInfo(
            url="https://panopto.com/video",
            title="  Test Lecture  ",
            course="15.401",
            date=datetime.date(2025, 1, 15),
        )
        assert lecture.title == "Test Lecture"


class TestAppConfig:
    """Tests for AppConfig model validation."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = AppConfig()
        assert config.browser == BrowserType.CHROME
        assert config.quality == QualitySetting.HIGHEST
        assert config.retry.max_attempts == 3
        assert config.download.parallel_workers == 2
        assert config.composition.camera_position.value == "left"
        assert config.composition.slides_position.value == "right"

    def test_path_expansion(self) -> None:
        """Test that home directory is expanded in paths."""
        config = AppConfig(download_path="~/Videos")
        assert "~" not in str(config.download_path)
        assert config.download_path.is_absolute()

    def test_same_position_raises_error(self) -> None:
        """Test that camera and slides in same position raises error."""
        with pytest.raises(ValueError, match="cannot be in the same position"):
            AppConfig(
                composition={
                    "camera_position": "left",
                    "slides_position": "left",
                }
            )

    def test_valid_config_with_lectures(self) -> None:
        """Test valid config with lectures."""
        config = AppConfig(
            browser=BrowserType.SAFARI,
            lectures=[
                {
                    "url": "https://panopto.com/video1",
                    "title": "Lecture 1",
                    "course": "15.401",
                    "date": datetime.date(2025, 1, 15),
                },
                {
                    "url": "https://panopto.com/video2",
                    "title": "Lecture 2",
                    "course": "15.401",
                    "date": datetime.date(2025, 1, 22),
                },
            ],
        )
        assert len(config.lectures) == 2
        assert config.browser == BrowserType.SAFARI


class TestConfigLoader:
    """Tests for ConfigLoader functionality."""

    def test_find_config_explicit_path(self, tmp_path: Path) -> None:
        """Test finding config with explicit path."""
        config_file = tmp_path / "my_config.yaml"
        config_file.write_text("browser: chrome\n")

        loader = ConfigLoader(config_file)
        found = loader.find_config_file()
        assert found == config_file

    def test_find_config_missing_explicit_path(self, tmp_path: Path) -> None:
        """Test finding missing explicit config file."""
        config_file = tmp_path / "missing.yaml"
        loader = ConfigLoader(config_file)
        found = loader.find_config_file()
        assert found is None

    def test_load_valid_config(self, tmp_path: Path) -> None:
        """Test loading a valid config file."""
        config_file = tmp_path / "config.yaml"
        config_data = {
            "browser": "safari",
            "download_path": str(tmp_path / "downloads"),
            "lectures": [
                {
                    "url": "https://panopto.com/video",
                    "title": "Test Lecture",
                    "course": "15.401",
                    "date": "2025-01-15",
                }
            ],
        }
        config_file.write_text(yaml.dump(config_data))

        loader = ConfigLoader(config_file)
        config = loader.load()

        assert config.browser == BrowserType.SAFARI
        assert len(config.lectures) == 1
        assert config.lectures[0].title == "Test Lecture"

    def test_load_invalid_yaml(self, tmp_path: Path) -> None:
        """Test loading invalid YAML raises error."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("invalid: yaml: content:")

        loader = ConfigLoader(config_file)
        with pytest.raises(ConfigError, match="Invalid YAML"):
            loader.load()

    def test_load_invalid_config_values(self, tmp_path: Path) -> None:
        """Test loading config with invalid values raises error."""
        config_file = tmp_path / "config.yaml"
        config_data = {
            "browser": "invalid_browser",
        }
        config_file.write_text(yaml.dump(config_data))

        loader = ConfigLoader(config_file)
        with pytest.raises(ConfigError, match="Configuration validation failed"):
            loader.load()

    def test_env_var_override(self, tmp_path: Path) -> None:
        """Test environment variable overrides."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("browser: chrome\n")

        with patch.dict("os.environ", {"PANOPTO_BROWSER": "safari"}):
            loader = ConfigLoader(config_file)
            config = loader.load()
            assert config.browser == BrowserType.SAFARI

    def test_config_not_loaded_error(self) -> None:
        """Test accessing config before load raises error."""
        loader = ConfigLoader()
        with pytest.raises(ConfigError, match="Config not loaded"):
            _ = loader.config


class TestValidateLectureEntry:
    """Tests for validate_lecture_entry function."""

    def test_valid_entry(self) -> None:
        """Test validating a valid lecture entry."""
        entry = {
            "url": "https://panopto.com/video",
            "title": "Test",
            "course": "15.401",
            "date": "2025-01-15",
        }
        is_valid, error = validate_lecture_entry(entry)
        assert is_valid is True
        assert error is None

    def test_invalid_entry(self) -> None:
        """Test validating an invalid lecture entry."""
        entry = {
            "url": "",
            "title": "Test",
            "course": "15.401",
            "date": "2025-01-15",
        }
        is_valid, error = validate_lecture_entry(entry)
        assert is_valid is False
        assert error is not None


class TestLoadConfigFunction:
    """Tests for load_config convenience function."""

    def test_load_config_success(self, tmp_path: Path) -> None:
        """Test load_config function with valid config."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("browser: chrome\n")

        config = load_config(config_file)
        assert config.browser == BrowserType.CHROME

    def test_load_config_not_found(self, tmp_path: Path) -> None:
        """Test load_config function with missing config."""
        config_file = tmp_path / "missing.yaml"

        with pytest.raises(ConfigError, match="Config file not found"):
            load_config(config_file)

