"""
Event types and rule definitions for Phase 6: Semantic Event Understanding.

Every event type in the system is defined here as an EventRule.
Adding a new event type requires adding one EventRule entry — no code changes.

Design principle:
    Start with interpretable, verifiable rules. Each rule answers:
    "What observable conditions must hold for this event to occur?"
    This makes debugging straightforward and provides a clear audit trail
    for the explainability layer.

    Rules can be extended to hybrid (rule + LLM) reasoning in Phase 9.
    The interface stays the same — the engine calls rule.evaluate().

Rule priority:
    When multiple rules match the same track, all matching events are
    generated. The ranking engine (Phase 10) resolves overlaps.

Research note:
    This rule set constitutes the domain knowledge base described in the
    project architecture. It is intentionally human-readable, not
    a learned classifier, so it can be directly cited in a methods section.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.engines.perception.motion_analyzer.analyzer import MotionProfile
    from app.engines.perception.tracker.track import Track

from app.engines.perception.motion_analyzer.analyzer import ApproachSignal, SpeedClass


# ---------------------------------------------------------------------------
# Known event type constants
# ---------------------------------------------------------------------------

class EventType:
    # Person motion
    PERSON_WALKING = "person_walking"
    PERSON_RUNNING = "person_running"
    PERSON_STANDING = "person_standing"
    PERSON_LOITERING = "person_loitering"

    # Person entry / exit
    PERSON_ENTERED_SCENE = "person_entered_scene"
    PERSON_LEFT_SCENE = "person_left_scene"

    # Vehicle
    VEHICLE_APPROACHING = "vehicle_approaching"
    VEHICLE_RECEDING = "vehicle_receding"
    VEHICLE_STATIONARY = "vehicle_stationary"

    # General object
    OBJECT_APPEARED = "object_appeared"
    OBJECT_DISAPPEARED = "object_disappeared"

    # Scene level
    SCENE_ACTIVITY = "scene_activity"


# Class name groupings (COCO-based)
PERSON_CLASSES: frozenset[str] = frozenset({"person"})
VEHICLE_CLASSES: frozenset[str] = frozenset({"car", "truck", "bus", "motorcycle", "bicycle"})


# ---------------------------------------------------------------------------
# EventRule
# ---------------------------------------------------------------------------

@dataclass
class EventRule:
    """
    A single declarative event rule.

    Conditions are evaluated against a (track, motion_profile) pair.
    If all conditions pass, the rule fires and an Event is generated.

    All condition fields default to None, which means "match any".
    Specify only the conditions relevant to this event type.
    """
    name: str
    event_type: str
    description: str

    # Class conditions
    class_names: frozenset[str] | None = None     # None = any class

    # Motion conditions
    speed_classes: frozenset[SpeedClass] | None = None
    require_stationary: bool | None = None        # True/False/None
    require_approach: bool = False
    require_recede: bool = False

    # Duration
    min_track_length_ms: float = 0.0              # track must last at least this long
    min_track_frames: int = 0                     # track must span at least N frames

    # Lifecycle conditions
    require_new_track: bool = False               # only fire on track creation
    require_ended_track: bool = False             # only fire when track ends

    # Confidence gate: don't fire below this motion_confidence
    min_motion_confidence: float = 0.0

    # Rule-intrinsic confidence [0.0, 1.0]
    # Reflects how reliable/specific this rule is as a prior.
    # Specific rules (person_running) score higher than general ones (object_appeared).
    # Used by Phase 7 Confidence Fusion as the "rule_confidence" dimension.
    rule_confidence: float = 0.75

    def evaluate(
        self,
        track: Track,
        profile: MotionProfile | None,
        context: dict,
    ) -> tuple[bool, float, dict]:
        """
        Evaluate this rule against a track.

        Args:
            track:   The Track object.
            profile: MotionProfile (may be None for tracks with < 2 observations).
            context: Extra context dict (e.g. {"is_new": True, "is_ended": True}).

        Returns:
            (matched, confidence, evidence)
            - matched:    True if all conditions are satisfied.
            - confidence: Event confidence [0.0, 1.0].
            - evidence:   Dict explaining which conditions fired (for explainability).
        """
        evidence: dict = {}

        # ── Class filter ──────────────────────────────────────────────────
        if self.class_names is not None:
            if track.class_name not in self.class_names:
                return False, 0.0, {}
            evidence["class_match"] = track.class_name

        # ── Lifecycle filters ─────────────────────────────────────────────
        if self.require_new_track and not context.get("is_new", False):
            return False, 0.0, {}
        if self.require_ended_track and not context.get("is_ended", False):
            return False, 0.0, {}

        # ── Track length ──────────────────────────────────────────────────
        if self.min_track_length_ms > 0:
            if track.track_length_ms < self.min_track_length_ms:
                return False, 0.0, {}
        if self.min_track_frames > 0:
            if track.total_frames_matched < self.min_track_frames:
                return False, 0.0, {}

        # ── Motion conditions — require profile ───────────────────────────
        if profile is None and (
            self.speed_classes is not None
            or self.require_stationary is not None
            or self.require_approach
            or self.require_recede
        ):
            return False, 0.0, {}

        if profile is not None:
            # Motion confidence gate
            if profile.motion_confidence < self.min_motion_confidence:
                return False, 0.0, {}

            # Speed class
            if self.speed_classes is not None:
                if profile.dominant_speed_class not in self.speed_classes:
                    return False, 0.0, {}
                evidence["speed_class"] = profile.dominant_speed_class.value

            # Stationary
            if self.require_stationary is not None:
                if profile.is_stationary != self.require_stationary:
                    return False, 0.0, {}
                evidence["is_stationary"] = profile.is_stationary

            # Approach / recede
            if self.require_approach and not profile.has_approach_phase:
                return False, 0.0, {}
            if self.require_recede and not profile.has_recede_phase:
                return False, 0.0, {}
            if self.require_approach:
                evidence["approach"] = True
            if self.require_recede:
                evidence["recede"] = True

        # ── All conditions passed ─────────────────────────────────────────
        confidence = self._compute_confidence(track, profile)
        evidence["rule"] = self.name
        evidence["track_id"] = track.track_id
        evidence["track_length_ms"] = track.track_length_ms

        return True, confidence, evidence

    def _compute_confidence(self, track: Track, profile: MotionProfile | None) -> float:
        """
        Event confidence = detection confidence × motion confidence × track stability.

        Short tracks, low-confidence detections, or erratic motion all reduce it.
        """
        det_conf = track.avg_confidence
        motion_conf = profile.motion_confidence if profile else 0.5

        # Track length bonus: long tracks are more credible
        length_bonus = min(track.total_frames_matched / 8.0, 1.0)

        confidence = (0.5 * det_conf + 0.3 * motion_conf + 0.2 * length_bonus)
        return round(min(1.0, max(0.0, confidence)), 4)


# ---------------------------------------------------------------------------
# The Knowledge Base — all event rules
# ---------------------------------------------------------------------------

KNOWLEDGE_BASE: list[EventRule] = [
    # ── Person motion ──────────────────────────────────────────────────────
    EventRule(
        name="rule_person_standing",
        event_type=EventType.PERSON_STANDING,
        description="Person track classified as stationary",
        class_names=PERSON_CLASSES,
        require_stationary=True,
        min_track_frames=2,
        min_motion_confidence=0.3,
        rule_confidence=0.80,  # fairly specific — stationary is well-defined
    ),
    EventRule(
        name="rule_person_walking",
        event_type=EventType.PERSON_WALKING,
        description="Person moving at walking speed",
        class_names=PERSON_CLASSES,
        speed_classes=frozenset({SpeedClass.SLOW, SpeedClass.WALKING}),
        min_track_frames=2,
        min_motion_confidence=0.3,
        rule_confidence=0.78,  # common — moderate confidence
    ),
    EventRule(
        name="rule_person_running",
        event_type=EventType.PERSON_RUNNING,
        description="Person moving at fast speed",
        class_names=PERSON_CLASSES,
        speed_classes=frozenset({SpeedClass.FAST}),
        min_track_frames=2,
        min_motion_confidence=0.3,
        rule_confidence=0.88,  # specific — fast speed is a strong signal
    ),
    EventRule(
        name="rule_person_loitering",
        event_type=EventType.PERSON_LOITERING,
        description="Person stationary for extended duration (>= 5 seconds)",
        class_names=PERSON_CLASSES,
        require_stationary=True,
        min_track_length_ms=5000.0,
        min_motion_confidence=0.3,
        rule_confidence=0.85,  # high — duration threshold makes this specific
    ),

    # ── Person entry / exit ────────────────────────────────────────────────
    EventRule(
        name="rule_person_entered",
        event_type=EventType.PERSON_ENTERED_SCENE,
        description="Person track first appears (new confirmed track)",
        class_names=PERSON_CLASSES,
        require_new_track=True,
        min_track_frames=1,
        rule_confidence=0.82,
    ),
    EventRule(
        name="rule_person_left",
        event_type=EventType.PERSON_LEFT_SCENE,
        description="Person track permanently closed (left scene)",
        class_names=PERSON_CLASSES,
        require_ended_track=True,
        min_track_frames=1,
        rule_confidence=0.80,
    ),

    # ── Vehicle events ─────────────────────────────────────────────────────
    EventRule(
        name="rule_vehicle_approaching",
        event_type=EventType.VEHICLE_APPROACHING,
        description="Vehicle bounding box growing (moving toward camera)",
        class_names=VEHICLE_CLASSES,
        require_approach=True,
        min_track_frames=2,
        min_motion_confidence=0.3,
        rule_confidence=0.83,  # bbox area growth is a reliable signal
    ),
    EventRule(
        name="rule_vehicle_receding",
        event_type=EventType.VEHICLE_RECEDING,
        description="Vehicle bounding box shrinking (moving away from camera)",
        class_names=VEHICLE_CLASSES,
        require_recede=True,
        min_track_frames=2,
        min_motion_confidence=0.3,
        rule_confidence=0.80,
    ),
    EventRule(
        name="rule_vehicle_stationary",
        event_type=EventType.VEHICLE_STATIONARY,
        description="Vehicle parked or stopped",
        class_names=VEHICLE_CLASSES,
        require_stationary=True,
        min_track_frames=2,
        min_motion_confidence=0.3,
        rule_confidence=0.78,
    ),

    # ── General object events ──────────────────────────────────────────────
    EventRule(
        name="rule_object_appeared",
        event_type=EventType.OBJECT_APPEARED,
        description="Any new confirmed object track appeared",
        require_new_track=True,
        min_track_frames=1,
        rule_confidence=0.65,  # general — any class, more noise
    ),
    EventRule(
        name="rule_object_disappeared",
        event_type=EventType.OBJECT_DISAPPEARED,
        description="Any confirmed object track ended",
        require_ended_track=True,
        min_track_frames=1,
        rule_confidence=0.65,
    ),
]
