# 📐 Verified UML Architectural Specification
## Project: Time Compression Engine (TCE v1.0.1 / v1.1)

> **Document Status**: Production Architecture & System Design Specification  
> **Target Audience**: System Architects, Senior Software Engineers, Academic Evaluators, and AI LLM Assistants (Claude, GPT, Gemini) generating IEEE 830 / ISO/IEC/IEEE 29148 SRS documentation.  
> **Source Grounding**: 100% faithful to the active codebase, 12-stage sequential pipeline ($S01 \to S12$), 3-Engine decoupled design, and measured benchmarks on the NVIDIA RTX 5050 GPU. Zero invented or hallucinated features.  
> **Mermaid Compatibility**: Fully tested and optimized for reliable rendering across VS Code, GitHub Markdown, and Claude without parser syntax crashes, line overlaps, or text truncation.

---

## 📑 Table of Contents
1. [1. Use Case Diagram (Actor-System Interactions)](#1-use-case-diagram-actor-system-interactions)
2. [2. Class Diagram (Domain Object Model & Engine Architecture)](#2-class-diagram-domain-object-model--engine-architecture)
3. [3. Sequence Diagram (End-to-End Ingestion, Processing & Playback)](#3-sequence-diagram-end-to-end-ingestion-processing--playback)
4. [4. Activity Diagram (Pipeline Dataflow & Perspective Elevation Logic)](#4-activity-diagram-pipeline-dataflow--perspective-elevation-logic)
5. [5. State Machine Diagram (Track Lifecycle & Job Processing)](#5-state-machine-diagram-track-lifecycle--job-processing)
6. [6. Component Diagram (Subsystem Boundaries & Modular Architecture)](#6-component-diagram-subsystem-boundaries--modular-architecture)
7. [7. Deployment Diagram (Hardware, Docker Containers & Topography)](#7-deployment-diagram-hardware-docker-containers--topography)
8. [8. Source Code Traceability & IEEE 830 Compliance Matrix](#8-source-code-traceability--ieee-830-compliance-matrix)

---

## 1. Use Case Diagram (Actor-System Interactions)

### 1.1 Overview & Actor Taxonomy
The Use Case Diagram defines the interactions between human/automated actors and the Time Compression Engine system boundary:
- **Surveillance Operator / Forensic Analyst (Primary Human Actor)**:
  - Ingests raw CCTV/surveillance video files and selects optimization profiles (`fast`, `balanced`, `accuracy`).
  - Monitors real-time 12-stage pipeline telemetry and stage logs.
  - Reviews accelerated footage in the Forensic Cinema Player with synchronized HUD bounding box overlays.
  - Queries semantic events, inspects Before/During/After context frames, and verifies loss prevention alerts.
  - Performs one-click seeking to actor milestones and reviews multi-actor ReID appearance dossiers.
- **Security Administrator / System Engineer (Secondary Human Actor)**:
  - Audits system diagnostics, GPU VRAM footprint, and hardware utilization.
  - Inspects frozen benchmark reference parameters (`TCE_V1_REFERENCE`) to ensure audit reproducibility.
- **FFmpeg / Hardware Acceleration Subsystem (Automated External Actor)**:
  - Performs container probing, 5x stride frame extraction, keyframe decoding, and highlight MP4 clip slicing.

### 1.2 Diagram (Mermaid)

```mermaid
flowchart LR
    %% Primary and Secondary Actors
    Operator(("Surveillance Operator / Forensic Analyst"))
    Admin(("Security Administrator / System Engineer"))
    FFmpegWorker(["FFmpeg / Hardware Subsystem"])

    %% System Boundary
    subgraph SystemBoundary ["Time Compression Engine (TCE Platform)"]
        
        subgraph IngestionPkg ["1. Video Ingestion & Telemetry"]
            UC_Upload(["UC-01: Ingest Surveillance Video"])
            UC_Profile(["UC-02: Select Model Profile (fast / balanced / accuracy)"])
            UC_Probe(["UC-03: Probe Stream & Validate Video Container"])
            UC_Monitor(["UC-04: Monitor 12-Stage Pipeline Telemetry"])
        end

        subgraph PlaybackPkg ["2. Forensic Cinema Player & HUD"]
            UC_Cinema(["UC-05: Review Forensic Cinema Video Player"])
            UC_Stream(["UC-06: Stream HTTP 206 Partial Video Content"])
            UC_HUD(["UC-07: Render Synchronized HUD Bounding Boxes"])
            UC_Seek(["UC-08: One-Click Seek to Actor or Milestone"])
            UC_Dossier(["UC-09: Inspect Actor ReID Dossier & Gallery"])
            UC_Inventory(["UC-10: Search Physical Assets & Desk Inventory"])
        end

        subgraph AnalysisPkg ["3. Semantic Intelligence & Threat Audit"]
            UC_Filter(["UC-11: Query & Filter Semantic Events"])
            UC_Context(["UC-12: Inspect Before / Event / After Context Frames"])
            UC_Alerts(["UC-13: Audit Threat & Loss Prevention Alerts"])
            UC_Brief(["UC-14: Review Narrative Brief & Key Milestones"])
        end

        subgraph OpsPkg ["4. System Configuration & Hardware Audit"]
            UC_Diagnostics(["UC-15: Monitor VRAM Footprint & Hardware Diagnostics"])
            UC_Settings(["UC-16: Inspect Frozen Benchmark Settings"])
        end

    end

    %% Operator Connections
    Operator --> UC_Upload
    Operator --> UC_Monitor
    Operator --> UC_Cinema
    Operator --> UC_Dossier
    Operator --> UC_Inventory
    Operator --> UC_Filter
    Operator --> UC_Alerts
    Operator --> UC_Brief

    %% Administrator Connections
    Admin --> UC_Upload
    Admin --> UC_Diagnostics
    Admin --> UC_Settings

    %% System Dependencies (Includes & Extends)
    UC_Upload -.->|includes| UC_Profile
    UC_Upload -.->|includes| UC_Probe
    UC_Cinema -.->|includes| UC_Stream
    UC_Cinema -.->|includes| UC_HUD
    UC_Dossier -.->|extends| UC_Seek
    UC_Inventory -.->|extends| UC_Seek
    UC_Filter -.->|includes| UC_Context

    %% External System Connections
    UC_Probe --- FFmpegWorker
    UC_Stream --- FFmpegWorker
```

---

## 2. Class Diagram (Domain Object Model & Engine Architecture)

### 2.1 Overview & Architecture Grounding
The Class Diagram models the core domain entities, data contracts, and engine managers implemented in `backend/app/`.
- **Orchestration Backbone**: `PipelineOrchestrator` controls execution flow using `PipelineContext` and standard `StageResult` outputs.
- **Perception Intelligence (`app/engines/perception`)**: Models physical tracking via `Track`, `TrackState`, `TrackObservation`, `TrackBBox`, and `MotionProfile`.
- **Semantic Intelligence (`app/engines/semantic`)**: Evaluates domain rules through `Event`, enforces perspective verification via `SceneStairGuard` and `StairGuardResult`, and calibrates multi-factor confidence via `ConfidenceFuser`.
- **Temporal Intelligence (`app/engines/temporal`)**: Structures narrative continuity via `StorySegment`, `StoryCompleteness`, `EventGraph`, `RankingEngine`, `CompressionPolicy`, and `NarrativeValidator`.

### 2.2 Diagram (Mermaid)

```mermaid
classDiagram
    %% Core Orchestration Backbone
    class PipelineOrchestrator {
        -job_repo: JobRepository
        -event_repo: EventRepository
        +run(context: PipelineContext) Boolean
        +get_status(job_id: String) Dict
    }

    class PipelineContext {
        +job_id: String
        +video_id: String
        +video_path: String
        +output_dir: String
        +settings: Dict
        +stage_results: Dict
        +metadata: Dict
        +get_stage_result(name: String) StageResult
    }

    class StageResult {
        +success: Boolean
        +stage_name: String
        +duration_ms: Int
        +warnings: List
        +errors: List
        +metrics: Dict
        +artifacts: List
        +logs: List
        +to_dict() Dict
    }

    %% Perception Engine Classes
    class TrackState {
        <<enumeration>>
        TENTATIVE
        ACTIVE
        LOST
        ENDED
    }

    class TrackBBox {
        +x1: Float
        +y1: Float
        +x2: Float
        +y2: Float
        +confidence: Float
        +class_id: Int
        +class_name: String
        +cx() Float
        +cy() Float
        +width() Float
        +height() Float
        +area() Float
    }

    class TrackObservation {
        +frame_number: Int
        +timestamp_ms: Float
        +bbox: TrackBBox
        +detection_confidence: Float
    }

    class Track {
        +track_id: Int
        +class_name: String
        +class_id: Int
        +state: TrackState
        +created_frame: Int
        +created_timestamp_ms: Float
        +last_seen_frame: Int
        +last_seen_timestamp_ms: Float
        +current_bbox: TrackBBox
        +observations: List
        +lost_frames: Int
        +total_frames_matched: Int
        +confirmed_at_frame: Int
        +person_label: String
        +entry_direction: String
        +exit_direction: String
        +appearance_embedding: Object
        +age_frames() Int
        +track_length_ms() Float
        +avg_confidence() Float
        +is_confirmed() Boolean
        +update(obs: TrackObservation) Void
        +mark_lost() Void
        +finalize() Void
    }

    class MotionProfile {
        +track_id: Int
        +velocity_x: Float
        +velocity_y: Float
        +speed_magnitude: Float
        +speed_class: String
        +direction_compass: String
        +is_approaching: Boolean
        +is_receding: Boolean
    }

    %% Semantic Intelligence Classes
    class Event {
        +event_id: String
        +event_type: String
        +track_id: Int
        +class_name: String
        +rule_name: String
        +confidence: Float
        +evidence: Dict
        +start_frame: Int
        +end_frame: Int
        +start_ms: Float
        +end_ms: Float
        +dependencies: List
        +duration_ms() Float
    }

    class SceneStairGuard {
        -model_name: String
        -target_classes: List
        +evaluate_track_stair_context(track: Track, frame_paths: Dict, frame_w: Int, frame_h: Int) StairGuardResult
    }

    class StairGuardResult {
        +is_verified: Boolean
        +final_stair_confidence: Float
        +scene_stair_confidence: Float
        +scene_stair_persistence: Int
        +spatial_relation_iop: Float
        +fallback_activity_label: String
        +to_dict() Dict
    }

    class ConfidenceFuser {
        -config: FusionConfig
        +fuse(events: List, all_tracks: List, motion_profiles: List) List
    }

    class FusionConfig {
        +w_detection: Float
        +w_motion: Float
        +w_rule: Float
        +w_track_stability: Float
        +w_scene_reliability: Float
        +min_fused_confidence: Float
    }

    %% Temporal Intelligence Classes
    class StoryCompleteness {
        <<enumeration>>
        COMPLETE
        PARTIAL
        ENTRY_ONLY
        EXIT_ONLY
        MINIMAL
    }

    class StorySegment {
        +segment_id: String
        +track_id: Int
        +person_label: String
        +events: List
        +completeness: StoryCompleteness
        +narrative_score: Float
        +start_ms: Float
        +end_ms: Float
        +duration_ms() Float
        +event_count() Int
    }

    class EventNode {
        +node_id: String
        +event: Event
        +in_edge_ids: List
        +out_edge_ids: List
        +degree() Int
    }

    class EventEdge {
        +edge_id: String
        +source_node_id: String
        +target_node_id: String
        +relationship: String
        +weight: Float
    }

    class EventGraph {
        +nodes: Dict
        +edges: Dict
        +add_node(event: Event) EventNode
        +add_edge(src: String, tgt: String, rel: String, weight: Float) EventEdge
        +get_hub_nodes() List
    }

    class RankingEngine {
        -config: Dict
        +rank(segments: List, profiles: Dict) List
    }

    class CompressionPolicy {
        -target_ratio: Float
        +apply(ranked_segments: List) Dict
    }

    class NarrativeValidator {
        +validate(kept_segments: List, event_graph: EventGraph) Dict
    }

    %% Relationships
    PipelineOrchestrator --> PipelineContext : executes
    PipelineContext *-- StageResult : aggregates
    Track --> TrackState : possesses
    Track *-- TrackObservation : records
    TrackObservation *-- TrackBBox : contains
    Track ..> MotionProfile : produces
    
    SceneStairGuard ..> StairGuardResult : outputs
    ConfidenceFuser ..> Event : calibrates
    ConfidenceFuser *-- FusionConfig : configured_by

    StorySegment --> StoryCompleteness : classified_by
    StorySegment o-- Event : clusters
    EventNode *-- Event : encapsulates
    EventGraph *-- EventNode : contains
    EventGraph *-- EventEdge : contains
    StorySegment ..> EventGraph : projects_to
    
    RankingEngine ..> StorySegment : scores
    CompressionPolicy ..> StorySegment : filters_with_atomicity
    NarrativeValidator ..> StorySegment : verifies_continuity
```

---

## 3. Sequence Diagram (End-to-End Ingestion, Processing & Playback)

### 3.1 Overview
The Sequence Diagram documents the end-to-end operational flow of the system:
1. **Video Ingestion & Validation**: The client uploads the video, triggers metadata probing via ffprobe, and initializes database records.
2. **Background Execution**: FastAPI launches the `PipelineOrchestrator` in a background worker task, sequentially executing the 3 engines across stages $S01 \to S12$.
3. **Forensic Cinema Playback**: The frontend retrieves the processed timeline, streams video slices using `HTTP 206 Partial Content`, and synchronizes HUD bounding box overlays.

### 3.2 Diagram (Mermaid)

```mermaid
sequenceDiagram
    autonumber
    actor Operator as "Surveillance Operator"
    participant UI as "Next.js Web UI"
    participant API as "FastAPI Gateway (/api/v1)"
    participant Orch as "PipelineOrchestrator"
    participant S01_S06 as "Perception Engine (S01-S06)"
    participant S07_S08 as "Semantic Engine (S07-S08)"
    participant S09_S12 as "Temporal Engine (S09-S12)"
    participant Store as "Storage & Database"

    %% Ingestion
    Operator->>UI: Select Surveillance Video & Profile ("accuracy")
    UI->>API: POST /api/v1/upload (Video File, Profile="accuracy")
    activate API
    API->>Store: Save raw video container to /storage/uploads/
    API->>Store: ffprobe metadata extraction (fps, duration, resolution)
    API->>Store: Create VideoRecord & JobRecord (status="queued", progress=0)
    API-->>UI: 200 OK (job_id, video_id, status="queued")
    deactivate API

    %% Pipeline Launch
    Note over API,Orch: BackgroundTasks triggers PipelineOrchestrator
    API->>Orch: run(context)
    activate Orch
    Orch->>Store: Update JobRecord (status="running", progress=0)

    %% Perception Stages
    loop Stages S01 to S06 [Perception Engine]
        Orch->>S01_S06: Execute Stage (context)
        activate S01_S06
        S01_S06->>Store: Extract 5x frames (S02) / YOLO11 infer (S04) / ByteTrack (S05)
        S01_S06-->>Orch: StageResult (success=True, tracks, kinematics)
        deactivate S01_S06
        Orch->>Store: Update Job progress (+8.3% per stage)
    end

    %% Semantic Stages
    loop Stages S07 to S08 [Semantic Engine]
        Orch->>S07_S08: Execute Stage (context, tracks, frames)
        activate S07_S08
        Note over S07_S08: S07: 7-Pass Rules + SceneStairGuard 1.5x ROI Verification
        Note over S07_S08: S08: 5-Factor Linear Confidence Fusion
        S07_S08-->>Orch: StageResult (fused_events, calibrated_scores)
        deactivate S07_S08
        Orch->>Store: Update Job progress (+8.3% per stage)
    end

    %% Temporal Stages
    loop Stages S09 to S12 [Temporal Engine]
        Orch->>S09_S12: Execute Stage (context, fused_events)
        activate S09_S12
        Note over S09_S12: S09: Event Graph & Story Segments
        Note over S09_S12: S10: Multi-Factor Importance Ranking
        Note over S09_S12: S11: Narrative Chain Atomicity Policy
        Note over S09_S12: S12: FFmpeg Highlight Slicing & export_manifest.json
        S09_S12->>Store: Save MP4 highlight clips and export_manifest.json
        S09_S12-->>Orch: StageResult (validation_report, manifest_path)
        deactivate S09_S12
        Orch->>Store: Update Job progress (+8.3% per stage)
    end

    %% Finalization
    Orch->>Store: Finalize JobRecord (status="completed", progress=100)
    deactivate Orch

    %% Playback & Forensic Review
    Operator->>UI: Open Forensic Timeline Page (/timeline/[videoId])
    UI->>API: GET /api/v1/timeline/{videoId}
    API->>Store: Query Events, Tracks, Person Dossiers, Milestones
    API-->>UI: 200 OK (Timeline Payload)
    
    UI->>API: GET /api/v1/videos/{videoId}/stream (HTTP Range Header)
    activate API
    API->>Store: Read binary slice from storage
    API-->>UI: HTTP 206 Partial Content (Video Chunk)
    deactivate API
    UI->>Operator: Play Video with Synchronized HUD Overlays & One-Click Seeking
```

---

## 4. Activity Diagram (Pipeline Dataflow & Perspective Elevation Logic)

### 4.1 Overview & Decision Gates
The Activity Diagram models the step-by-step data transformations and decision gates across all 12 stages:
- **Early Corruption Guard**: Checks container validity before allocating inference memory.
- **Adaptive CLAHE Equalization**: Evaluates mean luminance to dynamically enhance low-light CCTV footage.
- **Global Camera Motion Gate**: Distinguishes true object movement from panning/shaking camera noise.
- **SceneStairGuard Perspective Verification**: Verifies vertical displacement against a $1.5\times$ dynamic person crop evaluated by YOLO-World v2, eliminating perspective depth drift false alarms.
- **5-Factor Confidence Filter**: Enforces the calibrated $\ge 0.35$ confidence threshold.
- **Narrative Chain Atomicity**: Guarantees that multi-event occupant stories are preserved as complete behavioral units.

### 4.2 Diagram (Mermaid)

```mermaid
flowchart TD
    Start(["Start: Upload Surveillance Video"]) --> Probe["Probe Video Stream & Validate Codec via ffprobe"]
    
    Probe --> CorruptCheck{"Is File Corrupted or Invalid?"}
    CorruptCheck -- "Yes" --> FailEarly["Raise VideoCorruptedError"]
    FailEarly --> TerminateFail(["Job Marked FAILED & Terminated"])
    
    CorruptCheck -- "No" --> ExtractFrames["S02: Frame Extraction via FFmpeg (5x Stride)"]
    ExtractFrames --> SceneDetect["S03: Adaptive Histogram & Scene Cut Analysis"]
    SceneDetect --> ClassifyBoundaries["Identify Scene Cuts & Discard Duplicate Frames"]
    
    ClassifyBoundaries --> LightCheck{"Mean Luminance < Low-Light Threshold?"}
    LightCheck -- "Yes" --> ApplyCLAHE["Apply CLAHE Adaptive Contrast Equalization"]
    LightCheck -- "No" --> NormalPass["Maintain Standard RGB Pipeline"]
    
    ApplyCLAHE --> ObjectDetect["S04: YOLO11 Object Detection Tensor Inference"]
    NormalPass --> ObjectDetect
    
    ObjectDetect --> Tracking["S05: Kalman State Filter & Hungarian IoU Matching"]
    Tracking --> ReID["Extract MobileNetV3 L2 Feature Embeddings"]
    ReID --> MotionAnalysis["S06: Trajectory Kinematics & Global Camera Homography"]
    
    MotionAnalysis --> CamMotionCheck{"Global Camera Motion Flagged?"}
    CamMotionCheck -- "Yes" --> SuppressTracks["Compensate Homography & Suppress Spurious Motion"]
    CamMotionCheck -- "No" --> KeepTracks["Retain Physical Object Motion Vectors"]
    
    SuppressTracks --> EventRules["S07: 7-Pass Domain Semantic Rule Engine"]
    KeepTracks --> EventRules
    
    EventRules --> ElevationCheck{"Vertical Velocity dy/dt Indicates Elevation Change?"}
    ElevationCheck -- "No" --> NormalLocomotion["Emit Standard Locomotion or Stationary Event"]
    
    ElevationCheck -- "Yes" --> ExpandROI["SceneStairGuard: Crop 1.5x Dynamic Person ROI"]
    ExpandROI --> QueryYOLOWorld["Query YOLO-World v2 with stair prompts"]
    QueryYOLOWorld --> StairCheck{"Stair Detected in Scene & IoP Overlap > 0.05?"}
    
    StairCheck -- "No" --> SuppressDrift["Suppress Perspective Drift: Fallback to walking"]
    StairCheck -- "Yes" --> EmitStair["Emit Verified walking_upstairs or walking_downstairs"]
    
    NormalLocomotion --> FuseConfidence["S08: 5-Factor Linear Confidence Fusion"]
    SuppressDrift --> FuseConfidence
    EmitStair --> FuseConfidence
    
    FuseConfidence --> ConfThreshold{"Fused Confidence >= 0.35 Threshold?"}
    ConfThreshold -- "No" --> DiscardEvent["Discard Low-Confidence False Positive Event"]
    ConfThreshold -- "Yes" --> RetainEvent["Retain Event for Narrative Graph Structuring"]
    
    DiscardEvent --> BuildGraph["S09: Construct Directed Event Graph G=(V,E)"]
    RetainEvent --> BuildGraph
    
    BuildGraph --> SegmentStories["Group Events into Actor-Centric Story Arcs"]
    SegmentStories --> RankSegments["S10: Multi-Factor Narrative Importance Ranking"]
    RankSegments --> CompressPolicy["S11: Enforce Narrative Chain Atomicity Policy"]
    
    CompressPolicy --> S12Export["S12: FFmpeg Lossless Highlight Slicing & Thumbs"]
    S12Export --> WriteManifest["Generate and Validate export_manifest.json"]
    WriteManifest --> Done(["End: Job Marked COMPLETED"])
```

---

## 5. State Machine Diagram (Track Lifecycle & Job Processing)

### 5.1 Multi-Object Track Lifecycle State Machine (S05 ByteTrack & ReID)
The core physical state machine of the computer vision pipeline. It manages tracking confidence, eliminates single-frame false detections, and tolerates temporary occlusions up to 30 frames ($1.0\text{s}$ at 30 fps):
- **TENTATIVE**: Newly spawned track; must be confirmed across $\ge 3$ consecutive frames before becoming visible.
- **ACTIVE**: Stable confirmed track with Kalman filter position updates and Hungarian IoU associations.
- **LOST**: Temporarily lost during occlusions or lighting dropouts; kept alive for up to 30 frames to permit ReID re-acquisition.
- **ENDED**: Object has permanently exited the camera field-of-view; trajectory finalized and appearance embedding archived.

```mermaid
stateDiagram-v2
    [*] --> TENTATIVE : Raw Detection Unmatched (Frame t)
    
    TENTATIVE --> ACTIVE : Matched for min_confirmation_frames (>= 3 frames)
    TENTATIVE --> ENDED : Unmatched in next frame (Single-frame noise discarded)
    
    ACTIVE --> ACTIVE : Successful Hungarian IoU Match (lost_frames reset to 0)
    ACTIVE --> LOST : Unmatched in current frame (lost_frames incremented)
    
    LOST --> ACTIVE : Re-matched by IoU or ReID embedding within 30 frames
    LOST --> LOST : Remains unmatched (lost_frames < 30)
    LOST --> ENDED : lost_frames >= 30 (Actor departed scene boundary)
    
    ENDED --> ARCHIVED : Extract MobileNetV3 L2 Embedding & Build Dossier
    ARCHIVED --> [*] : Track permanently saved to forensic timeline
```

### 5.2 System Job Processing Lifecycle State Machine
Governs the lifecycle of an ingested video processing task within `PipelineOrchestrator`:

```mermaid
stateDiagram-v2
    [*] --> QUEUED : Video Ingested & Job Created
    
    QUEUED --> RUNNING : PipelineOrchestrator Worker Dispatched
    
    RUNNING --> PERCEPTION_PASS : Stages S01 to S06 (Frames, YOLO11, ByteTrack)
    PERCEPTION_PASS --> SEMANTIC_PASS : Stages S07 to S08 (Rules, StairGuard, Fusion)
    SEMANTIC_PASS --> TEMPORAL_PASS : Stages S09 to S12 (Graph, Ranking, S12 Slicing)
    
    TEMPORAL_PASS --> COMPLETED : All 12 Stages Pass (Manifest Generated)
    
    RUNNING --> FAILED : Unhandled Stage Exception
    PERCEPTION_PASS --> FAILED : Hardware or Decoding Failure
    SEMANTIC_PASS --> FAILED : Reasoning Failure
    TEMPORAL_PASS --> FAILED : Slicing or Export Failure
    
    RUNNING --> CANCELLED : Terminated by Security Operator
    
    COMPLETED --> [*] : Highlights & Dossiers Ready
    FAILED --> [*] : Audit Error Logged
    CANCELLED --> [*] : Resources Released
```

---

## 6. Component Diagram (Subsystem Boundaries & Modular Architecture)

### 6.1 Overview
The Component Diagram illustrates the 4 decoupled architectural tiers:
- **Presentation Layer**: Next.js 14 client application with typed API client and HTML5 cinema video player.
- **Application Layer**: FastAPI 0.111.0 gateway providing REST routing, HTTP 206 chunked range streaming, and background task orchestration.
- **Core Processing Layer**: The 3 decoupled intelligence engines (Perception, Semantic, Temporal) executing stages $S01 \to S12$.
- **Persistence Layer**: PostgreSQL database and local storage volumes mounted for video assets.

### 6.2 Diagram (Mermaid)

```mermaid
flowchart TD
    %% Presentation Tier
    subgraph PresentationTier ["Presentation Layer (Next.js 14 Web Frontend)"]
        UI_Player["CinemaVideoPlayer<br/>(HTML5 Streaming & SVG HUD BBoxes)"]
        UI_Dossier["PersonDossierModal<br/>(Actor Gallery & Trajectory Inspector)"]
        UI_Events["EventsHub<br/>(Severity Filters & Context Frame Modals)"]
        UI_Telemetry["ProcessingMonitor<br/>(12-Stage Stepper & Live Telemetry)"]
        UI_Client["Typed API Client<br/>(lib/api/client.ts)"]
    end

    %% Application / API Tier
    subgraph APITier ["Application Layer (FastAPI 0.111.0 Gateway)"]
        API_Router["REST API Router<br/>(api/v1 routes)"]
        API_Stream["Video Range Streamer<br/>(HTTP 206 Partial Content)"]
        API_Orch["PipelineOrchestrator Service<br/>(Sequential 12-Stage Pipeline)"]
    end

    %% Core Processing Tier
    subgraph EngineTier ["Core Processing Layer (Three Decoupled Engines)"]
        subgraph PerceptionEngine ["1. Perception Intelligence Engine"]
            P_Extractor["FFmpeg Stride Extractor (S02)"]
            P_Scene["Histogram Scene Cut Detector (S03)"]
            P_Detect["YOLO11 Object Detector (S04)"]
            P_Track["ByteTrack Kalman Filter & ReID (S05)"]
            P_Motion["Kinematics & Homography (S06)"]
        end

        subgraph SemanticEngine ["2. Semantic Intelligence Engine"]
            S_Rules["18-Rule Domain Evaluator (S07)"]
            S_Stair["SceneStairGuard YOLO-World v2 (S07)"]
            S_Fuse["5-Factor Linear Confidence Fuser (S08)"]
        end

        subgraph TemporalEngine ["3. Temporal Intelligence Engine"]
            T_Graph["NetworkX Event Graph Builder (S09)"]
            T_Story["Story Segment Completeness Builder (S09)"]
            T_Rank["Multi-Factor Importance Ranker (S10)"]
            T_Compress["Chain Atomicity Policy Engine (S11)"]
            T_Export["FFmpeg Highlight Slicer & Validator (S12)"]
        end
    end

    %% Persistence Tier
    subgraph PersistenceTier ["Persistence Layer (Storage & Database)"]
        DB_Postgres[("PostgreSQL 16 Database<br/>(Videos, Jobs, Events, Tracks)")]
        FS_Uploads[("Filesystem: storage/uploads<br/>(Raw Surveillance Videos)")]
        FS_Outputs[("Filesystem: outputs/job_id<br/>(MP4 Clips, Thumbs, Manifests)")]
    end

    %% Clean Dataflow Connections
    UI_Player --> UI_Client
    UI_Dossier --> UI_Client
    UI_Events --> UI_Client
    UI_Telemetry --> UI_Client
    UI_Client ==>|"HTTP / JSON REST"| API_Router
    UI_Player ==>|"HTTP 206 Byte-Range"| API_Stream

    API_Router --> API_Orch
    API_Stream --> FS_Uploads
    API_Stream --> FS_Outputs

    API_Orch ==>|"Executes S01-S06"| PerceptionEngine
    PerceptionEngine ==>|"Tracks & Kinematics"| SemanticEngine
    SemanticEngine ==>|"Fused Semantic Events"| TemporalEngine
    TemporalEngine ==>|"Highlight MP4s & Manifest"| FS_Outputs

    P_Extractor --> FS_Uploads
    API_Router --> DB_Postgres
    API_Orch --> DB_Postgres
```

---

## 7. Deployment Diagram (Hardware, Docker Containers & Topography)

### 7.1 Overview
The Deployment Diagram defines the physical and container topology configured in `docker-compose.yml` and verified on the host platform:
- **Client Workstation**: Browser running the Next.js bundle with hardware-accelerated H.264 video decoding.
- **Host Server (Windows 11 / Ubuntu)**:
  - **Docker Network (`tce-network`)**: Bridges `tce_frontend` (Port 3000), `tce_backend` (Port 8000), `tce_postgres` (Port 5432), and `tce_redis` (Port 6379).
  - **Hardware Acceleration**: The backend container communicates directly with the **NVIDIA GeForce RTX 5050 Laptop GPU** (`sm_120`, Blackwell) via CUDA 13.2 and PyTorch. Peak VRAM footprint measured at **983 MB** (12% of 8 GB capacity).
  - **Mounted Host Volumes**: Maps host NVMe directories to `/storage/uploads/` and `/outputs/` for persistence across container restarts.

### 7.2 Diagram (Mermaid)

```mermaid
flowchart TD
    subgraph ClientNode ["Client Workstation (Forensic Operator PC)"]
        Browser["Modern Web Browser (Chrome / Edge / Firefox)<br/>- Next.js 14 Client Bundle<br/>- HTML5 Video Player with Hardware Decoders<br/>- SVG / Canvas Bounding Box Overlays"]
    end

    subgraph HostServer ["Host Machine / Edge Server (Windows 11 / Ubuntu Linux)"]
        subgraph HardwareEnv ["Host Hardware Resources"]
            GPU["NVIDIA GeForce RTX 5050 Laptop GPU<br/>- Architecture: sm_120 (Blackwell)<br/>- VRAM: 8 GB GDDR6 (Peak Usage: 983 MB)<br/>- CUDA Compute: 13.2 / PyTorch Direct Access"]
            CPU_RAM["Host CPU & System RAM<br/>- x86_64 Multi-Core CPU<br/>- 16 GB to 32 GB RAM"]
            NVMeDisk["High-Speed NVMe Storage<br/>- Mounted Volume: storage/uploads<br/>- Mounted Volume: outputs/job_id"]
        end

        subgraph DockerEnvironment ["Docker Container Runtime (docker-compose)"]
            ContainerFrontend["Container: tce_frontend<br/>- Node.js 18 Alpine<br/>- Next.js 14 Production Server<br/>- Port: 3000"]
            ContainerBackend["Container: tce_backend<br/>- Python 3.11 Runtime<br/>- FastAPI 0.111 / Uvicorn Server<br/>- PyTorch + CUDA 13.2 Runtime<br/>- FFmpeg 6.x Binary<br/>- Port: 8000"]
            ContainerPostgres["Container: tce_postgres<br/>- PostgreSQL 16 Alpine<br/>- Database: time_compression_engine<br/>- Port: 5432"]
            ContainerRedis["Container: tce_redis<br/>- Redis 7 Alpine<br/>- Cache & Background Task Broker<br/>- Port: 6379"]
        end
    end

    %% Network & Port Bindings
    Browser ==>|"HTTP :3000 (UI Traffic)"| ContainerFrontend
    Browser ==>|"HTTP :8000 (REST & HTTP 206 Streaming)"| ContainerBackend
    ContainerFrontend -.->|"Server Fetch :8000"| ContainerBackend

    ContainerBackend ==>|"TCP :5432 (SQLAlchemy / asyncpg)"| ContainerPostgres
    ContainerBackend ==>|"TCP :6379 (Redis Connection)"| ContainerRedis

    %% Hardware Acceleration & Storage Bindings
    ContainerBackend ==>|"CUDA IPC & TensorRT"| GPU
    ContainerBackend --- NVMeDisk
    ContainerPostgres --- NVMeDisk
```

---

## 8. Source Code Traceability & IEEE 830 Compliance Matrix

The matrix below provides complete two-way traceability linking each UML diagram directly to concrete source code implementation files, benchmark results, and target IEEE 830 SRS specification sections:

| UML Diagram | Architecture Level | Primary Codebase Files | Benchmark / Verified Metric | Target IEEE 830 Section |
| :--- | :--- | :--- | :--- | :--- |
| **1. Use Case Diagram** | User & System Boundary | `backend/app/api/v1/routes/`, `frontend/src/app/` | 8 active frontend routes, 0 mock data | Section 2.2 (User Characteristics) & 3.1 |
| **2. Class Diagram** | Domain Object Model | `backend/app/engines/`, `backend/app/pipeline/` | 12 SQLAlchemy models, 693 passing unit tests | Section 3.2 (Data / Entity Models) |
| **3. Sequence Diagram** | Ingestion & Playback Flow | `pipeline/orchestrator.py`, `upload.py`, `timeline.py` | 118.4s processing time across 595.2s video | Section 3.3 (System Operations Sequence) |
| **4. Activity Diagram** | Pipeline Dataflow & Logic | `s01_upload.py` to `s12_export.py`, `scene_stair_guard.py` | $\text{RTF} = 0.199$ ($5.03\times$ playback speed) | Section 2.4 (General Constraints) & 3.5 |
| **5. State Diagram** | Track & Job State Lifecycle | `engines/perception/tracker/track.py`, `orchestrator.py` | 187 confirmed tracks, 100% chain atomicity | Section 3.6 (System & Entity State Models) |
| **6. Component Diagram** | Modular Subsystems | `docker-compose.yml`, `backend/app/`, `frontend/` | 3 decoupled engines, 15 REST route modules | Section 2.1 (Product Perspective) |
| **7. Deployment Diagram** | Physical Infrastructure | `docker-compose.yml`, `health.py`, GPU hardware | RTX 5050 Laptop GPU, 983 MB peak VRAM | Section 2.5 (Operating Environment) |
