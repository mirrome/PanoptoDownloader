"""Data models for Panopto Downloader configuration and entities.

Uses Pydantic for validation and type safety.
"""

import datetime
from enum import Enum
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, Field, field_validator, model_validator


class BrowserType(str, Enum):
    """Supported browsers for cookie extraction."""

    CHROME = "chrome"
    SAFARI = "safari"


class QualitySetting(str, Enum):
    """Video quality selection options."""

    HIGHEST = "highest"
    # Future: could add specific resolutions like 1080p, 720p, etc.


class CameraPosition(str, Enum):
    """Position of camera stream in composition."""

    LEFT = "left"
    RIGHT = "right"


class SlidesPosition(str, Enum):
    """Position of slides stream in composition."""

    LEFT = "left"
    RIGHT = "right"


class AudioSource(str, Enum):
    """Audio source for composed video."""

    CAMERA = "camera"
    SLIDES = "slides"
    BOTH = "both"


class AspectRatioHandling(str, Enum):
    """How to handle different aspect ratios."""

    BLACK_BARS = "black_bars"
    STRETCH = "stretch"
    CROP = "crop"


class TextPosition(str, Enum):
    """Position for text overlay."""

    TOP_LEFT = "top-left"
    TOP_RIGHT = "top-right"
    BOTTOM_LEFT = "bottom-left"
    BOTTOM_RIGHT = "bottom-right"
    TOP_CENTER = "top-center"
    BOTTOM_CENTER = "bottom-center"


class EncodingPreset(str, Enum):
    """FFmpeg encoding presets for x265."""

    ULTRAFAST = "ultrafast"
    SUPERFAST = "superfast"
    VERYFAST = "veryfast"
    FASTER = "faster"
    FAST = "fast"
    MEDIUM = "medium"
    SLOW = "slow"
    SLOWER = "slower"
    VERYSLOW = "veryslow"


class EncodingSettings(BaseModel):
    """Video encoding configuration."""

    codec: str = Field(default="x265", description="Video codec (x265 recommended)")
    crf: Annotated[int, Field(ge=0, le=51)] = Field(
        default=23, description="Constant Rate Factor (0-51, lower = higher quality)"
    )
    preset: EncodingPreset = Field(
        default=EncodingPreset.MEDIUM, description="Encoding speed preset"
    )
    max_bitrate: str = Field(default="10M", description="Maximum bitrate")
    buffer_size: str = Field(default="20M", description="Buffer size for rate control")


class TextOverlaySettings(BaseModel):
    """Text overlay configuration."""

    enabled: bool = Field(default=True, description="Enable text overlay")
    font: str = Field(default="Helvetica", description="Font family")
    size: Annotated[int, Field(ge=8, le=72)] = Field(
        default=24, description="Font size in points"
    )
    color: str = Field(default="white", description="Text color")
    position: TextPosition = Field(
        default=TextPosition.TOP_RIGHT, description="Text position on video"
    )


class CompositionSettings(BaseModel):
    """Video composition configuration."""

    layout: str = Field(default="side-by-side", description="Composition layout")
    camera_position: CameraPosition = Field(
        default=CameraPosition.LEFT, description="Camera stream position"
    )
    slides_position: SlidesPosition = Field(
        default=SlidesPosition.RIGHT, description="Slides stream position"
    )
    audio_source: AudioSource = Field(
        default=AudioSource.CAMERA, description="Audio source for output"
    )
    aspect_ratio_handling: AspectRatioHandling = Field(
        default=AspectRatioHandling.BLACK_BARS,
        description="How to handle different aspect ratios",
    )
    encoding: EncodingSettings = Field(
        default_factory=EncodingSettings, description="Encoding settings"
    )
    text_overlay: TextOverlaySettings = Field(
        default_factory=TextOverlaySettings, description="Text overlay settings"
    )


class NamingSettings(BaseModel):
    """File naming configuration."""

    format: str = Field(
        default="{course}_{title}_{date}",
        description="Naming format with placeholders",
    )
    date_format: str = Field(default="%Y-%m-%d", description="Date format string")
    create_lecture_folders: bool = Field(
        default=False, 
        description="Create a subfolder for each lecture named after the title"
    )


class RetrySettings(BaseModel):
    """Retry configuration for failed downloads."""

    enabled: bool = Field(default=True, description="Enable retry on failure")
    max_attempts: Annotated[int, Field(ge=1, le=10)] = Field(
        default=3, description="Maximum retry attempts"
    )


class DownloadSettings(BaseModel):
    """Download configuration."""

    parallel_workers: Annotated[int, Field(ge=1, le=10)] = Field(
        default=2, description="Number of parallel download workers"
    )
    download_all_streams: bool = Field(
        default=False,
        description="Download all stream types (composed, camera, slides) for each lecture"
    )


class ResumeSettings(BaseModel):
    """Resume configuration for interrupted downloads."""

    enabled: bool = Field(default=True, description="Enable resume capability")
    check_existing: bool = Field(
        default=True, description="Check and skip existing files"
    )


class LectureInfo(BaseModel):
    """Information about a single lecture to download."""

    url: str = Field(..., description="Panopto video URL")
    title: str = Field(..., description="Lecture title")
    course: str = Field(..., description="Course name/code")
    date: datetime.date = Field(..., description="Lecture date")
    instructor: str | None = Field(default=None, description="Instructor name")

    @field_validator("url")
    @classmethod
    def validate_panopto_url(cls, v: str) -> str:
        """Validate that URL is a Panopto URL."""
        if not v:
            raise ValueError("URL cannot be empty")
        if "panopto" not in v.lower():
            raise ValueError(
                f"URL does not appear to be a Panopto URL: {v}. "
                "Expected URL containing 'panopto'."
            )
        return v

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        """Validate title is not empty."""
        if not v or not v.strip():
            raise ValueError("Title cannot be empty")
        return v.strip()

    @field_validator("course")
    @classmethod
    def validate_course(cls, v: str) -> str:
        """Validate course is not empty."""
        if not v or not v.strip():
            raise ValueError("Course cannot be empty")
        return v.strip()


class AppConfig(BaseModel):
    """Main application configuration."""

    browser: BrowserType = Field(
        default=BrowserType.CHROME, description="Browser for cookie extraction"
    )
    download_path: Path = Field(
        default=Path("~/Videos/MIT_Lectures").expanduser(),
        description="Download directory",
    )
    quality: QualitySetting = Field(
        default=QualitySetting.HIGHEST, description="Quality setting"
    )
    composition: CompositionSettings = Field(
        default_factory=CompositionSettings, description="Composition settings"
    )
    naming: NamingSettings = Field(
        default_factory=NamingSettings, description="File naming settings"
    )
    retry: RetrySettings = Field(
        default_factory=RetrySettings, description="Retry settings"
    )
    download: DownloadSettings = Field(
        default_factory=DownloadSettings, description="Download settings"
    )
    resume: ResumeSettings = Field(
        default_factory=ResumeSettings, description="Resume settings"
    )
    lectures: list[LectureInfo] = Field(
        default_factory=list, description="List of lectures to download"
    )

    @field_validator("download_path", mode="before")
    @classmethod
    def expand_path(cls, v: str | Path) -> Path:
        """Expand user home directory in path."""
        if isinstance(v, str):
            v = Path(v)
        return v.expanduser()

    @model_validator(mode="after")
    def validate_positions(self) -> "AppConfig":
        """Validate camera and slides positions are different."""
        if (
            self.composition.camera_position.value
            == self.composition.slides_position.value
        ):
            raise ValueError(
                "Camera and slides cannot be in the same position. "
                f"Both are set to '{self.composition.camera_position.value}'."
            )
        return self


class StreamInfo(BaseModel):
    """Information about a video stream."""

    stream_id: str = Field(..., description="Stream identifier")
    url: str = Field(..., description="Stream URL")
    resolution: str = Field(..., description="Resolution (e.g., 1280x720)")
    width: int = Field(..., description="Video width in pixels")
    height: int = Field(..., description="Video height in pixels")
    duration: float = Field(..., description="Duration in seconds")
    format: str = Field(..., description="Video format (e.g., mp4)")
    codec: str | None = Field(default=None, description="Video codec")
    has_audio: bool = Field(default=False, description="Whether stream has audio")
    is_camera: bool = Field(default=False, description="Whether this is camera stream")
    is_slides: bool = Field(default=False, description="Whether this is slides stream")


class DownloadResult(BaseModel):
    """Result of a download operation."""

    success: bool = Field(..., description="Whether download succeeded")
    lecture: LectureInfo = Field(..., description="Lecture info")
    output_path: Path | None = Field(default=None, description="Output file path")
    error_message: str | None = Field(default=None, description="Error message if failed")
    duration_seconds: float = Field(default=0, description="Download duration")
    file_size_bytes: int = Field(default=0, description="Output file size")
    was_skipped: bool = Field(default=False, description="Whether file was skipped (already existed)")

