# The Three Engines

TCE separates the problem of video summarization into three distinct intelligence layers.

## 1. Perception Engine
The "eyes" of the system.
- **Responsibility**: Pixel-to-Signal translation. Detects objects, tracks them across frames, and extracts motion data.
- **Key Modules**:
  - `Object Detector`: State-of-the-art YOLO variant.
  - `Tracker`: Maintains temporal consistency of objects.
  - `Scene Context Classifier`: Determines if the camera is indoor/outdoor/night/day to adjust confidence weights.
- **Extension Points**: Easily swappable models for specific domains (e.g., replacing a general YOLO with a thermal-camera specific detector).

## 2. Semantic Intelligence Engine
The "brain" of the system.
- **Responsibility**: Signal-to-Meaning translation. Uses the `knowledge/` taxonomy to decide *what* is happening based on the signals from the Perception Engine.
- **Key Modules**:
  - `Rule Engine`: Maps spatio-temporal tracking data to the `event_taxonomy.json`.
  - `Confidence Fusion`: A novel algorithm that weighs tracking certainty, bounding box confidence, and rule-match strictness to output a final event probability.
  - `Explainability Logger`: Records exactly which rules and signals fired to propose an event.

## 3. Temporal Intelligence Engine
The "editor" of the system.
- **Responsibility**: Meaning-to-Narrative translation. Decides *which* events are important enough to keep in the final compressed video.
- **Key Modules**:
  - `Event Graph Builder`: Links disparate events (e.g., 'Person Entered' -> 'Object Placed' -> 'Person Exited') into a directed causal graph.
  - `Story Preservation Layer`: Ensures that if 'Object Placed' is selected for the final video, the causal prerequisites ('Person Entered') are also included, even if they have a lower standalone confidence.
  - `Compression Policy`: Trims the fat based on user-defined target ratios (e.g., "give me a 1-minute summary of this 10-hour video").
