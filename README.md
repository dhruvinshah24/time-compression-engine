# 🧠 Time Compression Engine (TCE)

> **Research-grade video event summarization system** — detects every person, object, and activity in long-duration video and compresses it into a precise, human-readable event timeline.

[![Python](https://img.shields.io/badge/Python-3.14-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green?logo=fastapi)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-14-black?logo=next.js)](https://nextjs.org)
[![YOLO11x](https://img.shields.io/badge/YOLO-11x-purple)](https://ultralytics.com)
[![CUDA](https://img.shields.io/badge/CUDA-13.2-76B900?logo=nvidia)](https://developer.nvidia.com/cuda-toolkit)

---

## What It Does

Upload a video (even 24-hour CCTV footage). TCE processes it through a 12-stage AI pipeline and returns:

- **Event timeline** - every person entry/exit, interaction, posture change, lighting event
- **31 event types** - from `person_walking` to `unattended_bag` and `person_fallen`
- **Compressed summary** - skip the boring parts, keep everything meaningful
- **Live dashboard** - real-time processing status, GPU metrics, event feed

## Architecture

```
Video Upload -> Frame Extraction -> Scene Detection -> Object Detection (YOLO11x + SAHI)
    -> Tracking -> Motion Analysis -> Event Understanding -> Confidence Fusion
    -> Story Building -> Ranking -> Summarization -> Export
```

### Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI + Python 3.14 |
| Frontend | Next.js 14 + Framer Motion |
| Detection | YOLO11x (57M params, mAP 54.7) |
| Tiling | SAHI batch GPU tile inference |
| GPU | NVIDIA RTX 5050, CUDA 13.2, PyTorch 2.13 |
| Tracking | Custom IoU + appearance tracker |
| Events | 7-pass semantic understanding engine |

---

## Key Features

### GPU-Accelerated Pipeline
- Full CUDA inference on YOLO11x - 38 fps on 1080p
- SAHI tiled detection for small objects (phones at 15m range)
- Adaptive frame skipping - more frames when motion is detected

### 31 Event Types

| Category | Events |
|---|---|
| Motion | walking, running, loitering |
| Posture | sitting, standing up, crouching, fallen |
| Interaction | using phone/laptop, drinking, reading, carrying |
| Security | unattended bag, person fallen, group gathering, package left |
| Scene | light on/off, door opened/closed |
| Vehicle | approaching, receding, stopped |

### Multi-Model Registry
```
yolo11x (default) . yolo11l . yolo11m . yolo11s . yolo11n
yolov8x . yolov8l . yolov8s-worldv2 . yolov8l-worldv2
```

---

## Getting Started

### Prerequisites
- Python 3.11+
- Node.js 18+
- NVIDIA GPU with CUDA 12+ (CPU fallback works too)

### Backend
```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:3000** and upload a video.

API docs: **http://localhost:8000/api/docs**

---

## Project Structure

```
time-compression-engine/
├── backend/
│   ├── app/
│   │   ├── api/v1/routes/        # FastAPI endpoints
│   │   ├── engines/              # Perception / Semantic / Temporal AI
│   │   ├── pipeline/stages/      # 12-stage processing pipeline
│   │   ├── model_registry/       # YOLO model management
│   │   └── utils/                # SAHI, adaptive skip, benchmark, tracking
│   └── requirements.txt
├── frontend/
│   └── src/app/
│       ├── (dashboard)/          # Main dashboard + event feed
│       ├── upload/               # Video upload page
│       ├── processing/[jobId]/   # Real-time processing view
│       └── timeline/[videoId]/   # Event timeline viewer
└── README.md
```

---

## Pipeline Stages

| Stage | Name | Description |
|---|---|---|
| S01 | Upload | Video ingestion + metadata extraction |
| S02 | Extract | Frame extraction (adaptive rate) |
| S03 | Scene Detect | Shot boundary + scene change detection |
| S04 | Object Detect | YOLO11x + SAHI GPU inference |
| S05 | Track | Multi-object tracking with ReID |
| S06 | Motion Analyze | Velocity, direction, approach signals |
| S07 | Event Understand | 7-pass semantic engine (31 event types) |
| S08 | Confidence Fusion | Multi-source evidence merging |
| S09 | Story Build | Narrative continuity + sequence building |
| S10 | Rank | Event importance scoring |
| S11 | Summarize | Compression + highlight selection |
| S12 | Export | Timeline JSON + clip generation |

---

## Performance

| Metric | Value |
|---|---|
| Detection speed (1080p) | 38 fps (YOLO11x GPU) |
| SAHI tiled inference | 85ms for 4-tile batch |
| GPU VRAM usage | ~290MB (yolo11x) |
| Supported video length | 24h+ (chunked processing) |

---

## Roadmap

- [ ] BoT-SORT tracker integration
- [ ] LLM-based event narration (GPT-4V / Gemini)
- [ ] Real-time RTSP stream support
- [ ] PostgreSQL + async persistence layer
- [ ] Docker Compose deployment

---

**Dhruvin Shah** - [@dhruvinshah24](https://github.com/dhruvinshah24)
