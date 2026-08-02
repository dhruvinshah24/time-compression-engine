# API Reference (v1)

Base URL: `/api/v1`

## 1. Video Ingestion

### `POST /videos/upload`
Uploads a new raw video for processing.
- **Request Body**: `multipart/form-data` containing the video file.
- **Response**: 
  ```json
  {
    "video_id": "vid_abc123",
    "status": "queued"
  }
  ```

### `GET /videos/{video_id}/status`
Check processing status.
- **Response**:
  ```json
  {
    "video_id": "vid_abc123",
    "status": "processing",
    "progress": 45.5,
    "current_stage": "semantic_intelligence"
  }
  ```

## 2. Compression Policy

### `POST /videos/{video_id}/compress`
Triggers the Temporal Intelligence Engine to generate a new summary based on a policy.
- **Request Body**:
  ```json
  {
    "target_compression_ratio": 100,
    "preserve_narrative": true,
    "focus_events": ["parcel_delivered", "person_idle"]
  }
  ```
- **Response**: Returns a `job_id`.

## 3. Results & Explainability

### `GET /summaries/{job_id}/video`
Returns the final compressed video file.

### `GET /summaries/{job_id}/explainability`
Returns the reasoning chain for the summary.
- **Response**:
  ```json
  {
    "summary_duration_sec": 30,
    "original_duration_sec": 3000,
    "included_events": [
      {
        "event_id": "evt_001",
        "type": "person_entered",
        "reason": "Causal prerequisite for focused event 'parcel_delivered'.",
        "fused_confidence": 0.92
      }
    ]
  }
  ```
