"""
Failure Catalogue — Phase 11 Evaluation Tool.

Per mentor recommendation:
  "For every incorrect result, classify it. After evaluating a few dozen videos,
   you'll have a much clearer picture of where the system needs improvement than
   you would from Precision/Recall alone. That failure catalogue often becomes
   one of the most valuable sections of a research report."

Usage during benchmark runs:
  1. Run the full TCE pipeline on a benchmark video with ground truth annotations.
  2. For each discrepancy between TCE output and ground truth, create a FailureRecord.
  3. Call catalogue.add(record) and save to reports/failures/<video_id>.json.
  4. At the end of benchmarking, call catalogue.summary() for aggregate analysis.

The six failure categories (per mentor):
  MISSED_EVENT       — real event in ground truth, not produced by pipeline
  FALSE_EVENT        — event produced by pipeline, not in ground truth
  TRACKING_FAILURE   — track identity switch broke narrative continuity
  STORY_BREAK        — a chain that should be complete was split at compression
  COMPRESSION_ERROR  — a segment the evaluator judged important was discarded
  VALIDATOR_WARNING  — NarrativeValidator flagged a structural inconsistency

The catalogue is intentionally simple — a structured list, not a database.
Simplicity matters: during benchmarking you want to add failures quickly,
not maintain complex infrastructure.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path


# ---------------------------------------------------------------------------
# Failure taxonomy
# ---------------------------------------------------------------------------

class FailureCategory(str, Enum):
    """
    The six failure categories from the mentor's recommendation.

    Each category naturally motivates a specific improvement direction:

    MISSED_EVENT      → improve detection sensitivity or tracking recall
    FALSE_EVENT       → tighten rule conditions or raise confidence threshold
    TRACKING_FAILURE  → upgrade to SORT/DeepSORT, add ReID module
    STORY_BREAK       → tune chain_atomicity or completeness_min_threshold
    COMPRESSION_ERROR → adjust w_narrative or target_ratio
    VALIDATOR_WARNING → investigate compression_policy + chain_atomicity settings
    """
    MISSED_EVENT = "missed_event"
    FALSE_EVENT = "false_event"
    TRACKING_FAILURE = "tracking_failure"
    STORY_BREAK = "story_break"
    COMPRESSION_ERROR = "compression_error"
    VALIDATOR_WARNING = "validator_warning"


class FailureSeverity(str, Enum):
    CRITICAL      = "critical"       # Changes the narrative or produces an incorrect summary
    MAJOR         = "major"          # Loses an important event but overall story remains understandable
    MINOR         = "minor"          # Cosmetic or low-impact issue
    INFORMATIONAL = "informational"  # Worth noting but doesn't affect the final summary


# ---------------------------------------------------------------------------
# FailureRecord
# ---------------------------------------------------------------------------

@dataclass
class FailureRecord:
    """
    One failure on one benchmark video.

    All fields are intentionally human-readable strings — this is filled in
    by the researcher during analysis, not automatically by the pipeline.

    Fields:
        video_id:           Benchmark video identifier
        timestamp_ms:       Where in the video this failure occurs
        category:           One of the six FailureCategory values
        severity:           CRITICAL / MODERATE / MINOR
        description:        Human-readable description of what went wrong
        ground_truth:       What the annotator said should have happened
        pipeline_output:    What the pipeline actually produced
        pipeline_stage:     Which stage caused the failure (e.g. "s04_object_detect")
        improvement_hypothesis: What change might fix this (for future work section)
        event_ids:          Relevant event IDs from the TCE output (if available)
        notes:              Any additional context
    """
    video_id: str
    timestamp_ms: float
    category: FailureCategory
    severity: FailureSeverity
    description: str
    ground_truth: str
    pipeline_output: str
    pipeline_stage: str = ""
    improvement_hypothesis: str = ""
    event_ids: list[str] = field(default_factory=list)
    notes: str = ""
    recorded_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        return {
            "video_id": self.video_id,
            "timestamp_ms": self.timestamp_ms,
            "category": self.category.value,
            "severity": self.severity.value,
            "description": self.description,
            "ground_truth": self.ground_truth,
            "pipeline_output": self.pipeline_output,
            "pipeline_stage": self.pipeline_stage,
            "improvement_hypothesis": self.improvement_hypothesis,
            "event_ids": self.event_ids,
            "notes": self.notes,
            "recorded_at": self.recorded_at,
        }


# ---------------------------------------------------------------------------
# FailureCatalogue
# ---------------------------------------------------------------------------

@dataclass
class FailureCatalogue:
    """
    Structured collection of failures across all benchmark videos.

    Typical workflow:
        catalogue = FailureCatalogue()
        catalogue.add(FailureRecord(...))
        catalogue.save("reports/failures/video_01.json")
        print(catalogue.summary())
    """
    records: list[FailureRecord] = field(default_factory=list)

    def add(self, record: FailureRecord) -> None:
        self.records.append(record)

    def by_category(self, category: FailureCategory) -> list[FailureRecord]:
        return [r for r in self.records if r.category == category]

    def by_severity(self, severity: FailureSeverity) -> list[FailureRecord]:
        return [r for r in self.records if r.severity == severity]

    def by_video(self, video_id: str) -> list[FailureRecord]:
        return [r for r in self.records if r.video_id == video_id]

    def by_stage(self, stage_name: str) -> list[FailureRecord]:
        return [r for r in self.records if r.pipeline_stage == stage_name]

    def summary(self) -> dict:
        """
        Aggregate summary across all records.

        This produces the table that goes into the Phase 11 research report.
        """
        total = len(self.records)
        if total == 0:
            return {"total_failures": 0}

        by_cat = {cat.value: 0 for cat in FailureCategory}
        by_sev = {sev.value: 0 for sev in FailureSeverity}
        by_stage: dict[str, int] = {}
        videos: set[str] = set()

        for r in self.records:
            by_cat[r.category.value] += 1
            by_sev[r.severity.value] += 1
            by_stage[r.pipeline_stage] = by_stage.get(r.pipeline_stage, 0) + 1
            videos.add(r.video_id)

        # Most common failure mode
        top_category = max(by_cat, key=by_cat.get)
        # Stage most implicated
        top_stage = max(by_stage, key=by_stage.get) if by_stage else "unknown"

        return {
            "total_failures": total,
            "videos_analysed": len(videos),
            "by_category": by_cat,
            "by_severity": by_sev,
            "by_stage": dict(sorted(by_stage.items(), key=lambda x: -x[1])),
            "most_common_failure": top_category,
            "most_implicated_stage": top_stage,
            "critical_count": by_sev.get("critical", 0),
        }

    def to_markdown_table(self) -> str:
        """
        Render the category breakdown as a markdown table for the research report.
        """
        summary = self.summary()
        by_cat = summary.get("by_category", {})
        total = summary.get("total_failures", 0)

        header = (
            "| Failure Category | Count | % of Total | Motivates |\n"
            "|---|---|---|---|\n"
        )
        improvement_map = {
            "missed_event": "Higher detection sensitivity / tracking recall",
            "false_event": "Stricter rule conditions / confidence threshold",
            "tracking_failure": "SORT/DeepSORT / ReID module",
            "story_break": "Tune chain_atomicity / completeness threshold",
            "compression_error": "Adjust narrative weight / target_ratio",
            "validator_warning": "Review compression_policy settings",
        }
        rows = ""
        for cat, count in sorted(by_cat.items(), key=lambda x: -x[1]):
            pct = f"{count / total:.0%}" if total > 0 else "0%"
            improvement = improvement_map.get(cat, "—")
            rows += f"| {cat} | {count} | {pct} | {improvement} |\n"

        return header + rows

    def save(self, path: str | Path) -> None:
        """Save the catalogue to a JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_records": len(self.records),
            "summary": self.summary(),
            "records": [r.to_dict() for r in self.records],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    @classmethod
    def load(cls, path: str | Path) -> "FailureCatalogue":
        """Load a previously saved catalogue."""
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        catalogue = cls()
        for rec in data.get("records", []):
            catalogue.add(FailureRecord(
                video_id=rec["video_id"],
                timestamp_ms=rec["timestamp_ms"],
                category=FailureCategory(rec["category"]),
                severity=FailureSeverity(rec["severity"]),
                description=rec["description"],
                ground_truth=rec["ground_truth"],
                pipeline_output=rec["pipeline_output"],
                pipeline_stage=rec.get("pipeline_stage", ""),
                improvement_hypothesis=rec.get("improvement_hypothesis", ""),
                event_ids=rec.get("event_ids", []),
                notes=rec.get("notes", ""),
                recorded_at=rec.get("recorded_at", ""),
            ))
        return catalogue
