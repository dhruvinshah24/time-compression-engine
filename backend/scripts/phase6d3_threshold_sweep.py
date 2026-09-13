"""
Phase 6D.3 — Threshold Sweep Analysis.

Uses the existing Phase 6D.2 feature data (no pipeline rerun).
Evaluates each experimental threshold on the 230-track population.

For each threshold computes:
  - cycling tracks (Signal 1 + Signal 2 combined)
  - cycling tracks under temporal alignment fix (Signal 1 suppressed)
  - cycling tracks with both fixes (temporal + threshold)
  - Signal 2 only (height_std < 0.03) at each threshold
"""
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND))

DATA = BACKEND.parent / 'results/TCE-v1.0/phase6d2-cycling-track-features.json'
OUT  = BACKEND.parent / 'results/TCE-v1.0/phase6d3-threshold-sweep.json'

THRESHOLDS = [0.018, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35]

# From Phase 6D.2: 221 cycling tracks classified by the baseline
# Signal 1 trigger: 205/230 (89.1%)
# Signal 2 both: 121/230 (52.6%)
# Height-only (height_std < 0.03): 124/230 (53.9%)


def analyse(features: list, threshold: float, temporal_fix: bool) -> dict:
    """
    Re-evaluate cycling classification for each track under experimental settings.

    temporal_fix=True suppresses Signal 1 for tracks where the bicycle track
    frame range is disjoint from the person track's frame range.

    NOTE: Phase 6D.2 data doesn't store bicycle observation frame ranges.
    We use signal1_fires as a proxy:
      - When temporal_fix=True, we suppress Signal 1 entirely (worst-case approximation)
        because we cannot determine overlap from the precomputed data.
        This is conservative: the actual fix would preserve Signal 1 for
        tracks that DO temporally overlap with the bicycle.
    """
    cycling = 0
    speed_only_cycling = 0
    height_only_below_threshold = 0
    signal2_both = 0

    speed_triggers = 0
    height_triggers = 0

    for f in features:
        s2_speed  = f['mean_speed'] >= threshold
        s2_height = f['height_std'] < 0.03
        s2_fires  = s2_speed and s2_height

        # Signal 1 handling
        if temporal_fix:
            # Conservative: suppress ALL Signal 1 (we lack per-track bicycle overlap data)
            # Actual fix would preserve genuine co-location cases
            s1_fires = False
        else:
            s1_fires = f['signal1_fires']

        # Classification (mirrors ActivityClassifier logic)
        cycling_conf = 0.0
        if s1_fires:
            cycling_conf = f['signal1_conf']  # 0.70–0.95
        elif s2_fires:
            cycling_conf = 0.65

        is_cycling = cycling_conf >= 0.60

        if is_cycling:
            cycling += 1
        if s2_speed and s2_height:
            signal2_both += 1
        if s2_speed:
            speed_triggers += 1
        if s2_height:
            height_triggers += 1

    return {
        'threshold': threshold,
        'temporal_fix': temporal_fix,
        'cycling_tracks': cycling,
        'cycling_pct': round(100 * cycling / max(len(features), 1), 1),
        'signal2_speed_triggers': speed_triggers,
        'signal2_height_triggers': height_triggers,
        'signal2_both': signal2_both,
        'signal2_speed_pct': round(100 * speed_triggers / max(len(features), 1), 1),
        'removed_vs_baseline': 221 - cycling,
        'pct_remaining_vs_baseline': round(100 * cycling / 221, 1),
    }


def speed_percentile(features: list, threshold: float) -> float:
    """What percentile of speed values is at this threshold?"""
    speeds = sorted(f['mean_speed'] for f in features)
    n = len(speeds)
    below = sum(1 for s in speeds if s < threshold)
    return round(100 * below / max(n, 1), 1)


def main():
    data = json.loads(DATA.read_text())
    features = data['all_track_features']
    n = len(features)
    print(f"Loaded {n} track features from {DATA.name}")
    print()

    sweep_results = []

    print(f"{'Threshold':>10}  {'TempFix':>8}  {'Cycling':>8}  {'Pct':>6}  "
          f"{'Removed':>8}  {'SpeedPct':>9}  {'Percentile':>11}")
    print("-" * 80)

    for th in THRESHOLDS:
        pctile = speed_percentile(features, th)
        for temporal_fix in (False, True):
            r = analyse(features, th, temporal_fix)
            r['speed_distribution_percentile'] = pctile
            sweep_results.append(r)
            tag = 'TempFix+' if temporal_fix else 'Baseline'
            print(f"  {th:>8.3f}  {tag:>8}  {r['cycling_tracks']:>8}  "
                  f"{r['cycling_pct']:>5.1f}%  {r['removed_vs_baseline']:>8}  "
                  f"{r['signal2_speed_pct']:>8.1f}%  {pctile:>10.1f}th")

    print()

    # Also report ablation variants at key thresholds
    print("=== ABLATION: Speed only vs Speed+Height (no Signal 1, no temporal fix) ===")
    print(f"{'Threshold':>10}  {'SpeedOnly':>10}  {'Speed+Height':>13}  {'Height Adds':>12}")
    print("-" * 60)
    for th in THRESHOLDS:
        speed_only_ct = sum(1 for f in features if f['mean_speed'] >= th)
        both_ct = sum(1 for f in features if f['mean_speed'] >= th and f['height_std'] < 0.03)
        print(f"  {th:>8.3f}  {speed_only_ct:>10}  {both_ct:>13}  {both_ct - speed_only_ct:>12}")

    # Save
    result = {
        'source_data': str(DATA),
        'total_tracks': n,
        'baseline_cycling_tracks': 221,
        'thresholds_evaluated': THRESHOLDS,
        'sweep': sweep_results,
        'note_temporal_fix_conservative': (
            "temporal_fix=True suppresses ALL Signal 1 because per-track "
            "bicycle frame overlap data is not stored in phase6d2 feature JSON. "
            "Actual fix preserves genuine temporal overlaps. "
            "True cycling count after temporal fix would be >= this estimate."
        ),
    }
    with open(OUT, 'w') as fh:
        json.dump(result, fh, indent=2)
    print(f"\nSaved: {OUT}")


if __name__ == '__main__':
    main()
