# VIRAT Video Dataset — TCE Validation Set

## Source

VIRAT Video Dataset v2.0  
Homepage: https://viratdata.org/  
Paper: Sangmin Oh et al., "A Large-Scale Benchmark Dataset for Event Recognition
in Surveillance Video", CVPR 2011.

## License

The VIRAT dataset is available for **research use only**.  
Raw footage is **NOT committed to this repository**.  
Only metadata and annotation extracts are stored here.

## Why VIRAT

VIRAT contains surveillance-style scenes with:
- outdoor campus environments (parking lots, open areas)
- genuine human activities (walking, running, carrying objects, entering/leaving vehicles)
- multiple people in frame simultaneously
- real camera perspectives (elevated fixed cameras)
- varied lighting conditions

This is substantially closer to the TCE target use case than generic
object-detection datasets (COCO, OpenImages) or pedestrian re-identification
datasets (Market-1501, DukeMTMC).

## Directory Structure

```
raw/          — download destination. Do NOT commit video files. (.gitignored)
selected/     — symlinks or short clips extracted for specific tests. (.gitignored)
metadata/     — YAML files describing each video. COMMIT THESE.
```

## Download Instructions

1. Visit https://viratdata.org/ and agree to the research license.
2. Download VIRAT Ground Dataset files (VIRAT_S_*.mp4 or .avi).
3. Place downloaded files in `data/real/virat/raw/`.
4. Create a metadata YAML file for each video you intend to use.

No automated download script is provided — manual registration is required.

## Metadata Convention

For each video used in validation, create:
```
metadata/{video_id}.yaml
```

See `metadata/template.yaml` for the required fields.

## Validation Coverage Target

The following conditions should be covered across the selected clips.
If a condition is not covered, mark it **NOT YET VALIDATED** in the report.

| Condition | Target | Status |
|---|---|---|
| Normal daylight | ≥ 1 clip | NOT YET DOWNLOADED |
| Low-light / dusk | ≥ 1 clip | NOT YET DOWNLOADED |
| Multiple people | ≥ 1 clip | NOT YET DOWNLOADED |
| Person entering/leaving frame | ≥ 1 clip | NOT YET DOWNLOADED |
| Occlusion | ≥ 1 clip | NOT YET DOWNLOADED |
| Fast-moving person | ≥ 1 clip | NOT YET DOWNLOADED |
| Stationary person (loitering) | ≥ 1 clip | NOT YET DOWNLOADED |
| Long periods of static background | ≥ 1 clip | NOT YET DOWNLOADED |
| Frame boundary appearance | ≥ 1 clip | NOT YET DOWNLOADED |
| Difficult tracking (similar clothing) | ≥ 1 clip | NOT YET DOWNLOADED |

## Git Policy

The following are added to `.gitignore` in this directory:
- `raw/` — large video files
- `selected/` — derived clips
- `*.mp4`, `*.avi`, `*.mov`, `*.mkv`

Only `metadata/*.yaml` and `README.md` are committed.
