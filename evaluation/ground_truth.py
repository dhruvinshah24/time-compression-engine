"""
Ground truth dataset loader and schemas for TCE evaluation.
"""

import json
from pathlib import Path
from typing import List, Dict, Any

class GroundTruthLoader:
    def __init__(self, dataset_path: str):
        self.dataset_path = Path(dataset_path)

    def load_annotations(self, video_id: str) -> Dict[str, Any]:
        """
        Loads the ground truth annotations for a specific video.
        Expected schema includes a list of true events with timestamps and narrative chains.
        """
        annotation_file = self.dataset_path / f"{video_id}_gt.json"
        if not annotation_file.exists():
            raise FileNotFoundError(f"No ground truth found for {video_id}")
        
        with open(annotation_file, 'r') as f:
            return json.load(f)

    def extract_narrative_chains(self, video_id: str) -> List[List[str]]:
        """
        Extracts causal event chains for evaluating narrative preservation.
        Returns a list of chains, where each chain is a list of event IDs.
        """
        data = self.load_annotations(video_id)
        return data.get("narrative_chains", [])
