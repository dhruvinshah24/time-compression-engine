"""
Phase 6 — Evidence Inspector.

For every event thumbnail, before/event/after frame, and clip generated
by S12, verify: file exists, size > 0, and file is readable as an image.

Writes:
  reports/evidence-inspection-archive001-60s.json
  reports/evidence-inspection-archive001-60s.md
"""
from __future__ import annotations
import json, sys, time
from pathlib import Path

BACKEND_DIR = Path(__file__).parent.parent
REPO_ROOT   = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

EVIDENCE_DIR = REPO_ROOT / "results" / "TCE-v1.0" / "evidence-archive_001_60s"
REPORTS_DIR  = REPO_ROOT / "reports"


def check_file(path_str: str) -> dict:
    p = Path(path_str)
    result = {"path": str(p), "exists": p.exists(), "size_bytes": 0, "readable": False, "status": "MISSING"}
    if not p.exists():
        result["status"] = "EVIDENCE_GENERATION_FAILURE"
        return result
    result["size_bytes"] = p.stat().st_size
    if result["size_bytes"] == 0:
        result["status"] = "ZERO_BYTES"
        return result
    # Try to read as image
    if p.suffix.lower() in (".jpg", ".jpeg", ".png"):
        try:
            import cv2
            img = cv2.imread(str(p))
            if img is not None and img.size > 0:
                result["readable"] = True
                result["image_shape"] = list(img.shape)
                result["status"] = "OK"
            else:
                result["status"] = "UNREADABLE_IMAGE"
        except Exception as e:
            result["status"] = "READ_ERROR: %s" % str(e)
    elif p.suffix.lower() in (".mp4", ".avi", ".mov"):
        try:
            import cv2
            cap = cv2.VideoCapture(str(p))
            frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            cap.release()
            result["readable"] = frames > 0
            result["video_frames"] = frames
            result["status"] = "OK" if frames > 0 else "ZERO_FRAME_VIDEO"
        except Exception as e:
            result["status"] = "READ_ERROR: %s" % str(e)
    elif p.suffix.lower() == ".json":
        try:
            json.loads(p.read_text(encoding="utf-8"))
            result["readable"] = True
            result["status"] = "OK"
        except Exception as e:
            result["status"] = "JSON_PARSE_ERROR: %s" % str(e)
    else:
        result["readable"] = True
        result["status"] = "OK (not validated)"
    return result


def main():
    if not EVIDENCE_DIR.exists():
        print("ERROR: Evidence directory not found: %s" % EVIDENCE_DIR)
        sys.exit(1)

    print("Phase 6 — Evidence Inspection")
    print("Evidence dir: %s" % EVIDENCE_DIR)
    print()

    # Collect all files
    all_files = sorted(EVIDENCE_DIR.rglob("*"))
    all_files = [f for f in all_files if f.is_file()]
    print("Total files found: %d" % len(all_files))
    print()

    results = {"by_category": {}, "failures": [], "summary": {}}

    # Categorize by subdirectory
    for f in all_files:
        rel = f.relative_to(EVIDENCE_DIR)
        parts = rel.parts
        category = parts[0] if len(parts) > 1 else "root"
        if category not in results["by_category"]:
            results["by_category"][category] = []
        check = check_file(str(f))
        check["relative_path"] = str(rel)
        results["by_category"][category].append(check)
        if check["status"] not in ("OK", "OK (not validated)"):
            results["failures"].append(check)

    # Summary
    ok_count = sum(
        1 for cat in results["by_category"].values()
        for c in cat if c["status"] in ("OK", "OK (not validated)")
    )
    fail_count = len(results["failures"])
    results["summary"] = {
        "total_files":    len(all_files),
        "ok":             ok_count,
        "failures":       fail_count,
        "evidence_success_rate": round(ok_count / max(len(all_files), 1) * 100, 1),
    }

    # Print by category
    for cat, items in sorted(results["by_category"].items()):
        ok = sum(1 for i in items if i["status"] in ("OK","OK (not validated)"))
        print("  [%s] %d files, %d OK, %d failures" % (cat, len(items), ok, len(items)-ok))
        for item in items[:3]:
            print("    %s — %s (%d bytes)" % (
                item["relative_path"], item["status"], item["size_bytes"]
            ))
        if len(items) > 3:
            print("    ... and %d more" % (len(items)-3))
    print()

    if results["failures"]:
        print("FAILURES:")
        for f in results["failures"]:
            print("  EVIDENCE_GENERATION_FAILURE: %s — %s" % (f["relative_path"], f["status"]))
    else:
        print("No evidence failures detected.")
    print()
    print("Summary: %d/%d OK (%.1f%%)" % (ok_count, len(all_files), results["summary"]["evidence_success_rate"]))

    # Sample visual inspection: pick one thumbnail and one frame
    thumbnails = [
        item for cat, items in results["by_category"].items()
        if "thumbnail" in cat.lower()
        for item in items if item["status"] == "OK"
    ]
    annotated = [
        item for cat, items in results["by_category"].items()
        if "annotated" in cat.lower()
        for item in items if item["status"] == "OK"
    ]
    if thumbnails:
        t = thumbnails[0]
        print()
        print("Sample thumbnail: %s — %s" % (t["relative_path"], t.get("image_shape", "?")))
    if annotated:
        a = annotated[0]
        print("Sample annotated: %s — %s" % (a["relative_path"], a.get("image_shape", "?")))

    # Save JSON
    out_json = REPORTS_DIR / "evidence-inspection-archive001-60s.json"
    with open(out_json, "w") as fp:
        json.dump(results, fp, indent=2, default=str)

    # Save MD
    out_md = REPORTS_DIR / "evidence-inspection-archive001-60s.md"
    with open(out_md, "w", encoding="utf-8") as fp:
        fp.write("# Evidence Inspection — archive_001 60s\n\n")
        fp.write("Evidence dir: `%s`  \n" % EVIDENCE_DIR)
        fp.write("Measured: %s  \n\n" % time.strftime("%Y-%m-%d %H:%M"))
        fp.write("## Summary\n\n")
        fp.write("| Metric | Value |\n|---|---|\n")
        fp.write("| Total files | %d |\n" % results["summary"]["total_files"])
        fp.write("| OK | %d |\n" % results["summary"]["ok"])
        fp.write("| Failures | %d |\n" % results["summary"]["failures"])
        fp.write("| Success rate | %.1f%% |\n\n" % results["summary"]["evidence_success_rate"])
        fp.write("## By Category\n\n")
        fp.write("| Category | Files | OK | Failures |\n|---|---|---|---|\n")
        for cat, items in sorted(results["by_category"].items()):
            ok_c = sum(1 for i in items if i["status"] in ("OK","OK (not validated)"))
            fp.write("| %s | %d | %d | %d |\n" % (cat, len(items), ok_c, len(items)-ok_c))
        if results["failures"]:
            fp.write("\n## Failures\n\n")
            for f in results["failures"]:
                fp.write("- `%s` — **%s**\n" % (f["relative_path"], f["status"]))
        else:
            fp.write("\n## Failures\n\n_No failures detected._\n")

    print()
    print("JSON: %s" % out_json)
    print("MD:   %s" % out_md)


if __name__ == "__main__":
    main()
