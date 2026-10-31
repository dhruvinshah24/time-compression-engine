"""Regression checks for optional infrared routing and mixed-class results."""
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest
import torch
from fastapi import HTTPException, UploadFile

from app.engines.perception.object_detector.detector import ObjectDetectionResult
from app.model_registry.base_model import Detection, FrameDetectionResult
from app.utils.night_vision import MODEL_NAME, replace_person_detections


def detection(class_id, name):
    return Detection(class_id, name, 0.8, 0.1, 0.1, 0.4, 0.6)


def test_replaces_people_preserves_objects_and_uses_original_ir_frame(tmp_path, monkeypatch):
    weight = tmp_path / "best.pt"
    weight.touch()
    person, chair = detection(0, "person"), detection(56, "chair")
    frames = [FrameDetectionResult(7, "enhanced/frame_7.jpg", 700, [person, chair]),
              FrameDetectionResult(8, "enhanced/frame_8.jpg", 800, [person])]
    result = ObjectDetectionResult(frame_results=frames, model_name="standard")
    box = SimpleNamespace(xyxy=torch.tensor([[20., 10., 60., 80.]]), conf=torch.tensor([0.9]))
    model = MagicMock(names={0: "person"})
    model.names = {0: "person"}
    model.predict.side_effect = [[SimpleNamespace(boxes=[box])], [SimpleNamespace(boxes=[])]]
    monkeypatch.setattr("ultralytics.YOLO", lambda path: model)
    reader = MagicMock(return_value=np.zeros((100, 200, 3), dtype=np.uint8))
    monkeypatch.setattr("cv2.imread", reader)
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)

    count = replace_person_detections(result, str(weight), ["raw/frame_7.jpg", "raw/frame_8.jpg"], 0.25)

    assert count == 1
    assert frames[0].detections[0] is chair
    night_person = frames[0].detections[1]
    assert night_person.model_name == MODEL_NAME
    assert night_person.bbox_x1 == 0.1 and night_person.bbox_y2 == 0.8
    assert night_person.frame_number == 7 and night_person.timestamp_ms == 700
    assert frames[1].detections == []  # Do not retain a standard-model person on an empty night result.
    assert reader.call_args_list[0].args == ("raw/frame_7.jpg",)
    assert model.predict.call_args.kwargs["conf"] == 0.25
    assert MODEL_NAME in result.model_name


def test_missing_weights_fails_explicitly(tmp_path):
    with pytest.raises(FileNotFoundError, match="unavailable"):
        replace_person_detections(ObjectDetectionResult(), str(tmp_path / "missing.pt"), [], 0.25)


def test_wrong_class_model_is_rejected(tmp_path, monkeypatch):
    weight = tmp_path / "best.pt"
    weight.touch()
    monkeypatch.setattr("ultralytics.YOLO", lambda path: SimpleNamespace(names={0: "car"}))
    with pytest.raises(ValueError, match="person class"):
        replace_person_detections(ObjectDetectionResult(), str(weight), [], 0.25)


@pytest.mark.asyncio
async def test_invalid_upload_mode_rejected_before_saving():
    from app.api.v1.routes.upload import upload_video
    with pytest.raises(HTTPException) as exc:
        await upload_video(file=UploadFile(filename="test.mp4", file=BytesIO(b"")),
                           source_domain="general", model_profile="fast", detection_mode="invalid")
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_night_upload_without_weights_is_rejected(tmp_path, monkeypatch):
    from app.api.v1.routes.upload import app_settings, upload_video
    monkeypatch.setattr(app_settings, "NIGHT_VISION_WEIGHTS", str(tmp_path / "missing.pt"))
    with pytest.raises(HTTPException) as exc:
        await upload_video(file=UploadFile(filename="test.mp4", file=BytesIO(b"")),
                           source_domain="general", model_profile="fast", detection_mode="night_vision")
    assert exc.value.status_code == 503
