# TCE v1.1 — Frontend Audit Report

**Date**: 2026-09-14  
**Auditor**: Antigravity Engine (direct source-code + live application review)  
**Branch**: experiment/v1.1-intelligence-upgrade  
**Backend**: Running at http://localhost:8000 (CUDA confirmed, RTX 5050, 8.5 GB VRAM)  
**Frontend**: Running at http://localhost:3000  
**Test video**: test_real.mp4 (65 KB)  
**Database state**: Fresh (0 videos, 0 jobs, 0 events)

---

## 0. Page/API Map

| Route | API Called | Data | User Purpose | Current UX | Grade |
|:------|:-----------|:-----|:-------------|:-----------|:-----:|
| `/` | `/analytics/stats`, `/jobs`, `/events?limit=8`, `/health` | Stats, jobs list, recent events, device info | Overview of processed videos | Dark dashboard with stat cards, job list, event feed | C+ |
| `/upload` | POST `/upload/` | Upload result + job ID | Submit video for analysis | Dropzone + profile selector + metadata preview | B- |
| `/processing/[jobId]` | GET `/jobs/[id]` (polled 2s) | Job status, stages, logs | Watch pipeline progress | Stage checklist with durations + log panel | B |
| `/timeline/[videoId]` | GET `/timeline/[videoId]` | Events, persons, objects | Understand what happened | Scrollable event list by category + story strip | C |
| `/events` | GET `/events` | All events | Browse/search events globally | Flat grid of event cards + fake filter panel | D |
| `/analytics` | GET `/analytics/stats` | Aggregate stats + stage timing | System performance | 4 stat cards + bar chart | C- |
| `/summary/[videoId]` | GET `/summary/[videoId]` | Summary + compression stats | Compression result | Compression hero + event list | C |
| `/settings` | GET `/settings`, PUT `/settings/[key]` | Key-value config | Tune pipeline settings | Table of key-value settings | D |

---

## A. Existing Frontend Inventory

### Pages

| Page | File Size | Status |
|:-----|:------|:-------|
| Dashboard (`/`) | 30.6 KB | Functional — real data, some issues |
| Upload (`/upload`) | 14.0 KB | Functional — works well |
| Processing (`/processing/[jobId]`) | 14.8 KB | Functional — good stage display |
| Timeline (`/timeline/[videoId]`) | 46.8 KB | Functional — largest page, most complete |
| Summary (`/summary/[videoId]`) | 8.5 KB | Partial — renders but weak content |
| Events (`/events`) | 7.0 KB | Broken — fake filters, placeholder graph |
| Analytics (`/analytics`) | 6.9 KB | Minimal — 4 stats + 1 chart |
| Settings (`/settings`) | 6.5 KB | Skeleton — renders but no description |

### Components
| Component | Size | Status |
|:----------|:-----|:-------|
| `EventPreviewModal.tsx` | 13.5 KB | Functional — event before/after frame viewer |
| `ModelProfileSelector.tsx` | 6.4 KB | Functional — used in upload |
| `DiagnosticsPanel.tsx` | 14.3 KB | Functional — detailed job diagnostics |
| `Sidebar.tsx` | 4.8 KB | Functional — basic nav, demo mode toggle |
| `Shell.tsx` | 1.7 KB | OK — layout shell |

### API Client
- `lib/api/client.ts`: Thin wrapper — covers health, videos, jobs, events, timeline, event-graph, summary, analytics, settings, upload
- **Missing**: `/api/v1/jobs/{id}/diagnostics`, `/api/v1/events/{id}/explanation`, story endpoints

---

## B. Problems Found

### CRITICAL PROBLEMS (breaks primary user goal)

**C1 — Events page is a ghost: completely non-functional**  
`/events/page.tsx` line 75: Filter checkboxes use HARDCODED values `['Person Entered', 'Object Moved', 'Vehicle Arrived', 'Anomaly']` — not from API. The confidence slider is decorative. The "Graph" tab shows a permanent placeholder: "Interactive causal event graphs will be available in Phase 4." This page provides zero value.

**C2 — Timeline has no video player**  
The timeline page shows events chronologically but has no video player. You cannot click an event and see the video jump to that moment. The `EventPreviewModal` shows static frames but there is no way to play the actual video. The core promise ("click event → see it in video") is absent.

**C3 — Story view doesn't exist**  
The user prompt says "Stories discovered" but there is no stories page, no story view on the timeline. The `StoryStrip` is a horizontal icon strip with no temporal context, no confidence, no evidence chain. It looks decorative.

**C4 — Summary page is near-empty**  
`/summary/[videoId]` renders a "Time Compression Result" hero showing duration and a ratio but no explanation of what was retained. The event list below is bare — no evidence, no activity, no confidence breakdown. The "Download Report" and "Share" buttons do nothing (no handlers). Summary page feels like a placeholder.

**C5 — No compression visualization**  
The compression ratio is shown as a number (0.398) with no chart, no visual comparison, no explanation of what was removed vs. kept. Users cannot understand what TCE actually did.

**C6 — Demo mode in sidebar is dangerous**  
The sidebar has a "Demo Mode" toggle that writes to localStorage. There is NO demo mode implementation anywhere — toggling it only shows an amber banner. It adds confusion without benefit and implies fake data is possible when the user rule is "real data only."

### MAJOR PROBLEMS

**M1 — No route for Stories**  
Backend has `/api/v1/summary` and event graph, but there is no `/stories` page in the frontend. The `EventGraphBuilder` in `s09_story_build.py` generates story segments and narrative arcs that are never surfaced.

**M2 — Processing page uses old CSS tokens**  
`processing/[jobId]/page.tsx` lines 53-62: Uses `text-muted`, `text-accent`, `border-border`, `bg-surface`, `bg-background` — legacy CSS variables that are partially defined in `globals.css` as CSS custom properties but are NOT Tailwind utility classes. This causes broken styles on the processing page (stages show wrong colors).

**M3 — Dashboard page has a syntax error**  
`page.tsx` lines 570-581: Two adjacent `<p className="text-xs text-white/20">` tags opened without the first being closed before the second. This is a JSX syntax error that React silently recovers from but produces invalid HTML.

**M4 — Timeline is not inside the sidebar layout**  
`/timeline/[videoId]` renders its own full-page layout (`min-h-screen bg-[#08080f]`) independently — not inside the `Shell` + `Sidebar` layout. When on this page, the sidebar disappears. Users cannot navigate back without the browser back button or the breadcrumb. No consistent navigation.

**M5 — Summary page is also outside the layout**  
Same issue as M4 — `/summary/[videoId]` renders without the sidebar.

**M6 — No real-time live event count during processing**  
The processing page shows stage progress but does NOT show how many events have been detected so far. The `/jobs/{id}` API returns `event_count` but the UI only shows it at completion.

**M7 — Analytics page shows "avg compression ratio" as X:1 (wrong format)**  
`analytics/page.tsx` line 76: `value: data.avg_compression_ratio ? ${data.avg_compression_ratio.toFixed(1)}:1`  
The backend stores compression ratio as 0.398 (fraction), so `0.4:1` is nonsensical. Should be `39.8%` or `2.5:1` with the math corrected.

**M8 — Events page graph tab shows permanent "Phase 4" placeholder**  
`/events/page.tsx` lines 138-142: Hardcoded placeholder text. The backend has `/event-graph/{videoId}` working. This should be wired up.

**M9 — Settings page has no descriptions**  
The settings page exists but renders an empty list because `GET /settings` returns `[]` (empty — no settings registered). There is no explanation of what settings are available or how to change them.

### MODERATE PROBLEMS

**MD1 — Story Strip on timeline is just icons with no narrative**  
The `StoryStrip` component shows icons in a horizontal row with timestamps. There is no grouping by person, no arc visualization, no story segment rendering.

**MD2 — Evidence panel dumps raw JSON keys**  
When you expand an event on the timeline, the evidence shows raw keys like `person_label`, `track_id`, `confidence`, `bbox` in a 2-column grid. Users see `bbox=[123, 45, 234, 190]` with no explanation.

**MD3 — Person thumbnails hardcode localhost:8000**  
`timeline/[videoId]/page.tsx` line 743: `src={"http://localhost:8000/api/v1${person.crop_url}"}` — hardcoded localhost. Same in the EventPreviewModal.

**MD4 — No skeleton loading states**  
Every page shows a spinning loader (`Loader2`) centered on a black background. There are no skeleton screens. Data appears abruptly after loading.

**MD5 — Upload page doesn't show domain selection clearly**  
The "source_domain" field (`general`, `retail`, `security`, etc.) is present in the form but not explained to users.

**MD6 — No error retry on timeline**  
If the `/timeline/{videoId}` call fails, the page shows an error with a "Back to Dashboard" link. There is no retry button.

**MD7 — Compression display is confusing**  
The dashboard stat card shows "Compression: 40%" with a `TrendingUp` icon — but compression going UP is actually a BAD thing (less compression). Should be `TrendingDown` or "Savings: 60%".

**MD8 — No breadcrumbs on most pages**  
Only the timeline page has breadcrumbs. All other pages have no navigation context.

### MINOR PROBLEMS

**MI1 — Dashboard polls every 5 seconds even when no jobs are running**  
`page.tsx` line 328: `setInterval(load, 5000)` — always polling, no pause when everything is completed.

**MI2 — Job filename display is fragile**  
`job.filename?.replace('original.mp4', 'Video')` — if the filename format changes, "original.mp4" will be displayed to users.

**MI3 — "Demo Mode" toggle in sidebar serves no purpose**  
See C6 — should be removed entirely in v1.1.

**MI4 — StageIcon uses `text-accent` class which is undefined**  
`processing/[jobId]/page.tsx` line 53: `className="... text-accent ..."` — `accent` is not a Tailwind color class. Should be `text-indigo-400`.

**MI5 — DiagnosticsPanel is imported but never used on any page**  
`DiagnosticsPanel.tsx` is a standalone component (14.3 KB) but is not rendered on any visible page. It exists as dead code.

**MI6 — `animate-fade-in` class referenced but not defined**  
`events/page.tsx` line 40: `className="... animate-fade-in ..."` — this class is not in `globals.css` or `tailwind.config.ts`. It silently does nothing.

---

## C. Page Scores (1–10)

| Page | Visual Design | Info Hierarchy | Usability | AI Explainability | Loading | Error Handling | Data Density | Professional Quality | **Total** |
|:-----|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Dashboard | 7 | 6 | 7 | 3 | 5 | 7 | 5 | 6 | **6.3** |
| Upload | 8 | 7 | 8 | 5 | 7 | 7 | 6 | 7 | **7.1** |
| Processing | 7 | 8 | 7 | 6 | 6 | 7 | 7 | 7 | **6.9** |
| Timeline | 7 | 6 | 5 | 4 | 5 | 6 | 7 | 6 | **5.8** |
| Events | 5 | 2 | 2 | 2 | 5 | 5 | 2 | 3 | **3.3** |
| Summary | 6 | 4 | 4 | 3 | 5 | 5 | 3 | 4 | **4.3** |
| Analytics | 6 | 5 | 5 | 3 | 5 | 6 | 4 | 5 | **4.9** |
| Settings | 3 | 2 | 2 | 1 | 5 | 4 | 2 | 2 | **2.6** |

**Overall product score: 5.2 / 10**

The application is functional but not yet a professional product. The biggest failures are:
1. No video player on the results page
2. Events page is non-functional
3. No story visualization
4. Evidence panel exposes raw JSON
5. Compression visualization missing

---

## D. User Journey Test Results

### Journey: Upload → Process → Results

**Step 1: Open Dashboard** — Works. Empty state is clean. GPU badge visible.  
**Step 2: Navigate to Upload** — Works. Dropzone + profile selector functional.  
**Step 3: Upload video** — Works. Upload progress real, metadata returned immediately.  
**Step 4: Processing page** — Works. Stages visible with durations. BUG: `text-accent` renders wrong color.  
**Step 5: Results (Timeline)** — Partial. Events listed by category. No video player.  
**Step 6: Click event** — Partial. Evidence panel expands with raw key-value JSON.  
**Step 7: Preview event** — Works. EventPreviewModal shows before/event/after frames.  
**Step 8: View story** — FAIL. No story page. StoryStrip is decorative only.  
**Step 9: Compression result** — FAIL. Summary page is nearly empty.  
**Step 10: Analytics** — Works partially. Only aggregate metrics, no per-video analysis.

**Result: 5/10 steps fully working. 3/10 partial. 2/10 broken.**

---

## E. Key Findings Summary

1. **What exists and works**: Upload, processing monitor, timeline events list, person gallery, EventPreviewModal, analytics aggregates, health/diagnostics
2. **What exists but is broken**: Events page filters, summary page, settings page, Demo Mode
3. **What doesn't exist at all**: Video player, stories page, compression visualization, evidence chain (human-readable), actual event search/filter
4. **What backend supports but frontend ignores**: Story segments (S09), compression ratio explanation, event graph (`/event-graph/{videoId}`), event explanation (`/events/{id}/explanation`), diagnostics (`DiagnosticsPanel.tsx` unused)

*This audit was performed on a fresh backend instance with 0 processed videos. All findings are based on code review, API verification, and live application testing.*
