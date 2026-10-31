"""Five-video, GPU-only pseudo-label adaptation. Outputs are experimental, not ground truth."""
from __future__ import annotations

import argparse
import gc
import json
import time
from pathlib import Path

import cv2
import numpy as np
import torch
from ultralytics import YOLO


VIDEOS = {
    "train": ["v_Walk_g01_c01.mp4", "v_Walk_g02_c01.mp4", "v_Walk_g05_c01.mp4"],
    "val": ["v_Walk_g03_c01.mp4"],
    "test": ["v_Walk_g04_c01.mp4"],
}


def dump(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--teacher", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=20)
    args = parser.parse_args()
    if not torch.cuda.is_available():
        raise RuntimeError("This experiment requires CUDA; refusing silent CPU fallback.")
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    started = time.time()
    report = {
        "status": "preparing", "gpu": torch.cuda.get_device_name(0),
        "torch": torch.__version__, "videos": VIDEOS,
        "label_source": "YOLO11l person predictions, confidence >= 0.45; NOT human ground truth",
        "limitations": [
            "Exactly five short videos; three train, one validation, one untouched test location.",
            "Pseudo-label scores measure agreement with the teacher, not true detection accuracy.",
            "Frames with no teacher detection are excluded from training to avoid false negative supervision.",
            "Person-only candidate; not a replacement for the general multi-class detector.",
        ],
        "frames": [],
    }
    dump(out / "experiment.json", report)
    teacher = YOLO(str(args.teacher.resolve()))
    for split, names in VIDEOS.items():
        image_dir, label_dir = out / "images" / split, out / "labels" / split
        image_dir.mkdir(parents=True)
        label_dir.mkdir(parents=True)
        for name in names:
            source = args.source / name
            if not source.is_file():
                raise FileNotFoundError(source)
            cap = cv2.VideoCapture(str(source))
            frame_idx = 0
            sampled = boxes_count = kept = 0
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                frame_idx += 1
                if (frame_idx - 1) % 2:
                    continue
                sampled += 1
                result = teacher.predict(frame, device=0, imgsz=640, classes=[0], conf=0.45, verbose=False)[0]
                boxes = result.boxes.xywhn.cpu().numpy()
                confidences = result.boxes.conf.cpu().tolist()
                stem = f"{source.stem}_f{frame_idx:05d}"
                include = split != "train" or len(boxes) > 0
                if include:
                    cv2.imwrite(str(image_dir / f"{stem}.jpg"), frame)
                    lines = ["0 " + " ".join(f"{float(v):.6f}" for v in box) for box in boxes]
                    (label_dir / f"{stem}.txt").write_text("\n".join(lines), encoding="utf-8")
                    kept += 1
                boxes_count += len(boxes)
                report["frames"].append({"video": name, "split": split, "frame": frame_idx,
                    "image": f"images/{split}/{stem}.jpg" if include else None,
                    "draft_boxes": len(boxes), "confidences": confidences, "human_reviewed": False})
            cap.release()
            print(f"PREPARED {split}: {name}: {sampled} sampled, {kept} saved, {boxes_count} draft boxes", flush=True)
        if not any(label_dir.glob("*.txt")) or not any(p.stat().st_size for p in label_dir.glob("*.txt")):
            raise RuntimeError(f"No usable person labels in {split}; cannot train responsibly.")
    del teacher
    gc.collect()
    torch.cuda.empty_cache()
    yaml_path = out / "dataset.yaml"
    yaml_path.write_text(f"path: {out.as_posix()}\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n  0: person\n", encoding="utf-8")
    report["status"] = "training"
    dump(out / "experiment.json", report)
    student = YOLO("yolo11n.pt")
    student.train(data=str(yaml_path), epochs=args.epochs, imgsz=640, batch=4,
        device=0, workers=0, project=str(out / "runs"), name="nightvision_candidate",
        seed=42, deterministic=True, optimizer="AdamW", lr0=0.0003,
        freeze=10, patience=8, amp=False, cache=False, plots=True,
        hsv_h=0.0, hsv_s=0.0, hsv_v=0.15, degrees=0.0, translate=0.05,
        scale=0.2, fliplr=0.5, mosaic=0.0, mixup=0.0, close_mosaic=0,
        save=True, verbose=False)
    best = Path(student.trainer.best)
    del student
    gc.collect()
    torch.cuda.empty_cache()
    # Only after training: compare both models on the same untouched test video.
    metrics = {}
    test_images = sorted((out / "images" / "test").glob("*.jpg"))
    preview_indices = np.linspace(0, len(test_images) - 1, min(8, len(test_images)), dtype=int)
    panels = {}
    for tag, weight in [("pretrained", "yolo11n.pt"), ("finetuned", str(best))]:
        model = YOLO(weight)
        validation = model.val(data=str(yaml_path), split="test", device=0,
            imgsz=640, batch=4, workers=0, classes=[0], plots=True,
            project=str(out / "evaluation"), name=tag, verbose=False)
        metrics[tag] = {k: float(v) for k, v in validation.results_dict.items()}
        panels[tag] = []
        detection_count = 0
        for index, path in enumerate(test_images):
            result = model.predict(str(path), device=0, imgsz=640, classes=[0], conf=0.25, verbose=False)[0]
            detection_count += len(result.boxes)
            if index in preview_indices:
                image = cv2.resize(result.plot(), (480, 248))
                cv2.rectangle(image, (0, 0), (480, 24), (0, 0, 0), -1)
                cv2.putText(image, f"{tag}: {path.stem[-6:]}", (8, 17), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
                panels[tag].append(image)
        metrics[tag]["test_detections_at_0.25"] = detection_count
        del model
        gc.collect()
        torch.cuda.empty_cache()
    sheet = np.vstack([np.hstack(pair) for pair in zip(panels["pretrained"], panels["finetuned"])])
    cv2.imwrite(str(out / "before_after_test.jpg"), sheet)
    report.update(status="completed", elapsed_seconds=round(time.time() - started, 1),
        best_weights=str(best), test_metrics_against_pseudo_labels=metrics,
        deployment="Not activated; original application detector unchanged.")
    dump(out / "experiment.json", report)
    (out / "README.md").write_text(
        "# Five-video infrared person-detector experiment\n\n"
        "Experimental YOLO11n weights trained on YOLO11l-generated labels. No labels were manually verified.\n\n"
        "Three distinct location videos train the model; one validates it; a fifth is reserved for testing. "
        "Test mAP/precision/recall are agreement with automatic labels, not verified real-world accuracy. "
        "Inspect before_after_test.jpg and manually annotate held-out footage before deployment.\n\n"
        f"Weights: `{best}`\n\nThe application has not been switched to these person-only weights.\n",
        encoding="utf-8")
    print("COMPLETED " + str(best), flush=True)
    print(json.dumps(metrics, indent=2), flush=True)


if __name__ == "__main__":
    main()
