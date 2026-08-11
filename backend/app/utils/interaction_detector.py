"""
Person-Object Interaction Detector — Pass 6 of Event Understanding.

Detects high-level semantic interactions between person tracks and object tracks:
  - person_picked_up_object:    Person bbox overlaps object, object track ends
  - person_put_down_object:     Object track appears near person's last position
  - person_using_phone:         Person near phone/smartphone for 3+ frames
  - person_using_laptop:        Person near laptop for 3+ frames
  - person_drinking:            Person near bottle/cup/mug for 2+ frames
  - person_reading:             Person near book for 3+ frames
  - person_pocketed_object:     Small object (wallet, phone) disappears at hip level
  - person_at_desk:             Person near desk/table + stationary 4+ frames
  - person_opened_cabinet:      Cabinet track area changes while person nearby
  - person_near_screen:         Person facing TV/monitor for extended time

All detections use spatial proximity (bbox IoU + centroid distance) and
temporal co-occurrence — no additional ML inference required.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from app.utils.track import Track


@dataclass
class InteractionEvent:
    """A detected person-object interaction."""
    event_id: str
    event_type: str
    track_id: int           # person track
    object_class: str       # object involved
    object_track_id: int    # object track
    confidence: float
    start_ms: float
    end_ms: float
    start_frame: int
    end_frame: int
    evidence: dict = field(default_factory=dict)

    @property
    def duration_ms(self) -> float:
        return self.end_ms - self.start_ms


# ── Spatial helpers ──────────────────────────────────────────────────────────

def _bbox_iou(b1, b2) -> float:
    """IoU between two bboxes (each has x1,y1,x2,y2 in normalised [0,1] coords)."""
    x1 = max(b1.x1, b2.x1); y1 = max(b1.y1, b2.y1)
    x2 = min(b1.x2, b2.x2); y2 = min(b1.y2, b2.y2)
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    if inter == 0:
        return 0.0
    a1 = (b1.x2 - b1.x1) * (b1.y2 - b1.y1)
    a2 = (b2.x2 - b2.x1) * (b2.y2 - b2.y1)
    return inter / max(a1 + a2 - inter, 1e-9)


def _centroid_dist(b1, b2) -> float:
    """Euclidean distance between bbox centroids (normalised)."""
    cx1, cy1 = (b1.x1 + b1.x2) / 2, (b1.y1 + b1.y2) / 2
    cx2, cy2 = (b2.x1 + b2.x2) / 2, (b2.y1 + b2.y2) / 2
    return ((cx1 - cx2) ** 2 + (cy1 - cy2) ** 2) ** 0.5


def _get_obs_at_frame(track: "Track", frame: int):
    """Return the observation closest to the given frame number."""
    best, best_dist = None, float("inf")
    for o in track.observations:
        d = abs(o.frame_number - frame)
        if d < best_dist:
            best, best_dist = o, d
    return best if best_dist <= 10 else None  # within 10 frames


def _overlapping_frames(t1: "Track", t2: "Track") -> list[int]:
    """Sorted list of frame numbers where both tracks are active."""
    s1 = {o.frame_number for o in t1.observations}
    s2 = {o.frame_number for o in t2.observations}
    return sorted(s1 & s2)


def _close_frames(person_track: "Track", obj_track: "Track",
                  max_dist: float = 0.25, min_iou: float = 0.0) -> list[int]:
    """
    Returns frame numbers where person and object are spatially close.
    'Close' means centroid distance < max_dist OR iou > min_iou.
    """
    shared = _overlapping_frames(person_track, obj_track)
    close = []
    for fn in shared:
        po = _get_obs_at_frame(person_track, fn)
        oo = _get_obs_at_frame(obj_track, fn)
        if po is None or oo is None:
            continue
        dist = _centroid_dist(po.bbox, oo.bbox)
        iou = _bbox_iou(po.bbox, oo.bbox)
        if dist < max_dist or iou > min_iou:
            close.append(fn)
    return close


# ── Interaction vocabulary ────────────────────────────────────────────────────

# Objects where "person nearby for N frames" = meaningful interaction
_PHONE_CLASSES = frozenset({
    "phone", "smartphone", "mobile_phone", "cell_phone", "iphone",
})
_LAPTOP_CLASSES = frozenset({
    "laptop", "notebook_computer", "notebook",
})
_DRINK_CLASSES = frozenset({
    "bottle", "water_bottle", "cup", "mug", "coffee_mug", "tea_cup",
    "wine_glass", "glass", "can",
})
_BOOK_CLASSES = frozenset({
    "book", "notebook", "document", "magazine",
})
_SCREEN_CLASSES = frozenset({
    "tv", "television", "monitor", "screen", "projector",
})
_DESK_CLASSES = frozenset({
    "desk", "table", "dining_table", "coffee_table", "workbench",
})
_CABINET_CLASSES = frozenset({
    "cabinet", "wardrobe", "closet", "drawer", "shelf", "bookshelf",
    "refrigerator",
})
_SMALL_POCKET_CLASSES = frozenset({
    "wallet", "phone", "smartphone", "mobile_phone", "remote_control",
    "remote", "pen", "pencil", "keys", "key", "glasses",
})
_PICK_UP_CLASSES = frozenset({
    "bottle", "cup", "mug", "coffee_mug", "book", "remote_control",
    "remote", "phone", "smartphone", "wallet", "glasses", "backpack",
    "handbag", "briefcase", "laptop", "box", "package",
})

# Background fixtures — never fire pickup/interaction for these
_BACKGROUND_CLASSES = frozenset({
    "chair", "office_chair", "sofa", "couch", "bed", "desk", "table",
    "dining_table", "shelf", "bookshelf", "cabinet", "wardrobe", "bench",
    "curtain", "window", "door", "wall", "floor", "ceiling",
    "air_conditioner", "ceiling_fan", "carpet", "rug",
})


# ── Main detector ─────────────────────────────────────────────────────────────

class InteractionDetector:
    """
    Detects person-object interactions from confirmed tracks.

    Usage:
        detector = InteractionDetector(fps=30.0, frame_skip=5)
        events = detector.detect(person_tracks, all_tracks)
    """

    def __init__(self, fps: float = 30.0, frame_skip: int = 5):
        # At frame_skip=5, each observation = 1 extracted frame = 5 real frames
        self.fps = fps
        self.frame_skip = frame_skip
        # At extracted fps, N close_frames = N * frame_skip / fps seconds
        self._real_fps = fps / frame_skip  # extracted frame rate

    def _ms(self, frame: int) -> float:
        return frame / self.fps * 1000.0

    def detect(
        self,
        person_tracks: list["Track"],
        all_tracks: list["Track"],
    ) -> list[InteractionEvent]:
        events: list[InteractionEvent] = []

        for p_track in person_tracks:
            if len(p_track.observations) < 2:
                continue
            for obj_track in all_tracks:
                if obj_track.track_id == p_track.track_id:
                    continue
                obj_cls = (obj_track.class_name or "").lower()
                if obj_cls in _BACKGROUND_CLASSES:
                    continue
                if not obj_track.observations:
                    continue

                # Detect specific interaction types
                evts = self._check_interaction(p_track, obj_track, obj_cls)
                events.extend(evts)

        # Remove duplicate interactions (same type + same object class within 3s)
        events = self._dedup(events)
        return events

    def _check_interaction(
        self,
        p_track: "Track",
        obj_track: "Track",
        obj_cls: str,
    ) -> list[InteractionEvent]:
        results: list[InteractionEvent] = []

        close = _close_frames(p_track, obj_track, max_dist=0.30)
        if not close:
            return []

        duration_close_s = len(close) * self.frame_skip / self.fps

        # ── Phone usage ──────────────────────────────────────────────────────
        if obj_cls in _PHONE_CLASSES and duration_close_s >= 1.0:
            results.append(self._make_event(
                event_type="person_using_phone",
                p_track=p_track, obj_track=obj_track, obj_cls=obj_cls,
                close_frames=close,
                confidence=min(0.85, 0.6 + duration_close_s * 0.05),
                evidence={"duration_s": round(duration_close_s, 1), "close_frames": len(close)},
            ))

        # ── Laptop usage ─────────────────────────────────────────────────────
        elif obj_cls in _LAPTOP_CLASSES and duration_close_s >= 2.0:
            results.append(self._make_event(
                event_type="person_using_laptop",
                p_track=p_track, obj_track=obj_track, obj_cls=obj_cls,
                close_frames=close,
                confidence=min(0.88, 0.65 + duration_close_s * 0.03),
                evidence={"duration_s": round(duration_close_s, 1)},
            ))

        # ── Drinking ────────────────────────────────────────────────
        # Threshold: 1.5s min (was 0.5s) — prevents false positives when
        # person walks past a table with bottles on it.
        elif obj_cls in _DRINK_CLASSES and duration_close_s >= 1.5:
            results.append(self._make_event(
                event_type="person_drinking",
                p_track=p_track, obj_track=obj_track, obj_cls=obj_cls,
                close_frames=close,
                confidence=min(0.80, 0.55 + duration_close_s * 0.07),
                evidence={"object": obj_cls, "duration_s": round(duration_close_s, 1)},
            ))

        # ── Reading ──────────────────────────────────────────────────────────
        elif obj_cls in _BOOK_CLASSES and duration_close_s >= 1.5:
            results.append(self._make_event(
                event_type="person_reading",
                p_track=p_track, obj_track=obj_track, obj_cls=obj_cls,
                close_frames=close,
                confidence=min(0.82, 0.60 + duration_close_s * 0.04),
                evidence={"object": obj_cls, "duration_s": round(duration_close_s, 1)},
            ))

        # ── Screen watching ──────────────────────────────────────────────
        # Threshold: 8s min (was 3s) — in offices, persons are always
        # near their monitor; only flag extended intentional screen use.
        elif obj_cls in _SCREEN_CLASSES and duration_close_s >= 8.0:
            results.append(self._make_event(
                event_type="person_watching_screen",
                p_track=p_track, obj_track=obj_track, obj_cls=obj_cls,
                close_frames=close,
                confidence=min(0.78, 0.55 + duration_close_s * 0.02),
                evidence={"screen": obj_cls, "duration_s": round(duration_close_s, 1)},
            ))

        # ── Pick up object ───────────────────────────────────────────────────
        # Object track ENDS while person is nearby — person picked it up
        elif obj_cls in _PICK_UP_CLASSES:
            p_end = max(o.frame_number for o in p_track.observations)
            obj_end = max(o.frame_number for o in obj_track.observations)
            obj_start = min(o.frame_number for o in obj_track.observations)
            p_start = min(o.frame_number for o in p_track.observations)

            # Object ends at least 5 frames before person, person was nearby
            if (obj_end < p_end - 5 and len(close) >= 2
                    and close[-1] >= obj_end - 5):
                # Check if object appeared during the video (not always present)
                obj_duration_s = (obj_end - obj_start) * self.frame_skip / self.fps
                confidence = 0.72 if len(close) >= 4 else 0.60
                results.append(self._make_event(
                    event_type=f"person_picked_up_{obj_cls}",
                    p_track=p_track, obj_track=obj_track, obj_cls=obj_cls,
                    close_frames=close,
                    confidence=confidence,
                    evidence={
                        "object": obj_cls,
                        "obj_disappeared_frame": obj_end,
                        "close_frames": len(close),
                    },
                ))

            # Object appears AFTER person nearby — person put it down
            elif (obj_start > p_start + 10 and len(close) >= 2
                    and close[0] >= obj_start - 5):
                results.append(self._make_event(
                    event_type=f"person_placed_{obj_cls}",
                    p_track=p_track, obj_track=obj_track, obj_cls=obj_cls,
                    close_frames=close,
                    confidence=0.65,
                    evidence={"object": obj_cls, "obj_appeared_frame": obj_start},
                ))

        # ── Pocket interaction ────────────────────────────────────────────────
        # Small object disappears at hip level (y > 0.5 = bottom half)
        elif obj_cls in _SMALL_POCKET_CLASSES:
            obj_end_obs = max(obj_track.observations, key=lambda o: o.frame_number)
            obj_end_y = (obj_end_obs.bbox.y1 + obj_end_obs.bbox.y2) / 2

            if obj_end_y > 0.45 and len(close) >= 2:  # disappeared in lower half
                results.append(self._make_event(
                    event_type="person_pocketed_object",
                    p_track=p_track, obj_track=obj_track, obj_cls=obj_cls,
                    close_frames=close,
                    confidence=0.68,
                    evidence={
                        "object": obj_cls,
                        "disappeared_at_y": round(obj_end_y, 2),
                        "hint": "object disappeared at hip level",
                    },
                ))

        return results

    def _make_event(
        self,
        event_type: str,
        p_track: "Track",
        obj_track: "Track",
        obj_cls: str,
        close_frames: list[int],
        confidence: float,
        evidence: dict,
    ) -> InteractionEvent:
        start_frame = close_frames[0] if close_frames else p_track.observations[0].frame_number
        end_frame = close_frames[-1] if close_frames else p_track.observations[-1].frame_number
        return InteractionEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            track_id=p_track.track_id,
            object_class=obj_cls,
            object_track_id=obj_track.track_id,
            confidence=round(confidence, 4),
            start_ms=self._ms(start_frame),
            end_ms=self._ms(end_frame),
            start_frame=start_frame,
            end_frame=end_frame,
            evidence=evidence,
        )


    def detect_scene_events(
        self,
        all_tracks: list["Track"],
        person_tracks: list["Track"],
        video_fps: float = 30.0,
    ) -> list[InteractionEvent]:
        """
        Detect scene-level security events that don't require a person-object pair.

        1. unattended_bag    — bag/backpack/suitcase visible for 10+s with no person nearby
        2. group_gathering   — 3+ person tracks within 0.20 normalised distance simultaneously
        3. person_fallen     — person bbox becomes horizontal (width >> height) and stops moving
        4. person_carrying   — person track and movable object track move together for 3s+
        """
        results: list[InteractionEvent] = []
        _BAG_CLASSES = frozenset({
            "backpack", "handbag", "suitcase", "bag", "luggage",
            "briefcase", "duffel_bag", "tote_bag",
        })
        _CARRY_CLASSES = frozenset({
            "backpack", "handbag", "suitcase", "bag", "briefcase",
            "bottle", "box", "package", "laptop", "book",
        })

        # ── 1. Unattended bag ──────────────────────────────────────────────────
        bag_tracks = [t for t in all_tracks
                      if (t.class_name or "").lower() in _BAG_CLASSES
                      and len(t.observations) >= 3]
        for bag in bag_tracks:
            bag_start  = min(o.frame_number for o in bag.observations)
            bag_end    = max(o.frame_number for o in bag.observations)
            bag_dur_s  = (bag_end - bag_start) * self.frame_skip / self.fps

            if bag_dur_s < 10.0:   # only if visible for 10+ seconds
                continue

            # Check if any person is close during the bag's full visible span
            has_owner = False
            for p in person_tracks:
                close = _close_frames(p, bag, max_dist=0.30)
                if len(close) >= 2:
                    has_owner = True
                    break

            if not has_owner:
                # Bag in scene with nobody nearby — flag it
                mid_obs = bag.observations[len(bag.observations) // 2]
                results.append(InteractionEvent(
                    event_id=str(uuid.uuid4()),
                    event_type="unattended_bag",
                    track_id=-1,
                    object_class=bag.class_name or "bag",
                    object_track_id=bag.track_id,
                    confidence=min(0.88, 0.65 + bag_dur_s * 0.01),
                    start_ms=bag_start / self.fps * 1000,
                    end_ms=bag_end / self.fps * 1000,
                    start_frame=bag_start,
                    end_frame=bag_end,
                    evidence={
                        "duration_s": round(bag_dur_s, 1),
                        "object": bag.class_name,
                        "hint": "bag visible with no person nearby for 10+ seconds",
                    },
                ))

        # ── 2. Group gathering ────────────────────────────────────────────────
        if len(person_tracks) >= 3:
            # Find frame ranges where 3+ persons are simultaneously close
            # Sample every 10 frames for efficiency
            all_frames: set[int] = set()
            for t in person_tracks:
                for o in t.observations:
                    all_frames.add(o.frame_number)
            sample_frames = sorted(all_frames)[::10]

            gathering_frames: list[int] = []
            for fn in sample_frames:
                close_count = 0
                obs_at_fn = []
                for t in person_tracks:
                    o = _get_obs_at_frame(t, fn)
                    if o is not None:
                        obs_at_fn.append(o)
                # Count pairs within 0.25 distance
                for i in range(len(obs_at_fn)):
                    for j in range(i+1, len(obs_at_fn)):
                        cx1 = (obs_at_fn[i].bbox.x1 + obs_at_fn[i].bbox.x2) / 2
                        cy1 = (obs_at_fn[i].bbox.y1 + obs_at_fn[i].bbox.y2) / 2
                        cx2 = (obs_at_fn[j].bbox.x1 + obs_at_fn[j].bbox.x2) / 2
                        cy2 = (obs_at_fn[j].bbox.y1 + obs_at_fn[j].bbox.y2) / 2
                        dist = ((cx1-cx2)**2 + (cy1-cy2)**2) ** 0.5
                        if dist < 0.25:
                            close_count += 1
                # Need at least 3 persons within range = at least 3 pairs
                if close_count >= 3 and len(obs_at_fn) >= 3:
                    gathering_frames.append(fn)

            if len(gathering_frames) >= 3:
                results.append(InteractionEvent(
                    event_id=str(uuid.uuid4()),
                    event_type="group_gathering",
                    track_id=-1,
                    object_class="group",
                    object_track_id=-1,
                    confidence=0.80,
                    start_ms=gathering_frames[0] / self.fps * 1000,
                    end_ms=gathering_frames[-1] / self.fps * 1000,
                    start_frame=gathering_frames[0],
                    end_frame=gathering_frames[-1],
                    evidence={
                        "person_count": len(person_tracks),
                        "gathering_frames": len(gathering_frames),
                        "hint": f"{len(person_tracks)} people gathered in close proximity",
                    },
                ))

        # ── 3. Person fallen ──────────────────────────────────────────────────
        for p in person_tracks:
            if len(p.observations) < 5:
                continue
            fallen_frames: list[int] = []
            for obs in p.observations:
                bbox_w = obs.bbox.x2 - obs.bbox.x1
                bbox_h = obs.bbox.y2 - obs.bbox.y1
                if bbox_h < 1e-6:
                    continue
                aspect = bbox_w / bbox_h
                # Fallen person: width > height (aspect > 1.0), especially > 1.5
                if aspect > 1.2:
                    fallen_frames.append(obs.frame_number)

            if len(fallen_frames) >= 5:   # sustained 5+ frames in horizontal position
                # Also check motion is minimal (fallen = not moving)
                xs = [(o.bbox.x1 + o.bbox.x2) / 2 for o in p.observations
                      if o.frame_number in set(fallen_frames)]
                ys = [(o.bbox.y1 + o.bbox.y2) / 2 for o in p.observations
                      if o.frame_number in set(fallen_frames)]
                motion = (max(xs, default=0) - min(xs, default=0)) +                          (max(ys, default=0) - min(ys, default=0))
                if motion < 0.15:  # barely moving = likely fallen
                    results.append(InteractionEvent(
                        event_id=str(uuid.uuid4()),
                        event_type="person_fallen",
                        track_id=p.track_id,
                        object_class="person",
                        object_track_id=p.track_id,
                        confidence=min(0.82, 0.55 + len(fallen_frames) * 0.03),
                        start_ms=fallen_frames[0] / self.fps * 1000,
                        end_ms=fallen_frames[-1] / self.fps * 1000,
                        start_frame=fallen_frames[0],
                        end_frame=fallen_frames[-1],
                        evidence={
                            "fallen_frames": len(fallen_frames),
                            "motion_score": round(motion, 3),
                            "hint": "person in horizontal position with minimal motion",
                        },
                    ))

        # ── 4. Person carrying ────────────────────────────────────────────────
        for p in person_tracks:
            for obj_track in all_tracks:
                if obj_track.track_id == p.track_id:
                    continue
                if (obj_track.class_name or "").lower() not in _CARRY_CLASSES:
                    continue
                if len(obj_track.observations) < 3:
                    continue

                # "Carrying" = object moves WITH person (same velocity direction)
                close = _close_frames(p, obj_track, max_dist=0.20)
                if len(close) < 5:  # must be close for 5+ frames
                    continue

                # Both must be moving (not just sitting at a desk)
                p_obs_close = [o for o in p.observations if o.frame_number in set(close)]
                if len(p_obs_close) < 2:
                    continue
                p_motion = abs(p_obs_close[-1].bbox.x1 - p_obs_close[0].bbox.x1) +                            abs(p_obs_close[-1].bbox.y1 - p_obs_close[0].bbox.y1)
                if p_motion < 0.05:  # person must actually move
                    continue

                dur_s = len(close) * self.frame_skip / self.fps
                results.append(InteractionEvent(
                    event_id=str(uuid.uuid4()),
                    event_type="person_carrying",
                    track_id=p.track_id,
                    object_class=obj_track.class_name or "object",
                    object_track_id=obj_track.track_id,
                    confidence=min(0.78, 0.60 + dur_s * 0.02),
                    start_ms=close[0] / self.fps * 1000,
                    end_ms=close[-1] / self.fps * 1000,
                    start_frame=close[0],
                    end_frame=close[-1],
                    evidence={
                        "object": obj_track.class_name,
                        "duration_s": round(dur_s, 1),
                        "motion_score": round(p_motion, 3),
                    },
                ))

        return self._dedup(results)

    def _dedup(self, events: list[InteractionEvent]) -> list[InteractionEvent]:
        """Remove duplicate interactions of the same type within 3 seconds."""
        seen: dict[str, float] = {}  # event_type -> last_start_ms
        out = []
        for e in sorted(events, key=lambda x: x.start_ms):
            key = f"{e.event_type}_{e.track_id}"
            last = seen.get(key, -99999)
            if e.start_ms - last > 3000:
                out.append(e)
                seen[key] = e.start_ms
        return out
