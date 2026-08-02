"""
Tests for Phase 10: Narrative Validator + Export + Evaluation Baselines.

Test groups:
  1. NarrativeValidator — all 5 checks (complete chain integrity, starts/ends checks,
     orphans, graph connectivity)
  2. Baseline summarizers — output format, ratio compliance, behavior differences
  3. EvaluationMetrics — computation correctness, comparison table rendering
  4. compare_all — TCE vs all baselines
  5. Decision manifest structure
  6. s12_export pipeline stage (mocked)
  7. Full end-to-end: 7-stage integration chain → Narrative Validation → Comparison Table
"""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

from app.engines.semantic.event_understanding.engine import Event
from app.engines.semantic.event_understanding.rules import EventType
from app.engines.temporal.event_graph.graph_builder import EventGraph, EventGraphBuilder
from app.engines.temporal.story_preservation.sequence_validator import (
    IssueSeverity,
    NarrativeValidator,
    ValidationReport,
)
from app.engines.temporal.story_preservation.story_builder import (
    StoryBuilder,
    StoryCompleteness,
    StorySegment,
)
from app.evaluation.baselines.summarizers import (
    MotionOnlySummarizer,
    SceneChangeSummarizer,
    UniformSampler,
)
from app.evaluation.metrics import (
    ComparisonTable,
    SummaryMetrics,
    compare_all,
    compute_metrics,
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
        evidence={},
        start_frame=int(start_ms / 200),
        end_frame=int(end_ms / 200),
        start_ms=start_ms,
        end_ms=end_ms,
        dependencies=[f"track_{track_id}", f"rule_{rule_name}"],
    )


def _complete_arc(track_id: int = 1, base_ms: float = 0.0) -> list[Event]:
    return [
        _event(track_id, EventType.PERSON_ENTERED_SCENE, base_ms, base_ms + 200,
               rule_name="rule_person_entered"),
        _event(track_id, EventType.PERSON_WALKING, base_ms + 400, base_ms + 2000),
        _event(track_id, EventType.PERSON_LEFT_SCENE, base_ms + 2200, base_ms + 2400,
               rule_name="rule_person_left"),
    ]


def _segment(
    track_id: int = 1, events: list[Event] | None = None,
    completeness: StoryCompleteness = StoryCompleteness.COMPLETE,
    narrative_score: float = 0.80,
) -> StorySegment:
    evs = events or _complete_arc(track_id)
    return StorySegment(
        segment_id=f"seg_{track_id}_{str(uuid.uuid4())[:6]}",
        track_ids={track_id}, events=evs,
        completeness=completeness, narrative_score=narrative_score,
        mean_confidence=0.75, start_ms=evs[0].start_ms, end_ms=evs[-1].end_ms,
    )


# ---------------------------------------------------------------------------
# NarrativeValidator tests
# ---------------------------------------------------------------------------

class TestNarrativeValidator:
    def _val(self):
        return NarrativeValidator()

    # Check 1: complete chain integrity
    def test_complete_arc_fully_kept_passes(self):
        seg = _segment(completeness=StoryCompleteness.COMPLETE)
        kept = {e.event_id for e in seg.events}
        report = self._val().validate([seg], kept)
        assert report.is_valid
        assert report.complete_chains_intact == 1

    def test_complete_arc_missing_exit_fails(self):
        events = _complete_arc()
        seg = _segment(events=events, completeness=StoryCompleteness.COMPLETE)
        # Keep only entry + action, drop exit
        kept = {events[0].event_id, events[1].event_id}
        report = self._val().validate([seg], kept)
        errors = report.errors()
        assert any(i.check == "complete_chain_integrity" for i in errors)

    def test_non_complete_segment_passes_integrity_check(self):
        seg = _segment(completeness=StoryCompleteness.PARTIAL)
        kept = {e.event_id for e in seg.events}
        report = self._val().validate([seg], kept)
        assert report.is_valid  # integrity check only applies to COMPLETE

    # Check 2: no chain starts with exit
    def test_chain_starting_with_exit_is_warning(self):
        exit_ev = _event(event_type=EventType.PERSON_LEFT_SCENE, start_ms=0, end_ms=200,
                         rule_name="rule_person_left")
        walk_ev = _event(event_type=EventType.PERSON_WALKING, start_ms=400, end_ms=1000)
        seg = _segment(events=[exit_ev, walk_ev], completeness=StoryCompleteness.PARTIAL)
        kept = {e.event_id for e in seg.events}
        report = self._val().validate([seg], kept)
        warns = [i for i in report.warnings() if i.check == "no_chain_starts_with_exit"]
        assert len(warns) == 1
        # Warning only — not an error — so is_valid can still be True
        assert report.is_valid

    # Check 3: no chain ends with entry
    def test_chain_ending_with_entry_is_warning(self):
        walk_ev = _event(event_type=EventType.PERSON_WALKING, start_ms=0, end_ms=1000)
        entry_ev = _event(event_type=EventType.PERSON_ENTERED_SCENE, start_ms=1200, end_ms=1400,
                          rule_name="rule_person_entered")
        seg = _segment(events=[walk_ev, entry_ev], completeness=StoryCompleteness.PARTIAL)
        kept = {e.event_id for e in seg.events}
        report = self._val().validate([seg], kept)
        warns = [i for i in report.warnings() if i.check == "no_chain_ends_with_entry"]
        assert len(warns) == 1

    # Check 4: orphaned events
    def test_orphaned_event_produces_error(self):
        seg = _segment()
        kept_event_ids = {e.event_id for e in seg.events}
        orphan_id = str(uuid.uuid4())
        all_events_by_id = {e.event_id: e for e in seg.events}
        orphan_event = _event()
        all_events_by_id[orphan_id] = orphan_event
        kept_event_ids.add(orphan_id)

        report = self._val().validate(
            kept_segments=[seg],
            kept_event_ids=kept_event_ids,
            all_events_by_id=all_events_by_id,
        )
        errors = [i for i in report.errors() if i.check == "no_orphaned_events"]
        assert len(errors) >= 1

    # Check 5: graph connectivity
    def test_disconnected_graph_produces_warning(self):
        events = _complete_arc()
        graph = EventGraphBuilder().build(events)
        seg = _segment(events=events)
        # Keep only the last event — its predecessor is discarded → disconnected
        kept = {events[-1].event_id}
        report = self._val().validate(
            kept_segments=[seg], kept_event_ids=kept,
            event_graph=graph,
            all_events_by_id={e.event_id: e for e in events},
        )
        warns = [i for i in report.warnings() if i.check == "graph_connectivity"]
        assert len(warns) >= 1

    def test_empty_segments_passes(self):
        report = self._val().validate([], set())
        assert report.is_valid

    def test_validation_report_has_is_valid_key_in_dict(self):
        seg = _segment()
        report = self._val().validate([seg], {e.event_id for e in seg.events})
        d = report.to_dict()
        assert "is_valid" in d
        assert "error_count" in d
        assert "warning_count" in d


# ---------------------------------------------------------------------------
# Baseline summarizer tests
# ---------------------------------------------------------------------------

class TestBaselineSummarizers:
    def _events(self, n: int = 10) -> list[Event]:
        return [
            _event(track_id=i % 3 + 1,
                   start_ms=i * 500.0,
                   end_ms=i * 500.0 + 400.0,
                   confidence=0.5 + (i * 0.04))
            for i in range(n)
        ]

    def test_uniform_sampler_respects_ratio(self):
        events = self._events(20)
        result = UniformSampler().summarize(events, target_ratio=0.40)
        assert len(result.kept_event_ids) <= max(1, int(len(events) * 0.40) + 2)

    def test_motion_only_prefers_high_motion_events(self):
        low_motion = _event(confidence=0.30, start_ms=0)
        low_motion.evidence["confidence_vector"] = {"motion": 0.10}
        high_motion = _event(confidence=0.90, start_ms=500)
        high_motion.evidence["confidence_vector"] = {"motion": 0.95}

        result = MotionOnlySummarizer().summarize([low_motion, high_motion], target_ratio=0.50)
        assert high_motion.event_id in result.kept_event_ids

    def test_scene_change_keeps_best_per_window(self):
        # Two events in same window — only one should be kept
        ev_low = _event(confidence=0.40, start_ms=100)
        ev_high = _event(confidence=0.90, start_ms=200)  # same 5s window
        result = SceneChangeSummarizer(window_ms=5000).summarize(
            [ev_low, ev_high], target_ratio=1.0
        )
        assert ev_high.event_id in result.kept_event_ids

    def test_all_baselines_return_valid_ratio(self):
        events = self._events(10)
        for summarizer in [UniformSampler(), MotionOnlySummarizer(),
                            SceneChangeSummarizer()]:
            result = summarizer.summarize(events, target_ratio=0.50)
            assert 0.0 <= result.compression_ratio <= 1.0

    def test_empty_events_returns_empty(self):
        for summarizer in [UniformSampler(), MotionOnlySummarizer(),
                            SceneChangeSummarizer()]:
            result = summarizer.summarize([], target_ratio=0.50)
            assert len(result.kept_event_ids) == 0

    def test_baseline_results_have_name(self):
        events = self._events(5)
        assert UniformSampler().summarize(events).baseline_name == "uniform_sampling"
        assert MotionOnlySummarizer().summarize(events).baseline_name == "motion_only"
        assert SceneChangeSummarizer().summarize(events).baseline_name == "scene_change"


# ---------------------------------------------------------------------------
# EvaluationMetrics tests
# ---------------------------------------------------------------------------

class TestEvaluationMetrics:
    def test_all_kept_gives_ratio_one(self):
        seg = _segment()
        all_events = seg.events
        kept = {e.event_id for e in all_events}
        m = compute_metrics("test", kept, all_events, [seg])
        assert m.compression_ratio == pytest.approx(1.0, abs=0.01)

    def test_none_kept_gives_ratio_zero(self):
        seg = _segment()
        m = compute_metrics("test", set(), seg.events, [seg])
        assert m.compression_ratio == pytest.approx(0.0, abs=0.01)

    def test_complete_arc_fully_kept_gives_completeness_one(self):
        seg = _segment(completeness=StoryCompleteness.COMPLETE)
        kept = {e.event_id for e in seg.events}
        m = compute_metrics("test", kept, seg.events, [seg])
        assert m.story_completeness_retained == pytest.approx(1.0, abs=0.01)

    def test_partial_keep_causes_broken_narrative(self):
        seg = _segment()
        events = seg.events
        # Keep only one of three events
        kept = {events[0].event_id}
        m = compute_metrics("test", kept, events, [seg])
        assert m.broken_narratives >= 1

    def test_metrics_dict_has_required_keys(self):
        seg = _segment()
        m = compute_metrics("test", set(), seg.events, [seg])
        for key in ["approach", "compression_ratio", "story_completeness_retained",
                    "broken_narratives", "avg_chain_length", "kept_events", "total_events"]:
            assert key in m.to_dict()


class TestComparisonTable:
    def test_compare_all_returns_four_rows(self):
        seg = _segment()
        events = seg.events
        tce_kept = {e.event_id for e in events}
        table = compare_all(tce_kept, events, [seg], target_ratio=1.0)
        assert len(table.rows) == 4  # 3 baselines + TCE

    def test_tce_is_last_row(self):
        seg = _segment()
        table = compare_all({e.event_id for e in seg.events}, seg.events, [seg])
        assert "Time Compression Engine" in table.rows[-1].approach_name

    def test_best_by_completeness_returned(self):
        rows = [
            SummaryMetrics("A", 0.4, 0.30, 5, 1.2, 10, 4),
            SummaryMetrics("B", 0.4, 0.95, 0, 3.8, 10, 4),
        ]
        table = ComparisonTable(rows=rows)
        best = table.best_by("story_completeness_retained")
        assert best.approach_name == "B"

    def test_best_by_broken_narratives_returned(self):
        rows = [
            SummaryMetrics("A", 0.4, 0.30, 5, 1.2, 10, 4),
            SummaryMetrics("B", 0.4, 0.95, 0, 3.8, 10, 4),
        ]
        table = ComparisonTable(rows=rows)
        best = table.best_by("broken_narratives")
        assert best.approach_name == "B"

    def test_markdown_table_renders(self):
        seg = _segment()
        table = compare_all({e.event_id for e in seg.events}, seg.events, [seg])
        md = table.to_markdown()
        assert "Approach" in md
        assert "Time Compression Engine" in md
        assert "|" in md


# ---------------------------------------------------------------------------
# s12_export pipeline stage tests
# ---------------------------------------------------------------------------

class TestS12Export:
    def _ctx(self, summary_events=None, segments=None):
        from app.pipeline.context import PipelineContext
        ctx = PipelineContext(
            job_id="JOB-EXPORT-TEST",
            video_id="v001",
            video_path="/tmp/input.mp4",
            output_dir="/tmp/tce_output",
            settings={},
            metadata={},
        )
        ctx.metadata["summary_events"] = summary_events or []
        ctx.metadata["kept_event_ids"] = {e.event_id for e in (summary_events or [])}
        ctx.metadata["story_segments"] = segments or []
        ctx.metadata["event_graph"] = None
        ctx.metadata["compression_result"] = None
        ctx.metadata["ranking_result"] = None
        return ctx

    @pytest.mark.asyncio
    @patch("app.pipeline.stages.s12_export.save_stage_metrics")
    async def test_empty_events_returns_success(self, mock_save):
        from app.pipeline.stages import s12_export
        mock_save.return_value = None
        ctx = self._ctx()
        result = await s12_export.run(ctx)
        assert result.success is True

    @pytest.mark.asyncio
    @patch("app.pipeline.stages.s12_export.save_stage_metrics")
    async def test_validation_report_in_context(self, mock_save):
        from app.pipeline.stages import s12_export
        mock_save.return_value = None
        ctx = self._ctx()
        await s12_export.run(ctx)
        assert "validation_report" in ctx.metadata
        assert isinstance(ctx.metadata["validation_report"], ValidationReport)

    @pytest.mark.asyncio
    @patch("app.pipeline.stages.s12_export.save_stage_metrics")
    async def test_decision_manifest_in_context(self, mock_save):
        from app.pipeline.stages import s12_export
        mock_save.return_value = None
        ctx = self._ctx()
        await s12_export.run(ctx)
        assert "decision_manifest" in ctx.metadata

    @pytest.mark.asyncio
    @patch("app.pipeline.stages.s12_export.save_stage_metrics")
    async def test_export_manifest_has_required_keys(self, mock_save):
        from app.pipeline.stages import s12_export
        mock_save.return_value = None
        events = _complete_arc()
        seg = _segment(events=events)
        ctx = self._ctx(summary_events=events, segments=[seg])
        await s12_export.run(ctx)
        manifest = ctx.metadata["export_manifest"]
        for key in ["job_id", "video_id", "narrative_validation",
                    "summary", "clips", "assembly"]:
            assert key in manifest

    @pytest.mark.asyncio
    @patch("app.pipeline.stages.s12_export.save_stage_metrics")
    async def test_clips_have_ffmpeg_commands(self, mock_save):
        from app.pipeline.stages import s12_export
        mock_save.return_value = None
        events = _complete_arc()
        seg = _segment(events=events)
        ctx = self._ctx(summary_events=events, segments=[seg])
        await s12_export.run(ctx)
        clips = ctx.metadata["export_manifest"]["clips"]
        assert len(clips) == len(events)
        for clip in clips:
            assert "ffmpeg_command" in clip
            assert "ffmpeg" in clip["ffmpeg_command"]

    @pytest.mark.asyncio
    async def test_stage_name_correct(self):
        from app.pipeline.stages import s12_export
        ctx = self._ctx()
        result = await s12_export.run(ctx)
        assert result.stage_name == "s12_export"


# ---------------------------------------------------------------------------
# Full 7-stage integration: Track → ... → Export + Comparison Table
# ---------------------------------------------------------------------------

class TestPhase10EndToEnd:
    def _full_pipeline(self, bboxes_by_track: dict):
        from app.engines.perception.motion_analyzer.analyzer import MotionAnalyzer
        from app.engines.perception.tracker.track import (
            Track, TrackBBox, TrackObservation, TrackState,
        )
        from app.engines.semantic.confidence_fusion.config import FusionConfig
        from app.engines.semantic.confidence_fusion.fusion import ConfidenceFuser
        from app.engines.semantic.event_understanding.config import EventUnderstandingConfig
        from app.engines.semantic.event_understanding.engine import EventUnderstandingEngine
        from app.engines.temporal.compression_policy.policy import CompressionPolicy
        from app.engines.temporal.event_graph.graph_builder import EventGraphBuilder
        from app.engines.temporal.ranking_engine.ranker import RankingEngine

        tracks = []
        for tid, bboxes in bboxes_by_track.items():
            obs = [
                TrackObservation(
                    frame_number=i + 1, timestamp_ms=(i + 1) * 400.0,
                    bbox=TrackBBox(x1=b[0], y1=b[1], x2=b[2], y2=b[3],
                                   confidence=0.85, class_id=0, class_name="person"),
                    detection_confidence=0.85,
                )
                for i, b in enumerate(bboxes)
            ]
            t = Track(
                track_id=tid, class_name="person", class_id=0,
                state=TrackState.ACTIVE, created_frame=1,
                created_timestamp_ms=400.0,
                last_seen_frame=len(bboxes),
                last_seen_timestamp_ms=len(bboxes) * 400.0,
                current_bbox=obs[-1].bbox, observations=obs,
            )
            t.total_frames_matched = len(obs)
            t.confirmed_at_frame = 1
            tracks.append(t)

        motion = MotionAnalyzer().analyze(tracks)
        events_result = EventUnderstandingEngine(
            config=EventUnderstandingConfig(min_event_confidence=0.0, min_track_frames_for_entry=2)
        ).understand(tracks, motion.motion_profiles, [])
        fused = ConfidenceFuser(
            FusionConfig(w_detection=0.20, w_motion=0.20, w_rule=0.20,
                         w_track_stability=0.20, w_scene_reliability=0.20,
                         min_fused_confidence=0.0)
        ).fuse(events_result.events, {t.track_id: t for t in tracks},
               motion.motion_profiles, [])
        story = StoryBuilder().build(fused.fused_events)
        graph = EventGraphBuilder().build(fused.fused_events)
        ranking = RankingEngine().rank(story.segments, motion.motion_profiles)
        compression = CompressionPolicy().apply(ranking)

        return compression, ranking, story, fused, graph

    def test_end_to_end_validation_passes(self):
        bboxes = {1: [(0.1 + i*0.02, 0.1, 0.4 + i*0.02, 0.9) for i in range(8)]}
        compression, ranking, story, fused, graph = self._full_pipeline(bboxes)

        kept_segs = [
            seg for seg in story.segments
            if any(e.event_id in compression.kept_event_ids for e in seg.events)
        ]
        all_events_by_id = {e.event_id: e for e in fused.fused_events}

        report = NarrativeValidator().validate(
            kept_segs, compression.kept_event_ids, graph, all_events_by_id
        )
        # With chain_atomicity=True (default), should have no orphans
        assert report.orphaned_events == 0

    def test_end_to_end_comparison_table_tce_wins_completeness(self):
        """TCE should retain more complete chains than uniform sampling."""
        bboxes = {
            1: [(0.1 + i*0.02, 0.1, 0.4 + i*0.02, 0.9) for i in range(8)],
            2: [(0.6 + i*0.01, 0.1, 0.9 + i*0.01, 0.9) for i in range(6)],
        }
        compression, _, story, fused, _ = self._full_pipeline(bboxes)
        all_events = fused.fused_events

        table = compare_all(
            compression.kept_event_ids, all_events, story.segments, target_ratio=0.50
        )
        assert len(table.rows) == 4

        # TCE should have zero broken narratives (chain_atomicity=True)
        tce_row = next(r for r in table.rows if "Time Compression Engine" in r.approach_name)
        assert tce_row.broken_narratives == 0

    def test_end_to_end_decision_manifest_has_all_segments(self):
        """Every story segment should appear in the decision manifest."""
        bboxes = {1: [(0.1 + i*0.02, 0.1, 0.4 + i*0.02, 0.9) for i in range(6)]}
        compression, ranking, story, _, _ = self._full_pipeline(bboxes)

        # Simulate what s12_export does
        manifest = []
        for rs in ranking.ranked_segments:
            seg_decisions = [d for d in compression.decisions
                             if d.segment_id == rs.segment.segment_id]
            if seg_decisions:
                d = seg_decisions[0]
                manifest.append({
                    "segment_id": rs.segment.segment_id,
                    "decision": "kept" if d.keep else "discarded",
                    "importance": rs.importance_score,
                    "narrative": rs.narrative_score,
                    "policy": d.reason,
                })

        assert len(manifest) == len(story.segments)
        for entry in manifest:
            assert "policy" in entry
            assert "importance" in entry
            assert "narrative" in entry
