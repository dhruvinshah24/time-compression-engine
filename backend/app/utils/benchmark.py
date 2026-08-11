"""
Benchmark Runner — Experiment Framework for TCE.

Runs the same video through different detection configurations and records:
  - Frames per second (throughput)
  - Total detections per frame (recall proxy)
  - Unique person identities found
  - Lighting events detected
  - GPU vs CPU utilization

This enables the "Experiment A/B/C/D" framework:
  Experiment A: YOLOv8l baseline
  Experiment B: YOLO11x
  Experiment C: YOLO11x + SAHI
  Experiment D: YOLO11x + SAHI + Adaptive Skip
  Experiment E: YOLO11x + SAHI + Adaptive Skip + BoT-SORT

Usage (from CLI or API):
    runner = BenchmarkRunner(video_path="test.mp4")
    result = runner.run(experiment_name="A", config={...})
    print(result.summary_table())
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ExperimentResult:
    """Results of a single benchmark experiment."""
    name: str
    config: dict[str, Any] = field(default_factory=dict)
    
    # Timing
    total_wall_seconds: float = 0.0
    frames_processed: int = 0
    frames_per_second: float = 0.0
    avg_inference_ms: float = 0.0
    
    # Detection quality
    total_detections: int = 0
    avg_detections_per_frame: float = 0.0
    unique_classes: list[str] = field(default_factory=list)
    person_count: int = 0
    
    # Event quality
    total_events: int = 0
    events_by_type: dict[str, int] = field(default_factory=dict)
    lighting_events: int = 0
    
    # Resource usage
    device: str = "cpu"
    peak_vram_mb: float = 0.0
    peak_ram_mb: float = 0.0
    
    # Errors / warnings
    errors: list[str] = field(default_factory=list)
    
    def summary_table_row(self) -> dict:
        """Return a row for comparison table."""
        return {
            "Experiment": self.name,
            "FPS":        round(self.frames_per_second, 1),
            "Avg Det/Frame": round(self.avg_detections_per_frame, 1),
            "Persons":    self.person_count,
            "Events":     self.total_events,
            "Lighting":   self.lighting_events,
            "Device":     self.device,
            "VRAM MB":    round(self.peak_vram_mb, 0),
            "Inf ms":     round(self.avg_inference_ms, 1),
        }
    
    def to_dict(self) -> dict:
        """Serialize for storage/API response."""
        return {
            "name":                  self.name,
            "config":                self.config,
            "timing": {
                "total_seconds":     round(self.total_wall_seconds, 2),
                "frames_processed":  self.frames_processed,
                "fps":               round(self.frames_per_second, 2),
                "avg_inference_ms":  round(self.avg_inference_ms, 2),
            },
            "detection": {
                "total":             self.total_detections,
                "avg_per_frame":     round(self.avg_detections_per_frame, 2),
                "unique_classes":    sorted(self.unique_classes),
                "person_count":      self.person_count,
            },
            "events": {
                "total":             self.total_events,
                "by_type":           self.events_by_type,
                "lighting":          self.lighting_events,
            },
            "resources": {
                "device":            self.device,
                "peak_vram_mb":      round(self.peak_vram_mb, 0),
                "peak_ram_mb":       round(self.peak_ram_mb, 0),
            },
            "errors":                self.errors,
        }


class BenchmarkRunner:
    """
    Runs detection experiments on a video and collects performance metrics.
    
    Each experiment is a named configuration dict that overrides
    the default pipeline settings. Results are stored as ExperimentResult
    objects and can be serialized to JSON for the UI.
    """

    def __init__(self, video_path: str) -> None:
        self.video_path = video_path
        self.results: list[ExperimentResult] = []

    def run_detection_experiment(
        self,
        experiment_name: str,
        model_name: str = "yolov8l",
        confidence: float = 0.20,
        use_sahi: bool = False,
        sahi_tile_size: int = 640,
        sahi_overlap: float = 0.2,
        frame_skip: int = 3,
        max_frames: int = 300,
    ) -> ExperimentResult:
        """
        Run a single detection experiment and return metrics.
        
        Args:
            experiment_name: Human-readable label (e.g. "A: YOLOv8l baseline")
            model_name:     Model to use (yolov8l, yolo11x, etc.)
            confidence:     Detection confidence threshold
            use_sahi:       Enable SAHI tiled inference
            sahi_tile_size: SAHI tile size in pixels
            sahi_overlap:   SAHI tile overlap ratio
            frame_skip:     Process every Nth frame (fixed skip)
            max_frames:     Max frames to process (for quick benchmarks)
        
        Returns:
            ExperimentResult with all collected metrics.
        """
        import cv2
        import torch
        import psutil
        import os
        
        result = ExperimentResult(
            name=experiment_name,
            config={
                "model": model_name, "confidence": confidence,
                "use_sahi": use_sahi, "sahi_tile_size": sahi_tile_size,
                "frame_skip": frame_skip,
            }
        )
        
        # Device info
        result.device = "cuda" if torch.cuda.is_available() else "cpu"
        
        try:
            from app.model_registry.registry import ModelRegistry
            registry = ModelRegistry()
            model = registry.get_model(model_name)
            if model is None:
                result.errors.append(f"Model {model_name} not found in registry")
                return result
            
            if use_sahi:
                from app.utils.sahi_detector import SAHIDetector, SAHIConfig
                detector = SAHIDetector(
                    model,
                    SAHIConfig(enabled=True, tile_size=sahi_tile_size, overlap_ratio=sahi_overlap)
                )
            else:
                detector = model
            
            cap = cv2.VideoCapture(self.video_path)
            if not cap.isOpened():
                result.errors.append(f"Cannot open video: {self.video_path}")
                return result
            
            fps_vid = cap.get(cv2.CAP_PROP_FPS) or 30.0
            frame_idx = 0
            processed = 0
            inference_times: list[float] = []
            all_classes: set[str] = set()
            total_dets = 0
            
            proc = psutil.Process(os.getpid())
            peak_ram = 0.0
            peak_vram = 0.0
            
            wall_start = time.perf_counter()
            
            while processed < max_frames:
                ret, frame = cap.read()
                if not ret:
                    break
                
                if frame_idx % frame_skip != 0:
                    frame_idx += 1
                    continue
                
                ts_ms = (frame_idx / fps_vid) * 1000.0
                t0 = time.perf_counter()
                det_result = detector.detect(frame, frame_number=frame_idx, timestamp_ms=ts_ms,
                                             override_confidence=confidence)
                inf_ms = (time.perf_counter() - t0) * 1000
                
                inference_times.append(inf_ms)
                total_dets += len(det_result.detections)
                for d in det_result.detections:
                    all_classes.add(d.class_name)
                
                # Track RAM/VRAM
                ram_mb = proc.memory_info().rss / 1e6
                peak_ram = max(peak_ram, ram_mb)
                if torch.cuda.is_available():
                    vram_mb = torch.cuda.memory_allocated() / 1e6
                    peak_vram = max(peak_vram, vram_mb)
                
                processed += 1
                frame_idx += 1
            
            cap.release()
            wall_elapsed = time.perf_counter() - wall_start
            
            result.total_wall_seconds = wall_elapsed
            result.frames_processed = processed
            result.frames_per_second = processed / max(wall_elapsed, 0.001)
            result.total_detections = total_dets
            result.avg_detections_per_frame = total_dets / max(processed, 1)
            result.unique_classes = list(all_classes)
            result.person_count = sum(
                1 for c in all_classes if "person" in c.lower() or c in {"man", "woman", "child"}
            )
            result.avg_inference_ms = sum(inference_times) / max(len(inference_times), 1)
            result.peak_vram_mb = peak_vram
            result.peak_ram_mb = peak_ram
            
            logger.info(
                "[Benchmark] %s: %.1f fps | %.1f det/frame | %d classes | %.0f ms/frame",
                experiment_name, result.frames_per_second,
                result.avg_detections_per_frame, len(all_classes),
                result.avg_inference_ms
            )
        
        except Exception as exc:
            import traceback
            result.errors.append(str(exc))
            result.errors.append(traceback.format_exc()[:500])
            logger.error("[Benchmark] %s failed: %s", experiment_name, exc)
        
        self.results.append(result)
        return result

    def comparison_table(self) -> list[dict]:
        """Return list of row dicts for display in UI comparison table."""
        return [r.summary_table_row() for r in self.results]
