"""
Tests: Failure Catalogue (Phase 4).
"""
import json
import pytest
from app.utils.failure_catalogue import FailureCatalogue, FailureRecord


def _add_sample(cat, video_id="vid1", category="MISSED_EVENT", severity="MAJOR"):
    return cat.add(
        video_id=video_id,
        category=category,
        severity=severity,
        description="Test failure",
        stage="s04_object_detect",
        possible_cause="Synthetic video",
    )


def test_add_returns_failure_record():
    cat = FailureCatalogue()
    rec = _add_sample(cat)
    assert isinstance(rec, FailureRecord)
    assert rec.failure_id == "FAIL-001"
    assert rec.category == "MISSED_EVENT"
    assert rec.severity == "MAJOR"


def test_failure_ids_increment():
    cat = FailureCatalogue()
    r1 = _add_sample(cat)
    r2 = _add_sample(cat)
    r3 = _add_sample(cat)
    assert r1.failure_id == "FAIL-001"
    assert r2.failure_id == "FAIL-002"
    assert r3.failure_id == "FAIL-003"


def test_invalid_category_raises():
    cat = FailureCatalogue()
    with pytest.raises(ValueError, match="Invalid category"):
        cat.add("vid", "NOT_A_CATEGORY", "MAJOR", "desc", "s04")


def test_invalid_severity_raises():
    cat = FailureCatalogue()
    with pytest.raises(ValueError, match="Invalid severity"):
        cat.add("vid", "MISSED_EVENT", "CATASTROPHIC", "desc", "s04")


def test_statistics_empty():
    cat = FailureCatalogue()
    stats = cat.statistics()
    assert stats["total"] == 0
    assert stats["most_common_failure"] is None


def test_statistics_by_category():
    cat = FailureCatalogue()
    _add_sample(cat, category="MISSED_EVENT")
    _add_sample(cat, category="MISSED_EVENT")
    _add_sample(cat, category="FALSE_EVENT")
    stats = cat.statistics()
    assert stats["total"] == 3
    assert stats["failure_count_by_category"]["MISSED_EVENT"] == 2
    assert stats["failure_count_by_category"]["FALSE_EVENT"] == 1
    assert stats["most_common_failure"] == "MISSED_EVENT"


def test_statistics_most_implicated_stage():
    cat = FailureCatalogue()
    cat.add("v", "MISSED_EVENT", "MAJOR", "d", "s04_object_detect")
    cat.add("v", "MISSED_EVENT", "MAJOR", "d", "s04_object_detect")
    cat.add("v", "FALSE_EVENT",  "MINOR", "d", "s07_event_understand")
    stats = cat.statistics()
    assert stats["most_implicated_stage"] == "s04_object_detect"


def test_save_creates_json(tmp_path):
    cat = FailureCatalogue()
    _add_sample(cat)
    _add_sample(cat, category="FALSE_EVENT", severity="MINOR")
    path = cat.save(tmp_path, run_id="test")
    assert (tmp_path / "catalogue-test.json").exists()
    data = json.loads((tmp_path / "catalogue-test.json").read_text())
    assert len(data["failures"]) == 2


def test_save_creates_markdown_for_major(tmp_path):
    cat = FailureCatalogue()
    rec = _add_sample(cat, severity="MAJOR")
    cat.save(tmp_path)
    md = tmp_path / f"{rec.failure_id}.md"
    assert md.exists()
    content = md.read_text()
    assert "MISSED_EVENT" in content
    assert "MAJOR" in content


def test_save_no_markdown_for_minor(tmp_path):
    cat = FailureCatalogue()
    rec = _add_sample(cat, severity="MINOR")
    cat.save(tmp_path)
    md = tmp_path / f"{rec.failure_id}.md"
    assert not md.exists()


def test_load_roundtrip(tmp_path):
    cat = FailureCatalogue()
    _add_sample(cat, category="TRACKING_FAILURE", severity="CRITICAL")
    _add_sample(cat, category="COMPRESSION_ERROR", severity="MINOR")
    path = cat.save(tmp_path)
    loaded = FailureCatalogue.load(path)
    assert len(loaded.failures) == 2
    assert loaded.failures[0].category == "TRACKING_FAILURE"
    assert loaded.failures[1].category == "COMPRESSION_ERROR"
    # Counter should be synced
    r3 = _add_sample(loaded)
    assert r3.failure_id == "FAIL-003"


def test_all_valid_categories():
    cat = FailureCatalogue()
    for cat_name in [
        "MISSED_EVENT", "FALSE_EVENT", "TRACKING_FAILURE",
        "STORY_BREAK", "COMPRESSION_ERROR", "VALIDATOR_WARNING",
    ]:
        r = cat.add("v", cat_name, "INFORMATIONAL", "test", "s01")
        assert r.category == cat_name


def test_all_valid_severities():
    cat = FailureCatalogue()
    for sev in ["CRITICAL", "MAJOR", "MINOR", "INFORMATIONAL"]:
        r = cat.add("v", "MISSED_EVENT", sev, "test", "s01")
        assert r.severity == sev
