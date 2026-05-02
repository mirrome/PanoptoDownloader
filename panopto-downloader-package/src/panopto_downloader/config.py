"""Configuration management for Panopto Downloader.

Handles loading, parsing, and validating YAML configuration files.
"""

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError
from rich.console import Console

from .models import AppConfig, LectureInfo

console = Console()


class ConfigError(Exception):
    """Configuration-related errors."""

    pass


class ConfigLoader:
    """Loads and validates configuration from YAML files."""

    DEFAULT_CONFIG_PATHS = [
        Path("config.yaml"),
        Path("config.yml"),
        Path.home() / ".config" / "panopto-downloader" / "config.yaml",
    ]

    def __init__(self, config_path: Path | None = None) -> None:
        """Initialize config loader.

        Args:
            config_path: Optional path to config file. If None, searches default locations.
        """
        self.config_path = config_path
        self._config: AppConfig | None = None

    def find_config_file(self) -> Path | None:
        """Find the first existing config file from default paths.

        Returns:
            Path to config file or None if not found.
        """
        if self.config_path:
            if self.config_path.exists():
                return self.config_path
            return None

        for path in self.DEFAULT_CONFIG_PATHS:
            if path.exists():
                return path
        return None

    def load(self) -> AppConfig:
        """Load and validate configuration.

        Returns:
            Validated AppConfig object.

        Raises:
            ConfigError: If config file not found or invalid.
        """
        config_file = self.find_config_file()

        if config_file is None:
            if self.config_path:
                raise ConfigError(f"Config file not found: {self.config_path}")
            raise ConfigError(
                "No config file found. Create config.yaml or specify with --config. "
                f"Searched: {', '.join(str(p) for p in self.DEFAULT_CONFIG_PATHS)}"
            )

        try:
            raw_config = self._load_yaml(config_file)
        except yaml.YAMLError as e:
            raise ConfigError(f"Invalid YAML in {config_file}: {e}") from e

        # Apply environment variable overrides
        raw_config = self._apply_env_overrides(raw_config)

        try:
            self._config = AppConfig.model_validate(raw_config)
        except ValidationError as e:
            error_messages = self._format_validation_errors(e)
            raise ConfigError(
                f"Configuration validation failed:\n{error_messages}"
            ) from e

        # Validate lectures with warnings
        self._validate_lectures_metadata()

        return self._config

    def _load_yaml(self, path: Path) -> dict[str, Any]:
        """Load YAML file.

        Args:
            path: Path to YAML file.

        Returns:
            Parsed YAML as dictionary.
        """
        with open(path) as f:
            content = yaml.safe_load(f)
        return content if content else {}

    def _apply_env_overrides(self, config: dict[str, Any]) -> dict[str, Any]:
        """Apply environment variable overrides to config.

        Environment variables are prefixed with PANOPTO_.
        Examples:
            PANOPTO_BROWSER=safari
            PANOPTO_DOWNLOAD_PATH=/custom/path

        Args:
            config: Raw config dictionary.

        Returns:
            Config with env overrides applied.
        """
        env_mappings = {
            "PANOPTO_BROWSER": "browser",
            "PANOPTO_DOWNLOAD_PATH": "download_path",
            "PANOPTO_QUALITY": "quality",
        }

        for env_var, config_key in env_mappings.items():
            value = os.environ.get(env_var)
            if value:
                config[config_key] = value

        # Nested env vars
        parallel_workers = os.environ.get("PANOPTO_PARALLEL_WORKERS")
        if parallel_workers:
            if "download" not in config:
                config["download"] = {}
            config["download"]["parallel_workers"] = int(parallel_workers)

        max_retries = os.environ.get("PANOPTO_MAX_RETRIES")
        if max_retries:
            if "retry" not in config:
                config["retry"] = {}
            config["retry"]["max_attempts"] = int(max_retries)

        return config

    def _format_validation_errors(self, error: ValidationError) -> str:
        """Format Pydantic validation errors for display.

        Args:
            error: Pydantic ValidationError.

        Returns:
            Formatted error string.
        """
        messages = []
        for err in error.errors():
            location = " -> ".join(str(loc) for loc in err["loc"])
            messages.append(f"  - {location}: {err['msg']}")
        return "\n".join(messages)

    def _validate_lectures_metadata(self) -> None:
        """Validate lecture metadata and emit warnings for issues."""
        if not self._config or not self._config.lectures:
            console.print(
                "[yellow]Warning:[/yellow] No lectures configured. "
                "Add lectures to your config.yaml file."
            )
            return

        for i, lecture in enumerate(self._config.lectures, 1):
            # Check for missing optional fields
            if not lecture.instructor:
                console.print(
                    f"[yellow]Warning:[/yellow] Lecture {i} ({lecture.title}) "
                    "has no instructor specified."
                )

            # Validate URL format more strictly
            if "Viewer.aspx" not in lecture.url and "viewer" not in lecture.url.lower():
                console.print(
                    f"[yellow]Warning:[/yellow] Lecture {i} URL may not be a "
                    f"valid Panopto viewer URL: {lecture.url}"
                )

    @property
    def config(self) -> AppConfig:
        """Get loaded config.

        Returns:
            AppConfig object.

        Raises:
            ConfigError: If config not yet loaded.
        """
        if self._config is None:
            raise ConfigError("Config not loaded. Call load() first.")
        return self._config


def load_config(config_path: Path | None = None) -> AppConfig:
    """Convenience function to load configuration.

    Args:
        config_path: Optional path to config file.

    Returns:
        Validated AppConfig object.

    Raises:
        ConfigError: If config file not found or invalid.
    """
    loader = ConfigLoader(config_path)
    return loader.load()


def create_default_config(output_path: Path) -> None:
    """Create a default configuration file.

    Args:
        output_path: Where to write the config file.

    Raises:
        ConfigError: If file already exists or cannot be written.
    """
    if output_path.exists():
        raise ConfigError(f"Config file already exists: {output_path}")

    # Read the example config
    example_path = Path(__file__).parent.parent.parent / "config.example.yaml"
    if not example_path.exists():
        # Fallback: create minimal config
        default_config = {
            "browser": "chrome",
            "download_path": "~/Videos/MIT_Lectures",
            "quality": "highest",
            "lectures": [],
        }
        content = yaml.dump(default_config, default_flow_style=False)
    else:
        content = example_path.read_text()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content)
    console.print(f"[green]Created config file:[/green] {output_path}")


def validate_lecture_entry(lecture_data: dict[str, Any]) -> tuple[bool, str | None]:
    """Validate a single lecture entry.

    Args:
        lecture_data: Dictionary with lecture data.

    Returns:
        Tuple of (is_valid, error_message).
    """
    try:
        LectureInfo.model_validate(lecture_data)
        return True, None
    except ValidationError as e:
        errors = "; ".join(
            f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}"
            for err in e.errors()
        )
        return False, errors

