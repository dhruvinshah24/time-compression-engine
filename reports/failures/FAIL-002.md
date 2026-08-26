# FAIL-002 — MISSED_EVENT

**Severity:** CRITICAL  
**Video:** exp_e_roi_crossing  
**Stage:** s07_event_understand  
**At:** 0.0s  

## Description

When a track's first observation is inside a restricted zone, no restricted_zone_entry event is emitted. The ROIManager.check_point() method silently records the initial state without generating an event. This means any person who is ALREADY in a restricted area when the camera starts recording will never trigger an entry alert.

## Expected

restricted_zone_entry event at frame 0 when track starts inside zone

## Actual

0 events generated (no transition detected, only initial state recorded)

## Possible Cause

ROIManager._membership[track_id][zone_id] is None on first observation. Code silently assigned the state: `if was_inside is None: self._membership[...] = inside_now; continue` without emitting any event. Fixed in Phase 4: now emits entry event immediately with evidence={'cold_start': True}.
