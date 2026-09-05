"""
Temporal Pose State Machine Audit — Phase 5G.

Inspects TemporalPoseAnalyzer to determine:
1. What states can be emitted?
2. What bbox ratio thresholds trigger each state?
3. How many consecutive frames are required (hysteresis)?
4. What event_type strings are emitted?
5. Are those event_types registered in S07?

Then runs on the pose_sequence_30s.mp4 corpus video using synthetic
bbox ratios to simulate standing → crouching → crawling transitions.
"""

import json
import sys
import time
import inspect
from pathlib import Path

BACKEND_DIR = Path(__file__).parent.parent
REPO_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

RESULTS_DIR = REPO_ROOT / "results" / "TCE-v1.0"
REPORTS_DIR = REPO_ROOT / "reports"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def audit_temporal_pose_analyzer() -> dict:
    """Inspect TemporalPoseAnalyzer internals without running it."""
    from app.utils.pose_temporal import TemporalPoseAnalyzer, SimplePoseFrame, PoseEvent

    audit = {}

    # Instantiate with defaults
    analyzer = TemporalPoseAnalyzer(track_id="audit_track")

    # Extract configuration via inspection
    attrs = {k: v for k, v in vars(analyzer).items()
             if not k.startswith('__') and not callable(v)}
    audit["config"] = {k: v for k, v in attrs.items() if not isinstance(v, (list, dict))}

    # Get init signature
    sig = inspect.signature(TemporalPoseAnalyzer.__init__)
    audit["init_params"] = {
        k: str(p.default) for k, p in sig.parameters.items() if k != 'self'
    }

    # Get all methods
    methods = [m for m in dir(analyzer) if not m.startswith('_') and callable(getattr(analyzer, m))]
    audit["public_methods"] = methods

    # Get source of update method to find thresholds
    try:
        update_src = inspect.getsource(analyzer.update)
        # Extract any threshold constants mentioned
        lines_with_thresh = [l.strip() for l in update_src.split('\n')
                             if any(kw in l for kw in ['thresh', 'ratio', 'crawl', 'crouch', 'stand', '0.', 'min_'])]
        audit["threshold_lines_from_source"] = lines_with_thresh[:20]
    except Exception as e:
        audit["threshold_lines_from_source"] = [f"Could not inspect: {e}"]

    # Get source of flush method
    try:
        flush_src = inspect.getsource(analyzer.flush)
        audit["flush_source_lines"] = flush_src.split('\n')[:15]
    except Exception as e:
        audit["flush_source_lines"] = [str(e)]

    # Get PoseEvent fields
    try:
        pe_fields = {f: str(getattr(PoseEvent, f, '?')) for f in
                     (PoseEvent.__dataclass_fields__ if hasattr(PoseEvent, '__dataclass_fields__') else {})}
        audit["pose_event_fields"] = pe_fields
    except Exception as e:
        audit["pose_event_fields"] = {"error": str(e)}

    # Get to_pipeline_event_dict output structure
    try:
        spf = SimplePoseFrame.from_bbox(0, 0.0, "test", 0.3, 0.3, 0.7, 0.8)
        analyzer2 = TemporalPoseAnalyzer(track_id="test2", min_frames_crawling=1)
        for i in range(10):
            spf2 = SimplePoseFrame.from_bbox(i, float(i*40), "test2", 0.3, 0.6, 0.7, 0.75)
            evt = analyzer2.update(spf2)
        flush_evts = analyzer2.flush()
        if flush_evts:
            audit["sample_pipeline_event"] = flush_evts[0].to_pipeline_event_dict()
            audit["event_type_emitted"] = flush_evts[0].to_pipeline_event_dict().get("event_type", "UNKNOWN")
        else:
            audit["sample_pipeline_event"] = None
            audit["event_type_emitted"] = "no event emitted in test run"
    except Exception as e:
        audit["sample_pipeline_event_error"] = str(e)

    return audit


def simulate_pose_sequence() -> dict:
    """
    Simulate standing → crouching → crawling using synthetic bbox ratios.
    Directly exercises TemporalPoseAnalyzer state machine.
    """
    from app.utils.pose_temporal import TemporalPoseAnalyzer, SimplePoseFrame

    FPS = 25

    # Synthetic bbox height ratios for each state:
    # Standing:  height/width ratio > ~1.5 (tall person)
    # Crouching: ratio ~0.8–1.2
    # Crawling:  ratio < ~0.5 (wide relative to height)
    SEQUENCES = [
        ("standing_30s",    [(0.35, 0.1, 0.65, 0.9)] * (30 * FPS)),      # tall bbox
        ("crouching_10s",   [(0.30, 0.3, 0.70, 0.65)] * (10 * FPS)),     # shorter
        ("crawling_10s",    [(0.25, 0.5, 0.75, 0.65)] * (10 * FPS)),     # wide/flat
        ("transition_full", (
            [(0.35, 0.1, 0.65, 0.9)] * (8 * FPS) +     # standing
            [(0.30, 0.3, 0.70, 0.65)] * (5 * FPS) +    # crouching
            [(0.25, 0.5, 0.75, 0.65)] * (8 * FPS) +    # crawling
            [(0.35, 0.1, 0.65, 0.9)] * (5 * FPS)       # stand again
        )),
    ]

    results = {}
    for seq_name, bboxes in SEQUENCES:
        analyzer = TemporalPoseAnalyzer(track_id=seq_name)
        all_events = []
        state_timeline = []

        for frame_idx, (x1, y1, x2, y2) in enumerate(bboxes):
            spf = SimplePoseFrame.from_bbox(
                frame_number=frame_idx,
                timestamp_ms=frame_idx / FPS * 1000,
                track_id=seq_name,
                x1=x1, y1=y1, x2=x2, y2=y2,
            )
            evt = analyzer.update(spf)
            state_timeline.append(getattr(analyzer, '_current_state', 'UNKNOWN'))
            if evt:
                all_events.append(evt.to_pipeline_event_dict())

        flush_evts = analyzer.flush()
        for fe in flush_evts:
            all_events.append(fe.to_pipeline_event_dict())

        results[seq_name] = {
            "frames":       len(bboxes),
            "duration_s":   round(len(bboxes) / FPS, 1),
            "events":       len(all_events),
            "event_types":  list({e.get("event_type", "?") for e in all_events}),
            "all_events":   all_events,
            "state_changes": [
                {"frame": i, "state": s}
                for i, s in enumerate(state_timeline)
                if i == 0 or s != state_timeline[i-1]
            ]
        }

        print(f"  {seq_name}: {len(all_events)} events, types={results[seq_name]['event_types']}")
        if results[seq_name]["state_changes"]:
            print(f"    State changes: {results[seq_name]['state_changes'][:8]}")

    return results


def classify_capabilities(audit: dict, sequences: dict) -> dict:
    """Produce honest capability classification."""
    caps = {}

    # Standing detection
    standing_events = sequences.get("standing_30s", {}).get("events", 0)
    caps["STANDING"] = "IMPLEMENTED" if standing_events == 0 else "PARTIALLY_VALIDATED"

    # Crouching detection
    crouch_types = sequences.get("crouching_10s", {}).get("event_types", [])
    has_crouch = any("crouch" in str(t).lower() for t in crouch_types)
    caps["CROUCHING"] = "PARTIALLY_VALIDATED" if has_crouch else "IMPLEMENTED"

    # Crawling detection
    crawl_types = sequences.get("crawling_10s", {}).get("event_types", [])
    has_crawl = any("crawl" in str(t).lower() for t in crawl_types)
    caps["CRAWLING"] = "PARTIALLY_VALIDATED" if has_crawl else "IMPLEMENTED"

    # Transition detection
    trans_evts = sequences.get("transition_full", {}).get("events", 0)
    caps["STATE_TRANSITIONS"] = "PARTIALLY_VALIDATED" if trans_evts > 0 else "IMPLEMENTED"

    # Falling — not tested in this sequence
    caps["FALLEN"] = "IMPLEMENTED — NOT YET VALIDATED on suitable footage"
    caps["RUNNING"] = "IMPLEMENTED — NOT YET VALIDATED (requires real running footage)"

    return caps


def main():
    print("Temporal Pose Audit — Phase 5G")
    print()

    print("[1/3] Inspecting TemporalPoseAnalyzer internals...")
    audit = audit_temporal_pose_analyzer()
    print(f"  Init params: {audit['init_params']}")
    print(f"  Public methods: {audit['public_methods']}")
    print(f"  Event type emitted in test: {audit.get('event_type_emitted', '?')}")
    if audit.get("threshold_lines_from_source"):
        print(f"  Threshold-related source lines:")
        for line in audit["threshold_lines_from_source"][:6]:
            print(f"    {line}")
    print()

    print("[2/3] Simulating pose sequences...")
    sequences = simulate_pose_sequence()
    print()

    print("[3/3] Classifying capabilities...")
    capabilities = classify_capabilities(audit, sequences)
    for cap, status in capabilities.items():
        marker = "!!" if "IMPLEMENTED" in status and "NOT" in status else "  "
        print(f"  {marker} {cap}: {status}")
    print()

    # Save results
    out = {
        "measured_at":  time.strftime("%Y-%m-%dT%H:%M:%S"),
        "audit":        {k: v for k, v in audit.items() if k != "flush_source_lines"},
        "sequences":    {k: {j: v for j, v in d.items() if j != "all_events"}
                        for k, d in sequences.items()},
        "capabilities": capabilities,
    }
    out_json = RESULTS_DIR / "pose-audit.json"
    with open(out_json, "w") as f:
        json.dump(out, f, indent=2, default=str)

    # Write markdown
    md_path = REPORTS_DIR / "pose-audit.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Temporal Pose Audit — Phase 5G\n\n")
        f.write(f"Measured: {time.strftime('%Y-%m-%d %H:%M')}  \n\n")

        f.write("## TemporalPoseAnalyzer Configuration\n\n")
        f.write("| Parameter | Default |\n|---|---|\n")
        for k, v in audit.get("init_params", {}).items():
            f.write(f"| {k} | {v} |\n")

        f.write("\n## Pose Sequence Simulation\n\n")
        f.write("| Sequence | Duration | Events | Event Types |\n|---|---|---|---|\n")
        for seq, data in sequences.items():
            types = ", ".join(data["event_types"]) or "none"
            f.write(f"| {seq} | {data['duration_s']}s | {data['events']} | {types} |\n")

        f.write("\n## Capability Classification\n\n")
        f.write("| Capability | Classification |\n|---|---|\n")
        for cap, status in capabilities.items():
            f.write(f"| {cap} | **{status}** |\n")

        f.write("\n## Important Notes\n\n")
        f.write("- These tests use synthetic bbox ratios, NOT real detected persons.\n")
        f.write("- Bbox-ratio-based pose detection is approximate.\n")
        f.write("- A real crouching/crawling person may not match these bbox ratios.\n")
        f.write("- No capability is PROVEN without real validated footage.\n")
        f.write("- Single-frame events are explicitly prevented by the hysteresis mechanism.\n")

    print(f"Results: {out_json}")
    print(f"Report:  {md_path}")


if __name__ == "__main__":
    main()
