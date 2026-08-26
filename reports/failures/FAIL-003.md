# FAIL-003 — MISSED_EVENT

**Severity:** MAJOR  
**Video:** exp_e_roi_crossing  
**Stage:** s07_event_understand  
**At:** 14.3s  

## Description

In the corpus video trajectory simulation, the rectangle entered the zone at ~t=14.3s but no restricted_zone_entry event was generated. An exit event was detected at t=18.36s (expected at t=25.7s — timing error of 7.34s). Note: this failure is partially explained by FAIL-002 (cold-start bug). The cold-start fix may resolve the entry detection issue.

## Expected

entry event at ~t=14.3s, exit event at ~t=25.7s

## Actual

0 entry events, 1 exit event at t=18.36s (7.34s error)

## Possible Cause

The ROI cold-start bug (FAIL-002) is the primary cause. The synthetic track starts outside the zone, so the cold-start bug doesn't apply directly. There may be a second issue: the zone boundary check fires inconsistently. The exit at 18.36s (instead of 25.7s) suggests the zone boundary polygon may have floating-point precision issues at the edge.
