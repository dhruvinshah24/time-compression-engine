"""
Tests for Phase 8: Story Preservation + Event Graph.

Includes:
  1. ContinuityChecker — temporal ordering, invalid sequences, terminal events
  2. StoryCompleteness classification — COMPLETE / PARTIAL / ENTRY_ONLY / EXIT_ONLY / MINIMAL
  3. Narrative score computation — weights, coherence penalty
  4. Co-occurrence linking across tracks
  5. EventGraph — node/edge creation, SAME_TRACK_TEMPORAL edges, CO_OCCURRENCE edges
  6. Hub nodes, isolated nodes
  7. StoryPreservationResult — ranking, metrics
  8. Integration: Synthetic Tracks → Motion → Event → Fusion → Story + Graph
  9. ConfidenceVector `components` key (pre-Phase 8 addition)
  10. s09_story_build pipeline stage (mocked)
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest

from app.engines.semantic.event_understanding.engine import Event
from app.engines.semantic.event_understanding.rules import EventType
from app.engines.temporal.event_graph.config import EventGraphConfig
from app.engines.temporal.event_graph.graph_builder import (
    EdgeRelationship,
    EventGraph,
    EventGraphBuilder,
    EventNode,
)
from app.engines.temporal.story_preservation.config import StoryConfig
from app.engines.temporal.story_preservation.continuity import ContinuityChecker
from app.engines.temporal.story_preservation.story_builder import (
    StoryBuilder,
    StoryCompleteness,
    StorySegment,
)


# ---------------------------------------------------------------------------
# Event factory
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


def _person_arc(
    track_id: int,
    base_ms: float = 0.0,
    include_entry: bool = True,
    include_action: bool = True,
    include_exit: bool = True,
) -> list[Event]:
    """Build a person's story arc with configurable parts."""
    events: list[Event] = []
    t = base_ms
    if include_entry:
        events.append(_event(track_id, EventType.PERSON_ENTERED_SCENE, t, t + 200, rule_name="rule_person_entered"))
        t += 400
    if include_action:
        events.append(_event(track_id, EventType.PERSON_WALKING, t, t + 2000, rule_name="rule_person_walking"))
        t += 2200
    if include_exit:
        events.append(_event(track_id, EventType.PERSON_LEFT_SCENE, t, t + 200, rule_name="rule_person_left"))
    return events


# ---------------------------------------------------------------------------
# ContinuityChecker tests
# ---------------------------------------------------------------------------

class TestContinuityChecker:
    def test_ordered_events_are_coherent(self):
        checker = ContinuityChecker()
        events = [
            _event(1, EventType.PERSON_ENTERED_SCENE, 0, 200),
            _event(1, EventType.PERSON_WALKING, 400, 2000),
            _event(1, EventType.PERSON_LEFT_SCENE, 2200, 2400),
        ]
        report = checker.check("seg_1", events)
        assert report.is_coherent is True
        assert len(report.issues) == 0

    def test_out_of_order_events_flagged(self):
        checker = ContinuityChecker()
        events = [
            _event(1, EventType.PERSON_WALKING, 1000, 2000),
            _event(1, EventType.PERSON_ENTERED_SCENE, 0, 200),  # wrong order
        ]
        report = checker.check("seg_1", events)
        assert report.is_coherent is False
        assert len(report.issues) > 0

    def test_event_after_terminal_flagged(self):
        checker = ContinuityChecker()
        events = [
            _event(1, EventType.PERSON_LEFT_SCENE, 0, 200),
            _event(1, EventType.PERSON_WALKING, 300, 1000),  # after left!
        ]
        report = checker.check("seg_1", events)
        assert report.is_coherent is False

    def test_invalid_sequence_flagged(self):
        checker = ContinuityChecker()
        events = [
            _event(1, EventType.PERSON_LEFT_SCENE, 0, 200),
            _event(1, EventType.PERSON_WALKING, 400, 1000),
        ]
        report = checker.check("seg_1", events)
        assert not report.is_coherent

    def test_single_event_always_coherent(self):
        checker = ContinuityChecker()
        events = [_event(1, EventType.PERSON_WALKING, 0, 1000)]
        report = checker.check("seg_1", events)
        assert report.is_coherent is True

    def test_large_gap_produces_warning_not_error(self):
        checker = ContinuityChecker()
        events = [
            _event(1, EventType.PERSON_WALKING, 0, 200),
            _event(1, EventType.PERSON_WALKING, 15000, 16000),  # 15s gap
        ]
        report = checker.check("seg_1", events)
        # Gap is a warning, not an error
        assert len(report.warnings) > 0
        assert report.is_coherent is True


# ---------------------------------------------------------------------------
# StoryCompleteness classification tests
# ---------------------------------------------------------------------------

class TestStoryCompleteness:
    def _builder(self) -> StoryBuilder:
        return StoryBuilder()

    def test_full_arc_is_complete(self):
        builder = self._builder()
        events = _person_arc(1)
        result = builder.build(events)
        assert result.segments[0].completeness == StoryCompleteness.COMPLETE

    def test_no_exit_is_partial_or_entry_only(self):
        builder = self._builder()
        events = _person_arc(1, include_exit=False)
        result = builder.build(events)
        comp = result.segments[0].completeness
        assert comp in (StoryCompleteness.PARTIAL, StoryCompleteness.ENTRY_ONLY)

    def test_only_action_is_partial(self):
        builder = self._builder()
        events = [_event(1, EventType.PERSON_WALKING, 0, 2000)]
        result = builder.build(events)
        assert result.segments[0].completeness == StoryCompleteness.MINIMAL

    def test_entry_and_action_no_exit_is_partial(self):
        builder = self._builder()
        events = _person_arc(1, include_exit=False, include_entry=True, include_action=True)
        result = builder.build(events)
        assert result.segments[0].completeness == StoryCompleteness.PARTIAL

    def test_only_exit_is_exit_only(self):
        builder = self._builder()
        events = [_event(1, EventType.PERSON_LEFT_SCENE, 0, 200, rule_name="rule_person_left")]
        result = builder.build(events)
        assert result.segments[0].completeness == StoryCompleteness.EXIT_ONLY

    def test_only_entry_is_entry_only(self):
        builder = self._builder()
        events = [_event(1, EventType.PERSON_ENTERED_SCENE, 0, 200, rule_name="rule_person_entered")]
        result = builder.build(events)
        assert result.segments[0].completeness == StoryCompleteness.ENTRY_ONLY


# ---------------------------------------------------------------------------
# Narrative score tests
# ---------------------------------------------------------------------------

class TestNarrativeScore:
    def test_complete_segment_scores_higher_than_minimal(self):
        builder = StoryBuilder()
        complete = builder.build(_person_arc(1)).segments[0]
        minimal = builder.build([_event(2, EventType.PERSON_WALKING)]).segments[0]
        assert complete.narrative_score > minimal.narrative_score

    def test_score_in_valid_range(self):
        builder = StoryBuilder()
        for events in [_person_arc(1), _person_arc(2, include_exit=False)]:
            result = builder.build(events)
            for seg in result.segments:
                assert 0.0 <= seg.narrative_score <= 1.0

    def test_incoherent_segment_penalised(self):
        """A segment with continuity issues should score lower than a coherent one."""
        builder = StoryBuilder()

        good_events = _person_arc(1)
        bad_events = [
            _event(2, EventType.PERSON_LEFT_SCENE, 0, 200, rule_name="rule_person_left"),
            _event(2, EventType.PERSON_WALKING, 400, 2000),  # after leaving!
        ]

        good_result = builder.build(good_events)
        bad_result = builder.build(bad_events)

        good_score = good_result.segments[0].narrative_score
        bad_score = bad_result.segments[0].narrative_score
        assert good_score > bad_score


# ---------------------------------------------------------------------------
# StoryBuilder multi-track tests
# ---------------------------------------------------------------------------

class TestStoryBuilderMultiTrack:
    def test_two_tracks_produce_two_segments(self):
        builder = StoryBuilder()
        events = _person_arc(1, base_ms=0) + _person_arc(2, base_ms=1000)
        result = builder.build(events)
        assert len(result.segments) == 2

    def test_concurrent_segments_are_linked(self):
        """Two tracks that overlap in time should be co-occurrence linked."""
        builder = StoryBuilder(StoryConfig(co_occurrence_window_ms=5000.0))
        # Both at same time
        events = _person_arc(1, base_ms=0) + _person_arc(2, base_ms=0)
        result = builder.build(events)
        seg1, seg2 = result.segments
        assert (seg2.segment_id in seg1.interacting_segment_ids
                or seg1.segment_id in seg2.interacting_segment_ids)

    def test_distant_segments_not_linked(self):
        """Tracks far apart in time should not be co-occurrence linked."""
        builder = StoryBuilder(StoryConfig(co_occurrence_window_ms=500.0))
        events = (
            _person_arc(1, base_ms=0) +
            _person_arc(2, base_ms=60_000)  # 60 seconds later
        )
        result = builder.build(events)
        for seg in result.segments:
            assert seg.interacting_segment_ids == []

    def test_ranked_segments_ordered_by_score(self):
        builder = StoryBuilder()
        events = _person_arc(1) + _person_arc(2, include_exit=False)
        result = builder.build(events)
        ranked = result.ranked_segments()
        for i in range(len(ranked) - 1):
            assert ranked[i].narrative_score >= ranked[i + 1].narrative_score

    def test_empty_events_returns_empty_result(self):
        builder = StoryBuilder()
        result = builder.build([])
        assert len(result.segments) == 0
        assert result.complete_segments == 0


# ---------------------------------------------------------------------------
# EventGraph tests
# ---------------------------------------------------------------------------

class TestEventGraph:
    def test_nodes_equal_event_count(self):
        events = _person_arc(1)
        graph = EventGraphBuilder().build(events)
        assert len(graph.nodes) == len(events)

    def test_same_track_temporal_edges_created(self):
        events = _person_arc(1)  # 3 events for track 1
        graph = EventGraphBuilder().build(events)
        same_track = [e for e in graph.edges
                      if e.relationship == EdgeRelationship.SAME_TRACK_TEMPORAL]
        assert len(same_track) == len(events) - 1  # N events → N-1 edges

    def test_co_occurrence_edges_between_tracks(self):
        """Two simultaneous tracks should get CO_OCCURRENCE edges."""
        events = _person_arc(1, base_ms=0) + _person_arc(2, base_ms=0)
        graph = EventGraphBuilder(EventGraphConfig(max_co_occurrence_gap_ms=5000)).build(events)
        co_edges = [e for e in graph.edges
                    if e.relationship == EdgeRelationship.CO_OCCURRENCE]
        assert len(co_edges) > 0

    def test_no_co_occurrence_for_same_track(self):
        """Same-track events should not get CO_OCCURRENCE edges."""
        events = _person_arc(1)
        graph = EventGraphBuilder().build(events)
        co_edges = [e for e in graph.edges
                    if e.relationship == EdgeRelationship.CO_OCCURRENCE]
        assert len(co_edges) == 0

    def test_hub_nodes_have_highest_degree(self):
        events = _person_arc(1) + _person_arc(2, base_ms=0)
        graph = EventGraphBuilder(EventGraphConfig(max_co_occurrence_gap_ms=5000)).build(events)
        hubs = graph.hub_nodes(2)
        if len(hubs) >= 2:
            assert hubs[0].degree >= hubs[1].degree

    def test_isolated_nodes_have_zero_degree(self):
        # Single event, no connections
        events = [_event(1, EventType.PERSON_STANDING, 0, 1000)]
        graph = EventGraphBuilder().build(events)
        isolated = graph.isolated_nodes()
        assert len(isolated) == 1
        assert isolated[0].degree == 0

    def test_subgraph_for_track_correct(self):
        events = _person_arc(1) + _person_arc(2, base_ms=5000)
        graph = EventGraphBuilder().build(events)
        track1_nodes = graph.subgraph_for_track(1)
        assert all(n.event.track_id == 1 for n in track1_nodes)

    def test_metrics_dict_keys_present(self):
        events = _person_arc(1)
        graph = EventGraphBuilder().build(events)
        m = graph.to_metrics_dict()
        for key in ["total_nodes", "total_edges", "edges_by_type",
                    "isolated_nodes", "hub_node_ids"]:
            assert key in m

    def test_empty_events_returns_empty_graph(self):
        graph = EventGraphBuilder().build([])
        assert len(graph.nodes) == 0
        assert len(graph.edges) == 0


# ---------------------------------------------------------------------------
# ConfidenceVector components key test (pre-Phase 8 addition)
# ---------------------------------------------------------------------------

class TestConfidenceVectorComponents:
    def test_components_key_present_in_to_dict(self):
        from app.engines.semantic.confidence_fusion.fusion import ConfidenceVector
        vec = ConfidenceVector(
            detection=0.85, motion=0.78, rule=0.83,
            track_stability=0.70, scene_reliability=1.0, fused=0.815,
        )
        d = vec.to_dict()
        assert "components" in d
        assert "fused" in d
        components = d["components"]
        for dim in ["detection", "motion", "rule", "track_stability", "scene_reliability"]:
            assert dim in components

    def test_fused_and_components_fused_match(self):
        from app.engines.semantic.confidence_fusion.fusion import ConfidenceVector
        vec = ConfidenceVector(
            detection=0.85, motion=0.78, rule=0.83,
            track_stability=0.70, scene_reliability=1.0, fused=0.815,
        )
        d = vec.to_dict()
        assert d["fused"] == pytest.approx(0.815, abs=0.001)


# ---------------------------------------------------------------------------
# Integration: full 5-stage chain
# Track → Motion → Event → Fusion → Story + Graph
# ---------------------------------------------------------------------------

class TestStoryIntegration:
    """Full pipeline: synthetic bboxes → StorySegments + EventGraph."""

    def _full_pipeline(self, bboxes_by_track: dict, class_name: str = "person"):
        """
        Build tracks → run Motion → Event → Fusion → Story.
        Returns (story_result, event_graph).
        """
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

        # Motion
        motion = MotionAnalyzer().analyze(tracks)

        # Events
        event_engine = EventUnderstandingEngine(
            config=EventUnderstandingConfig(min_event_confidence=0.0, min_track_frames_for_entry=2)
        )
        event_result = event_engine.understand(tracks, motion.motion_profiles, [])

        # Fusion
        cfg = FusionConfig(w_detection=0.20, w_motion=0.20, w_rule=0.20,
                           w_track_stability=0.20, w_scene_reliability=0.20,
                           min_fused_confidence=0.0)
        fusion_result = ConfidenceFuser(cfg).fuse(
            event_result.events, {t.track_id: t for t in tracks},
            motion.motion_profiles, []
        )

        # Story
        story_result = StoryBuilder().build(fusion_result.fused_events)
        event_graph = EventGraphBuilder().build(fusion_result.fused_events)

        return story_result, event_graph, fusion_result

    def test_integration_single_person_gets_story_segment(self):
        bboxes = {1: [(0.1 + i*0.02, 0.1, 0.4 + i*0.02, 0.9) for i in range(8)]}
        story, graph, fusion = self._full_pipeline(bboxes)
        assert len(story.segments) >= 1
        assert len(graph.nodes) == len(fusion.fused_events)

    def test_integration_two_people_get_two_segments(self):
        bboxes = {
            1: [(0.1 + i*0.02, 0.1, 0.3 + i*0.02, 0.9) for i in range(6)],
            2: [(0.6 + i*0.01, 0.1, 0.9 + i*0.01, 0.9) for i in range(6)],
        }
        story, graph, fusion = self._full_pipeline(bboxes)
        assert len(story.segments) >= 2
        track_ids_seen = set()
        for seg in story.segments:
            track_ids_seen.update(seg.track_ids)
        assert len(track_ids_seen) >= 2

    def test_integration_graph_has_same_track_edges(self):
        bboxes = {1: [(0.1 + i*0.02, 0.1, 0.4 + i*0.02, 0.9) for i in range(6)]}
        story, graph, fusion = self._full_pipeline(bboxes)
        same_track_edges = [e for e in graph.edges
                            if e.relationship == EdgeRelationship.SAME_TRACK_TEMPORAL]
        assert len(same_track_edges) >= 1

    def test_integration_narrative_scores_nonzero(self):
        bboxes = {1: [(0.1 + i*0.02, 0.1, 0.4 + i*0.02, 0.9) for i in range(8)]}
        story, _, _ = self._full_pipeline(bboxes)
        for seg in story.segments:
            assert seg.narrative_score > 0.0

    def test_integration_segments_ranked_descending(self):
        bboxes = {
            1: [(0.1 + i*0.02, 0.1, 0.4 + i*0.02, 0.9) for i in range(8)],
            2: [(0.6, 0.1, 0.9, 0.9)],  # single event → lower score
        }
        story, _, _ = self._full_pipeline(bboxes)
        ranked = story.ranked_segments()
        for i in range(len(ranked) - 1):
            assert ranked[i].narrative_score >= ranked[i + 1].narrative_score


# ---------------------------------------------------------------------------
# s09_story_build pipeline stage tests
# ---------------------------------------------------------------------------

class TestS09StoryBuild:
    def _make_context(self, events=None):
        from app.pipeline.context import PipelineContext
        ctx = PipelineContext(
            job_id="JOB-TEST", video_id="test", video_path="/tmp/v.mp4",
            output_dir="/tmp", settings={}, metadata={},
        )
        if events is not None:
            ctx.metadata["events"] = events
        return ctx

    @pytest.mark.asyncio
    async def test_missing_events_fails(self):
        from app.pipeline.stages import s09_story_build
        ctx = self._make_context()
        result = await s09_story_build.run(ctx)
        assert result.success is False
        assert any("events" in e for e in result.errors)

    @pytest.mark.asyncio
    @patch("app.pipeline.stages.s09_story_build.save_stage_metrics")
    async def test_empty_events_returns_success(self, mock_save):
        from app.pipeline.stages import s09_story_build
        mock_save.return_value = None
        ctx = self._make_context(events=[])
        result = await s09_story_build.run(ctx)
        assert result.success is True
        assert ctx.metadata["story_segments"] == []
        assert ctx.metadata["ranked_segments"] == []

    @pytest.mark.asyncio
    @patch("app.pipeline.stages.s09_story_build.save_stage_metrics")
    async def test_events_produce_segments_and_graph(self, mock_save):
        from app.pipeline.stages import s09_story_build
        mock_save.return_value = None
        events = _person_arc(1)
        ctx = self._make_context(events=events)
        result = await s09_story_build.run(ctx)
        assert result.success is True
        assert len(ctx.metadata["story_segments"]) >= 1
        assert ctx.metadata["event_graph"] is not None

    @pytest.mark.asyncio
    async def test_stage_name_correct(self):
        from app.pipeline.stages import s09_story_build
        ctx = self._make_context()
        result = await s09_story_build.run(ctx)
        assert result.stage_name == "s09_story_build"
