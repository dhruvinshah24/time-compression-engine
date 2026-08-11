"""
YOLO Detection Models — YOLOv8 (COCO 80 classes) + YOLO-World (open-vocabulary).

Two model classes:
  YOLODetectionModel       — YOLOv8n/s/m/x, fixed 80 COCO classes.
  YOLOWorldDetectionModel  — YOLO-Worldv2, detects ANY object via text prompts.
                             No retraining required. Uses CLIP image-text alignment
                             trained on 500M+ image-text pairs (Tencent AI Lab, 2024).

For new videos, use 'yolov8l-worldv2' (default) — it can detect wallets, pens,
mugs, ceiling fans, curtains, safes, and 200+ custom classes.
"""

from __future__ import annotations

import logging
import time

import numpy as np

from app.model_registry.base_model import BaseDetectionModel, Detection, FrameDetectionResult

logger = logging.getLogger(__name__)

# ── COCO 80-class support for YOLOv8 (fixed-class models) ────────────────────
RELEVANT_COCO_CLASSES: set[int] = {
    0,   # person
    1,   # bicycle
    2,   # car
    3,   # motorcycle
    5,   # bus
    7,   # truck
    9,   # traffic light
    10,  # fire hydrant
    11,  # stop sign
    13,  # bench
    14,  # bird
    15,  # cat
    16,  # dog
    24,  # backpack
    25,  # umbrella
    26,  # handbag
    27,  # tie
    28,  # suitcase
    32,  # sports ball
    38,  # tennis racket
    39,  # bottle
    40,  # wine glass
    41,  # cup
    42,  # fork
    43,  # knife
    44,  # spoon
    45,  # bowl
    46,  # banana
    47,  # apple
    48,  # sandwich
    53,  # pizza
    55,  # cake
    56,  # chair
    57,  # couch
    58,  # potted plant
    59,  # bed
    60,  # dining table
    62,  # tv / monitor
    63,  # laptop
    64,  # mouse
    65,  # remote
    66,  # keyboard
    67,  # cell phone
    73,  # book
    74,  # clock
    75,  # vase
    76,  # scissors
    77,  # teddy bear
    78,  # hair drier
    79,  # toothbrush
}

COCO_DISPLAY_NAMES: dict[int, str] = {
    0: "Person", 1: "Bicycle", 2: "Car", 3: "Motorcycle", 5: "Bus", 7: "Truck",
    9: "Traffic Light", 10: "Fire Hydrant", 11: "Stop Sign",
    13: "Bench", 14: "Bird", 15: "Cat", 16: "Dog",
    24: "Backpack", 25: "Umbrella", 26: "Handbag", 27: "Tie", 28: "Suitcase",
    32: "Sports Ball", 38: "Tennis Racket",
    39: "Bottle", 40: "Glass", 41: "Cup", 42: "Fork",
    43: "Knife", 44: "Spoon", 45: "Bowl",
    46: "Banana", 47: "Apple", 48: "Sandwich", 53: "Pizza", 55: "Cake",
    56: "Chair", 57: "Couch", 58: "Potted Plant", 59: "Bed",
    60: "Table", 62: "TV / Monitor", 63: "Laptop",
    64: "Mouse", 65: "Remote", 66: "Keyboard", 67: "Phone",
    73: "Book", 74: "Clock", 75: "Vase", 76: "Scissors",
    77: "Teddy Bear", 78: "Hair Dryer", 79: "Toothbrush",
}

COCO_CATEGORIES: dict[int, str] = {
    0: "people",
    1: "vehicle", 2: "vehicle", 3: "vehicle", 5: "vehicle", 7: "vehicle",
    9: "outdoor", 10: "outdoor", 11: "outdoor",
    13: "furniture",
    14: "animal", 15: "animal", 16: "animal",
    24: "bag", 25: "bag", 26: "bag", 27: "clothing", 28: "bag",
    32: "sport", 38: "sport",
    39: "drinkware", 40: "drinkware", 41: "drinkware",
    42: "utensil", 43: "utensil", 44: "utensil", 45: "drinkware",
    46: "food", 47: "food", 48: "food", 53: "food", 55: "food",
    56: "furniture", 57: "furniture", 58: "home", 59: "furniture", 60: "furniture",
    62: "electronics", 63: "electronics", 64: "electronics",
    65: "electronics", 66: "electronics", 67: "electronics",
    73: "documents",
    74: "home", 75: "home", 76: "home", 77: "home", 78: "home", 79: "home",
}

# ── YOLO-World vocabulary — 200+ classes, detects ANYTHING ───────────────────
# This is the text prompt list given to YOLO-World at runtime.
# Add any class name here in plain English and it will be detected.
# Organized by category for easy maintenance.
WORLD_VOCABULARY: list[str] = [
    # ── People & body ──────────────────────────────────────────────────────────
    "person", "man", "woman", "child", "baby", "crowd", "human hand", "face",

    # ── Furniture ─────────────────────────────────────────────────────────────
    "chair", "office chair", "sofa", "couch", "bed", "desk", "table",
    "dining table", "coffee table", "shelf", "bookshelf", "cabinet",
    "wardrobe", "closet", "drawer", "bench", "stool", "ottoman",
    "curtain", "window blind", "carpet", "rug", "pillow", "cushion",
    "lamp", "floor lamp", "desk lamp", "ceiling light", "light switch",
    "fan", "ceiling fan", "air conditioner", "heater",

    # ── Electronics ───────────────────────────────────────────────────────────
    "laptop", "notebook computer", "desktop computer", "monitor", "screen",
    "television", "TV", "tablet", "iPad", "phone", "smartphone",
    "mobile phone", "keyboard", "mouse", "remote control", "speaker",
    "headphones", "earphones", "microphone", "camera", "webcam",
    "charger", "power bank", "cable", "USB drive", "hard drive",
    "printer", "router", "modem", "projector", "smart watch",

    # ── Kitchen & drinkware ───────────────────────────────────────────────────
    "bottle", "water bottle", "glass", "wine glass", "cup", "mug",
    "coffee mug", "tea cup", "plate", "bowl", "fork", "knife", "spoon",
    "chopsticks", "tray", "cutting board", "kettle", "coffee maker",
    "microwave", "refrigerator", "toaster", "blender",

    # ── Food ──────────────────────────────────────────────────────────────────
    "banana", "apple", "orange", "pizza", "sandwich", "burger",
    "cake", "bread", "fruit", "vegetables",

    # ── Office & stationery ───────────────────────────────────────────────────
    "book", "notebook", "pen", "pencil", "marker", "highlighter",
    "folder", "binder", "stapler", "scissors", "tape", "ruler",
    "calculator", "clock", "calendar", "whiteboard", "sticky note",
    "envelope", "paper", "document",

    # ── Bags & personal items ─────────────────────────────────────────────────
    "backpack", "handbag", "purse", "wallet", "suitcase", "briefcase",
    "shopping bag", "gym bag", "tote bag",

    # ── Clothing & accessories ─────────────────────────────────────────────────
    "shoe", "sneaker", "glasses", "sunglasses", "hat", "cap",
    "jacket", "coat", "umbrella", "watch", "ring", "necklace",

    # ── Sports & recreation ───────────────────────────────────────────────────
    "ball", "basketball", "soccer ball", "tennis racket",
    "skateboard", "helmet", "gym equipment", "dumbbell", "yoga mat",

    # ── Vehicles ──────────────────────────────────────────────────────────────
    "car", "truck", "bus", "motorcycle", "bicycle", "scooter", "van",

    # ── Animals ───────────────────────────────────────────────────────────────
    "dog", "cat", "bird", "fish",

    # ── Home & miscellaneous ──────────────────────────────────────────────────
    "vase", "plant", "potted plant", "flower", "candle", "frame",
    "picture frame", "mirror", "door", "window", "key", "lock",
    "fire extinguisher", "trash can", "box", "package", "toy",
    "teddy bear", "musical instrument", "guitar", "piano",

    # ── Security items (special user request) ─────────────────────────────────
    "safe", "vault", "safe box", "security camera", "CCTV camera",
    "padlock", "keycard",
]

# Category mapping for YOLO-World detections (by class name)
WORLD_CATEGORIES: dict[str, str] = {
    # People
    "person": "people", "man": "people", "woman": "people", "child": "people",
    "baby": "people", "crowd": "people", "human hand": "people", "face": "people",
    # Furniture
    "chair": "furniture", "office chair": "furniture", "sofa": "furniture",
    "couch": "furniture", "bed": "furniture", "desk": "furniture", "table": "furniture",
    "dining table": "furniture", "coffee table": "furniture", "shelf": "furniture",
    "bookshelf": "furniture", "cabinet": "furniture", "wardrobe": "furniture",
    "bench": "furniture", "stool": "furniture", "ottoman": "furniture",
    "curtain": "home", "window blind": "home", "carpet": "home", "rug": "home",
    "pillow": "home", "cushion": "home", "lamp": "home", "floor lamp": "home",
    "desk lamp": "home", "ceiling light": "home", "light switch": "home",
    "fan": "home", "ceiling fan": "home", "air conditioner": "home",
    # Electronics
    "laptop": "electronics", "notebook computer": "electronics",
    "desktop computer": "electronics", "monitor": "electronics", "screen": "electronics",
    "television": "electronics", "tv": "electronics", "tablet": "electronics",
    "ipad": "electronics", "phone": "electronics", "smartphone": "electronics",
    "mobile phone": "electronics", "keyboard": "electronics", "mouse": "electronics",
    "remote control": "electronics", "speaker": "electronics",
    "headphones": "electronics", "earphones": "electronics",
    "camera": "electronics", "webcam": "electronics", "charger": "electronics",
    "projector": "electronics", "smart watch": "electronics",
    # Kitchen
    "bottle": "drinkware", "water bottle": "drinkware", "glass": "drinkware",
    "wine glass": "drinkware", "cup": "drinkware", "mug": "drinkware",
    "coffee mug": "drinkware", "tea cup": "drinkware", "plate": "kitchen",
    "bowl": "kitchen", "fork": "kitchen", "knife": "kitchen", "spoon": "kitchen",
    "kettle": "kitchen", "coffee maker": "kitchen", "microwave": "kitchen",
    # Office
    "book": "documents", "notebook": "documents", "pen": "stationery",
    "pencil": "stationery", "marker": "stationery", "folder": "documents",
    "calculator": "electronics", "clock": "home", "whiteboard": "furniture",
    "document": "documents", "paper": "documents",
    # Bags
    "backpack": "bag", "handbag": "bag", "purse": "bag", "wallet": "bag",
    "suitcase": "bag", "briefcase": "bag", "shopping bag": "bag",
    # Clothing
    "glasses": "clothing", "sunglasses": "clothing", "hat": "clothing",
    "jacket": "clothing", "umbrella": "bag", "watch": "clothing",
    # Vehicles
    "car": "vehicle", "truck": "vehicle", "bus": "vehicle",
    "motorcycle": "vehicle", "bicycle": "vehicle", "scooter": "vehicle",
    # Animals
    "dog": "animal", "cat": "animal", "bird": "animal",
    # Security
    "safe": "security", "vault": "security", "safe box": "security",
    "security camera": "security", "cctv camera": "security",
    "padlock": "security", "keycard": "security",
    # Home
    "vase": "home", "plant": "home", "potted plant": "home",
    "mirror": "home", "door": "home", "window": "home",
    "trash can": "home", "toy": "home", "teddy bear": "home",
    "fire extinguisher": "safety",
}


def _world_category(class_name: str) -> str:
    """Return category for a YOLO-World detected class."""
    key = class_name.lower().strip()
    if key in WORLD_CATEGORIES:
        return WORLD_CATEGORIES[key]
    # Fuzzy fallback by keyword
    if any(k in key for k in ("person", "man", "woman", "child", "human")):
        return "people"
    if any(k in key for k in ("chair", "desk", "table", "bed", "sofa", "shelf")):
        return "furniture"
    if any(k in key for k in ("phone", "laptop", "computer", "screen", "tv", "camera")):
        return "electronics"
    if any(k in key for k in ("car", "truck", "bus", "bike", "vehicle")):
        return "vehicle"
    if any(k in key for k in ("bottle", "glass", "cup", "mug", "drink")):
        return "drinkware"
    if any(k in key for k in ("book", "pen", "paper", "document", "folder")):
        return "documents"
    if any(k in key for k in ("bag", "backpack", "wallet", "purse")):
        return "bag"
    return "object"


class YOLODetectionModel(BaseDetectionModel):
    """
    YOLOv8 object detector — fixed 80 COCO classes.

    Lazy-loads the model on first call to detect().
    Use this for yolov8n/s/m/x models.
    """

    def __init__(self, spec) -> None:
        super().__init__(spec)
        self._model = None
        self._ultralytics_available: bool | None = None
        self._load_error: str | None = None

    def _ensure_loaded(self) -> bool:
        """Lazy-load the YOLO model on the correct device. Returns True if successfully loaded."""
        if self._model is not None:
            return True
        if self._load_error is not None:
            return False
        try:
            import torch
            from ultralytics import YOLO  # type: ignore
            weight = self.spec.weight_path or f"{self.spec.name}.pt"
            device = 0 if torch.cuda.is_available() else "cpu"
            logger.info(
                "Loading %s on device=%s (weights=%s)",
                self.spec.name, 'cuda' if device == 0 else 'cpu', weight,
            )
            self._model = YOLO(weight)
            self._model.to(device)
            self._device = device
            # Warmup: run one dummy inference to pre-compile CUDA kernels.
            # Without this, the first real video frame takes 10-30s.
            import numpy as _np
            _dummy = _np.zeros((640, 640, 3), dtype=_np.uint8)
            self._model(_dummy, verbose=False, device=device)
            logger.info("%s warmed up on %s", self.spec.name, 'cuda' if device == 0 else 'cpu')
            self._ultralytics_available = True
            return True
        except ImportError:
            self._load_error = "ultralytics not installed. Run: pip install ultralytics"
            self._ultralytics_available = False
            logger.warning(self._load_error)
            return False
        except Exception as exc:
            self._load_error = str(exc)
            logger.warning("Failed to load YOLO %s: %s", self.spec.name, exc)
            return False

    def detect(
        self,
        image: np.ndarray,
        frame_number: int = 0,
        timestamp_ms: float = 0.0,
        override_confidence: float | None = None,
    ) -> FrameDetectionResult:
        """Run YOLO inference on a single frame on GPU (or CPU fallback)."""
        self._calls_total += 1
        start = time.perf_counter()
        effective_conf = override_confidence if override_confidence is not None \
            else self.spec.confidence_threshold

        if not self._ensure_loaded():
            if self._ultralytics_available is False:
                raise ImportError(self._load_error or "ultralytics not available")
            return FrameDetectionResult(
                frame_number=frame_number, frame_path="", timestamp_ms=timestamp_ms,
                model_name=self.model_name, model_version=self.model_version,
            )

        img_h, img_w = image.shape[:2]
        detections: list[Detection] = []
        pre_count = 0
        device = getattr(self, '_device', 'cpu')

        try:
            results = self._model(
                image,
                conf=effective_conf,
                iou=0.45,
                agnostic_nms=False,
                max_det=100,
                verbose=False,
                device=device,  # ← GPU inference (was missing — 60x slowdown bug)
            )
            for result in results:
                boxes = result.boxes
                if boxes is None:
                    continue
                pre_count += len(boxes)
                for i in range(len(boxes)):
                    class_id = int(boxes.cls[i].item())
                    if self.spec.classes is None and class_id not in RELEVANT_COCO_CLASSES:
                        continue
                    confidence = float(boxes.conf[i].item())
                    x1, y1, x2, y2 = [int(v) for v in boxes.xyxy[i].tolist()]
                    raw_name = result.names.get(class_id, str(class_id))
                    display = COCO_DISPLAY_NAMES.get(class_id, raw_name)
                    detections.append(Detection(
                        class_id=class_id,
                        class_name=display.lower().replace(" / ", "_").replace(" ", "_"),
                        confidence=confidence,
                        bbox_x1=x1/img_w, bbox_y1=y1/img_h,
                        bbox_x2=x2/img_w, bbox_y2=y2/img_h,
                        bbox_px_x1=x1, bbox_px_y1=y1, bbox_px_x2=x2, bbox_px_y2=y2,
                        frame_number=frame_number, timestamp_ms=timestamp_ms,
                        model_name=self.model_name, model_version=self.model_version,
                    ))
        except Exception as exc:
            logger.warning("YOLO inference failed frame %d: %s", frame_number, exc)

        inference_ms = (time.perf_counter() - start) * 1000
        self._total_inference_ms += inference_ms
        for d in detections:
            d.inference_time_ms = inference_ms

        return FrameDetectionResult(
            frame_number=frame_number, frame_path="", timestamp_ms=timestamp_ms,
            detections=detections, inference_time_ms=inference_ms,
            model_name=self.model_name, model_version=self.model_version,
            weights_path=self.spec.weight_path or f"{self.spec.name}.pt",
            confidence_threshold=effective_conf,
            pre_confidence_filter_count=pre_count,
        )

    def detect_batch(
        self,
        images: list[np.ndarray],
        frame_numbers: list[int],
        timestamps: list[float],
        override_confidence: float | None = None,
    ) -> list[FrameDetectionResult]:
        """
        Run batched GPU inference on multiple frames at once.

        Up to 4× faster than sequential detect() calls on GPU because the
        GPU processes all frames in a single forward pass. Used by SAHI tiling
        and by the main detection loop for small-frame videos.
        """
        if not self._ensure_loaded():
            return [self.detect(img, fn, ts, override_confidence)
                    for img, fn, ts in zip(images, frame_numbers, timestamps)]

        effective_conf = override_confidence if override_confidence is not None \
            else self.spec.confidence_threshold
        device = getattr(self, '_device', 'cpu')
        start = time.perf_counter()

        try:
            all_results = self._model(
                images,           # ultralytics accepts a list of ndarray → batch
                conf=effective_conf,
                iou=0.45,
                agnostic_nms=False,
                max_det=100,
                verbose=False,
                device=device,
            )
        except Exception as exc:
            logger.warning("Batch YOLO inference failed: %s", exc)
            return [self.detect(img, fn, ts, override_confidence)
                    for img, fn, ts in zip(images, frame_numbers, timestamps)]

        inference_ms = (time.perf_counter() - start) * 1000
        output: list[FrameDetectionResult] = []

        for idx, (result, fn, ts) in enumerate(zip(all_results, frame_numbers, timestamps)):
            img_h, img_w = images[idx].shape[:2]
            detections: list[Detection] = []
            boxes = result.boxes
            if boxes is not None:
                for i in range(len(boxes)):
                    class_id = int(boxes.cls[i].item())
                    if self.spec.classes is None and class_id not in RELEVANT_COCO_CLASSES:
                        continue
                    confidence = float(boxes.conf[i].item())
                    x1, y1, x2, y2 = [int(v) for v in boxes.xyxy[i].tolist()]
                    raw_name = result.names.get(class_id, str(class_id))
                    display = COCO_DISPLAY_NAMES.get(class_id, raw_name)
                    detections.append(Detection(
                        class_id=class_id,
                        class_name=display.lower().replace(" / ", "_").replace(" ", "_"),
                        confidence=confidence,
                        bbox_x1=x1/img_w, bbox_y1=y1/img_h,
                        bbox_x2=x2/img_w, bbox_y2=y2/img_h,
                        bbox_px_x1=x1, bbox_px_y1=y1, bbox_px_x2=x2, bbox_px_y2=y2,
                        frame_number=fn, timestamp_ms=ts,
                        model_name=self.model_name, model_version=self.model_version,
                    ))
            output.append(FrameDetectionResult(
                frame_number=fn, frame_path="", timestamp_ms=ts,
                detections=detections, inference_time_ms=inference_ms / len(images),
                model_name=self.model_name, model_version=self.model_version,
                confidence_threshold=effective_conf,
                pre_confidence_filter_count=len(boxes) if boxes is not None else 0,
            ))

        return output

    def health(self) -> str:
        if self._model is not None:
            return "ready"
        if self._load_error:
            return "unavailable"
        try:
            import ultralytics  # noqa: F401
            return "ready"
        except ImportError:
            return "unavailable"


class YOLOWorldDetectionModel(BaseDetectionModel):
    """
    YOLO-World open-vocabulary detector.

    Detects ANY object described in plain English — no retraining required.
    Uses vision-language alignment (CLIP-based) trained on 500M image-text pairs.

    Vocabulary is defined in WORLD_VOCABULARY (200+ classes) and can be extended
    at any time by adding strings to that list. The model runs inference against
    whichever text prompts are set via set_classes().

    Reference: "YOLO-World: Real-Time Open-Vocabulary Object Detection"
               Cheng et al., Tencent AI Lab, CVPR 2024.
    """

    def __init__(self, spec) -> None:
        super().__init__(spec)
        self._model = None
        self._ultralytics_available: bool | None = None
        self._load_error: str | None = None
        self._classes_set: bool = False

    def _ensure_loaded(self) -> bool:
        """Lazy-load YOLO-World model on GPU and set vocabulary on first call."""
        if self._model is not None:
            return True
        if self._load_error is not None:
            return False
        try:
            import torch
            from ultralytics import YOLO  # type: ignore
            weight = self.spec.weight_path or f"{self.spec.name}.pt"
            device = 0 if torch.cuda.is_available() else "cpu"
            logger.info(
                "Loading YOLO-World: %s on %s (vocab=%d classes)",
                self.spec.name, 'cuda' if device == 0 else 'cpu', len(WORLD_VOCABULARY),
            )
            self._model = YOLO(weight)
            self._model.set_classes(WORLD_VOCABULARY)
            self._model.to(device)
            self._device = device
            # Warmup pass to pre-compile CUDA kernels
            import numpy as _np
            _dummy = _np.zeros((640, 640, 3), dtype=_np.uint8)
            self._model.predict(_dummy, verbose=False, device=device)
            self._classes_set = True
            self._ultralytics_available = True
            logger.info("YOLO-World %s warmed up on %s", self.spec.name, 'cuda' if device == 0 else 'cpu')
            return True
        except ImportError:
            self._load_error = "ultralytics not installed. Run: pip install ultralytics"
            self._ultralytics_available = False
            logger.warning(self._load_error)
            return False
        except Exception as exc:
            self._load_error = str(exc)
            logger.warning("Failed to load YOLO-World %s: %s", self.spec.name, exc)
            return False

    def detect(
        self,
        image: np.ndarray,
        frame_number: int = 0,
        timestamp_ms: float = 0.0,
        override_confidence: float | None = None,
    ) -> FrameDetectionResult:
        """
        Run YOLO-World open-vocabulary inference on a single frame.

        Returns detections for any class in WORLD_VOCABULARY that appears in
        the frame, with confidence >= effective_conf.
        """
        self._calls_total += 1
        start = time.perf_counter()
        effective_conf = override_confidence if override_confidence is not None \
            else self.spec.confidence_threshold

        if not self._ensure_loaded():
            if self._ultralytics_available is False:
                raise ImportError(self._load_error or "ultralytics not available")
            return FrameDetectionResult(
                frame_number=frame_number, frame_path="", timestamp_ms=timestamp_ms,
                model_name=self.model_name, model_version=self.model_version,
            )

        img_h, img_w = image.shape[:2]
        detections: list[Detection] = []
        pre_count = 0

        try:
            device = getattr(self, '_device', 'cpu')
            results = self._model.predict(
                image,
                conf=effective_conf,
                iou=0.45,
                max_det=150,         # World model finds more unique classes
                verbose=False,
                device=device,       # ← GPU inference (was missing)
            )
            for result in results:
                boxes = result.boxes
                if boxes is None:
                    continue
                pre_count += len(boxes)
                for i in range(len(boxes)):
                    class_id = int(boxes.cls[i].item())
                    confidence = float(boxes.conf[i].item())

                    # YOLO-World: class names come from the vocabulary we set
                    raw_name: str = result.names.get(class_id, str(class_id))
                    # Normalize: lowercase, replace spaces with underscores
                    class_name_norm = raw_name.lower().replace(" ", "_")

                    x1, y1, x2, y2 = [int(v) for v in boxes.xyxy[i].tolist()]

                    detections.append(Detection(
                        class_id=class_id,
                        class_name=class_name_norm,
                        confidence=confidence,
                        bbox_x1=x1/img_w, bbox_y1=y1/img_h,
                        bbox_x2=x2/img_w, bbox_y2=y2/img_h,
                        bbox_px_x1=x1, bbox_px_y1=y1, bbox_px_x2=x2, bbox_px_y2=y2,
                        frame_number=frame_number, timestamp_ms=timestamp_ms,
                        model_name=self.model_name, model_version=self.model_version,
                    ))
        except Exception as exc:
            logger.warning("YOLO-World inference failed frame %d: %s", frame_number, exc)

        inference_ms = (time.perf_counter() - start) * 1000
        self._total_inference_ms += inference_ms
        for d in detections:
            d.inference_time_ms = inference_ms

        logger.debug(
            "YOLO-World frame %d: %d detections (conf>=%.2f) %.1fms",
            frame_number, len(detections), effective_conf, inference_ms,
        )

        return FrameDetectionResult(
            frame_number=frame_number, frame_path="", timestamp_ms=timestamp_ms,
            detections=detections, inference_time_ms=inference_ms,
            model_name=self.model_name, model_version=self.model_version,
            weights_path=self.spec.weight_path or f"{self.spec.name}.pt",
            confidence_threshold=effective_conf,
            pre_confidence_filter_count=pre_count,
        )

    def health(self) -> str:
        if self._model is not None:
            return "ready"
        if self._load_error:
            return "unavailable"
        try:
            import ultralytics  # noqa: F401
            return "ready"
        except ImportError:
            return "unavailable"
