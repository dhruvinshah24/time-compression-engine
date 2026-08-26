"""
Tests: Evaluation Matrix (Phase 3).
"""

import json
import pytest
from pathlib import Path

from app.utils.evaluation import (
    EvaluationMatrix,
    evaluate_job,
    export_evaluation_json,
    export_evaluation_csv,
)


def _make_job(job_id="JOB-001", model_profile="accuracy", **overrides):
    job = {
        "id":             job_id,
        "video_id":       "VID-001",
        "model_profile":  model_profile,
        "detection_model": "yolo11x",
        "pose_model":     "yolo11x-pose",
        "status":         "completed",
        "stages": [
            {
                "name": "s02_extract",
                "status": "completed",
                "duration_ms": 1500,
                "metrics": {
                    "frames_extracted": 300,
                    "estimated_frames": 1500,
                    "adaptive_skip_enabled": True,
                    "processing_profile": "SHORT",
                    "adaptive_skip_stats": {
                        "effective_sampling_ratio": 0.2,
                        "frames_skipped": 1200,
                    },
                },
            },
            {
                "name": "s04_object_detect",
                "status": "completed",
                "duration_ms": 8000,
                "metrics": {
                    "total_detections": 450,
                    "low_light_frames": 5,
                    "unusable_frames_skipped": 2,
                    "sahi_enabled": True,
                },
            },
            {
                "name": "s07_event_understand",
                "status": "completed",
                "duration_ms": 500,
                "metrics": {
                    "total_events": 8,
                    "event_types": {"person_walking": 3, "person_entered_roi": 2},
                },
            },
        ],
    }
    job.update(overrides)
    return job


def test_evaluate_job_returns_evaluation_matrix():
    job = _make_job()
    matrix = evaluate_job(job)
    assert isinstance(matrix, EvaluationMatrix)


def test_evaluation_matrix_has_all_required_fields():
    matrix = EvaluationMatrix(video_id="test", video_source="synthetic")
    required_fields = [
        "video_id", "video_source", "duration_seconds", "resolution",
        "model_profile", "detection_model", "adaptive_skip_enabled",
        "total_detections", "events_generated", "processing_time_seconds",
        "real_time_factor", "validation_status", "failures",
    ]
    d = matrix.__dict__
    for field in required_fields:
        assert field in d, f"Missing required field: {field}"


def test_real_time_factor_calculated_correctly():
    job = _make_job()
    meta = {"duration_seconds": 30.0, "fps": 25.0}
    matrix = evaluate_job(job, meta)
    # total_ms = 1500 + 8000 + 500 = 10000ms = 10s
    # rtf = 10 / 30 = 0.333...
    assert matrix.processing_time_seconds == pytest.approx(10.0, rel=1e-3)
    assert matrix.real_time_factor == pytest.approx(10.0 / 30.0, rel=1e-3)


def test_missing_fields_remain_none_not_invented():
    """Fields not in job record must be None, not made-up values."""
    job = {
        "id": "JOB-999",
        "video_id": "VID-999",
        "stages": [],
    }
    matrix = evaluate_job(job)
    assert matrix.total_detections is None
    assert matrix.events_generated is None
    assert matrix.processing_time_seconds is None
    assert matrix.real_time_factor is None
    assert matrix.detection_precision is None   # GT not available
    assert matrix.detection_recall is None


def test_export_evaluation_json_creates_file(tmp_path):
    matrix = EvaluationMatrix(video_id="v1", video_source="test")
    out = tmp_path / "result.json"
    export_evaluation_json(matrix, out)
    assert out.exists()
    data = json.loads(out.read_text())
    assert data["video_id"] == "v1"
    assert "validation_status" in data


def test_export_evaluation_csv_creates_file(tmp_path):
    matrices = [
        EvaluationMatrix(video_id="v1", video_source="test"),
        EvaluationMatrix(video_id="v2", video_source="test"),
    ]
    out = tmp_path / "results.csv"
    export_evaluation_csv(matrices, out)
    assert out.exists()
    lines = out.read_text().splitlines()
    assert len(lines) == 3  # header + 2 rows


def test_export_evaluation_csv_empty_list_no_crash(tmp_path):
    out = tmp_path / "empty.csv"
    export_evaluation_csv([], out)
    assert not out.exists()  # nothing written for empty list


def test_validation_status_defaults_to_not_yet_validated():
    matrix = EvaluationMatrix(video_id="v1", video_source="test")
    assert matrix.validation_status == "NOT_YET_VALIDATED"


def test_ground_truth_fields_null_when_not_available():
    matrix = EvaluationMatrix(video_id="v1", video_source="test")
    assert matrix.ground_truth_available is False
    assert matrix.detection_precision is None
    assert matrix.detection_recall is None
    assert matrix.detection_f1 is None
