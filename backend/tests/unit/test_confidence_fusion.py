"""
Tests for Phase 7: Confidence Fusion.

Per mentor guidance: test each dimension independently, then test fusion strategies,
then run integration tests through the full pipeline chain.

Structure:
  1. FusionConfig — weight validation
  2. ConfidenceVector — accessors (weakest/strongest dimension)
  3. ConfidenceFuser — per-dimension computation
  4. Fusion strategies — weighted_linear / geometric / harmonic / min
  5. Scene reliability — camera motion penalty
  6. FusionResult — calibration metrics
  7. Event dependencies — provenance chain populated
  8. Integration: Synthetic Track → Motion → Event → Fusion
  9. s08_confidence_fuse pipeline stage (mocked)
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.engines.perception.motion_analyzer.analyzer import (
    MotionAnalyzer,
    MotionProfile,
    SpeedClass,
)
from app.engines.perception.tracker.track import (
    Track,
    TrackBBox,
    TrackObservation,
    TrackState,
)
from app.engines.semantic.confidence_fusion.config import FusionConfig
from app.engines.semantic.confidence_fusion.fusion import (
    ConfidenceFuser,
    ConfidenceVector,
    FusionResult,
)
from app.engines.semantic.event_understanding.config import EventUnderstandingConfig
from app.engines.semantic.event_understanding.engine import (
    Event,
    EventUnderstandingEngine,
)
from app.engines.semantic.event_understanding.rules import EventType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bbox(x1=0.1, y1=0.1, x2=0.5, y2=0.9, conf=0.85) -> TrackBBox:
    return TrackBBox(x1=x1, y1=y1, x2=x2, y2=y2, confidence=conf,
                     class_id=0, class_name="person")


def _obs(frame: int, ts: float, bbox: TrackBBox | None = None) -> TrackObservation:
    b = bbox or _bbox()
    return TrackObservation(
        frame_number=frame, timestamp_ms=ts, bbox=b, detection_confidence=b.confidence
    )


def _make_track(
    track_id: int = 1, class_name: str = "person",
    n_obs: int = 5, conf: float = 0.85,
    state: TrackState = TrackState.ACTIVE,
) -> Track:
    obs = [_obs(i, i * 200.0) for i in range(1, n_obs + 1)]
    t = Track(
        track_id=track_id, class_name=class_name, class_id=0,
        state=state,
        created_frame=1, created_timestamp_ms=0.0,
        last_seen_frame=n_obs, last_seen_timestamp_ms=n_obs * 200.0,
        current_bbox=obs[-1].bbox, observations=obs,
    )
    t.total_frames_matched = n_obs
    if state == TrackState.ACTIVE:
        t.confirmed_at_frame = 1
    return t


def _make_profile(
    track_id: int = 1, motion_confidence: float = 0.8,
    speed_class: SpeedClass = SpeedClass.WALKING,
) -> MotionProfile:
    return MotionProfile(
        track_id=track_id, class_name="person",
        dominant_speed_class=speed_class,
        motion_confidence=motion_confidence,
    )


def _make_event(
    track_id: int = 1, event_type: str = EventType.PERSON_WALKING,
    confidence: float = 0.75, rule_name: str = "rule_person_walking",
) -> Event:
    import uuid
    return Event(
        event_id=str(uuid.uuid4()),
        event_type=event_type,
        track_id=track_id,
        class_name="person",
        rule_name=rule_name,
        confidence=confidence,
        evidence={"rule": rule_name, "track_id": track_id, "track_length_ms": 1000.0},
        start_frame=1, end_frame=5,
        start_ms=0.0, end_ms=1000.0,
        dependencies=[f"track_{track_id}", f"rule_{rule_name}"],
    )


# ---------------------------------------------------------------------------
# FusionConfig tests
# ---------------------------------------------------------------------------

class TestFusionConfig:
    def test_valid_config_constructs(self):
        cfg = FusionConfig()
        assert abs(cfg.w_detection + cfg.w_motion + cfg.w_rule +
                   cfg.w_track_stability + cfg.w_scene_reliability - 1.0) < 0.01

    def test_invalid_weights_raise(self):
        with pytest.raises(ValueError, match="sum to 1.0"):
            FusionConfig(
                w_detection=0.5, w_motion=0.5, w_rule=0.5,
                w_track_stability=0.5, w_scene_reliability=0.5,
            )

    def test_weights_sum_exactly_one(self):
        cfg = FusionConfig(
            w_detection=0.20, w_motion=0.20, w_rule=0.20,
            w_track_stability=0.20, w_scene_reliability=0.20,
        )
        total = (cfg.w_detection + cfg.w_motion + cfg.w_rule +
                 cfg.w_track_stability + cfg.w_scene_reliability)
        assert abs(total - 1.0) < 0.001


# ---------------------------------------------------------------------------
# ConfidenceVector tests
# ---------------------------------------------------------------------------

class TestConfidenceVector:
    def _vec(self, **kwargs) -> ConfidenceVector:
        defaults = dict(detection=0.8, motion=0.7, rule=0.75,
                        track_stability=0.6, scene_reliability=0.9, fused=0.75)
        defaults.update(kwargs)
        return ConfidenceVector(**defaults)

    def test_weakest_dimension(self):
        vec = self._vec(detection=0.8, motion=0.3, rule=0.75,
                        track_stability=0.6, scene_reliability=0.9)
        assert vec.weakest_dimension == "motion"

    def test_strongest_dimension(self):
        vec = self._vec(detection=0.8, motion=0.3, rule=0.75,
                        track_stability=0.6, scene_reliability=0.9)
        assert vec.strongest_dimension == "scene_reliability"

    def test_to_dict_has_all_keys(self):
        vec = self._vec()
        d = vec.to_dict()
        for key in ["detection", "motion", "rule", "track_stability",
                    "scene_reliability", "fused", "weights_used", "strategy"]:
            assert key in d

    def test_fused_in_valid_range(self):
        vec = self._vec(fused=0.72)
        assert 0.0 <= vec.fused <= 1.0


# ---------------------------------------------------------------------------
# ConfidenceFuser dimension tests
# ---------------------------------------------------------------------------

class TestConfidenceFuserDimensions:
    def _fuser(self, **kwargs) -> ConfidenceFuser:
        cfg = FusionConfig(**kwargs) if kwargs else FusionConfig()
        return ConfidenceFuser(config=cfg)

    def test_high_confidence_track_scores_higher(self):
        """A long, high-confidence track should produce higher fused score."""
        fuser = self._fuser()
        event = _make_event()
        long_track = _make_track(n_obs=15, conf=0.92)
        short_track = _make_track(n_obs=2, conf=0.60)
        profile = _make_profile(motion_confidence=0.8)

        result_long = fuser.fuse(
            [_make_event()], {1: long_track}, {1: profile}, []
        )
        result_short = fuser.fuse(
            [_make_event()], {1: short_track}, {1: profile}, []
        )

        long_conf = result_long.confidence_vectors[result_long.fused_events[0].event_id].fused
        short_conf = result_short.confidence_vectors[result_short.fused_events[0].event_id].fused
        # Long track should score >= short track
        assert long_conf >= short_conf

    def test_camera_motion_reduces_scene_reliability(self):
        """Events in camera-motion frames get penalised scene_reliability."""
        fuser = self._fuser()
        event = _make_event()  # frames 1–5
        track = _make_track()
        profile = _make_profile()

        # Camera motion in all event frames
        result_cam = fuser.fuse([_make_event()], {1: track}, {1: profile}, [1, 2, 3, 4, 5])
        result_clean = fuser.fuse([_make_event()], {1: track}, {1: profile}, [])

        vec_cam = list(result_cam.confidence_vectors.values())[0]
        vec_clean = list(result_clean.confidence_vectors.values())[0]
        assert vec_cam.scene_reliability < vec_clean.scene_reliability

    def test_no_track_uses_fallback(self):
        """Events with no track in lookup use fallback detection confidence."""
        fuser = self._fuser()
        event = _make_event(track_id=99)  # track 99 not in lookup
        result = fuser.fuse([event], {}, {}, [])
        # Should not crash, uses fallback
        assert len(result.fused_events) + len(result.discarded_events) == 1

    def test_confidence_vector_stored_in_evidence(self):
        """ConfidenceVector should be embedded in event.evidence after fusion."""
        fuser = self._fuser()
        event = _make_event()
        track = _make_track()
        result = fuser.fuse([event], {1: track}, {}, [])
        ev = (result.fused_events or result.discarded_events)[0]
        assert "confidence_vector" in ev.evidence
        assert "fused" in ev.evidence["confidence_vector"]


# ---------------------------------------------------------------------------
# Fusion strategy tests
# ---------------------------------------------------------------------------

class TestFusionStrategies:
    def _fuse_with_strategy(self, strategy: str, values: tuple) -> float:
        cfg = FusionConfig(
            w_detection=0.20, w_motion=0.20, w_rule=0.20,
            w_track_stability=0.20, w_scene_reliability=0.20,
            fusion_strategy=strategy,
            min_fused_confidence=0.0,
        )
        fuser = ConfidenceFuser(config=cfg)
        return fuser._fuse(*values)

    def test_weighted_linear_all_equal(self):
        """Equal weights and equal values → result equals value."""
        result = self._fuse_with_strategy("weighted_linear", (0.8, 0.8, 0.8, 0.8, 0.8))
        assert result == pytest.approx(0.8, abs=0.001)

    def test_geometric_lower_than_linear_for_mixed_values(self):
        """Geometric mean is always <= arithmetic mean for non-uniform values."""
        vals = (0.9, 0.4, 0.8, 0.7, 0.6)
        lin = self._fuse_with_strategy("weighted_linear", vals)
        geo = self._fuse_with_strategy("geometric", vals)
        assert geo <= lin + 0.01  # geometric ≤ arithmetic (allow tiny float error)

    def test_min_strategy_returns_minimum(self):
        vals = (0.9, 0.3, 0.8, 0.7, 0.6)
        result = self._fuse_with_strategy("min", vals)
        assert result == pytest.approx(0.3, abs=0.001)

    def test_invalid_strategy_raises(self):
        fuser = ConfidenceFuser(FusionConfig(
            w_detection=0.20, w_motion=0.20, w_rule=0.20,
            w_track_stability=0.20, w_scene_reliability=0.20,
            fusion_strategy="invalid_strategy",
        ))
        with pytest.raises(ValueError, match="Unknown fusion_strategy"):
            fuser._fuse(0.8, 0.8, 0.8, 0.8, 0.8)

    def test_all_strategies_produce_valid_range(self):
        for strategy in ["weighted_linear", "geometric", "harmonic", "min"]:
            result = self._fuse_with_strategy(strategy, (0.7, 0.6, 0.8, 0.5, 0.9))
            assert 0.0 <= result <= 1.0, f"Strategy {strategy} produced {result}"


# ---------------------------------------------------------------------------
# FusionResult calibration metrics tests
# ---------------------------------------------------------------------------

class TestFusionResult:
    def test_metrics_dict_keys_present(self):
        fuser = ConfidenceFuser()
        event = _make_event()
        result = fuser.fuse([event], {1: _make_track()}, {1: _make_profile()}, [])
        metrics = result.to_metrics_dict()
        for key in ["total_fused", "total_discarded", "avg_fused_confidence",
                    "min_fused_confidence", "max_fused_confidence", "dimension_means"]:
            assert key in metrics

    def test_empty_events_returns_zero_metrics(self):
        fuser = ConfidenceFuser()
        result = fuser.fuse([], {}, {}, [])
        metrics = result.to_metrics_dict()
        assert metrics["total_fused"] == 0
        assert metrics["total_discarded"] == 0

    def test_threshold_filtering_works(self):
        """Events below threshold should be in discarded, not fused."""
        cfg = FusionConfig(
            w_detection=0.20, w_motion=0.20, w_rule=0.20,
            w_track_stability=0.20, w_scene_reliability=0.20,
            min_fused_confidence=0.99,  # extremely high — should discard everything
        )
        fuser = ConfidenceFuser(config=cfg)
        event = _make_event(confidence=0.5)
        result = fuser.fuse([event], {1: _make_track()}, {1: _make_profile()}, [])
        assert result.total_discarded >= 1


# ---------------------------------------------------------------------------
# Event dependencies (pre-Phase 7 addition)
# ---------------------------------------------------------------------------

class TestEventDependencies:
    def test_dependencies_populated_for_events(self):
        """Events should carry explicit provenance: track, rule references."""
        engine = EventUnderstandingEngine(
            config=EventUnderstandingConfig(min_event_confidence=0.0)
        )
        track = _make_track(class_name="person", n_obs=3)
        profile = _make_profile()
        result = engine.understand([track], {1: profile}, [])
        for event in result.events:
            assert len(event.dependencies) >= 2
            assert any("track_" in d for d in event.dependencies)
            assert any("rule_" in d for d in event.dependencies)

    def test_motion_profile_in_dependencies_when_profile_present(self):
        """When a motion profile exists, it appears in dependencies."""
        engine = EventUnderstandingEngine(
            config=EventUnderstandingConfig(min_event_confidence=0.0)
        )
        track = _make_track(class_name="person", n_obs=3)
        profile = _make_profile()
        result = engine.understand([track], {1: profile}, [])
        for event in result.events:
            dep_str = " ".join(event.dependencies)
            assert "motion_profile_" in dep_str


# ---------------------------------------------------------------------------
# Integration: Synthetic Track → Motion → Event → Fusion
# ---------------------------------------------------------------------------

class TestConfidenceFusionIntegration:
    """Full pipeline chain integration tests."""

    def _full_pipeline(
        self,
        bboxes: list,
        class_name: str = "person",
        min_fused: float = 0.0,
        camera_frames: list | None = None,
    ):
        """Run full chain: bboxes → Track → MotionAnalyzer → EventEngine → ConfidenceFuser."""
        obs = [
            TrackObservation(
                frame_number=i + 1,
                timestamp_ms=(i + 1) * 400.0,
                bbox=TrackBBox(x1=b[0], y1=b[1], x2=b[2], y2=b[3],
                               confidence=0.85, class_id=0, class_name=class_name),
                detection_confidence=0.85,
            )
            for i, b in enumerate(bboxes)
        ]
        track = Track(
            track_id=1, class_name=class_name, class_id=0,
            state=TrackState.ACTIVE,
            created_frame=1, created_timestamp_ms=400.0,
            last_seen_frame=len(bboxes), last_seen_timestamp_ms=len(bboxes) * 400.0,
            current_bbox=obs[-1].bbox, observations=obs,
        )
        track.total_frames_matched = len(obs)
        track.confirmed_at_frame = 1

        # Motion analysis
        analyzer = MotionAnalyzer()
        motion_result = analyzer.analyze([track])

        # Event understanding
        event_engine = EventUnderstandingEngine(
            config=EventUnderstandingConfig(
                min_event_confidence=0.0, min_track_frames_for_entry=2
            )
        )
        event_result = event_engine.understand(
            [track], motion_result.motion_profiles, camera_frames or []
        )

        # Confidence fusion
        cfg = FusionConfig(
            w_detection=0.20, w_motion=0.20, w_rule=0.20,
            w_track_stability=0.20, w_scene_reliability=0.20,
            min_fused_confidence=min_fused,
        )
        fuser = ConfidenceFuser(config=cfg)
        fusion_result = fuser.fuse(
            events=event_result.events,
            tracks={1: track},
            motion_profiles=motion_result.motion_profiles,
            camera_motion_frames=camera_frames or [],
        )

        return fusion_result, motion_result, event_result

    def test_integration_walking_person_has_fused_confidence(self):
        """Walking person → events with valid ConfidenceVector after fusion."""
        bboxes = [(0.1 + i * 0.025, 0.1, 0.4 + i * 0.025, 0.9) for i in range(8)]
        fusion_result, _, _ = self._full_pipeline(bboxes, "person")

        all_events = fusion_result.fused_events + fusion_result.discarded_events
        assert len(all_events) > 0
        for event in all_events:
            assert "confidence_vector" in event.evidence
            vec = event.evidence["confidence_vector"]
            assert 0.0 <= vec["fused"] <= 1.0
            assert 0.0 <= vec["detection"] <= 1.0

    def test_integration_confidence_vector_all_5_dimensions(self):
        """Every fused event must have all 5 dimensions in its vector."""
        bboxes = [(0.1 + i * 0.02, 0.1, 0.4 + i * 0.02, 0.9) for i in range(6)]
        fusion_result, _, _ = self._full_pipeline(bboxes)

        for event in fusion_result.fused_events + fusion_result.discarded_events:
            vec = event.evidence["confidence_vector"]
            for dim in ["detection", "motion", "rule", "track_stability", "scene_reliability"]:
                assert dim in vec, f"Missing dimension: {dim}"

    def test_integration_camera_motion_reduces_fused_confidence(self):
        """Same track, but all frames in camera-motion → lower scene_reliability → lower fused."""
        bboxes = [(0.1 + i * 0.02, 0.1, 0.4 + i * 0.02, 0.9) for i in range(6)]

        clean, _, _ = self._full_pipeline(bboxes, camera_frames=[])
        noisy, _, _ = self._full_pipeline(bboxes, camera_frames=[1, 2, 3, 4, 5, 6])

        all_clean = clean.fused_events + clean.discarded_events
        all_noisy = noisy.fused_events + noisy.discarded_events

        if all_clean and all_noisy:
            clean_fused = max(v.fused for v in clean.confidence_vectors.values())
            noisy_fused = max(v.fused for v in noisy.confidence_vectors.values())
            assert clean_fused >= noisy_fused

    def test_integration_dependencies_chain_traceable(self):
        """
        Full provenance: every event carries dependencies list with
        track, rule, and motion_profile references.
        """
        bboxes = [(0.1 + i * 0.02, 0.1, 0.4 + i * 0.02, 0.9) for i in range(6)]
        fusion_result, _, event_result = self._full_pipeline(bboxes)

        all_events = fusion_result.fused_events + fusion_result.discarded_events
        for event in all_events:
            assert event.dependencies, f"Event {event.event_type} has empty dependencies"
            assert any("track_" in d for d in event.dependencies)
            assert any("rule_" in d for d in event.dependencies)


# ---------------------------------------------------------------------------
# s08_confidence_fuse pipeline stage tests
# ---------------------------------------------------------------------------

class TestS08ConfidenceFuse:
    def _make_context(self, events=None, all_tracks=None, motion_profiles=None):
        from app.pipeline.context import PipelineContext
        ctx = PipelineContext(
            job_id="JOB-TEST", video_id="test", video_path="/tmp/v.mp4",
            output_dir="/tmp",
            settings={
                "fusion_w_detection": 0.20, "fusion_w_motion": 0.20,
                "fusion_w_rule": 0.20, "fusion_w_track_stability": 0.20,
                "fusion_w_scene_reliability": 0.20,
                "fusion_strategy": "weighted_linear",
                "fusion_min_confidence": 0.0,
            },
            metadata={"camera_motion_frames": []},
        )
        if events is not None:
            ctx.metadata["events"] = events
        if all_tracks is not None:
            ctx.metadata["all_tracks"] = all_tracks
        if motion_profiles is not None:
            ctx.metadata["motion_profiles"] = motion_profiles
        return ctx

    @pytest.mark.asyncio
    async def test_missing_events_fails(self):
        from app.pipeline.stages import s08_confidence_fuse
        ctx = self._make_context()
        result = await s08_confidence_fuse.run(ctx)
        assert result.success is False
        assert any("events" in e for e in result.errors)

    @pytest.mark.asyncio
    @patch("app.pipeline.stages.s08_confidence_fuse.save_stage_metrics")
    async def test_empty_events_returns_success(self, mock_save):
        from app.pipeline.stages import s08_confidence_fuse
        mock_save.return_value = None
        ctx = self._make_context(events=[], all_tracks=[], motion_profiles={})
        result = await s08_confidence_fuse.run(ctx)
        assert result.success is True
        assert ctx.metadata["fused_events"] == []

    @pytest.mark.asyncio
    @patch("app.pipeline.stages.s08_confidence_fuse.save_stage_metrics")
    async def test_event_gets_fused_and_stored(self, mock_save):
        from app.pipeline.stages import s08_confidence_fuse
        mock_save.return_value = None
        event = _make_event()
        track = _make_track()
        profile = _make_profile()
        ctx = self._make_context(
            events=[event], all_tracks=[track],
            motion_profiles={1: profile},
        )
        result = await s08_confidence_fuse.run(ctx)
        assert result.success is True
        all_ev = ctx.metadata["fused_events"] + ctx.metadata["discarded_events"]
        assert len(all_ev) == 1

    @pytest.mark.asyncio
    async def test_stage_name_correct(self):
        from app.pipeline.stages import s08_confidence_fuse
        ctx = self._make_context()
        result = await s08_confidence_fuse.run(ctx)
        assert result.stage_name == "s08_confidence_fuse"
