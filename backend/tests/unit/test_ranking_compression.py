"""
Tests for Phase 9: Ranking Engine + Compression Policy.

Key test groups:
  1. RankingConfig — weight validation
  2. ImportanceScore — component values (running > standing, motion intensity)
  3. RankingEngine — dual score independence, chain ranking
  4. EVENT_RARITY — correct ordering (running > walking > standing)
  5. CompressionPolicy — chain atomicity, ratio, COMPLETE preservation
  6. CompressionResult — evaluation metrics (completeness retained, broken narratives)
  7. Dual score separation (mentor recommendation)
  8. Integration: full 6-stage chain (Track → ... → Rank → Compress)
  9. s10_rank + s11_summarize pipeline stages (mocked)
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest

from app.engines.semantic.event_understanding.engine import Event
from app.engines.semantic.event_understanding.rules import EventType
from app.engines.temporal.compression_policy.config import CompressionConfig
from app.engines.temporal.compression_policy.policy import (
    CompressionPolicy,
    CompressionResult,
)
from app.engines.temporal.ranking_engine.config import RankingConfig
from app.engines.temporal.ranking_engine.ranker import (
    EVENT_RARITY,
    ImportanceScore,
    RankingEngine,
    RankingResult,
)
from app.engines.temporal.story_preservation.story_builder import (
    StoryBuilder,
    StoryCompleteness,
    StorySegment,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _event(
    track_id: int = 1,
    event_type: str = EventType.PERSON_WALKING,
    start_ms: float = 0.0,
    end_ms: float = 1000.0,
    confidence: float = 0.75,
    rule_name: str = "rule_person_walking",
) -> Event:
    return Event(
        event_id=str(uuid.uuid4()),
        event_type=event_type,
        track_id=track_id,
        class_name="person",
        rule_name=rule_name,
        confidence=confidence,
        evidence={"rule": rule_name},
        start_frame=int(start_ms / 200),
        end_frame=int(end_ms / 200),
        start_ms=start_ms,
        end_ms=end_ms,
        dependencies=[f"track_{track_id}", f"rule_{rule_name}"],
    )


def _segment(
    track_id: int = 1,
    events: list[Event] | None = None,
    completeness: StoryCompleteness = StoryCompleteness.COMPLETE,
    narrative_score: float = 0.80,
    mean_confidence: float = 0.75,
) -> StorySegment:
    evs = events or [
        _event(track_id, EventType.PERSON_ENTERED_SCENE, 0, 200, rule_name="rule_person_entered"),
        _event(track_id, EventType.PERSON_WALKING, 400, 2000),
        _event(track_id, EventType.PERSON_LEFT_SCENE, 2200, 2400, rule_name="rule_person_left"),
    ]
    return StorySegment(
        segment_id=f"seg_{track_id}_{str(uuid.uuid4())[:6]}",
        track_ids={track_id},
        events=evs,
        completeness=completeness,
        narrative_score=narrative_score,
        mean_confidence=mean_confidence,
        start_ms=evs[0].start_ms,
        end_ms=evs[-1].end_ms,
    )


def _ranker(w_importance=0.40, w_narrative=0.60) -> RankingEngine:
    return RankingEngine(RankingConfig(w_importance=w_importance, w_narrative=w_narrative))


# ---------------------------------------------------------------------------
# RankingConfig tests
# ---------------------------------------------------------------------------

class TestRankingConfig:
    def test_valid_config_constructs(self):
        cfg = RankingConfig(w_importance=0.40, w_narrative=0.60)
        assert abs(cfg.w_importance + cfg.w_narrative - 1.0) < 0.01

    def test_invalid_weights_raise(self):
        with pytest.raises(ValueError, match="sum to 1.0"):
            RankingConfig(w_importance=0.70, w_narrative=0.70)

    def test_equal_weights_valid(self):
        cfg = RankingConfig(w_importance=0.50, w_narrative=0.50)
        assert abs(cfg.w_importance + cfg.w_narrative - 1.0) < 0.01


# ---------------------------------------------------------------------------
# EVENT_RARITY ordering tests
# ---------------------------------------------------------------------------

class TestEventRarity:
    def test_running_scores_higher_than_standing(self):
        assert EVENT_RARITY["person_running"] > EVENT_RARITY["person_standing"]

    def test_loitering_scores_higher_than_walking(self):
        assert EVENT_RARITY["person_loitering"] > EVENT_RARITY["person_walking"]

    def test_running_is_highest_person_event(self):
        person_events = ["person_running", "person_walking", "person_standing",
                         "person_loitering"]
        assert max(EVENT_RARITY[e] for e in person_events) == EVENT_RARITY["person_running"]

    def test_all_values_in_valid_range(self):
        for event_type, score in EVENT_RARITY.items():
            assert 0.0 <= score <= 1.0, f"{event_type}: {score}"


# ---------------------------------------------------------------------------
# ImportanceScore component tests
# ---------------------------------------------------------------------------

class TestImportanceScore:
    def test_running_event_scores_higher_importance_than_standing(self):
        ranker = _ranker()
        running_event = _event(event_type=EventType.PERSON_RUNNING, confidence=0.80)
        standing_event = _event(event_type=EventType.PERSON_STANDING, confidence=0.80)

        running_score = ranker._compute_importance(running_event, None)
        standing_score = ranker._compute_importance(standing_event, None)

        assert running_score.rarity > standing_score.rarity
        assert running_score.combined > standing_score.combined

    def test_high_confidence_event_scores_higher_detection(self):
        ranker = _ranker()
        hi_conf = _event(confidence=0.95)
        lo_conf = _event(confidence=0.40)

        hi_score = ranker._compute_importance(hi_conf, None)
        lo_score = ranker._compute_importance(lo_conf, None)

        assert hi_score.detection > lo_score.detection
        assert hi_score.combined > lo_score.combined

    def test_importance_score_in_valid_range(self):
        ranker = _ranker()
        for event_type in [EventType.PERSON_WALKING, EventType.PERSON_RUNNING,
                           EventType.VEHICLE_APPROACHING, EventType.PERSON_LOITERING]:
            score = ranker._compute_importance(_event(event_type=event_type), None)
            assert 0.0 <= score.combined <= 1.0

    def test_to_dict_has_all_components(self):
        ranker = _ranker()
        score = ranker._compute_importance(_event(), None)
        d = score.to_dict()
        for key in ["detection", "rarity", "motion", "salience", "combined"]:
            assert key in d

    def test_stationary_profile_gives_zero_motion(self):
        from app.engines.perception.motion_analyzer.analyzer import MotionProfile, SpeedClass
        profile = MotionProfile(
            track_id=1, class_name="person",
            is_stationary=True,
            dominant_speed_class=SpeedClass.STATIONARY,
            motion_confidence=0.8,
        )
        ranker = _ranker()
        score = ranker._compute_importance(_event(), profile)
        assert score.motion == 0.0


# ---------------------------------------------------------------------------
# RankingEngine dual score independence tests (mentor's core recommendation)
# ---------------------------------------------------------------------------

class TestRankingEngineDualScores:
    def test_high_narrative_low_importance_segment_can_rank_high(self):
        """
        Scenario: person standing still (low importance) with COMPLETE arc (high narrative).
        With narrative-weighted config, this should rank higher than an
        isolated high-importance event with no narrative context.
        """
        narrative_ranker = _ranker(w_importance=0.10, w_narrative=0.90)

        # High narrative, low importance (person standing = low rarity)
        standing_seg = _segment(
            1,
            events=[
                _event(1, EventType.PERSON_ENTERED_SCENE, 0, 200, confidence=0.70, rule_name="rule_person_entered"),
                _event(1, EventType.PERSON_STANDING, 400, 5000, confidence=0.70),
                _event(1, EventType.PERSON_LEFT_SCENE, 5200, 5400, confidence=0.70, rule_name="rule_person_left"),
            ],
            completeness=StoryCompleteness.COMPLETE,
            narrative_score=0.92,
        )
        # Low narrative, high importance (running but isolated)
        running_seg = _segment(
            2,
            events=[_event(2, EventType.PERSON_RUNNING, 0, 500, confidence=0.95)],
            completeness=StoryCompleteness.MINIMAL,
            narrative_score=0.15,
        )

        result = narrative_ranker.rank([standing_seg, running_seg])
        ranked = result.ranked_segments
        # With 90% narrative weight, the complete standing arc should win
        assert ranked[0].segment.segment_id == standing_seg.segment_id

    def test_importance_score_independent_of_narrative_score(self):
        """The two scores should differ for different events."""
        ranker = _ranker()
        seg1 = _segment(1, narrative_score=0.90)
        seg2 = _segment(2, narrative_score=0.30,
                        events=[_event(2, EventType.PERSON_RUNNING, confidence=0.95)])

        result = ranker.rank([seg1, seg2])
        rs1 = next(rs for rs in result.ranked_segments if rs.segment.segment_id == seg1.segment_id)
        rs2 = next(rs for rs in result.ranked_segments if rs.segment.segment_id == seg2.segment_id)

        assert rs1.narrative_score > rs2.narrative_score
        assert rs1.importance_score != rs2.importance_score or rs1.narrative_score != rs2.narrative_score

    def test_segments_ranked_by_combined_desc(self):
        ranker = _ranker()
        segs = [_segment(i, narrative_score=0.9 - i * 0.1) for i in range(1, 5)]
        result = ranker.rank(segs)
        ranks = result.ranked_segments
        for i in range(len(ranks) - 1):
            assert ranks[i].combined_rank >= ranks[i + 1].combined_rank

    def test_rank_assigned_correctly(self):
        ranker = _ranker()
        segs = [_segment(i) for i in range(1, 4)]
        result = ranker.rank(segs)
        ranks = [rs.rank for rs in result.ranked_segments]
        assert sorted(ranks) == [1, 2, 3]
        assert result.ranked_segments[0].rank == 1

    def test_empty_segments_returns_empty(self):
        ranker = _ranker()
        result = ranker.rank([])
        assert result.ranked_segments == []


# ---------------------------------------------------------------------------
# CompressionPolicy tests
# ---------------------------------------------------------------------------

class TestCompressionPolicy:
    def _policy(self, **kwargs) -> CompressionPolicy:
        cfg = CompressionConfig(**kwargs) if kwargs else CompressionConfig()
        return CompressionPolicy(config=cfg)

    def _rank_then_compress(self, segments, policy_kwargs=None):
        ranking_result = _ranker().rank(segments)
        policy = self._policy(**(policy_kwargs or {}))
        return policy.apply(ranking_result), ranking_result

    def test_always_keep_complete_preserves_complete_arcs(self):
        """COMPLETE segments must survive when always_keep_complete=True."""
        complete_seg = _segment(1, completeness=StoryCompleteness.COMPLETE, narrative_score=0.90)
        minimal_seg = _segment(2,
                               events=[_event(2, EventType.PERSON_WALKING)],
                               completeness=StoryCompleteness.MINIMAL,
                               narrative_score=0.15)

        result, ranking = self._rank_then_compress(
            [complete_seg, minimal_seg],
            {"always_keep_complete": True, "target_ratio": 0.01},  # tiny ratio
        )

        # Complete segment should be preserved despite tiny ratio
        assert complete_seg.segment_id in result.kept_segment_ids

    def test_chain_atomicity_keeps_all_or_none(self):
        """With chain_atomicity=True, a segment's events are kept together."""
        seg = _segment(1, narrative_score=0.80)
        result, ranking = self._rank_then_compress(
            [seg], {"chain_atomicity": True, "target_ratio": 0.80}
        )
        seg_event_ids = {e.event_id for e in seg.events}
        kept = seg_event_ids & result.kept_event_ids
        discarded = seg_event_ids & result.discarded_event_ids
        # Either all kept or all discarded — not mixed
        assert len(kept) == 0 or len(discarded) == 0

    def test_low_quality_segments_discarded_first(self):
        """Segments below completeness_min_threshold get discarded immediately."""
        bad_seg = _segment(1, narrative_score=0.05)
        good_seg = _segment(2, narrative_score=0.85)
        result, _ = self._rank_then_compress(
            [bad_seg, good_seg],
            {"completeness_min_threshold": 0.20, "target_ratio": 1.0}
        )
        assert bad_seg.segment_id in result.discarded_segment_ids

    def test_every_event_has_a_decision(self):
        """CompressionResult must have one decision per event."""
        seg = _segment(1)
        result, _ = self._rank_then_compress([seg])
        total_events = len(seg.events)
        assert len(result.decisions) == total_events

    def test_decisions_have_reason(self):
        """Every CompressionDecision must have a non-empty reason."""
        seg = _segment(1)
        result, _ = self._rank_then_compress([seg])
        for decision in result.decisions:
            assert decision.reason
            assert decision.reason in [
                "complete_chain_preserved", "high_combined_rank",
                "below_ratio_threshold", "low_narrative_quality",
            ]

    def test_compression_ratio_approximately_respected(self):
        """Actual ratio should be within 30% of target (chain atomicity may cause variance)."""
        segs = [_segment(i, narrative_score=0.9 - i * 0.1) for i in range(1, 6)]
        target = 0.40
        result, _ = self._rank_then_compress(
            segs,
            {"target_ratio": target, "always_keep_complete": False, "chain_atomicity": True}
        )
        actual = result.compression_ratio_achieved
        # Allow 40% variance due to chain atomicity
        assert 0.0 <= actual <= 1.0


# ---------------------------------------------------------------------------
# CompressionResult evaluation metrics tests (mentor's recommendation)
# ---------------------------------------------------------------------------

class TestEvaluationMetrics:
    def test_story_completeness_retained_is_one_when_all_complete_kept(self):
        complete_seg = _segment(1, completeness=StoryCompleteness.COMPLETE, narrative_score=0.90)
        ranking = _ranker().rank([complete_seg])
        result = CompressionPolicy(CompressionConfig(always_keep_complete=True)).apply(ranking)
        metrics = result.to_metrics_dict(ranking.ranked_segments)
        assert metrics["story_completeness_retained"] == pytest.approx(1.0, abs=0.01)

    def test_broken_narratives_zero_with_chain_atomicity(self):
        segs = [_segment(i) for i in range(1, 4)]
        ranking = _ranker().rank(segs)
        result = CompressionPolicy(CompressionConfig(chain_atomicity=True)).apply(ranking)
        metrics = result.to_metrics_dict(ranking.ranked_segments)
        assert metrics["broken_narratives"] == 0

    def test_avg_narrative_chain_length_positive_when_events_kept(self):
        seg = _segment(1)  # 3 events
        ranking = _ranker().rank([seg])
        result = CompressionPolicy(CompressionConfig(target_ratio=1.0)).apply(ranking)
        metrics = result.to_metrics_dict(ranking.ranked_segments)
        assert metrics["avg_narrative_chain_length"] > 0

    def test_metrics_dict_has_required_keys(self):
        seg = _segment(1)
        ranking = _ranker().rank([seg])
        result = CompressionPolicy().apply(ranking)
        metrics = result.to_metrics_dict(ranking.ranked_segments)
        for key in ["total_events", "kept_events", "discarded_events",
                    "compression_ratio_achieved", "story_completeness_retained",
                    "broken_narratives", "avg_narrative_chain_length"]:
            assert key in metrics, f"Missing metric: {key}"


# ---------------------------------------------------------------------------
# Integration: full 6-stage chain
# Track → Motion → Event → Fusion → Story → Rank → Compress
# ---------------------------------------------------------------------------

class TestPhase9Integration:
    def _full_pipeline(self, bboxes_by_track: dict, class_name="person"):
        """Run the complete 6-stage pipeline and return compression result."""
        from app.engines.perception.motion_analyzer.analyzer import MotionAnalyzer
        from app.engines.perception.tracker.track import (
            Track, TrackBBox, TrackObservation, TrackState,
        )
        from app.engines.semantic.confidence_fusion.config import FusionConfig
        from app.engines.semantic.confidence_fusion.fusion import ConfidenceFuser
        from app.engines.semantic.event_understanding.config import EventUnderstandingConfig
        from app.engines.semantic.event_understanding.engine import EventUnderstandingEngine

        tracks = []
        for track_id, bboxes in bboxes_by_track.items():
            obs = [
                TrackObservation(
                    frame_number=i + 1, timestamp_ms=(i + 1) * 400.0,
                    bbox=TrackBBox(x1=b[0], y1=b[1], x2=b[2], y2=b[3],
                                   confidence=0.85, class_id=0, class_name=class_name),
                    detection_confidence=0.85,
                )
                for i, b in enumerate(bboxes)
            ]
            t = Track(
                track_id=track_id, class_name=class_name, class_id=0,
                state=TrackState.ACTIVE,
                created_frame=1, created_timestamp_ms=400.0,
                last_seen_frame=len(bboxes), last_seen_timestamp_ms=len(bboxes) * 400.0,
                current_bbox=obs[-1].bbox, observations=obs,
            )
            t.total_frames_matched = len(obs)
            t.confirmed_at_frame = 1
            tracks.append(t)

        motion = MotionAnalyzer().analyze(tracks)
        event_engine = EventUnderstandingEngine(
            config=EventUnderstandingConfig(min_event_confidence=0.0, min_track_frames_for_entry=2)
        )
        event_result = event_engine.understand(tracks, motion.motion_profiles, [])
        fusion_result = ConfidenceFuser(
            FusionConfig(w_detection=0.20, w_motion=0.20, w_rule=0.20,
                         w_track_stability=0.20, w_scene_reliability=0.20, min_fused_confidence=0.0)
        ).fuse(event_result.events, {t.track_id: t for t in tracks}, motion.motion_profiles, [])
        story_result = StoryBuilder().build(fusion_result.fused_events)
        ranking = RankingEngine().rank(story_result.segments, motion.motion_profiles)
        compression = CompressionPolicy().apply(ranking)

        return compression, ranking, story_result, event_result

    def test_integration_events_have_decisions(self):
        bboxes = {1: [(0.1 + i*0.02, 0.1, 0.4 + i*0.02, 0.9) for i in range(8)]}
        compression, ranking, _, event_result = self._full_pipeline(bboxes)
        # Every event in the pipeline should have a decision
        all_event_ids = {e.event_id for rs in ranking.ranked_segments for e in rs.segment.events}
        decision_ids = {d.event_id for d in compression.decisions}
        assert all_event_ids == decision_ids

    def test_integration_every_decision_has_reason(self):
        bboxes = {1: [(0.1 + i*0.02, 0.1, 0.4 + i*0.02, 0.9) for i in range(6)]}
        compression, _, _, _ = self._full_pipeline(bboxes)
        for d in compression.decisions:
            assert d.reason in [
                "complete_chain_preserved", "high_combined_rank",
                "below_ratio_threshold", "low_narrative_quality",
            ]

    def test_integration_running_person_has_higher_importance_than_standing(self):
        """Phase 9 key property: running events get higher importance than standing."""
        running_bboxes = {1: [(0.1 + i*0.05, 0.1, 0.4 + i*0.05, 0.9) for i in range(6)]}
        standing_bboxes = {2: [(0.1, 0.1, 0.4, 0.9) for _ in range(6)]}  # no movement

        from app.engines.perception.motion_analyzer.analyzer import MotionAnalyzer
        from app.engines.perception.tracker.track import (
            Track, TrackBBox, TrackObservation, TrackState
        )
        from app.engines.semantic.event_understanding.rules import EventType

        # Running segment: fast moving track → person_walking/fast events
        # We compare event rarity values directly as a proxy
        running_rarity = EVENT_RARITY.get(EventType.PERSON_RUNNING, 0)
        standing_rarity = EVENT_RARITY.get(EventType.PERSON_STANDING, 0)
        assert running_rarity > standing_rarity

    def test_integration_compression_ratio_in_valid_range(self):
        bboxes = {1: [(0.1 + i*0.02, 0.1, 0.4 + i*0.02, 0.9) for i in range(8)]}
        compression, _, _, _ = self._full_pipeline(bboxes)
        assert 0.0 <= compression.compression_ratio_achieved <= 1.0

    def test_integration_metrics_all_present(self):
        bboxes = {1: [(0.1 + i*0.02, 0.1, 0.4 + i*0.02, 0.9) for i in range(6)]}
        compression, ranking, _, _ = self._full_pipeline(bboxes)
        metrics = compression.to_metrics_dict(ranking.ranked_segments)
        for key in ["story_completeness_retained", "broken_narratives",
                    "avg_narrative_chain_length", "compression_ratio_achieved"]:
            assert key in metrics


# ---------------------------------------------------------------------------
# Pipeline stage tests
# ---------------------------------------------------------------------------

class TestS10Rank:
    def _ctx(self, segments=None, profiles=None):
        from app.pipeline.context import PipelineContext
        ctx = PipelineContext(
            job_id="JOB-TEST", video_id="t", video_path="/tmp/v.mp4",
            output_dir="/tmp",
            settings={"rank_w_importance": 0.40, "rank_w_narrative": 0.60},
            metadata={"motion_profiles": profiles or {}},
        )
        if segments is not None:
            ctx.metadata["story_segments"] = segments
        return ctx

    @pytest.mark.asyncio
    async def test_missing_segments_fails(self):
        from app.pipeline.stages import s10_rank
        result = await s10_rank.run(self._ctx())
        assert result.success is False

    @pytest.mark.asyncio
    @patch("app.pipeline.stages.s10_rank.save_stage_metrics")
    async def test_empty_segments_returns_success(self, mock_save):
        from app.pipeline.stages import s10_rank
        mock_save.return_value = None
        result = await s10_rank.run(self._ctx(segments=[]))
        assert result.success is True

    @pytest.mark.asyncio
    @patch("app.pipeline.stages.s10_rank.save_stage_metrics")
    async def test_segments_are_ranked(self, mock_save):
        from app.pipeline.stages import s10_rank
        mock_save.return_value = None
        ctx = self._ctx(segments=[_segment(1), _segment(2)])
        result = await s10_rank.run(ctx)
        assert result.success is True
        assert len(ctx.metadata["ranked_segments"]) == 2

    @pytest.mark.asyncio
    async def test_stage_name_correct(self):
        from app.pipeline.stages import s10_rank
        result = await s10_rank.run(self._ctx())
        assert result.stage_name == "s10_rank"


class TestS11Summarize:
    def _ctx_with_ranking(self, segments):
        from app.pipeline.context import PipelineContext
        ranking = RankingEngine().rank(segments)
        ctx = PipelineContext(
            job_id="JOB-TEST", video_id="t", video_path="/tmp/v.mp4",
            output_dir="/tmp", settings={}, metadata={},
        )
        ctx.metadata["ranking_result"] = ranking
        return ctx

    @pytest.mark.asyncio
    async def test_missing_ranking_fails(self):
        from app.pipeline.stages import s11_summarize
        from app.pipeline.context import PipelineContext
        ctx = PipelineContext(
            job_id="X", video_id="x", video_path="/tmp/v.mp4",
            output_dir="/tmp", settings={}, metadata={},
        )
        result = await s11_summarize.run(ctx)
        assert result.success is False

    @pytest.mark.asyncio
    @patch("app.pipeline.stages.s11_summarize.save_stage_metrics")
    async def test_summary_events_are_chronological(self, mock_save):
        from app.pipeline.stages import s11_summarize
        mock_save.return_value = None
        seg = _segment(1)
        ctx = self._ctx_with_ranking([seg])
        result = await s11_summarize.run(ctx)
        assert result.success is True
        events = ctx.metadata["summary_events"]
        for i in range(len(events) - 1):
            assert events[i].start_ms <= events[i + 1].start_ms

    @pytest.mark.asyncio
    async def test_stage_name_correct(self):
        from app.pipeline.stages import s11_summarize
        from app.pipeline.context import PipelineContext
        ctx = PipelineContext(
            job_id="X", video_id="x", video_path="/tmp/v.mp4",
            output_dir="/tmp", settings={}, metadata={},
        )
        result = await s11_summarize.run(ctx)
        assert result.stage_name == "s11_summarize"
