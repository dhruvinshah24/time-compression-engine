# Five-video UNISV infrared person-detection experiment

Completed locally on NVIDIA GeForce RTX 2050, using PyTorch 2.11.0+cu128.

## Scope and method

Exactly five source videos were read from `C:/Users/acorp/OneDrive/Desktop/UNISV-Dataset/UNISV/Walk`.

| Split | Videos | Saved frames |
| --- | --- | ---: |
| Train | v_Walk_g01_c01, v_Walk_g02_c01, v_Walk_g05_c01 | 71 |
| Validation | v_Walk_g03_c01 | 49 |
| Test | v_Walk_g04_c01 | 47 |

Sampled every second frame. YOLO11l supplied person boxes at confidence >= 0.45. Training frames without teacher detections were excluded, leaving 71 frames and 72 boxes. Validation and test retained empty frames. Location groups are disjoint. Labels have not been manually verified.

A COCO-pretrained YOLO11n was adapted to one class, person, for 20 epochs at image size 640 and batch size 4. The first 10 layers were frozen. AdamW used a starting learning rate of 0.0003; seed 42; color hue/saturation augmentation and mosaic were disabled. Validation selected the best checkpoint. The test split was evaluated only after training. Training took approximately 58.5 seconds; preparation, training and evaluation took 101.2 seconds in total.

## Results against automatic test labels

| Metric | Original YOLO11n | Fine-tuned YOLO11n |
| --- | ---: | ---: |
| Precision | 93.44% | 97.65% |
| Recall | 97.06% | 100.00% |
| mAP at IoU 0.50 | 98.08% | 99.26% |
| mAP across IoU 0.50–0.95 | 87.11% | 85.45% |
| Predicted boxes at confidence 0.25 | 45 | 46 |

Precision and recall above use the validator's selected confidence operating point, not necessarily 0.25. Both models were evaluated on the same 47 test frames and 44 automatic reference boxes.

These are teacher-agreement scores, not independently measured detection accuracy. Confidence gains are not proof of correctness. Stricter localization agreement decreased by 1.66 percentage points. The experiment does not establish a general accuracy improvement, an improvement over the larger YOLO11l application detector, or a tracking-ID improvement.

## Outputs

- Weights: `datasets/processed/unisv_walk_five_v1/runs/nightvision_candidate/weights/best.pt`
- Full provenance and results: `datasets/processed/unisv_walk_five_v1/experiment.json`
- Before/after contact sheet: `datasets/processed/unisv_walk_five_v1/before_after_test.jpg`
- Training history: `datasets/processed/unisv_walk_five_v1/runs/nightvision_candidate/results.csv`
- Reproduction script: `backend/scripts/finetune_unisv_five.py`

The standard application detector remains the default. An opt-in **Night Vision — Experimental** upload mode now uses this checkpoint for person boxes and retains the selected standard detector for other object classes. This routing is manual; brightness alone does not establish that footage is infrared. Manually annotate the reserved test clip and representative empty/difficult footage before considering automatic/default use.

## Local integration verification

- 37 focused detector/routing tests passed, and the frontend TypeScript check passed.
- The upload page returned HTTP 200 and contained the new Night Vision option.
- Local job `JOB-20261031-D020871B`, using the reserved `v_Walk_g04_c01.mp4` clip, completed all 12 stages and produced six events.
- S04 recorded `detection_mode=night_vision`, model provenance `yolo11n+unisv-night-person-experimental`, and 28 person boxes across 30 processed frames. Counts are pipeline outputs, not manually verified accuracy measures.
- Model settings are saved with each job so reprocessing preserves the chosen mode. Selecting night vision with a missing checkpoint returns an explicit error instead of silently falling back.
- The deployment checkpoint is included at `backend/models/nightvision-unisv-five-v1.pt`. The application uses this repository-relative location by default; `NIGHT_VISION_WEIGHTS` can override it. Training data and intermediate artifacts remain ignored.

Source dataset attribution: Feng Z, Wang X, Zhou J, et al. *MDJ: A Multi-Scale Difference Joint Keyframe Extraction Algorithm for Infrared Surveillance Video Action Recognition*, Digital Signal Processing, 2024, 104469. The local dataset includes an MIT license, copyright 2024 Jonathan-fzq.
