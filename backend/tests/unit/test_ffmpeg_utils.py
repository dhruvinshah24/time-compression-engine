import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.utils.ffmpeg import (
    FFmpegError,
    FFmpegNotFoundError,
    FrameExtractionConfig,
    VideoCorruptedError,
    VideoMetadata,
    _parse_fraction,
    _parse_probe_data,
    validate_video_file,
)


# ---------------------------------------------------------------------------
# Markers
# ---------------------------------------------------------------------------

requires_ffmpeg = pytest.mark.skipif(
    shutil.which("ffprobe") is None,
    reason="FFmpeg not available on PATH",
)



# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_probe_data(
    duration: float = 60.0,
    width: int = 1920,
    height: int = 1080,
    fps: str = "25/1",
    codec: str = "h264",
    nb_frames: str = "1500",
    has_audio: bool = True,
) -> dict:
    """Build a minimal ffprobe JSON response for testing."""
    streams = [
        {
            "codec_type": "video",
            "codec_name": codec,
            "codec_long_name": f"{codec} long name",
            "width": width,
            "height": height,
            "avg_frame_rate": fps,
            "nb_frames": nb_frames,
            "duration": str(duration),
        }
    ]
    if has_audio:
        streams.append({"codec_type": "audio", "codec_name": "aac"})

    return {
        "format": {
            "duration": str(duration),
            "bit_rate": "5000000",
            "format_name": "mp4",
            "format_long_name": "QuickTime / MOV",
        },
        "streams": streams,
    }


# ---------------------------------------------------------------------------
# _parse_fraction
# ---------------------------------------------------------------------------

class TestParseFraction:
    def test_standard_fraction(self):
        assert _parse_fraction("30/1") == pytest.approx(30.0)

    def test_ntsc_fraction(self):
        assert _parse_fraction("30000/1001") == pytest.approx(29.97, rel=1e-3)

    def test_plain_float(self):
        assert _parse_fraction("25.0") == pytest.approx(25.0)

    def test_zero_denominator(self):
        assert _parse_fraction("30/0") == 0.0

    def test_invalid_string(self):
        assert _parse_fraction("not_a_number") == 0.0

    def test_empty_string(self):
        assert _parse_fraction("") == 0.0


# ---------------------------------------------------------------------------
# _parse_probe_data
# ---------------------------------------------------------------------------

class TestParseProbeData:
    def test_basic_metadata_extracted(self, tmp_path):
        fake_path = tmp_path / "test.mp4"
        fake_path.write_bytes(b"fake")
        data = _make_probe_data(duration=120.0, width=1920, height=1080, fps="25/1")
        meta = _parse_probe_data(fake_path, data)

        assert meta.duration_seconds == pytest.approx(120.0)
        assert meta.duration_ms == 120_000
        assert meta.width == 1920
        assert meta.height == 1080
        assert meta.fps == pytest.approx(25.0)
        assert meta.codec == "h264"
        assert meta.has_audio is True

    def test_no_audio_stream(self, tmp_path):
        fake_path = tmp_path / "test.mp4"
        fake_path.write_bytes(b"fake")
        data = _make_probe_data(has_audio=False)
        meta = _parse_probe_data(fake_path, data)
        assert meta.has_audio is False
        assert meta.audio_codec is None

    def test_frame_count_from_nb_frames(self, tmp_path):
        fake_path = tmp_path / "test.mp4"
        fake_path.write_bytes(b"fake")
        data = _make_probe_data(duration=60.0, fps="25/1", nb_frames="1500")
        meta = _parse_probe_data(fake_path, data)
        assert meta.frame_count == 1500

    def test_frame_count_estimated_when_missing(self, tmp_path):
        fake_path = tmp_path / "test.mp4"
        fake_path.write_bytes(b"fake")
        data = _make_probe_data(duration=60.0, fps="25/1", nb_frames="N/A")
        meta = _parse_probe_data(fake_path, data)
        # Estimated: 60s * 25fps = 1500
        assert meta.frame_count == 1500

    def test_no_video_stream_raises(self, tmp_path):
        fake_path = tmp_path / "test.mp4"
        fake_path.write_bytes(b"fake")
        data = {"format": {}, "streams": [{"codec_type": "audio", "codec_name": "aac"}]}
        with pytest.raises(VideoCorruptedError):
            _parse_probe_data(fake_path, data)

    def test_resolution_property(self, tmp_path):
        fake_path = tmp_path / "test.mp4"
        fake_path.write_bytes(b"fake")
        data = _make_probe_data(width=1280, height=720)
        meta = _parse_probe_data(fake_path, data)
        assert meta.resolution == "1280x720"

    def test_is_long_video_true_for_over_1hour(self, tmp_path):
        fake_path = tmp_path / "test.mp4"
        fake_path.write_bytes(b"fake")
        data = _make_probe_data(duration=3601.0)
        meta = _parse_probe_data(fake_path, data)
        assert meta.is_long_video is True

    def test_is_long_video_false_for_under_1hour(self, tmp_path):
        fake_path = tmp_path / "test.mp4"
        fake_path.write_bytes(b"fake")
        data = _make_probe_data(duration=3599.0)
        meta = _parse_probe_data(fake_path, data)
        assert meta.is_long_video is False


# ---------------------------------------------------------------------------
# FrameExtractionConfig
# ---------------------------------------------------------------------------

class TestFrameExtractionConfig:
    def test_defaults(self):
        config = FrameExtractionConfig()
        assert config.frame_skip_rate == 5
        assert config.output_format == "jpg"
        assert config.quality == 2

    def test_invalid_skip_rate_raises(self):
        with pytest.raises(ValueError, match="frame_skip_rate"):
            FrameExtractionConfig(frame_skip_rate=0)

    def test_invalid_quality_raises(self):
        with pytest.raises(ValueError, match="quality"):
            FrameExtractionConfig(quality=0)

    def test_invalid_quality_too_high_raises(self):
        with pytest.raises(ValueError, match="quality"):
            FrameExtractionConfig(quality=32)

    def test_custom_values(self):
        config = FrameExtractionConfig(frame_skip_rate=10, quality=5, resize=(640, 360))
        assert config.frame_skip_rate == 10
        assert config.quality == 5
        assert config.resize == (640, 360)


# ---------------------------------------------------------------------------
# validate_video_file — mocked ffprobe
# ---------------------------------------------------------------------------

class TestValidateVideoFile:
    def test_missing_file_returns_invalid(self, tmp_path):
        result = validate_video_file(tmp_path / "nonexistent.mp4")
        assert result.valid is False
        assert any("not found" in e.lower() for e in result.errors)

    def test_empty_file_returns_invalid(self, tmp_path):
        empty = tmp_path / "empty.mp4"
        empty.write_bytes(b"")
        result = validate_video_file(empty)
        assert result.valid is False
        assert any("empty" in e.lower() for e in result.errors)

    def test_unsupported_extension_returns_invalid(self, tmp_path):
        bad_ext = tmp_path / "video.xyz"
        bad_ext.write_bytes(b"fake content here")
        result = validate_video_file(bad_ext)
        assert result.valid is False
        assert any("extension" in e.lower() for e in result.errors)

    def test_supported_extensions_accepted(self, tmp_path):
        """All supported extensions should pass the extension check."""
        for ext in [".mp4", ".avi", ".mov", ".mkv", ".webm"]:
            f = tmp_path / f"video{ext}"
            f.write_bytes(b"fake content here")
            # Will fail at ffprobe stage, but NOT at extension stage
            result = validate_video_file(f)
            ext_errors = [e for e in result.errors if "extension" in e.lower()]
            assert len(ext_errors) == 0, f"Extension {ext} incorrectly rejected"

    @patch("app.utils.ffmpeg.probe_video")
    def test_valid_file_passes(self, mock_probe, tmp_path):
        """A valid file with good metadata should pass all checks."""
        video = tmp_path / "valid.mp4"
        video.write_bytes(b"fake but non-empty")

        mock_meta = MagicMock()
        mock_meta.codec = "h264"
        mock_meta.duration_seconds = 3600.0
        mock_meta.width = 1920
        mock_meta.height = 1080
        mock_meta.fps = 25.0
        mock_probe.return_value = mock_meta

        result = validate_video_file(video)
        assert result.valid is True
        assert result.errors == []

    @patch("app.utils.ffmpeg.probe_video")
    def test_corrupted_file_returns_invalid(self, mock_probe, tmp_path):
        video = tmp_path / "corrupted.mp4"
        video.write_bytes(b"not a real video file content")
        mock_probe.side_effect = VideoCorruptedError("moov atom not found")

        result = validate_video_file(video)
        assert result.valid is False
        assert any("corrupt" in e.lower() for e in result.errors)

    @patch("app.utils.ffmpeg.probe_video")
    def test_zero_duration_returns_invalid(self, mock_probe, tmp_path):
        video = tmp_path / "zero_duration.mp4"
        video.write_bytes(b"fake content here for testing")

        mock_meta = MagicMock()
        mock_meta.codec = "h264"
        mock_meta.duration_seconds = 0.0
        mock_meta.width = 1920
        mock_meta.height = 1080
        mock_meta.fps = 25.0
        mock_probe.return_value = mock_meta

        result = validate_video_file(video)
        assert result.valid is False
        assert any("duration" in e.lower() for e in result.errors)

    @patch("app.utils.ffmpeg.probe_video")
    def test_unknown_codec_produces_warning_not_error(self, mock_probe, tmp_path):
        video = tmp_path / "unknown_codec.mp4"
        video.write_bytes(b"fake content here for testing")

        mock_meta = MagicMock()
        mock_meta.codec = "some_unknown_codec_xyz"
        mock_meta.duration_seconds = 60.0
        mock_meta.width = 1280
        mock_meta.height = 720
        mock_meta.fps = 30.0
        mock_probe.return_value = mock_meta

        result = validate_video_file(video)
        # Unknown codec = warning, not error
        assert result.errors == []
        assert any("codec" in w.lower() for w in result.warnings)


# ---------------------------------------------------------------------------
# VideoMetadata
# ---------------------------------------------------------------------------

class TestVideoMetadata:
    def _make_meta(self, **kwargs) -> VideoMetadata:
        defaults = dict(
            file_path="/tmp/test.mp4",
            filename="test.mp4",
            file_size_bytes=1024 * 1024,
            duration_ms=60_000,
            duration_seconds=60.0,
            width=1920,
            height=1080,
            fps=25.0,
            frame_count=1500,
            codec="h264",
            codec_long="H.264",
            bit_rate_kbps=5000,
            has_audio=True,
        )
        defaults.update(kwargs)
        return VideoMetadata(**defaults)

    def test_resolution_string(self):
        meta = self._make_meta(width=1280, height=720)
        assert meta.resolution == "1280x720"

    def test_to_dict_contains_key_fields(self):
        meta = self._make_meta()
        d = meta.to_dict()
        assert "duration_seconds" in d
        assert "resolution" in d
        assert "codec" in d
        assert "fps" in d

    def test_is_long_video_boundary(self):
        assert self._make_meta(duration_seconds=3600.0).is_long_video is True
        assert self._make_meta(duration_seconds=3599.9).is_long_video is False
