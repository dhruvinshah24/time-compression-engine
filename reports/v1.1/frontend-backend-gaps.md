# TCE v1.1 — Frontend-Backend Gaps Report

**Date**: 2026-09-14  
**Branch**: experiment/v1.1-intelligence-upgrade

---

## Summary

This document catalogs backend APIs and data that exist but are not surfaced in the frontend,
frontend needs that have no backend support, and data quality gaps.

---

## 1. Backend APIs That Exist But Frontend Ignores

### GAP-01 — `/api/v1/events/{id}/explanation` (CRITICAL for AI explainability)

**Status**: Exists in `events.py` route, wired in `client.ts` as `api.events.explanation(id)`.  
**Problem**: Never called from any page. The explanation endpoint could power the "Why did TCE detect this?" feature.  
**Frontend need**: Event detail panel should call this and display a human-readable explanation chain.  
**Proposed endpoint response**: Already returns structured evidence. Frontend should render it as a step-by-step chain:
```
Detection (YOLO confidence 94%) → Track established (12 frames) → Motion classified (kinematic: walking) → Rule: person_entered_scene → Confidence fusion (0.87)
```

### GAP-02 — `/api/v1/event-graph/{videoId}` (Story relationships)

**Status**: Route exists in `event_graph.py`, wired in `client.ts` as `api.eventGraph(videoId)`.  
**Problem**: Never rendered. The Events page "Graph" tab shows a permanent Phase 4 placeholder.  
**Frontend need**: A proper story graph visualization on the timeline page.  
**What the API returns**: Event nodes with edges (CO_OCCURRENCE, SAME_TRACK_TEMPORAL, CAUSAL).

### GAP-03 — `/api/v1/jobs/{id}/diagnostics` (Rich diagnostic data)

**Status**: Route exists in `diagnostics.py`. `DiagnosticsPanel.tsx` exists (14.3 KB) but is NEVER rendered.  
**Problem**: The DiagnosticsPanel component is complete but orphaned — no page imports it.  
**Frontend need**: Add a "Diagnostics" tab on the processing page and the timeline page.  
**What the API returns**: GPU metrics, VRAM, RTF, per-stage timing detail.

### GAP-04 — `/api/v1/summary/{videoId}` story segment data

**Status**: `summary.py` route exists and returns story data. Summary page renders a shell.  
**Problem**: Summary page shows `data.summary` as raw JSON if it's not a string.  
**Frontend need**: Parse story segments and render them as a human-readable narrative arc.

### GAP-05 — Person crop thumbnails (partially working)

**Status**: Timeline API returns `crop_url` per person and per event. Person gallery renders them.  
**Problem**: URLs are hardcoded as `http://localhost:8000/api/v1${crop_url}` — breaks in any non-localhost deployment.  
**Fix needed**: Use `process.env.NEXT_PUBLIC_API_URL` as the base instead of hardcoded localhost.

### GAP-06 — `/api/v1/debug/*` debug endpoints

**Status**: Debug routes exist. Not exposed in any frontend page.  
**Frontend need**: Available under Diagnostics for technical users only.

---

## 2. Frontend Needs With No Backend Support

### GAP-07 — Video player endpoint (CRITICAL)

**Problem**: The frontend needs to play video clips. When a user clicks an event, they should see the video at that timestamp.  
**Current state**: `EventPreviewModal` fetches static frames from `/api/v1/events/{id}/preview` (before/event/after frames). There is NO video streaming or seeking endpoint.  
**What's needed**:
- `GET /api/v1/videos/{video_id}/stream` — streaming the original uploaded video
- OR `GET /api/v1/events/{id}/clip` — returning the pre-generated event clip (these exist in `outputs/clips/`)
**Workaround possible**: Mount `outputs/` as static files (already done in `main.py`). Clips at `outputs/jobs/{job_id}/clips/{event_id}.mp4` are accessible at `/outputs/jobs/{job_id}/clips/{event_id}.mp4`.  
**Gap**: The frontend doesn't know these paths. The job/event API doesn't return clip URLs.

### GAP-08 — Compression statistics endpoint

**Problem**: Dashboard shows avg compression ratio from analytics. But there is no per-video compression breakdown.  
**What's needed**: `/api/v1/summary/{videoId}/compression` returning:
```json
{
  "original_duration_s": 595.23,
  "compressed_duration_s": 236.9,
  "compression_ratio": 0.398,
  "events_retained": 117,
  "events_total": 117,
  "story_segments": 159,
  "segments_retained": 117
}
```
**Current state**: `stats.total_duration_ms` exists in the summary response but compression_ratio per video is not in the summary route.

### GAP-09 — Processing ETA and live metrics

**Problem**: Processing page shows stage progress but no FPS, frames processed, or estimated completion time.  
**What's needed**: The `/jobs/{id}` API should include:
```json
{
  "frames_processed": 1240,
  "frames_total": 3568,
  "fps_current": 34.2,
  "events_discovered": 42,
  "tracks_active": 7
}
```
**Current state**: Job API returns `progress` (0-100 integer) and `current_stage` only.

### GAP-10 — Story/narrative API surface

**Problem**: S09 `StoryBuilder` generates rich story segments (`StorySegment` objects with `events`, `importance_score`, `narrative_score`, `actor_id`, `confidence`). None of this is exposed in any API route.  
**What's needed**: `GET /api/v1/stories/{videoId}` returning story arcs with:
- `story_id`
- `track_id` / `person_label`
- `events[]` (ordered)
- `importance_score`
- `narrative_score`
- `start_ms` / `end_ms`
- `title` (generated or derived)

### GAP-11 — Event search/filter API

**Problem**: Events page has filter checkboxes for event type and a confidence slider, but GET /events has no filter params in practice.  
**What's needed**: `GET /api/v1/events?event_type=person_walking&min_confidence=0.8&video_id=VID-xxx&limit=50&offset=0`  
**Current state**: `/events` route in `events.py` accepts params but the frontend only sends `limit`.

### GAP-12 — Real-time processing SSE

**Problem**: Processing page polls every 2 seconds. For long videos (10+ minutes), this creates 300+ HTTP requests.  
**What's needed**: `GET /api/v1/jobs/{id}/stream` — Server-Sent Events stream with job status updates.  
**Current state**: Polling only.

---

## 3. Data Quality Gaps

### GAP-13 — Event `display_name` often null

**Problem**: `EventRecord.display_name` is the human-readable event description. When null, the frontend falls back to the raw event type string (`person_entered_scene`). The narrative builder in S07 Pass 7 sets this field, but it's not always populated.  
**Impact**: Event labels like "Person Entered Scene" look fine, but complex events like `person_picked_up_backpack` fallback to "Person Picked Up Backpack" from a string transform, which is acceptable.

### GAP-14 — Compression ratio in analytics is a fraction not a percentage

**Problem**: `avg_compression_ratio = 0.398` means "keeps 39.8% of the original." The analytics page displays this as `0.4:1` which is wrong math and confusing.  
**Fix needed in frontend**: Display as `39.8% kept` or `2.51:1 compression`.

### GAP-15 — Settings API returns empty array

**Problem**: `GET /api/v1/settings` returns `[]` because no settings are registered by default. The settings page renders nothing.  
**Impact**: Settings page is a dead end for users.

---

## 4. Priority Matrix

| Gap | Impact | Effort | Priority |
|:----|:------:|:------:|:--------:|
| GAP-07 Video player / clip URLs | HIGH | MEDIUM | P1 |
| GAP-01 Event explanation chain | HIGH | LOW | P1 |
| GAP-10 Stories API + page | HIGH | HIGH | P1 |
| GAP-08 Compression stats per video | MEDIUM | LOW | P2 |
| GAP-03 DiagnosticsPanel wiring | MEDIUM | LOW | P2 |
| GAP-09 Live processing metrics | MEDIUM | MEDIUM | P2 |
| GAP-02 Event graph rendering | MEDIUM | HIGH | P3 |
| GAP-11 Event filter API | MEDIUM | LOW | P2 |
| GAP-05 Crop URL base fix | LOW | LOW | P1 (quick win) |
| GAP-14 Compression ratio format | LOW | LOW | P1 (quick win) |
| GAP-12 SSE for processing | LOW | HIGH | P4 |

*This report covers only frontend-backend interface gaps. Backend algorithm gaps are documented in `reports/v1.1-intelligence-gap-analysis.md`.*
