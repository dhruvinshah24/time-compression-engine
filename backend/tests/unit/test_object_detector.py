"""
Unit tests for Phase 3B: Object Detection.

Testing approach (per mentor guidance):
  "Write unit tests with mocked model outputs BEFORE using a real model."

All tests use either:
  - StubDetectionModel (returns empty results, always available)
  - Mock YOLO model (MagicMock replacing the real ultralytics call)

No real model weights are loaded. No ultralytics dependency required.
The pipeline is fully testable without any AI model installed.

Coverage:
  1. Detection data classes (Detection, FrameDetectionResult)
  2. StubDetectionModel behaviour
  3. ModelRegistry — registration, lazy loading, singleton
  4. BaseDetectionModel interface contract
  5. ObjectDetectionResult aggregation
  6. s04_object_detect pipeline stage (mocked)
  7. Graceful fallback when YOLO not installed
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from app.model_registry.base_model import Detection, FrameDetectionResult
from app.model_registry.models.stub_model import StubDetectionModel
from app.model_registry.registry import ModelRegistry, ModelSpec, ModelBackend, STUB_SPEC


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_detection(
    class_name: str = "person",
    confidence: float = 0.85,
    frame_number: int = 0,
) -> Detection:
    return Detection(
        class_id=0,
        class_name=class_name,
        confidence=confidence,
        bbox_x1=0.1, bbox_y1=0.1, bbox_x2=0.5, bbox_y2=0.9,
        bbox_px_x1=64, bbox_px_y1=72, bbox_px_x2=320, bbox_px_y2=648,
        frame_number=frame_number,
        timestamp_ms=frame_number * 200.0,
        model_name="yolov8n",
        model_version="8.0.0",
        inference_time_ms=12.5,
    )


def _make_frame_result(
    frame_number: int = 1,
    detections: list | None = None,
) -> FrameDetectionResult:
    return FrameDetectionResult(
        frame_number=frame_number,
        frame_path=f"/frames/frame_{frame_number:08d}.jpg",
        timestamp_ms=frame_number * 200.0,
        detections=detections or [],
        inference_time_ms=15.0,
        model_name="yolov8n",
        model_version="8.0.0",
    )


def _make_context(tmp_path: Path, keyframe_paths: list[str] | None = None):
    from app.pipeline.context import PipelineContext
    ctx = PipelineContext(
        job_id="JOB-20260730-TEST",
        video_id="test-vid",
        video_path=str(tmp_path / "video.mp4"),
        output_dir=str(tmp_path),
        settings={
            "detection_model_name": "stub",
            "detection_confidence": 0.72,
        },
        metadata={
            "fps": 25.0,
            "frame_skip_rate": 5,
        },
    )
    if keyframe_paths is not None:
        ctx.metadata["keyframe_paths"] = keyframe_paths
        ctx.metadata["keyframe_numbers"] = list(range(len(keyframe_paths)))
    return ctx


# ---------------------------------------------------------------------------
# Detection dataclass tests
# ---------------------------------------------------------------------------

class TestDetection:
    def test_center_x(self):
        det = _make_detection()
        # bbox_x1=0.1, bbox_x2=0.5 → center = 0.3
        assert det.center_x == pytest.approx(0.3)

    def test_center_y(self):
        det = _make_detection()
        # bbox_y1=0.1, bbox_y2=0.9 → center = 0.5
        assert det.center_y == pytest.approx(0.5)

    def test_width(self):
        det = _make_detection()
        assert det.width == pytest.approx(0.4)

    def test_height(self):
        det = _make_detection()
        assert det.height == pytest.approx(0.8)

    def test_area(self):
        det = _make_detection()
        assert det.area == pytest.approx(0.32)

    def test_to_dict_contains_all_keys(self):
        det = _make_detection()
        d = det.to_dict()
        for key in ["class_id", "class_name", "confidence", "bbox_normalized",
                    "bbox_pixels", "frame_number", "timestamp_ms",
                    "model_name", "model_version", "inference_time_ms"]:
            assert key in d

    def test_to_dict_bbox_normalized_length(self):
        det = _make_detection()
        assert len(det.to_dict()["bbox_normalized"]) == 4

    def test_confidence_stored_correctly(self):
        det = _make_detection(confidence=0.92)
        assert det.confidence == pytest.approx(0.92)


# ---------------------------------------------------------------------------
# FrameDetectionResult tests
# ---------------------------------------------------------------------------

class TestFrameDetectionResult:
    def test_detection_count(self):
        result = _make_frame_result(detections=[_make_detection(), _make_detection()])
        assert result.detection_count == 2

    def test_empty_detection_count(self):
        result = _make_frame_result()
        assert result.detection_count == 0

    def test_to_dict_structure(self):
        result = _make_frame_result(detections=[_make_detection()])
        d = result.to_dict()
        assert "detections" in d
        assert "detection_count" in d
        assert d["detection_count"] == 1
        assert "inference_time_ms" in d


# ---------------------------------------------------------------------------
# StubDetectionModel tests
# ---------------------------------------------------------------------------

class TestStubDetectionModel:
    def test_returns_empty_detections(self):
        model = StubDetectionModel(STUB_SPEC)
        image = np.zeros((224, 224, 3), dtype=np.uint8)
        result = model.detect(image, frame_number=1, timestamp_ms=1000.0)
        assert result.detections == []

    def test_health_returns_stub(self):
        model = StubDetectionModel(STUB_SPEC)
        assert model.health() == "stub"

    def test_model_name_from_spec(self):
        model = StubDetectionModel(STUB_SPEC)
        assert model.model_name == "stub"

    def test_calls_total_increments(self):
        model = StubDetectionModel(STUB_SPEC)
        image = np.zeros((64, 64, 3), dtype=np.uint8)
        model.detect(image)
        model.detect(image)
        assert model._calls_total == 2

    def test_frame_number_in_result(self):
        model = StubDetectionModel(STUB_SPEC)
        image = np.zeros((224, 224, 3), dtype=np.uint8)
        result = model.detect(image, frame_number=42, timestamp_ms=5000.0)
        assert result.frame_number == 42
        assert result.timestamp_ms == pytest.approx(5000.0)


# ---------------------------------------------------------------------------
# ModelRegistry tests
# ---------------------------------------------------------------------------

class TestModelRegistry:
    def setup_method(self):
        ModelRegistry.reset()

    def test_singleton_returns_same_instance(self):
        r1 = ModelRegistry.instance()
        r2 = ModelRegistry.instance()
        assert r1 is r2

    def test_get_stub_model(self):
        registry = ModelRegistry.instance()
        model = registry.get("stub")
        assert model.health() == "stub"

    def test_get_unknown_model_raises(self):
        registry = ModelRegistry.instance()
        with pytest.raises(KeyError, match="not registered"):
            registry.get("does_not_exist")

    def test_register_custom_spec(self):
        registry = ModelRegistry.instance()
        custom = ModelSpec(
            name="my_custom_model",
            backend=ModelBackend.STUB,
            version="1.0.0",
            description="Test custom model",
        )
        registry.register(custom)
        assert registry.get_spec("my_custom_model") is not None

    def test_list_models_includes_builtins(self):
        registry = ModelRegistry.instance()
        names = [s.name for s in registry.list_models()]
        assert "stub" in names
        assert "yolov8n" in names

    def test_unload_removes_cached_instance(self):
        registry = ModelRegistry.instance()
        model = registry.get("stub")  # Load it
        registry.unload("stub")
        # After unload, getting it again should create a new instance
        model2 = registry.get("stub")
        assert model is not model2

    def test_health_report_empty_when_no_models_loaded(self):
        registry = ModelRegistry.instance()
        assert registry.health_report() == {}

    def test_health_report_includes_loaded_models(self):
        registry = ModelRegistry.instance()
        registry.get("stub")
        report = registry.health_report()
        assert "stub" in report
        assert report["stub"] == "stub"


# ---------------------------------------------------------------------------
# ObjectDetectionResult tests
# ---------------------------------------------------------------------------

class TestObjectDetectionResult:
    def test_detections_by_class(self):
        from app.engines.perception.object_detector.detector import ObjectDetectionResult
        result = ObjectDetectionResult(
            total_frames_processed=3,
            total_detections=3,
            frames_with_detections=2,
            frame_results=[
                _make_frame_result(1, [_make_detection("person"), _make_detection("person")]),
                _make_frame_result(2, [_make_detection("car")]),
                _make_frame_result(3),
            ],
        )
        by_class = result.detections_by_class()
        assert by_class["person"] == 2
        assert by_class["car"] == 1

    def test_metrics_dict_keys(self):
        from app.engines.perception.object_detector.detector import ObjectDetectionResult
        result = ObjectDetectionResult(
            total_frames_processed=5,
            total_detections=3,
            frames_with_detections=2,
        )
        d = result.to_metrics_dict()
        assert "total_frames_processed" in d
        assert "total_detections" in d
        assert "detection_rate" in d
        assert "avg_inference_time_ms" in d

    def test_detection_rate_calculation(self):
        from app.engines.perception.object_detector.detector import ObjectDetectionResult
        result = ObjectDetectionResult(
            total_frames_processed=10,
            frames_with_detections=3,
        )
        d = result.to_metrics_dict()
        assert d["detection_rate"] == pytest.approx(0.3)


# ---------------------------------------------------------------------------
# s04_object_detect pipeline stage tests
# ---------------------------------------------------------------------------

class TestS04ObjectDetect:
    @pytest.mark.asyncio
    async def test_missing_keyframe_paths_fails(self, tmp_path):
        from app.pipeline.stages import s04_object_detect
        # Neither keyframe_paths nor frame_paths in context → should fail
        context = _make_context(tmp_path)  # no keyframe_paths, no frame_paths
        result = await s04_object_detect.run(context)
        assert result.success is False
        # Error message should mention that no frames are available
        assert len(result.errors) > 0

    @pytest.mark.asyncio
    @patch("app.pipeline.stages.s04_object_detect.save_stage_metrics")
    async def test_stub_model_returns_success_with_zero_detections(
        self, mock_save, tmp_path
    ):
        from app.pipeline.stages import s04_object_detect
        ModelRegistry.reset()

        kf_paths = [
            str(tmp_path / f"frame_{i:08d}.jpg") for i in range(1, 32)
        ]
        # Create fake frame files so PIL doesn't crash
        for p in kf_paths:
            from PIL import Image
            Image.new("RGB", (64, 64), color=(128, 128, 128)).save(p)

        # 31 keyframes >= MIN_FRAMES_FOR_TRACKING(30), so keyframes are used directly
        context = _make_context(tmp_path, keyframe_paths=kf_paths)
        context.metadata["frame_paths"] = kf_paths

        result = await s04_object_detect.run(context)
        assert result.success is True
        assert context.metadata["total_detections"] == 0
        assert len(result.warnings) > 0  # zero detections → warning

    @pytest.mark.asyncio
    @patch("app.pipeline.stages.s04_object_detect.save_stage_metrics")
    @patch("app.pipeline.stages.s04_object_detect.ObjectDetector")
    async def test_mocked_detections_stored_in_context(
        self, MockDetector, mock_save, tmp_path
    ):
        from app.engines.perception.object_detector.detector import ObjectDetectionResult
        from app.pipeline.stages import s04_object_detect
        ModelRegistry.reset()

        mock_result = ObjectDetectionResult(
            total_frames_processed=2,
            total_detections=3,
            frames_with_detections=2,
            frame_results=[
                _make_frame_result(1, [_make_detection("person"), _make_detection("person")]),
                _make_frame_result(6, [_make_detection("car")]),
            ],
            avg_inference_time_ms=12.5,
            model_name="yolov8n",
            model_version="8.0.0",
        )

        MockDetector.return_value.detect_keyframes.return_value = mock_result
        mock_save.return_value = None

        # Supply frame_paths so the fallback path has frames to work with
        frame_paths = ["/frames/frame_00000001.jpg", "/frames/frame_00000006.jpg"]
        context = _make_context(tmp_path, keyframe_paths=frame_paths)
        context.metadata["frame_paths"] = frame_paths

        result = await s04_object_detect.run(context)
        assert result.success is True
        assert result.metrics["total_detections"] == 3
        assert context.metadata["total_detections"] == 3
        assert context.metadata["detected_classes"]["person"] == 2

    @pytest.mark.asyncio
    @patch("app.pipeline.stages.s04_object_detect.save_stage_metrics")
    @patch("app.pipeline.stages.s04_object_detect.ObjectDetector")
    async def test_yolo_import_error_falls_back_to_stub(
        self, MockDetector, mock_save, tmp_path
    ):
        from app.engines.perception.object_detector.detector import ObjectDetectionResult
        from app.pipeline.stages import s04_object_detect
        ModelRegistry.reset()

        # First call raises ImportError (YOLO not installed)
        stub_result = ObjectDetectionResult(
            total_frames_processed=2, total_detections=0, frames_with_detections=0
        )
        MockDetector.return_value.detect_keyframes.side_effect = [
            ImportError("ultralytics not installed"),
            stub_result,
        ]
        mock_save.return_value = None

        # Supply frame_paths so the fallback selection has frames
        frame_paths = ["/f1.jpg", "/f2.jpg"]
        context = _make_context(tmp_path, keyframe_paths=frame_paths)
        context.metadata["frame_paths"] = frame_paths
        result = await s04_object_detect.run(context)

        assert result.success is True
        assert any("stub" in w.lower() or "fallback" in w.lower() for w in result.warnings)

    @pytest.mark.asyncio
    async def test_stage_name_is_correct(self, tmp_path):
        from app.pipeline.stages import s04_object_detect
        context = _make_context(tmp_path)
        result = await s04_object_detect.run(context)
        assert result.stage_name == "s04_object_detect"
