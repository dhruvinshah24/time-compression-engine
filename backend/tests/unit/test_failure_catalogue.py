"""
Tests for the failure catalogue — Phase 11 evaluation tool.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from app.evaluation.failure_catalogue import (
    FailureCatalogue,
    FailureCategory,
    FailureRecord,
    FailureSeverity,
)


def _record(
    video_id: str = "vid_01",
    category: FailureCategory = FailureCategory.MISSED_EVENT,
    severity: FailureSeverity = FailureSeverity.MAJOR,
    stage: str = "s04_object_detect",
) -> FailureRecord:
    return FailureRecord(
        video_id=video_id,
        timestamp_ms=1200.0,
        category=category,
        severity=severity,
        description="Person entered but pipeline produced no entry event.",
        ground_truth="PERSON_ENTERED_SCENE at 1200ms",
        pipeline_output="No event produced",
        pipeline_stage=stage,
        improvement_hypothesis="Increase detection confidence or lower entry threshold.",
    )


class TestFailureCatalogue:
    def test_add_and_count(self):
        cat = FailureCatalogue()
        cat.add(_record())
        assert len(cat.records) == 1

    def test_by_category(self):
        cat = FailureCatalogue()
        cat.add(_record(category=FailureCategory.MISSED_EVENT))
        cat.add(_record(category=FailureCategory.FALSE_EVENT))
        assert len(cat.by_category(FailureCategory.MISSED_EVENT)) == 1

    def test_by_severity(self):
        cat = FailureCatalogue()
        cat.add(_record(severity=FailureSeverity.CRITICAL))
        cat.add(_record(severity=FailureSeverity.MINOR))
        assert len(cat.by_severity(FailureSeverity.CRITICAL)) == 1
        assert len(cat.by_severity(FailureSeverity.MINOR)) == 1
        assert len(cat.by_severity(FailureSeverity.INFORMATIONAL)) == 0

    def test_by_video(self):
        cat = FailureCatalogue()
        cat.add(_record(video_id="vid_01"))
        cat.add(_record(video_id="vid_02"))
        assert len(cat.by_video("vid_01")) == 1

    def test_by_stage(self):
        cat = FailureCatalogue()
        cat.add(_record(stage="s04_object_detect"))
        cat.add(_record(stage="s09_story_build"))
        assert len(cat.by_stage("s04_object_detect")) == 1

    def test_summary_has_required_keys(self):
        cat = FailureCatalogue()
        cat.add(_record())
        s = cat.summary()
        for key in ["total_failures", "videos_analysed", "by_category",
                    "by_severity", "most_common_failure", "most_implicated_stage"]:
            assert key in s

    def test_summary_empty_catalogue(self):
        cat = FailureCatalogue()
        s = cat.summary()
        assert s["total_failures"] == 0

    def test_most_common_failure_identified(self):
        cat = FailureCatalogue()
        cat.add(_record(category=FailureCategory.MISSED_EVENT))
        cat.add(_record(category=FailureCategory.MISSED_EVENT))
        cat.add(_record(category=FailureCategory.FALSE_EVENT))
        assert cat.summary()["most_common_failure"] == "missed_event"

    def test_critical_count_in_summary(self):
        cat = FailureCatalogue()
        cat.add(_record(severity=FailureSeverity.CRITICAL))
        cat.add(_record(severity=FailureSeverity.MAJOR))
        cat.add(_record(severity=FailureSeverity.INFORMATIONAL))
        assert cat.summary()["critical_count"] == 1

    def test_all_four_severities_representable(self):
        cat = FailureCatalogue()
        for sev in FailureSeverity:
            cat.add(_record(severity=sev))
        assert len(cat.records) == 4
        summary = cat.summary()
        for sev in FailureSeverity:
            assert sev.value in summary["by_severity"]

    def test_markdown_table_renders(self):
        cat = FailureCatalogue()
        cat.add(_record())
        md = cat.to_markdown_table()
        assert "| Failure Category |" in md
        assert "missed_event" in md
        assert "|" in md

    def test_save_and_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "failures.json"
            cat = FailureCatalogue()
            cat.add(_record(video_id="roundtrip_vid"))
            cat.save(path)

            assert path.exists()
            loaded = FailureCatalogue.load(path)
            assert len(loaded.records) == 1
            assert loaded.records[0].video_id == "roundtrip_vid"
            assert loaded.records[0].category == FailureCategory.MISSED_EVENT

    def test_save_json_valid(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "out.json"
            cat = FailureCatalogue()
            cat.add(_record())
            cat.save(path)

            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            assert "records" in data
            assert "summary" in data
            assert data["total_records"] == 1

    def test_all_six_categories_representable(self):
        cat = FailureCatalogue()
        for fc in FailureCategory:
            cat.add(_record(category=fc))
        assert len(cat.records) == 6
        summary = cat.summary()
        for fc in FailureCategory:
            assert fc.value in summary["by_category"]

    def test_improvement_hypothesis_preserved(self):
        rec = _record()
        rec.improvement_hypothesis = "Test hypothesis"
        cat = FailureCatalogue()
        cat.add(rec)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "out.json"
            cat.save(path)
            loaded = FailureCatalogue.load(path)
            assert loaded.records[0].improvement_hypothesis == "Test hypothesis"
