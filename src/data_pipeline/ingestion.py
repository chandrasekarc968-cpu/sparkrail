import json
import os
from typing import Dict, Any, Optional
from src.data_pipeline.models import Scenario

class DataIngestor:
    """
    Handles data ingestion from either local synthetic fixtures or Kafka/PostGIS.
    """
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.use_local = config.get("data_pipeline", {}).get("use_local_synthetic", True)
        self.local_path = config.get("data_pipeline", {}).get("synthetic_data_path", "data/synthetic")
        
    def load_scenario(self) -> Scenario:
        """Loads the current railway scenario data."""
        if self.use_local:
            return self._load_local_scenario()
        else:
            return self._load_remote_scenario()

    def _load_local_scenario(self) -> Scenario:
        """Loads data from a local JSON fixture."""
        file_path = os.path.join(self.local_path, "scenario.json")
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Synthetic data file not found at {file_path}. Run generate-data first.")
            
        with open(file_path, "r") as f:
            data = json.load(f)
            
        return Scenario(**data)
        
    def _load_remote_scenario(self) -> Scenario:
        """Placeholder for Kafka/PostGIS integration."""
        # For the MVP, we explicitly raise an error if remote is requested but not implemented
        raise NotImplementedError("Remote Kafka/PostGIS ingestion not fully implemented for MVP.")

    def map_chainage_to_block(self, chainage: float, scenario: Scenario) -> Optional[str]:
        """
        Maps a linear chainage coordinate to a discrete COA block section.
        """
        for block in scenario.blocks:
            if block.chainage_start <= chainage < block.chainage_end:
                return block.id
        return None
