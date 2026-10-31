"""Opt-in infrared person detection alongside the standard object detector."""
from pathlib import Path
import time

from app.model_registry.base_model import Detection

MODEL_NAME = "unisv-night-person-experimental"


def replace_person_detections(result, weights: str, original_paths: list[str], confidence: float) -> int:
    """Replace standard person boxes, retaining every other object class.

    Use original infrared frames: the candidate was trained without CLAHE/gamma.
    Errors propagate so an opted-in job cannot silently use a different model.
    """
    import cv2
    import torch
    from ultralytics import YOLO

    weight_path = Path(weights).resolve()
    if not weight_path.is_file():
        raise FileNotFoundError("Experimental night-vision weights are unavailable.")
    model = YOLO(str(weight_path))
    if model.names != {0: "person"}:
        raise ValueError("Night-vision weights must contain only the person class.")
    device = 0 if torch.cuda.is_available() else "cpu"
    originals = {Path(path).name: path for path in original_paths}
    total = 0
    for frame in result.frame_results:
        source = originals.get(Path(frame.frame_path).name, frame.frame_path)
        image = cv2.imread(source)
        if image is None:
            raise ValueError(f"Unable to read infrared frame {Path(source).name}")
        start = time.perf_counter()
        prediction = model.predict(image, device=device, imgsz=640, classes=[0],
                                   conf=confidence, verbose=False)[0]
        elapsed_ms = (time.perf_counter() - start) * 1000
        height, width = image.shape[:2]
        people = []
        for box in prediction.boxes:
            x1, y1, x2, y2 = box.xyxy[0].cpu().tolist()
            people.append(Detection(
                class_id=0, class_name="person", confidence=float(box.conf[0].cpu()),
                bbox_x1=x1 / width, bbox_y1=y1 / height,
                bbox_x2=x2 / width, bbox_y2=y2 / height,
                bbox_px_x1=int(x1), bbox_px_y1=int(y1), bbox_px_x2=int(x2), bbox_px_y2=int(y2),
                frame_number=frame.frame_number, timestamp_ms=frame.timestamp_ms,
                model_name=MODEL_NAME, model_version="five-video-v1",
                inference_time_ms=elapsed_ms,
            ))
        frame.detections = [d for d in frame.detections if d.class_id != 0 and d.class_name != "person"] + people
        frame.inference_time_ms += elapsed_ms
        frame.model_name = f"{frame.model_name}+{MODEL_NAME}"
        frame.weights_path = f"{frame.weights_path}; person={weight_path}"
        frame.pre_confidence_filter_count = len(frame.detections)
        total += len(people)
    result.model_name = f"{result.model_name}+{MODEL_NAME}"
    return total
