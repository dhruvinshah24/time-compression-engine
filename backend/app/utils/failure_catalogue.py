"""
Failure Catalogue — Time Compression Engine v1.0.1.

Records every observed pipeline failure with category, severity, and evidence.
Failures are NOT hidden. Every real failure is documented.

Categories:
  MISSED_EVENT      — a detectable event was not generated
  FALSE_EVENT       — an event was generated when nothing happened
  TRACKING_FAILURE  — track ID switched, fragmented, or lost
  STORY_BREAK       — narrative coherence broken
  COMPRESSION_ERROR — adaptive skip removed a critical frame
  VALIDATOR_WARNING — quality/integrity check failed

Severity:
  CRITICAL        — prevents meaningful output
  MAJOR           — significantly degrades output quality
  MINOR           — noticeable but system still functional
  INFORMATIONAL   — useful observation, no functional impact

Usage:
    catalogue = FailureCatalogue()
    catalogue.add(
        video_id="exp_c_fast_motion",
        category="MISSED_EVENT",
        severity="MAJOR",
        description="Person running at t=22s not detected",
        stage="s04_object_detect",
        expected="person_running event",
        actual="no events generated",
        possible_cause="YOLO confidence below threshold during fast motion"
    )
    catalogue.save("reports/failures/")
    stats = catalogue.statistics()
"""

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


VALID_CATEGORIES = {
    "MISSED_EVENT",
    "FALSE_EVENT",
    "TRACKING_FAILURE",
    "STORY_BREAK",
    "COMPRESSION_ERROR",
    "VALIDATOR_WARNING",
}

VALID_SEVERITIES = {"CRITICAL", "MAJOR", "MINOR", "INFORMATIONAL"}


@dataclass
class FailureRecord:
    """One observed pipeline failure."""
    failure_id:      str
    video_id:        str
    category:        str
    severity:        str
    description:     str
    stage:           str
    timestamp_s:     Optional[float] = None  # video timestamp where failure occurred
    expected:        Optional[str]   = None
    actual:          Optional[str]   = None
    evidence_frame:  Optional[str]   = None  # path to frame image
    possible_cause:  Optional[str]   = None
    benchmark_file:  Optional[str]   = None  # which benchmark-NNN.json this came from
    recorded_at:     str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%S"))

    def __post_init__(self):
        if self.category not in VALID_CATEGORIES:
            raise ValueError(f"Invalid category: {self.category}. Must be one of {VALID_CATEGORIES}")
        if self.severity not in VALID_SEVERITIES:
            raise ValueError(f"Invalid severity: {self.severity}. Must be one of {VALID_SEVERITIES}")


class FailureCatalogue:
    """
    Collects and persists failure records from pipeline runs.
    One catalogue per benchmark run, or shared across runs.
    """

    def __init__(self):
        self._failures: list[FailureRecord] = []
        self._counter = 0

    def add(
        self,
        video_id:       str,
        category:       str,
        severity:       str,
        description:    str,
        stage:          str,
        timestamp_s:    Optional[float] = None,
        expected:       Optional[str]   = None,
        actual:         Optional[str]   = None,
        evidence_frame: Optional[str]   = None,
        possible_cause: Optional[str]   = None,
        benchmark_file: Optional[str]   = None,
    ) -> FailureRecord:
        self._counter += 1
        fid = f"FAIL-{self._counter:03d}"
        rec = FailureRecord(
            failure_id=fid,
            video_id=video_id,
            category=category,
            severity=severity,
            description=description,
            stage=stage,
            timestamp_s=timestamp_s,
            expected=expected,
            actual=actual,
            evidence_frame=evidence_frame,
            possible_cause=possible_cause,
            benchmark_file=benchmark_file,
        )
        self._failures.append(rec)
        return rec

    @property
    def failures(self) -> list[FailureRecord]:
        return list(self._failures)

    def statistics(self) -> dict:
        if not self._failures:
            return {
                "total": 0,
                "most_common_failure": None,
                "most_implicated_stage": None,
                "failure_count_by_category": {},
                "failure_count_by_severity": {},
            }

        by_cat: dict[str, int] = {}
        by_sev: dict[str, int] = {}
        by_stage: dict[str, int] = {}

        for f in self._failures:
            by_cat[f.category] = by_cat.get(f.category, 0) + 1
            by_sev[f.severity] = by_sev.get(f.severity, 0) + 1
            by_stage[f.stage]  = by_stage.get(f.stage, 0) + 1

        most_common = max(by_cat, key=lambda k: by_cat[k])
        most_stage  = max(by_stage, key=lambda k: by_stage[k])

        return {
            "total":                      len(self._failures),
            "most_common_failure":        most_common,
            "most_implicated_stage":      most_stage,
            "failure_count_by_category":  by_cat,
            "failure_count_by_severity":  by_sev,
            "failure_count_by_stage":     by_stage,
        }

    def save(self, output_dir: str | Path, run_id: str = "") -> str:
        """
        Save catalogue as JSON and one Markdown file per CRITICAL/MAJOR failure.
        Returns path to the JSON summary file.
        """
        d = Path(output_dir)
        d.mkdir(parents=True, exist_ok=True)

        tag = f"-{run_id}" if run_id else ""
        json_path = d / f"catalogue{tag}.json"

        data = {
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "run_id":       run_id,
            "statistics":   self.statistics(),
            "failures":     [asdict(f) for f in self._failures],
        }
        with open(json_path, "w", encoding="utf-8") as fp:
            json.dump(data, fp, indent=2)

        # Write individual Markdown files for CRITICAL and MAJOR
        for rec in self._failures:
            if rec.severity in ("CRITICAL", "MAJOR"):
                md_path = d / f"{rec.failure_id}.md"
                with open(md_path, "w", encoding="utf-8") as fp:
                    fp.write(f"# {rec.failure_id} — {rec.category}\n\n")
                    fp.write(f"**Severity:** {rec.severity}  \n")
                    fp.write(f"**Video:** {rec.video_id}  \n")
                    fp.write(f"**Stage:** {rec.stage}  \n")
                    if rec.timestamp_s is not None:
                        fp.write(f"**At:** {rec.timestamp_s:.1f}s  \n")
                    fp.write(f"\n## Description\n\n{rec.description}\n")
                    if rec.expected:
                        fp.write(f"\n## Expected\n\n{rec.expected}\n")
                    if rec.actual:
                        fp.write(f"\n## Actual\n\n{rec.actual}\n")
                    if rec.possible_cause:
                        fp.write(f"\n## Possible Cause\n\n{rec.possible_cause}\n")
                    if rec.evidence_frame:
                        fp.write(f"\n## Evidence Frame\n\n`{rec.evidence_frame}`\n")

        return str(json_path)

    @classmethod
    def load(cls, json_path: str | Path) -> "FailureCatalogue":
        """Load a previously-saved catalogue."""
        with open(json_path) as f:
            data = json.load(f)
        cat = cls()
        for fd in data.get("failures", []):
            cat._counter += 1
            rec = FailureRecord(**fd)
            cat._failures.append(rec)
        # Sync counter to highest number seen
        nums = [int(f.failure_id.split("-")[1]) for f in cat._failures if "-" in f.failure_id]
        cat._counter = max(nums) if nums else 0
        return cat
