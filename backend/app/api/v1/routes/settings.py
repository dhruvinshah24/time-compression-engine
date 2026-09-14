"""Settings route — returns TCE pipeline configuration as informational settings.

These are READ-ONLY in v1.1. They describe the current TCE_V1_REFERENCE configuration.
PUT /settings/{key} is accepted but does not modify production algorithms.
"""
from fastapi import APIRouter, Body

router = APIRouter()

# TCE v1.0.1 reference configuration — read from TCE_V1_REFERENCE constants
# These match the frozen production configuration validated in Phase 6E.14.
_TCE_SETTINGS = [
    {
        "key": "detection_model",
        "value": "yolo11x",
        "display_name": "Detection Model",
        "description": "YOLO model used for object and person detection. yolo11x is the most accurate model in the YOLO11 family.",
        "category": "Detection",
        "readonly": True,
        "unit": None,
    },
    {
        "key": "pose_model",
        "value": "yolo11x-pose",
        "display_name": "Pose Model",
        "description": "Model used for human pose estimation (17 keypoints). Used for gesture, posture, and action classification.",
        "category": "Detection",
        "readonly": True,
        "unit": None,
    },
    {
        "key": "detection_confidence_threshold",
        "value": "0.25",
        "display_name": "Detection Confidence Threshold",
        "description": "Minimum YOLO detection confidence to retain a bounding box. Boxes below this are discarded before tracking.",
        "category": "Detection",
        "readonly": True,
        "unit": "float (0–1)",
    },
    {
        "key": "track_confirmation_frames",
        "value": "3",
        "display_name": "Track Confirmation Frames",
        "description": "Number of consecutive frames an object must appear in before its track is confirmed. Prevents false tracks from single-frame detections.",
        "category": "Tracking",
        "readonly": True,
        "unit": "frames",
    },
    {
        "key": "track_max_lost_frames",
        "value": "30",
        "display_name": "Track Max Lost Frames",
        "description": "Maximum number of frames a track can be missing before it is terminated. Higher values handle occlusion better.",
        "category": "Tracking",
        "readonly": True,
        "unit": "frames",
    },
    {
        "key": "frame_skip",
        "value": "adaptive",
        "display_name": "Frame Skip Strategy",
        "description": "Adaptive frame sampling based on scene motion. High-motion scenes sample more frames; static scenes skip more. Validated at 5.03× real-time on RTX 5050.",
        "category": "Performance",
        "readonly": True,
        "unit": None,
    },
    {
        "key": "compression_ratio_target",
        "value": "0.40",
        "display_name": "Compression Ratio Target",
        "description": "Target fraction of original footage to retain after compression. 0.40 means 40% of original duration is kept. Actual result depends on event density.",
        "category": "Compression",
        "readonly": True,
        "unit": "float (0–1)",
    },
    {
        "key": "min_event_confidence",
        "value": "0.60",
        "display_name": "Minimum Event Confidence",
        "description": "Minimum fused confidence for an event to be included in the output. Events below this threshold are filtered before export.",
        "category": "Events",
        "readonly": True,
        "unit": "float (0–1)",
    },
    {
        "key": "enable_scene_stair_guard",
        "value": "False",
        "display_name": "Scene Stair Guard",
        "description": "When enabled, suppresses false person detections on staircase regions. Validated: 8/8 stair false positives suppressed in Phase 6E.13. Disabled by default (conservative setting).",
        "category": "Events",
        "readonly": True,
        "unit": "boolean",
    },
    {
        "key": "story_min_segment_events",
        "value": "2",
        "display_name": "Story Min Segment Events",
        "description": "Minimum number of events required to form a story segment. Single-event detections are not elevated to story status.",
        "category": "Story",
        "readonly": True,
        "unit": "integer",
    },
    {
        "key": "roi_detection_enabled",
        "value": "True",
        "display_name": "ROI Zone Detection",
        "description": "Automatic region-of-interest detection. Identifies high-activity zones in the scene and weights events in those zones more heavily.",
        "category": "Detection",
        "readonly": True,
        "unit": "boolean",
    },
    {
        "key": "low_light_preprocessing",
        "value": "True",
        "display_name": "Low-Light Preprocessing",
        "description": "CLAHE-based preprocessing for low-light frames. Applied automatically when scene brightness falls below threshold. No effect on normal-light footage.",
        "category": "Quality",
        "readonly": True,
        "unit": "boolean",
    },
    {
        "key": "pipeline_version",
        "value": "1.0.1",
        "display_name": "Pipeline Version",
        "description": "Frozen TCE_V1_REFERENCE version. Validated in Phase 6E.14 on 595.23s benchmark: 0 CRITICAL failures, 0 MAJOR failures, RTF 0.199.",
        "category": "System",
        "readonly": True,
        "unit": None,
    },
    {
        "key": "validated_rtf",
        "value": "0.199",
        "display_name": "Validated Real-Time Factor",
        "description": "Empirically measured RTF on RTX 5050 Laptop GPU during Phase 6E.14 595s benchmark. RTF < 1.0 means faster than real-time. 0.199 = 5.03× real-time.",
        "category": "System",
        "readonly": True,
        "unit": "ratio",
    },
]


@router.get("/")
async def get_settings():
    return _TCE_SETTINGS


@router.put("/{key}")
async def update_setting(key: str, body: dict = Body(default={})):
    """
    Settings are read-only in v1.1.
    Returns the current value without modification.
    """
    match = next((s for s in _TCE_SETTINGS if s["key"] == key), None)
    if not match:
        return {"key": key, "updated": False, "error": f"Unknown setting: {key}"}
    return {
        "key": key,
        "updated": False,
        "current_value": match["value"],
        "message": "Settings are read-only in v1.1. Modify TCE_V1_REFERENCE to change production behavior.",
    }
