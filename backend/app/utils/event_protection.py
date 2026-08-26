"""
Event Protection Guard — Time Compression Engine v1.0.1.

Provides a named interface for the pipeline to trigger PROTECTED mode
in AdaptiveSkipAnalyzer from external signals that cannot be detected
by MOG2 motion scoring alone.

External signals that should trigger protection:
  - ROI proximity: a tracked person is near a configured restricted zone
  - Track count change: a new track appears (new person entered scene)
  - Brightness spike: sudden illumination change (lights on/off, flash)
  - Confidence drop: an existing track suddenly loses confidence

Usage in S02 (during frame selection):
    guard = EventProtectionGuard(analyzer)
    # For each frame during adaptive skip pass:
    guard.check_and_protect(
        frame_idx=i,
        motion_score=score,
        roi_proximity=False,
        track_count_changed=False,
        brightness_change=False,
    )

Status: IMPLEMENTED.
        NOT YET VALIDATED on real footage — protection trigger accuracy
        depends on upstream signals that require real tracking data.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.utils.adaptive_skip import AdaptiveSkipAnalyzer, MotionScore

logger = logging.getLogger(__name__)


class EventProtectionGuard:
    """
    Wraps AdaptiveSkipAnalyzer to trigger protection from external signals.

    This is a thin coordination layer. The actual protection countdown
    and skip-rate override live in AdaptiveSkipAnalyzer.
    """

    def __init__(self, analyzer: "AdaptiveSkipAnalyzer") -> None:
        self._analyzer = analyzer
        self._triggers: list[dict] = []   # audit trail of protection triggers

    def check_and_protect(
        self,
        frame_idx: int,
        motion_score: "MotionScore",
        *,
        roi_proximity: bool = False,
        track_count_changed: bool = False,
        brightness_change: bool = False,
    ) -> bool:
        """
        Evaluate external signals and trigger protection if needed.

        Args:
            frame_idx:            current frame index
            motion_score:         MotionScore already computed for this frame
            roi_proximity:        True if a tracked person is near a ROI boundary
            track_count_changed:  True if the number of confirmed tracks changed
            brightness_change:    True if a sudden brightness shift was detected

        Returns:
            True if protection was triggered by an external signal this frame.
            (Note: protection may also be active from motion threshold or
             from a previous trigger — check analyzer.is_protected separately.)
        """
        triggered = False

        if roi_proximity:
            self._analyzer.trigger_protection("roi_proximity")
            self._triggers.append({"frame": frame_idx, "reason": "roi_proximity"})
            logger.debug("[EventProtection] Frame %d: roi_proximity triggered protection", frame_idx)
            triggered = True

        if track_count_changed:
            self._analyzer.trigger_protection("new_track_appeared")
            self._triggers.append({"frame": frame_idx, "reason": "new_track_appeared"})
            logger.debug("[EventProtection] Frame %d: track_count_changed triggered protection", frame_idx)
            triggered = True

        if brightness_change:
            self._analyzer.trigger_protection("brightness_spike")
            self._triggers.append({"frame": frame_idx, "reason": "brightness_spike"})
            logger.debug("[EventProtection] Frame %d: brightness_change triggered protection", frame_idx)
            triggered = True

        return triggered

    @property
    def is_protected(self) -> bool:
        """True if the analyzer is currently in PROTECTED mode."""
        return self._analyzer.is_protected

    @property
    def trigger_log(self) -> list[dict]:
        """Audit trail of all external protection triggers."""
        return list(self._triggers)

    @property
    def stats(self) -> dict:
        """Summary statistics for diagnostics."""
        reasons: dict[str, int] = {}
        for t in self._triggers:
            r = t.get("reason", "unknown")
            reasons[r] = reasons.get(r, 0) + 1
        return {
            "external_triggers_total": len(self._triggers),
            "triggers_by_reason": reasons,
            "protection_currently_active": self.is_protected,
        }
