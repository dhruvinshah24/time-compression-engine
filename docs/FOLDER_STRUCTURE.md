# Project Folder Structure

```text
time-compression-engine/
├── backend/                  # Python FastAPI Backend
│   ├── app/                  # Main application package
│   │   ├── api/              # API routers and endpoints
│   │   ├── core/             # Configuration, security, DB setup
│   │   ├── engines/          # The three core intelligence engines
│   │   │   ├── perception/   # YOLO, tracking, CV utilities
│   │   │   ├── semantic/     # Rule evaluation, confidence fusion
│   │   │   └── temporal/     # Event graph, compression policy
│   │   ├── models/           # SQLAlchemy ORM models
│   │   └── schemas/          # Pydantic validation schemas
│   ├── tests/                # Backend unit and integration tests
│   ├── Dockerfile            # Backend container definition
│   └── requirements.txt      # Python dependencies
├── benchmark/                # Performance evaluation tools
│   ├── README.md             # Benchmarking instructions
│   └── metrics_definition.md # Core performance targets
├── docs/                     # System Documentation
│   ├── API.md                # REST API contract
│   ├── ARCHITECTURE.md       # High-level system design
│   ├── DATABASE.md           # ERD and schema descriptions
│   ├── ENGINES.md            # Detailed module breakdowns
│   ├── FOLDER_STRUCTURE.md   # This file
│   └── RESEARCH_CONTRIBUTIONS.md # Academic and patent notes
├── evaluation/               # Accuracy evaluation framework
│   ├── datasets/             # Ground truth video annotations
│   ├── comparison.py         # A/B testing logic
│   ├── ground_truth.py       # JSON annotation parser
│   └── metrics.py            # F1, Narrative, Coverage calculators
├── frontend/                 # Next.js Web Interface
│   ├── src/
│   │   ├── components/       # Reusable React components (UI)
│   │   ├── hooks/            # Custom React hooks (API calls)
│   │   ├── pages/            # Next.js routes
│   │   └── utils/            # Formatting and helper functions
│   ├── Dockerfile            # Frontend container definition
│   └── package.json          # Node.js dependencies
├── knowledge/                # Versioned Semantic Knowledge Base
│   └── v1/
│       ├── rules/            # JSON rule definitions for events
│       ├── event_taxonomy.json  # Definitions of semantic events
│       ├── metadata.json        # KB versioning info
│       ├── object_taxonomy.json # Hierarchical object classes
│       └── scene_taxonomy.json  # Environment context classes
├── research/                 # Theoretical and future work
│   ├── algorithms.md         # Drafts of core algorithms
│   ├── future_features.md    # Post-v1 product roadmap
│   ├── ideas.md              # Exploratory research directions
│   └── patent_notes.md       # Tracking for novel IP claims
├── .env.example              # Template for environment variables
├── .gitignore                # Source control exclusions
├── docker-compose.yml        # Multi-container orchestration
└── README.md                 # Primary entrypoint documentation
```
