# Changelog — Time Compression Engine

All notable changes to this project are documented here.  
Format: `[Phase X] — YYYY-MM-DD`

Each entry records: what was added, what changed, architectural decisions, known limitations, and future work for the next phase.

---

## [Phase 1] — 2026-07-30 — Project Foundation

### Added

**Frontend (Next.js 14 + TypeScript)**
- Complete premium dark UI built with TailwindCSS, Framer Motion, ShadCN UI, and Lucide Icons
- 8 fully implemented pages: Dashboard, Upload, Processing, Timeline, Events, AI Summary, Analytics, Settings
- 12-stage animated pipeline visualization organized by engine (Perception / Semantic Intelligence / Temporal Intelligence)
- Glassmorphism design system with custom color tokens, gradient text, glow effects, and stage pulse animations
- Typed API client (`lib/api/client.ts`) and Zustand global state store
- `config/pipeline-stages.ts` as the canonical source of truth for all 12 pipeline stages

**Backend (FastAPI + SQLAlchemy)**
- FastAPI application with CORS, lifespan events, structured logging via structlog
- 12 SQLAlchemy ORM models (UUID PKs): `users`, `videos`, `processing_jobs`, `pipeline_stages`, `frames`, `detected_objects`, `events`, `event_nodes`, `event_edges`, `ai_summaries`, `system_settings`, `system_logs`
- `StageResult` dataclass — uniform return type for every pipeline stage
- `PipelineContext` dataclass — shared state passed through all 12 stages
- `IntelligenceModule` abstract base class — contract for all engine modules
- 11 API route modules under `/api/v1/`
- Alembic migration `0001_initial_schema.py` — full schema creation
- `init_db.py` seeds 10 system settings defaults on first run
- Job ID generator: human-readable `JOB-YYYYMMDD-NNNN` format

**Three-Engine Architecture (all stubs, ready for Phase 2+)**
- **Perception Engine**: `frame_extractor`, `change_detector`, `object_detector`, `tracker`, `motion_analyzer`, `roi_manager`
- **Semantic Intelligence Engine**: `event_understanding` (with `hybrid_reasoner` stub for future LLM/VLM), `confidence_fusion`, `explainability`
- **Temporal Intelligence Engine**: `story_preservation` (story_builder + continuity + sequence_validator), `event_graph`, `ranking_engine`, `compression_policy`, `summary_engine`

**Research Foundation**
- `knowledge/v1/` — versioned knowledge base with 12 semantic event types, object taxonomy, scene taxonomy, and rule files
- `research/patent_notes.md` — 5 documented potential novel contributions
- `evaluation/metrics.py` — includes `narrative_preservation_score` and `human_satisfaction_score` as research-grade metrics
- `docs/RESEARCH_CONTRIBUTIONS.md` — formal novel contribution documentation

**Project Infrastructure**
- `datasets/` — organized by domain (cctv/dashcam/drone/wildlife/construction/lab), with processed/, annotations/, benchmarks/
- `outputs/` — predictable output locations (highlight_videos/, timelines/, reports/, logs/, thumbnails/, clips/)
- `docker-compose.yml` — PostgreSQL 16, Redis 7, backend, frontend services

### Architectural Decisions

1. **Three-engine separation** (Perception → Semantic Intelligence → Temporal Intelligence) chosen over a flat module list to clearly delineate responsibilities and enable independent testing of each layer.
2. **StageResult uniform contract** applied to every pipeline stage to enable consistent logging, metrics collection, and retry handling from day one.
3. **Versioned knowledge base** (`knowledge/v1/`) to allow future knowledge graph updates without breaking existing processing jobs.
4. **Event graph (nodes + edges)** modelled as separate DB tables rather than JSONB, enabling future graph traversal queries at the database level.
5. **Auth disabled by default** — `security.py` stub in place; all routes public. JWT/OAuth wires in without schema changes.
6. **Job IDs as `JOB-YYYYMMDD-NNNN`** for human-readable cross-referencing across logs, DB, and file outputs.

### Known Limitations

- All engine modules are stubs — no actual AI processing occurs yet
- No video file actually processed end-to-end (Phase 2 will implement this)
- `job_id.py` uses a local file counter; should be replaced with a DB sequence for production/concurrent use
- Frontend uses mock data for all visualizations; will connect to live API from Phase 2

### Next Phase

**Phase 2 — Video Ingestion & Preprocessing Pipeline**
- FFmpeg-based metadata extraction (accurate duration, fps, codec, resolution, frame count)
- Multi-format validation (MP4, AVI, MOV, MKV, WEBM)
- Corrupted file detection and graceful rejection
- Long-video chunking strategy for memory-efficient processing
- Configurable frame extraction with skip-rate control (`frame_skip_rate` from system_settings)
- Deterministic extraction (same video → same frames every run)
- Detailed preprocessing metrics per stage logged to `StageResult`
- Performance benchmarks for extraction speed

---

*This changelog will be updated at the completion of each phase.*
