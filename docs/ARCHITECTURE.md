# System Architecture

The Time Compression Engine (TCE) is designed around a three-engine pipeline that progressively extracts higher-level meaning from raw video data.

## Full System Flow

```mermaid
graph TD
    %% Inputs
    V[Raw Video Ingest] --> Decoder
    
    %% Perception Engine
    subgraph Perception Engine
        Decoder --> FrameBuffer
        FrameBuffer --> ObjectDetection[Object Detection YOLOv8]
        FrameBuffer --> MotionEstimator[Motion/Flow Estimator]
        FrameBuffer --> SceneClassifier[Scene Context Classifier]
        
        ObjectDetection --> Tracker[DeepSORT/ByteTrack]
    end
    
    %% Semantic Intelligence Engine
    subgraph Semantic Intelligence Engine
        Tracker --> FeatureVector
        MotionEstimator --> FeatureVector
        SceneClassifier --> ContextVector
        
        FeatureVector --> RuleEngine[Rule-based Mapping]
        ContextVector --> RuleEngine
        
        RuleEngine --> ConfidenceFusion[Confidence Fusion Module]
        KB[(Knowledge Base)] --> RuleEngine
        KB --> ConfidenceFusion
        
        ConfidenceFusion --> EventProposer[Event Proposal Generation]
    end
    
    %% Temporal Intelligence Engine
    subgraph Temporal Intelligence Engine
        EventProposer --> GraphBuilder[Event Graph Builder]
        GraphBuilder --> NarrativeEvaluator[Narrative Preservation Evaluator]
        NarrativeEvaluator --> PolicyEngine[Compression Policy Engine]
    end
    
    %% Outputs
    PolicyEngine --> VideoRender[Video Renderer]
    PolicyEngine --> MetadataGenerator[Explainability JSON Gen]
    
    VideoRender --> FinalVideo[Compressed Video Output]
    MetadataGenerator --> FinalMetadata[Explainability Report Output]
```

## Module Interface Contracts

1. **Perception -> Semantic**: Passes normalized, tracked bounding boxes, motion vectors, and frame-level scene classifications. Data is high-frequency, low-level.
2. **Semantic -> Temporal**: Passes discrete proposed events (e.g., `{"event": "person_entered", "confidence": 0.88, "start": 1.2, "end": 4.5, "entities": ["p1"]}`). Data is low-frequency, high-semantic value.
3. **Temporal -> Output**: Passes a selected subset of temporal intervals to be rendered, along with the graph subgraph representing the reasoning.
