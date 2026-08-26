"""
ROI / Virtual Boundary Manager — TCE Accuracy Overhaul v1.0.1.

Supports polygon zones and line boundaries for restricted-zone detection.
All coordinates are normalized [0.0, 1.0] relative to frame dimensions,
making ROIs resolution-independent.

How it works:
  1. The user defines one or more zones via the settings API (JSON config).
  2. Each zone is a named polygon with a type (RESTRICTED/SAFE/ENTRY/EXIT).
  3. For each tracked object, the ROIManager checks whether its bbox centroid
     has crossed a zone boundary since the last check.
  4. When a track transitions from OUTSIDE → INSIDE, a `restricted_zone_entry`
     event is emitted. INSIDE → OUTSIDE emits `restricted_zone_exit`.
  5. Events include the track ID, zone ID, crossing point, direction, and
     confidence, so the evidence chain is complete.

Why normalized coordinates?
  A zone drawn on a 1080p preview frame must work on the 720p exported frame
  and on any future resolution. Normalization decouples the zone geometry
  from the video resolution.

Design:
  - ROIManager is stateful per-job (not a singleton).
  - Each Track's zone membership state is maintained across frames.
  - Zone membership is checked per observation (per frame), not per second.
  - If a track has only one observation, zone entry is detected immediately.

Branch: experiment/v1.0.1-accuracy-overhaul
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------

class ZoneType(str, Enum):
    """Classification of an ROI zone."""
    RESTRICTED = "restricted"
    SAFE       = "safe"
    ENTRY      = "entry"
    EXIT       = "exit"
    MONITOR    = "monitor"   # Log crossings but do not flag as alert


@dataclass
class ROIZone:
    """
    A named polygon zone.

    Fields:
        zone_id:       Unique identifier string.
        name:          Human-readable label (e.g., "Server Room", "Safe Area").
        zone_type:     Classification of the zone.
        polygon:       List of (x, y) normalized [0.0, 1.0] vertices.
                       Minimum 3 points required (triangle).

    Example (JSON config):
        {
            "zone_id": "zone_1",
            "name": "Restricted Area",
            "zone_type": "restricted",
            "polygon": [[0.1, 0.1], [0.6, 0.1], [0.6, 0.9], [0.1, 0.9]]
        }
    """
    zone_id: str
    name: str
    zone_type: ZoneType
    polygon: list[tuple[float, float]]   # [(x1,y1), (x2,y2), ...]


@dataclass
class ZoneEvent:
    """
    A zone crossing event emitted by ROIManager.

    This maps directly to an Event in the pipeline:
        event_type = 'restricted_zone_entry' or 'restricted_zone_exit'
    """
    event_type: str      # 'restricted_zone_entry' | 'restricted_zone_exit' | 'zone_crossing'
    zone_id: str
    zone_name: str
    zone_type: ZoneType
    track_id: str
    frame_number: int
    timestamp_ms: float
    centroid_x: float    # Normalized x of track centroid at crossing
    centroid_y: float    # Normalized y of track centroid at crossing
    confidence: float    # Detection confidence of the triggering observation
    direction: str       # 'entering' | 'exiting'
    evidence: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# ROI Manager
# ---------------------------------------------------------------------------

class ROIManager:
    """
    Manages ROI zones and detects zone crossing events for tracked objects.

    Usage:
        mgr = ROIManager()
        mgr.load_zones(roi_zones_config)   # from context.settings["roi_zones"]
        ...
        for track in confirmed_tracks:
            for obs in track.observations:
                cx = (obs.bbox[0] + obs.bbox[2]) / 2.0   # normalized centroid x
                cy = (obs.bbox[1] + obs.bbox[3]) / 2.0   # normalized centroid y
                events = mgr.check_point(track.track_id, cx, cy,
                                         obs.frame_number, obs.timestamp_ms,
                                         obs.confidence)
                all_events.extend(events)
    """

    def __init__(self) -> None:
        self._zones: list[ROIZone] = []
        # Track membership state: {track_id: {zone_id: bool}}
        # True = track is currently INSIDE the zone
        self._membership: dict[str, dict[str, bool]] = {}

    def load_zones(self, zones_config: list[dict]) -> None:
        """
        Load zone definitions from a list of config dicts.

        Each dict should have: zone_id, name, zone_type, polygon.
        Zones with fewer than 3 polygon points are silently skipped.

        Args:
            zones_config: List of zone definition dicts (from settings API).
        """
        self._zones = []
        for cfg in zones_config:
            try:
                polygon = [tuple(p) for p in cfg.get("polygon", [])]
                if len(polygon) < 3:
                    logger.warning(
                        "[ROI] Zone '%s' has only %d points (need ≥3), skipping",
                        cfg.get("zone_id", "?"), len(polygon),
                    )
                    continue
                zone = ROIZone(
                    zone_id=cfg["zone_id"],
                    name=cfg.get("name", cfg["zone_id"]),
                    zone_type=ZoneType(cfg.get("zone_type", "restricted")),
                    polygon=polygon,
                )
                self._zones.append(zone)
                logger.info("[ROI] Loaded zone: %s (%s, %d pts)", zone.zone_id, zone.zone_type.value, len(polygon))
            except Exception as exc:
                logger.warning("[ROI] Could not load zone: %s — %s", cfg, exc)

        logger.info("[ROI] %d zone(s) loaded", len(self._zones))

    def check_point(
        self,
        track_id: str,
        cx: float,
        cy: float,
        frame_number: int,
        timestamp_ms: float,
        confidence: float = 1.0,
    ) -> list[ZoneEvent]:
        """
        Check whether a track centroid (cx, cy) has crossed any zone boundary.

        Compares the current zone membership to the previous state.
        Fires ZoneEvent when a transition (IN→OUT or OUT→IN) is detected.

        Args:
            track_id:     Unique track identifier string.
            cx, cy:       Normalized centroid coordinates [0.0, 1.0].
            frame_number: Current frame number.
            timestamp_ms: Current frame timestamp.
            confidence:   Detection confidence at this observation.

        Returns:
            List of ZoneEvent objects (usually 0 or 1, rarely >1).
        """
        if not self._zones:
            return []

        if track_id not in self._membership:
            self._membership[track_id] = {}

        events: list[ZoneEvent] = []

        for zone in self._zones:
            inside_now = self._point_in_polygon(cx, cy, zone.polygon)
            was_inside = self._membership[track_id].get(zone.zone_id, None)

            # First observation for this track/zone
            if was_inside is None:
                self._membership[track_id][zone.zone_id] = inside_now
                # Phase 4 fix: if first observation is inside, emit entry immediately.
                # Previous behaviour: silently recorded state, no event.
                # Bug found: 2026-08-26 during ROI validation (Exp-E).
                if inside_now:
                    if zone.zone_type == ZoneType.RESTRICTED:
                        event_type = "restricted_zone_entry"
                    elif zone.zone_type in (ZoneType.ENTRY, ZoneType.EXIT):
                        event_type = "zone_entry"
                    else:
                        event_type = "zone_crossing"
                    events.append(ZoneEvent(
                        event_type=event_type,
                        zone_id=zone.zone_id,
                        zone_name=zone.name,
                        zone_type=zone.zone_type,
                        track_id=track_id,
                        frame_number=frame_number,
                        timestamp_ms=timestamp_ms,
                        centroid_x=cx,
                        centroid_y=cy,
                        confidence=confidence,
                        direction="entering",
                        evidence={"cold_start": True},
                    ))
                continue

            # State change: crossing detected
            if inside_now != was_inside:
                direction = "entering" if inside_now else "exiting"

                # Map zone type + direction to event_type
                if zone.zone_type == ZoneType.RESTRICTED:
                    event_type = "restricted_zone_entry" if inside_now else "restricted_zone_exit"
                elif zone.zone_type == ZoneType.ENTRY:
                    event_type = "zone_entry" if inside_now else "zone_exit"
                elif zone.zone_type == ZoneType.EXIT:
                    event_type = "zone_exit" if inside_now else "zone_entry"
                else:
                    event_type = "zone_crossing"

                evt = ZoneEvent(
                    event_type=event_type,
                    zone_id=zone.zone_id,
                    zone_name=zone.name,
                    zone_type=zone.zone_type,
                    track_id=track_id,
                    frame_number=frame_number,
                    timestamp_ms=timestamp_ms,
                    centroid_x=round(cx, 4),
                    centroid_y=round(cy, 4),
                    confidence=round(confidence, 4),
                    direction=direction,
                    evidence={
                        "zone_id": zone.zone_id,
                        "zone_name": zone.name,
                        "zone_type": zone.zone_type.value,
                        "direction": direction,
                        "centroid": {"x": round(cx, 4), "y": round(cy, 4)},
                        "frame_number": frame_number,
                        "was_inside": was_inside,
                        "is_inside": inside_now,
                        "polygon_vertices": len(zone.polygon),
                    },
                )
                events.append(evt)
                logger.info(
                    "[ROI] Track %s %s zone '%s' at frame %d (%.4f,%.4f)",
                    track_id, direction, zone.name, frame_number, cx, cy,
                )

            self._membership[track_id][zone.zone_id] = inside_now

        return events

    def reset_track(self, track_id: str) -> None:
        """Remove a track's zone state (call when track ends)."""
        self._membership.pop(track_id, None)

    def get_zone_membership(self, track_id: str) -> dict[str, bool]:
        """Return current zone membership for a track ({zone_id: inside})."""
        return dict(self._membership.get(track_id, {}))

    # ---------------------------------------------------------------------------
    # Geometry
    # ---------------------------------------------------------------------------

    @staticmethod
    def _point_in_polygon(x: float, y: float, polygon: list[tuple[float, float]]) -> bool:
        """
        Ray-casting algorithm for point-in-polygon test.

        Casts a horizontal ray from (x, y) to the right and counts how many
        edges of the polygon it crosses. Odd = inside, even = outside.

        Works for any simple (non-self-intersecting) polygon.
        Handles edge cases: point on edge is treated as inside.

        Args:
            x, y:    Normalized point coordinates [0.0, 1.0].
            polygon: List of (px, py) vertices.

        Returns:
            True if point is inside or on the boundary of the polygon.
        """
        n = len(polygon)
        inside = False
        j = n - 1
        for i in range(n):
            xi, yi = polygon[i]
            xj, yj = polygon[j]
            if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi):
                inside = not inside
            j = i
        return inside

    @staticmethod
    def centroid_from_bbox(bbox_normalized: list[float]) -> tuple[float, float]:
        """
        Compute normalized centroid from a normalized bounding box.

        Args:
            bbox_normalized: [x1, y1, x2, y2] in [0, 1] coordinates.

        Returns:
            (cx, cy) centroid tuple.
        """
        x1, y1, x2, y2 = bbox_normalized
        return (x1 + x2) / 2.0, (y1 + y2) / 2.0

    def load_zones_from_defaults(self) -> None:
        """
        Load a default 'full-frame restricted zone' for testing when no config is provided.
        Should NOT be used in production — only for unit test convenience.
        """
        self._zones = [
            ROIZone(
                zone_id="default_zone",
                name="Default Restricted Zone",
                zone_type=ZoneType.RESTRICTED,
                polygon=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
            )
        ]
