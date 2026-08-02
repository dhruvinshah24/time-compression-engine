# Evaluation Datasets

This directory contains definitions and structures for the ground truth datasets used to evaluate the Time Compression Engine.

## Creating a Ground Truth Dataset
A ground truth dataset consists of raw video files and corresponding JSON annotation files.

### Annotation Schema
For each video `video123.mp4`, there must be a `video123_gt.json` file structured as follows:

```json
{
  "video_id": "video123",
  "duration_seconds": 3600,
  "events": [
    {
      "event_id": "evt_001",
      "type": "person_entered",
      "start_time": 12.5,
      "end_time": 15.0,
      "entities": ["person_1"]
    },
    {
      "event_id": "evt_002",
      "type": "parcel_delivered",
      "start_time": 14.0,
      "end_time": 18.0,
      "entities": ["person_1", "package_1"]
    }
  ],
  "narrative_chains": [
    ["evt_001", "evt_002"]
  ],
  "irrelevant_events": [
    {
      "type": "tree_blowing",
      "start_time": 500,
      "end_time": 550
    }
  ]
}
```

## Dataset Guidelines
- **Diversity**: Datasets should include indoor, outdoor, high-traffic, and low-traffic scenarios.
- **Narrative Chains**: The most critical part of annotation for TCE is explicitly linking events in the `narrative_chains` list. This enables the calculation of the `narrative_preservation_score`.
