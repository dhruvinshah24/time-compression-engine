"""
Unit tests for pipeline stages s01_upload and s02_extract — Phase 2.
"""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from app.pipeline.context import PipelineContext
from app.pipeline.result import StageResult
from app.pipeline.stages import s01_upload


def _make_context(tmp_path: Path, video_path: str | None = None) -> PipelineContext:
    """Create a test PipelineContext."""
    return PipelineContext(
        job_id="JOB-20260730-0001",
        video_id="test-video-uuid",
        video_path=video_path or str(tmp_path / "test.mp4"),
        output_dir=str(tmp_path / "output"),
        settings={"frame_skip_rate": 5},
        metadata={},
        logger=None,
    )


# ---------------------------------------------------------------------------
# s01_upload
# ---------------------------------------------------------------------------

class TestS01Upload:
    @pytest.mark.asyncio
    async def test_missing_file_fails(self, tmp_path):
        from app.pipeline.stages import s01_upload
        context = _make_context(tmp_path, video_path=str(tmp_path / "nonexistent.mp4"))
        result = await s01_upload.run(context)
        assert result.success is False
        assert any("not found" in e.lower() for e in result.errors)
        assert result.stage_name == "s01_upload"

    @pytest.mark.asyncio
    @patch("app.pipeline.stages.s01_upload.validate_video_file")
    @patch("app.pipeline.stages.s01_upload.extract_thumbnail")
    @patch("app.pipeline.stages.s01_upload.get_thumbnails_dir")
    async def test_valid_video_succeeds(
        self, mock_thumb_dir, mock_thumbnail, mock_validate, tmp_path
    ):
        # Create a real (fake) file so existence check passes
        video = tmp_path / "test.mp4"
        video.write_bytes(b"fake video content")

        # Mock validation to succeed
        mock_meta = MagicMock()
        mock_meta.file_size_bytes = 1024
        mock_meta.duration_seconds = 120.0
        mock_meta.fps = 25.0
        mock_meta.frame_count = 3000
        mock_meta.resolution = "1920x1080"
        mock_meta.codec = "h264"
        mock_meta.has_audio = True
        mock_meta.is_long_video = False

        mock_validate.return_value = MagicMock(
            valid=True, rejected=False, errors=[], warnings=[], metadata=mock_meta
        )
        mock_thumb_dir.return_value = tmp_path
        mock_thumbnail.return_value = str(tmp_path / "thumb.jpg")

        context = _make_context(tmp_path, video_path=str(video))
        result = await s01_upload.run(context)

        assert result.success is True
        assert result.errors == []
        assert context.metadata["video_metadata"] is mock_meta
        assert context.metadata["fps"] == 25.0
        assert context.metadata["duration_seconds"] == 120.0

    @pytest.mark.asyncio
    @patch("app.pipeline.stages.s01_upload.validate_video_file")
    async def test_corrupted_file_fails(self, mock_validate, tmp_path):
        video = tmp_path / "corrupted.mp4"
        video.write_bytes(b"garbage data")

        mock_validate.return_value = MagicMock(
            valid=False,
            rejected=True,
            errors=["File is corrupted or unreadable"],
            warnings=[],
            metadata=None,
        )

        context = _make_context(tmp_path, video_path=str(video))
        from app.pipeline.stages import s01_upload
        result = await s01_upload.run(context)

        assert result.success is False
        assert len(result.errors) > 0

    @pytest.mark.asyncio
    @patch("app.pipeline.stages.s01_upload.validate_video_file")
    @patch("app.pipeline.stages.s01_upload.extract_thumbnail")
    @patch("app.pipeline.stages.s01_upload.get_thumbnails_dir")
    async def test_long_video_adds_warning(
        self, mock_thumb_dir, mock_thumbnail, mock_validate, tmp_path
    ):
        video = tmp_path / "long.mp4"
        video.write_bytes(b"fake content")

        mock_meta = MagicMock()
        mock_meta.file_size_bytes = 100 * 1024 * 1024
        mock_meta.duration_seconds = 86400.0  # 24 hours
        mock_meta.fps = 25.0
        mock_meta.frame_count = 2_160_000
        mock_meta.resolution = "1920x1080"
        mock_meta.codec = "h264"
        mock_meta.has_audio = False
        mock_meta.is_long_video = True

        mock_validate.return_value = MagicMock(
            valid=True, rejected=False, errors=[], warnings=[], metadata=mock_meta
        )
        mock_thumb_dir.return_value = tmp_path
        mock_thumbnail.return_value = str(tmp_path / "thumb.jpg")

        context = _make_context(tmp_path, video_path=str(video))
        from app.pipeline.stages import s01_upload
        result = await s01_upload.run(context)

        assert result.success is True
        assert context.metadata["is_long_video"] is True
        assert any("chunk" in w.lower() or "hour" in w.lower() for w in result.warnings)

    @pytest.mark.asyncio
    @patch("app.pipeline.stages.s01_upload.validate_video_file")
    @patch("app.pipeline.stages.s01_upload.extract_thumbnail")
    @patch("app.pipeline.stages.s01_upload.get_thumbnails_dir")
    async def test_thumbnail_failure_is_non_fatal(
        self, mock_thumb_dir, mock_thumbnail, mock_validate, tmp_path
    ):
        video = tmp_path / "test.mp4"
        video.write_bytes(b"fake content")

        mock_meta = MagicMock()
        mock_meta.file_size_bytes = 1024
        mock_meta.duration_seconds = 60.0
        mock_meta.fps = 25.0
        mock_meta.frame_count = 1500
        mock_meta.resolution = "1280x720"
        mock_meta.codec = "h264"
        mock_meta.has_audio = True
        mock_meta.is_long_video = False

        mock_validate.return_value = MagicMock(
            valid=True, rejected=False, errors=[], warnings=[], metadata=mock_meta
        )
        mock_thumb_dir.return_value = tmp_path
        from app.utils.ffmpeg import FFmpegError
        mock_thumbnail.side_effect = FFmpegError("thumb failed", -1, "")

        context = _make_context(tmp_path, video_path=str(video))
        from app.pipeline.stages import s01_upload
        result = await s01_upload.run(context)

        # Thumbnail failure should NOT fail the stage
        assert result.success is True
        assert any("thumbnail" in w.lower() for w in result.warnings)

    @pytest.mark.asyncio
    async def test_stage_result_has_correct_name(self, tmp_path):
        from app.pipeline.stages import s01_upload
        context = _make_context(tmp_path, video_path=str(tmp_path / "missing.mp4"))
        result = await s01_upload.run(context)
        assert result.stage_name == "s01_upload"

    @pytest.mark.asyncio
    async def test_stage_result_duration_ms_populated(self, tmp_path):
        from app.pipeline.stages import s01_upload
        context = _make_context(tmp_path, video_path=str(tmp_path / "missing.mp4"))
        result = await s01_upload.run(context)
        assert isinstance(result.duration_ms, int)
        assert result.duration_ms >= 0


# ---------------------------------------------------------------------------
# s02_extract
# ---------------------------------------------------------------------------

class TestS02Extract:
    @pytest.mark.asyncio
    async def test_missing_metadata_in_context_fails(self, tmp_path):
        from app.pipeline.stages import s02_extract
        context = _make_context(tmp_path)
        # Don't populate context.metadata["video_metadata"]
        result = await s02_extract.run(context)
        assert result.success is False
        assert any("video_metadata" in e for e in result.errors)

    @pytest.mark.asyncio
    @patch("app.pipeline.stages.s02_extract.extract_frames")
    @patch("app.pipeline.stages.s02_extract.get_frames_dir")
    async def test_successful_extraction(
        self, mock_frames_dir, mock_extract, tmp_path
    ):
        from app.utils.ffmpeg import FrameExtractionConfig, FrameExtractionResult

        mock_frames_dir.return_value = tmp_path / "frames"

        mock_result = MagicMock(spec=FrameExtractionResult)
        mock_result.frame_paths = [f"/frames/frame_{i:08d}.jpg" for i in range(300)]
        mock_result.total_frames_extracted = 300
        mock_result.extraction_time_ms = 5000
        mock_result.errors = []
        mock_extract.return_value = mock_result

        mock_meta = MagicMock()
        mock_meta.duration_seconds = 30.0
        mock_meta.frame_count = 1500
        mock_meta.is_long_video = False

        context = _make_context(tmp_path)
        context.metadata["video_metadata"] = mock_meta

        from app.pipeline.stages import s02_extract
        result = await s02_extract.run(context)

        assert result.success is True
        assert result.metrics["frames_extracted"] == 300
        assert result.metrics["frame_skip_rate"] == 5
        assert context.metadata["frames_extracted"] == 300

    @pytest.mark.asyncio
    @patch("app.pipeline.stages.s02_extract.extract_frames")
    @patch("app.pipeline.stages.s02_extract.get_frames_dir")
    async def test_zero_frames_extracted_fails(
        self, mock_frames_dir, mock_extract, tmp_path
    ):
        from app.utils.ffmpeg import FrameExtractionResult

        mock_frames_dir.return_value = tmp_path / "frames"

        mock_result = MagicMock(spec=FrameExtractionResult)
        mock_result.frame_paths = []
        mock_result.total_frames_extracted = 0
        mock_result.extraction_time_ms = 100
        mock_result.errors = []
        mock_extract.return_value = mock_result

        mock_meta = MagicMock()
        mock_meta.duration_seconds = 60.0
        mock_meta.frame_count = 1500
        mock_meta.is_long_video = False

        context = _make_context(tmp_path)
        context.metadata["video_metadata"] = mock_meta

        from app.pipeline.stages import s02_extract
        result = await s02_extract.run(context)

        assert result.success is False
        assert any("no frames" in e.lower() for e in result.errors)

    @pytest.mark.asyncio
    @patch("app.pipeline.stages.s02_extract.extract_frames")
    @patch("app.pipeline.stages.s02_extract.get_frames_dir")
    async def test_custom_skip_rate_from_settings(
        self, mock_frames_dir, mock_extract, tmp_path
    ):
        from app.utils.ffmpeg import FrameExtractionResult

        mock_frames_dir.return_value = tmp_path / "frames"

        mock_result = MagicMock(spec=FrameExtractionResult)
        mock_result.frame_paths = ["frame1.jpg"]
        mock_result.total_frames_extracted = 1
        mock_result.extraction_time_ms = 100
        mock_result.errors = []
        mock_extract.return_value = mock_result

        mock_meta = MagicMock()
        mock_meta.duration_seconds = 10.0
        mock_meta.frame_count = 250
        mock_meta.is_long_video = False

        context = _make_context(tmp_path)
        context.settings["frame_skip_rate"] = 10  # Custom rate
        context.metadata["video_metadata"] = mock_meta

        from app.pipeline.stages import s02_extract
        result = await s02_extract.run(context)

        assert result.success is True
        assert result.metrics["frame_skip_rate"] == 10
